import streamlit as st
import json
import sqlite3
from datetime import datetime
from openai import OpenAI
# 在现有的 imports 下面增加这一行
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# ⚠️ CONFIG & CONSTANTS
# ==========================================
# [保留原样] 方便你直接运行
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf" 
BASE_URL = "https://api.moonshot.cn/v1"
MODEL_ID = "kimi-k2.5"
DB_NAME = 'neural_vocab_v2.db' # 升级数据库名以防冲突

# ==========================================
# 🛠️ SERVICE 1: NeuralDB (数据库核心)
# ==========================================
class NeuralDB:
    def __init__(self, db_name):
        self.db_name = db_name
        self._init_tables()

    def _get_conn(self):
        return sqlite3.connect(self.db_name)

    def _init_tables(self):
        with self._get_conn() as conn:
            c = conn.cursor()
            # Session 表：存储输入和生成的文章
            c.execute('''CREATE TABLE IF NOT EXISTS learning_sessions
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          words_input TEXT,
                          article_english TEXT,
                          article_chinese TEXT,
                          quiz_data TEXT, 
                          created_at TIMESTAMP)''')
            # Words 表：存储单词卡片
            c.execute('''CREATE TABLE IF NOT EXISTS session_words
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          session_id INTEGER,
                          word TEXT,
                          meaning TEXT,
                          root_explanation TEXT,
                          imagery_desc TEXT,
                          is_core BOOLEAN,
                          FOREIGN KEY(session_id) REFERENCES learning_sessions(id))''')
            conn.commit()

    def create_session(self, words_input):
        with self._get_conn() as conn:
            c = conn.cursor()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO learning_sessions (words_input, created_at) VALUES (?, ?)", 
                      (words_input, current_time))
            return c.lastrowid

    def update_article(self, session_id, en, cn):
        with self._get_conn() as conn:
            conn.execute("UPDATE learning_sessions SET article_english = ?, article_chinese = ? WHERE id = ?", 
                         (en, cn, session_id))

    def update_quiz(self, session_id, quiz_json_str):
        with self._get_conn() as conn:
            conn.execute("UPDATE learning_sessions SET quiz_data = ? WHERE id = ?", 
                         (quiz_json_str, session_id))

    def save_words(self, session_id, words_data):
        with self._get_conn() as conn:
            # 先清空旧的（防止重复生成时堆积）
            conn.execute("DELETE FROM session_words WHERE session_id = ?", (session_id,))
            for w in words_data:
                conn.execute('''INSERT INTO session_words 
                             (session_id, word, meaning, root_explanation, imagery_desc, is_core) 
                             VALUES (?, ?, ?, ?, ?, ?)''', 
                             (session_id, w['word'], w['meaning'], w['root'], w['imagery'], w['is_core']))

    def get_history_list(self):
        """获取最近 10 条历史记录用于侧边栏展示"""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT id, words_input, created_at FROM learning_sessions ORDER BY id DESC LIMIT 10")
            return c.fetchall()

    def load_session(self, session_id):
        """完整恢复一个 Session 的所有数据"""
        data = {}
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row # 允许通过列名访问
            c = conn.cursor()
            
            # 1. Load Session Info (Article & Quiz)
            c.execute("SELECT * FROM learning_sessions WHERE id = ?", (session_id,))
            sess = c.fetchone()
            if sess:
                data['info'] = dict(sess)
            
            # 2. Load Words
            c.execute("SELECT * FROM session_words WHERE session_id = ?", (session_id,))
            words = c.fetchall()
            data['words'] = [dict(w) for w in words]
            
        return data

# ==========================================
# 🧠 SERVICE 2: CyberMind (AI 智能体)
# ==========================================
class CyberMind:
    def __init__(self):
        # 优化：Client 只初始化一次
        self.client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)

    def _call(self, system, user):
        response = self.client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=1, # 稍微降低一点温度，增加稳定性
            response_format={"type": "json_object"}
        )
        # 简单处理：假设返回总是合法 JSON
        return json.loads(response.choices[0].message.content)

    def generate_article(self, words):
        prompt = """
        你是一个赛博朋克风格的小说家。请根据用户提供的单词，写一篇 CET-6 难度、带有未来科技感的短文。
        要求：
        1. 必须包含所有单词，并用 <span class='highlight-word'>单词</span> 包裹。
        2. 返回 JSON: {"article_english": "...", "article_chinese": "..."}
        """
        return self._call(prompt, f"单词列表: {words}")

    def analyze_words(self, words):
        prompt = """
        你是一个词源学家。分析单词。
        要求：
        1. 返回 JSON: 
        { "words": [ {"word": "...", "meaning": "...", "root": "...", "imagery": "...", "is_core": true/false} ] }
        """
        return self._call(prompt, f"单词列表: {words}")

    def generate_quiz(self, words, article_context=None):
        # 优化：上下文联动
        # 如果有文章上下文，AI 将基于文章出题
        context_str = f"基于以下文章内容出题:\n{article_context}" if article_context else "无文章上下文"
        
        prompt = f"""
        你是一个出题老师。请根据单词和提供的文章上下文设计 2 道阅读理解/词汇题。
        {context_str}
        
        要求：
        1. 题目需结合文章情节。
        2. 返回 JSON:
        {{ "quizzes": [ {{"question": "...", "options": ["A", "B", "C", "D"], "answer": "正确选项内容", "explanation": "..."}} ] }}
        """
        return self._call(prompt, f"考察单词: {words}")

# ==========================================
# 🖥️ UI SETUP
# ==========================================
st.set_page_config(page_title="NEURAL_SYSTEM_V2", page_icon="🧩", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #050505; color: #e0e0e0; font-family: 'Courier New'; }
    h1, h2, h3 { color: #00f3ff !important; text-shadow: 0 0 5px #00f3ff; }
    .status-box { border-left: 3px solid #39ff14; padding: 10px; background: #111; margin-bottom: 20px; }
    .highlight-word { color: #ff00ff; font-weight: bold; background: #220022; padding: 0 4px; border-radius: 4px; }
    div.stButton > button { border: 1px solid #39ff14; color: #39ff14; background: transparent; width: 100%; }
    div.stButton > button:hover { background: #39ff14; color: #000; box-shadow: 0 0 10px #39ff14; }
    .history-item { padding: 5px; border-bottom: 1px solid #333; cursor: pointer; font-size: 0.8em; color: #888; }
</style>
""", unsafe_allow_html=True)

# 初始化服务
if 'db' not in st.session_state: st.session_state.db = NeuralDB(DB_NAME)
if 'ai' not in st.session_state: st.session_state.ai = CyberMind()

# 状态管理
if 'session_id' not in st.session_state: st.session_state.session_id = None
if 'current_words' not in st.session_state: st.session_state.current_words = []
# 数据缓存
if 'data_article' not in st.session_state: st.session_state.data_article = None
if 'data_cards' not in st.session_state: st.session_state.data_cards = None
if 'data_quiz' not in st.session_state: st.session_state.data_quiz = None

# ==========================================
# 📂 SIDEBAR: INPUT & HISTORY
# ==========================================
with st.sidebar:
    st.title("🧩 NEURAL HUB V2.0")
    
    st.subheader("📡 新数据注入")
    user_input = st.text_area("Input Stream:", value="ephemeral, serendipity, cyberpunk", height=70)
    
    if st.button("📥 初始化 (Initialize)"):
        words = [w.strip() for w in user_input.split(',') if w.strip()]
        if words:
            # 1. 写入 DB
            new_id = st.session_state.db.create_session(user_input)
            
            # 2. 更新状态
            st.session_state.session_id = new_id
            st.session_state.current_words = words
            
            # 3. 清空缓存
            st.session_state.data_article = None
            st.session_state.data_cards = None
            st.session_state.data_quiz = None
            
            st.toast(f"系统初始化完成。Session ID: {new_id}", icon="✅")
            st.rerun()

    st.divider()
    
    # === 历史记录回溯功能 ===
    st.subheader("⏳ 时间胶囊 (History)")
    history_list = st.session_state.db.get_history_list()
    
    for h_id, h_words, h_date in history_list:
        # 显示前3个单词作为标题
        short_words = h_words[:20] + "..." if len(h_words) > 20 else h_words
        col_h1, col_h2 = st.columns([4, 1])
        with col_h1:
            st.caption(f"{h_date}\n**{short_words}**")
        with col_h2:
            if st.button("Load", key=f"load_{h_id}"):
                # 加载旧数据
                full_data = st.session_state.db.load_session(h_id)
                info = full_data['info']
                
                # 恢复状态
                st.session_state.session_id = h_id
                st.session_state.current_words = [w.strip() for w in info['words_input'].split(',') if w.strip()]
                
                # 恢复文章
                if info['article_english']:
                    st.session_state.data_article = {
                        "article_english": info['article_english'],
                        "article_chinese": info['article_chinese']
                    }
                else:
                    st.session_state.data_article = None

                # 恢复单词卡
                if full_data['words']:
                    st.session_state.data_cards = {"words": full_data['words']}
                else:
                    st.session_state.data_cards = None
                    
                # 恢复测验
                if info['quiz_data']:
                    st.session_state.data_quiz = json.loads(info['quiz_data'])
                else:
                    st.session_state.data_quiz = None
                    
                st.toast("时间线回溯成功！数据已重载。", icon="🔄")
                st.rerun()

# ==========================================
# 🎮 MAIN INTERFACE (State Machine Logic)
# ==========================================

# --- 顶部导航栏布局 (Title + Action Button) ---
col_header, col_btn = st.columns([5, 1], vertical_alignment="bottom")

with col_header:
    st.title("⚡ NEURAL MODULAR SYSTEM")

with col_btn:
    # 仅当文章已生成（有上下文）时，按钮才可用
    has_context = st.session_state.data_article is not None
    if st.button("🔄 再来一组", disabled=not has_context, help="基于当前文章生成一组新的测试题"):
        with st.spinner("正在重构战场..."):
            try:
                # 复用文章上下文，请求新题目
                article_context = st.session_state.data_article['article_english']
                # 重新调用 AI
                res_quiz = st.session_state.ai.generate_quiz(st.session_state.current_words, article_context)
                
                # 更新状态与数据库
                st.session_state.data_quiz = res_quiz
                st.session_state.db.update_quiz(st.session_state.session_id, json.dumps(res_quiz))
                
                st.toast("新题目已送达！请前往 [实战演练] 查看。", icon="⚔️")
                # 稍微延迟一下再刷新，让用户看到 toast
                import time
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

if not st.session_state.session_id:
    st.warning("👈 请先在左侧侧边栏初始化数据或加载历史记录。")
    st.stop()

# 状态栏
st.markdown(f"""
<div class='status-box'>
    <div>🆔 <b>SESSION:</b> {st.session_state.session_id}</div>
    <div>📡 <b>DATA:</b> {', '.join(st.session_state.current_words)}</div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📜 SYSTEM 2: 沉浸阅读", "🧩 SYSTEM 3: 记忆矩阵", "⚔️ SYSTEM 4: 实战演练"])

# === TAB 1: 文章模块 (全自动流水线核心) ===
with tab1:
    # 场景 A: 连文章都没有，显示启动大按钮
    if not st.session_state.data_article:
        st.info("等待指令... 神经网络处于待机状态。")
        
        if st.button("🚀 启动全链路序列 (Full Sequence)", use_container_width=True):
            with st.spinner("正在接收来自虚空的故事信号... (Step 1/3: Generating Article)"):
                try:
                    # 1. 请求文章
                    res_article = st.session_state.ai.generate_article(st.session_state.current_words)
                    st.session_state.data_article = res_article
                    # 存库
                    st.session_state.db.update_article(
                        st.session_state.session_id, 
                        res_article['article_english'], 
                        res_article['article_chinese']
                    )
                    # ⚠️ 文章生成完立即刷新
                    st.rerun()
                except Exception as e:
                    st.error(f"Article Generation Failed: {e}")

    # 场景 B: 文章已就绪 -> 渲染文章 + 自动触发后续任务
    else:
        # --- 1. 立即渲染文章 ---
        data = st.session_state.data_article
        c1, c2 = st.columns(2)
        with c1: 
            st.markdown("### English Stream")
            st.markdown(f"{data['article_english']}", unsafe_allow_html=True)
        with c2: 
            st.markdown("### 中文解析")
            st.markdown(f"<div style='color:#aaa'>{data['article_chinese']}</div>", unsafe_allow_html=True)

        st.divider()

        # --- 2. 自动检测链 ---
        if not st.session_state.data_cards or not st.session_state.data_quiz:
            with st.status("🤖 正在后台进行全系统神经重构...", expanded=False) as status:
                
                # Sub-Task 1: 单词
                if not st.session_state.data_cards:
                    st.write("Step 1: 正在提取记忆碎片 (Memory Analysis)...")
                    try:
                        res_words = st.session_state.ai.analyze_words(st.session_state.current_words)
                        st.session_state.data_cards = res_words
                        st.session_state.db.save_words(st.session_state.session_id, res_words['words'])
                        st.write("✅ 记忆碎片提取完成")
                    except Exception as e:
                        st.error(f"Memory Analysis Failed: {e}")

                # Sub-Task 2: 测验
                if not st.session_state.data_quiz:
                    st.write("Step 2: 正在构建实战模拟 (Quiz Generation)...")
                    try:
                        article_context = st.session_state.data_article['article_english']
                        res_quiz = st.session_state.ai.generate_quiz(st.session_state.current_words, article_context)
                        st.session_state.data_quiz = res_quiz
                        st.session_state.db.update_quiz(st.session_state.session_id, json.dumps(res_quiz))
                        st.write("✅ 战场生成完毕")
                    except Exception as e:
                        st.error(f"Quiz Generation Failed: {e}")

                status.update(label="✅ 所有模块加载完毕 (Tabs Ready)", state="complete", expanded=False)

# === TAB 2: 单词模块 ===
with tab2:
    if not st.session_state.data_cards:
        st.info("⏳ 记忆解析正在后台运行中...")
    else:
        words = st.session_state.data_cards['words']
        cols = st.columns(3)
        for idx, w in enumerate(words):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"### {w['word']}")
                    st.caption(w['meaning'])
                    st.markdown(f"**Root:** `{w['root']}`")
                    st.markdown(f"_{w['imagery']}_")

# === TAB 3: 测验模块 (纯展示，移除旧按钮) ===
with tab3:
    if not st.session_state.data_quiz:
        st.info("⏳ 战场数据正在生成中...")
    else:
        st.caption("🎯 点击右上角 [再来一组] 可刷新题目")
        for i, q in enumerate(st.session_state.data_quiz['quizzes']):
            st.markdown(f"#### Q{i+1}: {q['question']}")
            
            # 使用时间戳作为 Key 的一部分，确保点击“再来一组”后，Radio Button 状态会被重置
            import time
            unique_key = f"quiz_{st.session_state.session_id}_{i}_{int(time.time() / 100)}" 
            # 注意：这里简单的 Key 策略可能在短时间内重复，更好的做法是在 generate_quiz 时生成一个 uuid 存入 session_state
            # 但为了简化，我们直接用 session_state 中的数据对象 ID
            unique_key = f"quiz_{id(st.session_state.data_quiz)}_{i}"
            
            choice = st.radio("Select Option:", q['options'], key=unique_key, index=None)
            
            if choice:
                if choice == q['answer']:
                    st.success(f"✅ Correct! {q['explanation']}")
                else:
                    st.error(f"❌ Incorrect. Answer: {q['answer']}")
                    st.info(f"解析: {q['explanation']}")
            st.divider()