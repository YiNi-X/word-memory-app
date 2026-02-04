import streamlit as st
import json
import sqlite3
import time  # 👈 确保这里有 time
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import re
from datetime import datetime, timedelta
import streamlit.components.v1 as components # 用于嵌入 JS 发音代码
import pandas as pd # 用于导出 CSV
# ==========================================
# ⚠️ CONFIG & CONSTANTS
# ==========================================
# [保留原样] 方便你直接运行
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf" 
BASE_URL = "https://api.moonshot.cn/v1"
MODEL_ID = "kimi-k2.5"
DB_NAME = 'neural_vocab_v3.db' # 升级数据库名以防冲突

# ==========================================
# 🛠️ SERVICE 1: NeuralDB (数据库核心)
# ==========================================
class NeuralDB:
    def __init__(self, db_name):
        self.db_name = db_name
        self._init_tables()

    @contextmanager
    def _get_conn(self):
        # 1. Setup (进门): 建立连接
        conn = sqlite3.connect(self.db_name)
        try:
            # 2. Yield (交钥匙): 把连接给调用者使用
            yield conn
            # 如果代码跑到这里，说明没有报错，提交事务
            conn.commit()
        except Exception as e:
            # 3. Handle Error (急救): 如果报错，回滚更改
            conn.rollback()
            raise e # 继续抛出异常，让外层知道出错了
        finally:
            # 4. Teardown (打扫): 无论成功失败，必须关闭连接
            conn.close()

    def _init_tables(self):
        with self._get_conn() as conn:
            c = conn.cursor()
            # 1. 基础表结构（保持不变）
            c.execute('''CREATE TABLE IF NOT EXISTS learning_sessions
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          words_input TEXT,
                          article_english TEXT,
                          article_chinese TEXT,
                          quiz_data TEXT, 
                          created_at TIMESTAMP)''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS session_words
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          session_id INTEGER,
                          word TEXT,
                          meaning TEXT,
                          root_explanation TEXT,
                          imagery_desc TEXT,
                          is_core BOOLEAN,
                          FOREIGN KEY(session_id) REFERENCES learning_sessions(id))''')
            
            # 2. 🚀 莱特纳系统迁移：安全地添加新字段
            # 我们需要 tracking 'box' (盒子编号 1-5) 和 'next_review' (下次复习日期)
            try:
                # 默认所有词都在 盒子1
                c.execute("ALTER TABLE session_words ADD COLUMN box INTEGER DEFAULT 1")
            except sqlite3.OperationalError: pass 
            
            try:
                # 默认复习时间是今天（立即复习）
                c.execute("ALTER TABLE session_words ADD COLUMN next_review DATE DEFAULT CURRENT_DATE")
            except sqlite3.OperationalError: pass
                
            conn.commit()

    def create_session(self, words_input):
        with self._get_conn() as conn: 
            c = conn.cursor()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # ✅ 修复：补全了完整的 SQL 语句和默认参数
            # article_english, article_chinese, quiz_data 初始化为空字符串
            c.execute('''INSERT INTO learning_sessions 
                         (words_input, created_at, article_english, article_chinese, quiz_data) 
                         VALUES (?, ?, ?, ?, ?)''', 
                      (words_input, current_time, "", "", ""))
            
            # 返回新插入行的 ID (即 session_id)
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
        """完整恢复一个 Session 的所有数据 (已修复字段映射问题)"""
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
            
            # 关键修复：手动将数据库列名映射回前端需要的 JSON key
            cleaned_words = []
            for w in words:
                w_dict = dict(w)
                # 数据库列名 -> 前端使用的 Key
                w_dict['root'] = w_dict.get('root_explanation', '') # 映射 root
                w_dict['imagery'] = w_dict.get('imagery_desc', '')  # 映射 imagery
                cleaned_words.append(w_dict)
                
            data['words'] = cleaned_words
            
        return data
    
    def get_due_cards(self):
        """获取所有【今天到期】或【已过期】的卡片"""
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            # 逻辑：找出 next_review <= 今天的单词，且盒子等级 < 6 (6代表已退休)
            c.execute("SELECT * FROM session_words WHERE next_review <= ? AND box < 6 ORDER BY box ASC, RANDOM() LIMIT 50", (today,))
            
            # 🔥 修复：这里需要手动映射数据库列名 -> 前端通用 Key
            results = []
            for row in c.fetchall():
                w = dict(row)
                # 兼容性映射：把数据库的长名字映射回 UI 需要的短名字
                w['root'] = w.get('root_explanation', '暂无词根')
                w['imagery'] = w.get('imagery_desc', '暂无场景')
                results.append(w)
                
            return results

    def process_review(self, word_id, current_box, is_correct):
        """
        ⚡ 莱特纳算法核心 (The Leitner Algorithm)
        
        间隔规则 (Intervals):
        Box 1: 1天 (明天见)
        Box 2: 3天
        Box 3: 7天
        Box 4: 15天
        Box 5: 30天 (毕业)
        Box 6: 🏆 已掌握 (退休)
        """
        intervals = {1: 1, 2: 3, 3: 7, 4: 15, 5: 30}
        
        if is_correct:
            # ✅ 答对升级
            new_box = current_box + 1
            if new_box > 5:
                # 如果超过5级，设为6 (Mastered/Retired)
                next_date = "2099-12-31" # 以后不复习了
            else:
                days_to_add = intervals.get(new_box, 1)
                next_date = (datetime.now() + timedelta(days=days_to_add)).strftime("%Y-%m-%d")
        else:
            # ❌ 答错重置 (残酷模式：直接回 Box 1)
            new_box = 1
            next_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d") # 明天立刻复习

        # 更新数据库
        with self._get_conn() as conn:
            conn.execute("UPDATE session_words SET box = ?, next_review = ? WHERE id = ?", 
                         (new_box, next_date, word_id))
        
        return new_box, next_date

# ==========================================
# 🧠 SERVICE 2: CyberMind (AI 智能体)
# ==========================================
class CyberMind:
    def __init__(self):
        # 优化：Client 只初始化一次
        self.client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)

    def _call(self, system, user, retries=3):
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL_ID,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    temperature=1, 
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                
                # 🛠️ 清洗步骤：使用正则提取 Markdown 代码块中的 JSON
                if "```" in content:
                    # 匹配 ```json {...} ``` 或 ``` {...} ```
                    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                    if match:
                        content = match.group(1)
                
                # 去除首尾空白字符
                content = content.strip()

                # 尝试解析
                return json.loads(content)
                
            except json.JSONDecodeError as e:
                print(f"⚠️ [Attempt {attempt+1}/{retries}] JSON 解析失败: {e}")
                print(f"📄 原始内容片段: {content[:100]}...") # 只看前100个字符用于诊断
                
                if attempt == retries - 1:
                    st.error("AI 生成的数据格式异常，请重试或检查 Input Stream 内容。")
                    return {} # 返回空字典防止后续代码崩溃
                continue
                
            except Exception as e:
                st.error(f"API 网络或未知错误: {e}")
                return {}

    def generate_article(self, words):
        prompt = """
        ## 角色设定
        你是一位《经济学人》(The Economist) 或《纽约时报》的资深专栏作家。你的文风专业、逻辑严密，擅长将离散的概念串联成有深度的社会、科技或文化评论。

        ## 任务目标
        请基于用户提供的【单词列表】，撰写一篇 CET-6 (中国大学英语六级) 难度的短文。

        ## 严格要求
        1. **主题与逻辑**：严禁生硬堆砌单词。文章必须有一个明确的核心主题（如数字时代的焦虑、环保悖论、职场心理等），所有单词必须自然地服务于上下文。
        2. **语言标准**：
           - **难度**：CET-6/考研英语级别。
           - **句式**：必须包含至少 2 种复杂句型（如：倒装句、虚拟语气、独立主格、定语从句），避免通篇简单句。
           - **篇幅**：150 - 220 词。
        3. **格式高亮（关键）**：
           - 必须且只能将【单词列表】中的词（包含其时态/复数变形）用 `<span class='highlight-word'>...</span>` 包裹。
           - 例如：如果输入 "apply"，文中用了 "applied"，请输出 `<span class='highlight-word'>applied</span>`。
        4. **翻译要求**：
           - 提供意译而非直译。译文应流畅优美，符合中文表达习惯（信达雅）。

        ## 输出格式
        请仅返回纯 JSON 格式，不要使用 Markdown 代码块包裹：
        {
            "article_english": "Your English article content here...",
            "article_chinese": "你的中文翻译内容..."
        }
        """
        return self._call(prompt, f"单词列表: {words}")

    def analyze_words(self, words):
        # 修改建议
        prompt = """
        你是一个英语教学专家。分析单词。
        要求：
        1. "is_core" 字段逻辑：如果是 CET-6 (六级) 或 考研英语 的高频词汇，设为 true，否则为 false。
        2. 返回 JSON:
        { "words": [ {"word": "...", "meaning": "...", "root": "...", "imagery": "...", "is_core": true/false} ] }
        """
        return self._call(prompt, f"单词列表: {words}")

    def generate_quiz(self, words, article_context=None):
        # 优化：上下文联动
        # 如果有文章上下文，AI 将基于文章出题
        context_str = f"文章内容:\n{article_context}" if article_context else "无文章上下文（请基于单词构造通用场景）"
        
        prompt = f"""
        ## 角色设定
        你是一位经验丰富的 CET-6 (六级) 和 IELTS (雅思) 命题组专家。你需要根据提供的单词和文章内容，设计高质量的阅读理解或词汇辨析题。

        ## 输入数据
        1. 考察单词: {words}
        2. {context_str}

        ## 出题标准 (Strict Guidelines)
        1. **深度结合语境**：
           - 严禁出简单的“词义匹配”题。
           - 题目必须考察单词在**当前特定文章语境**下的深层含义、隐喻或它对情节发展的推动作用。
           - 正确选项必须是文章中具体信息的推论，而不仅仅是单词的字典定义。

        2. **干扰项设计 (Distractors)**：
           - 错误选项必须具有迷惑性（例如：通过偷换概念、因果倒置、或利用单词的字面意思设置陷阱）。
           - 避免出现一眼就能排除的荒谬选项。

        3. **题目类型**：
           - 请混合设计：词汇推断题 (Vocabulary in Context) 和 细节理解题 (Detail Comprehension)。

        ## 输出格式
        请返回纯 JSON 格式，不要使用 Markdown 代码块。
        JSON 结构如下（注意：key 必须严格对应）：
        {{
            "quizzes": [
                {{
                    "question": "题干内容 (英文)...",
                    "options": ["A. 选项内容", "B. 选项内容", "C. 选项内容", "D. 选项内容"],
                    "answer": "A. 选项内容", 
                    "explanation": "中文解析：1. 为什么选这个答案（结合文章引用）；2. 其他选项为什么错（解析干扰点）。"
                }}
            ]
        }}
        """
        return self._call(prompt, f"请为这些单词设计 3-5 道题目: {words}")
    
# ==========================================
# 🔊 TTS SERVICE (前端发音)
# ==========================================
def play_audio(text):
    # 简单的 JavaScript 注入，调用浏览器 TTS 引擎
    # 自动取消上一句，避免点击过快声音重叠
    js_code = f"""
        <script>
            window.speechSynthesis.cancel(); 
            var msg = new SpeechSynthesisUtterance("{text}");
            msg.lang = 'en-US'; // 设置为美式英语
            msg.rate = 0.9;     // 语速稍慢一点点，更清晰
            window.speechSynthesis.speak(msg);
        </script>
    """
    # height=0 隐藏组件，只执行逻辑
    components.html(js_code, height=0, width=0)

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
if 'quiz_version' not in st.session_state: st.session_state.quiz_version = 0

if 'review_queue' not in st.session_state: st.session_state.review_queue = []
if 'review_index' not in st.session_state: st.session_state.review_index = 0
if 'show_card_back' not in st.session_state: st.session_state.show_card_back = False
# 数据缓存
if 'data_article' not in st.session_state: st.session_state.data_article = None
if 'data_cards' not in st.session_state: st.session_state.data_cards = None
if 'data_quiz' not in st.session_state: st.session_state.data_quiz = None

# ... 在 st.set_page_config 之后 ...

# ==========================================
# 🎮 GAME STATE ENGINE (核心游戏引擎)
# ==========================================
if 'game' not in st.session_state:
    st.session_state.game = {
        'hp': 100,             # 当前生命值
        'max_hp': 100,         # 最大生命值
        'gold': 0,             # 金币 (用于商店)
        'xp': 0,               # 经验值
        'level': 1,            # 玩家等级
        'boss_hp': 100,        # Boss (文章) 生命值
        'boss_max_hp': 100,    # Boss 最大生命值
        'is_dead': False,      # 是否死亡
        'inventory': [],       # 道具栏
        'log': []              # 战斗日志
    }

# 辅助函数：更新游戏日志
def add_log(msg, type="info"):
    timestamp = datetime.now().strftime("%H:%M")
    icon = "⚔️" if type == "combat" else "💰" if type == "gold" else "💀" if type == "damage" else "ℹ️"
    st.session_state.game['log'].insert(0, f"[{timestamp}] {icon} {msg}")

# 辅助函数：HUD (Heads-Up Display) 抬头显示器
def render_hud():
    g = st.session_state.game
    
    # 死亡判定
    if g['hp'] <= 0:
        g['is_dead'] = True
        
    if g['is_dead']:
        st.error("💀 GAME OVER - 你的意识消散在了单词的虚空中...")
        if st.button("🔄 转生 (Reset Game)"):
            st.session_state.game['hp'] = 100
            st.session_state.game['gold'] = 0
            st.session_state.game['is_dead'] = False
            st.rerun()
        st.stop() # 停止渲染后续界面

    # 渲染状态栏
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        with c1:
            # 血条逻辑
            hp_percent = g['hp'] / g['max_hp']
            st.markdown(f"❤️ **HP: {g['hp']}/{g['max_hp']}**")
            st.progress(hp_percent)
        with c2:
            # Boss 血条逻辑 (仅在战斗/测验时显示)
            if st.session_state.data_quiz:
                boss_percent = max(0, g['boss_hp'] / g['boss_max_hp'])
                st.markdown(f"👹 **BOSS (Article): {g['boss_hp']}/{g['boss_max_hp']}**")
                st.progress(boss_percent, text="The Syntax Demon")
            else:
                st.caption("Searching for enemy...")
        with c3:
            st.metric("💰 Gold", g['gold'])
        with c4:
            st.metric("🔰 LV", g['level'])

    # 简单的战斗日志显示 (最近3条)
    with st.expander("📜 战斗记录 (Combat Log)", expanded=False):
        for log in g['log'][:5]:
            st.markdown(f"<small>{log}</small>", unsafe_allow_html=True)

# ==========================================
# 📂 SIDEBAR: INPUT & HISTORY
# ==========================================
with st.sidebar:

    # ==========================================
    # 🎮 MAIN INTERFACE
    # ==========================================

    # 1. 渲染游戏 HUD (时刻显示血条！)
    render_hud() 

    # 2. 原有的顶部 Header
    col_header, col_btn = st.columns([5, 1], vertical_alignment="bottom")
    st.title("🧩 NEURAL HUB V2.0")
    
    st.subheader("📡 新数据注入")
    user_input = st.text_area("Input Stream:", height=70)
    
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

    st.divider()
    st.subheader("🛒 黑市商人在售 (Shop)")
    
    cost_potion = 50
    if st.button(f"🧪 语法药水 (+30HP) | ${cost_potion}"):
        g = st.session_state.game
        if g['gold'] >= cost_potion:
            g['gold'] -= cost_potion
            g['hp'] = min(g['max_hp'], g['hp'] + 30)
            add_log("使用了语法药水，HP +30", "info")
            st.success("购买成功！HP 已恢复。")
            time.sleep(0.5) # 可选：加一点延迟让用户看到提示
            st.rerun() # 刷新显示血条
        else:
            st.error("金币不足！快去 Tab 4 复习赚钱！")

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
                st.session_state.quiz_version += 1
                
                st.toast("新题目已送达！请前往 [实战演练] 查看。", icon="⚔️")
                # 稍微延迟一下再刷新，让用户看到 toast
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

if not st.session_state.session_id:
    st.warning("👈 请先在左侧侧边栏初始化数据或加载历史记录。")
    st.stop()

# ✅ 粘贴这段新代码 (位置：st.tabs 定义之前)
with st.container(border=True):
    # 将一行分为左右两列，左边窄(ID)，右边宽(Data)
    c1, c2 = st.columns([1, 5])
    
    with c1:
        # 显示 Session ID，加个代码样式
        st.markdown(f"🆔 **ID:** `{st.session_state.session_id}`")
    
    with c2:
        # 获取单词列表
        all_words = st.session_state.current_words
        count = len(all_words)
        
        # 智能预览逻辑：如果超过 5 个词，就截断显示
        if count > 5:
            preview = ", ".join(all_words[:5]) + f" ... (+{count-5} more)"
        else:
            preview = ", ".join(all_words)
            
        # 核心魔法：使用 help 参数添加“悬停提示”
        st.markdown(
            f"📡 **DATA:** {preview}", 
            help=", ".join(all_words)  # 👈 鼠标悬停在这里时，会浮现出所有单词！
        )

# ✅ 修复：增加第四个 Tab 的标签和变量名
tab1, tab2, tab3, tab4 = st.tabs(["📜 SYSTEM 2: 沉浸阅读", "🧩 SYSTEM 3: 记忆矩阵", "⚔️ SYSTEM 4: 实战演练", "🧠 SYSTEM 5: 脑回强化"])

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

        # --- 2. 自动检测链 (并行重构版) ---
        if not st.session_state.data_cards or not st.session_state.data_quiz:
            with st.status("🤖 正在后台进行全系统神经重构 (Parallel Mode)...", expanded=True) as status:
                
                # 准备并行任务
                tasks = {}
                with ThreadPoolExecutor(max_workers=2) as executor:
                    # 如果缺单词卡，提交单词任务
                    if not st.session_state.data_cards:
                        st.write("📡 正在启动：记忆碎片提取...")
                        tasks['cards'] = executor.submit(st.session_state.ai.analyze_words, st.session_state.current_words)
                    
                    # 如果缺测验，提交测验任务
                    if not st.session_state.data_quiz:
                        st.write("📡 正在启动：战场模拟构建...")
                        article_context = st.session_state.data_article['article_english']
                        tasks['quiz'] = executor.submit(st.session_state.ai.generate_quiz, st.session_state.current_words, article_context)

                    # 等待并获取并行结果
                    if 'cards' in tasks:
                        try:
                            res_words = tasks['cards'].result()
                            st.session_state.data_cards = res_words
                            st.session_state.db.save_words(st.session_state.session_id, res_words['words'])
                            st.write("✅ 记忆碎片提取完成")
                        except Exception as e:
                            st.error(f"Memory Analysis Failed: {e}")

                    if 'quiz' in tasks:
                        try:
                            res_quiz = tasks['quiz'].result()
                            st.session_state.data_quiz = res_quiz
                            st.session_state.db.update_quiz(st.session_state.session_id, json.dumps(res_quiz))
                            st.write("✅ 战场生成完毕")
                        except Exception as e:
                            st.error(f"Quiz Generation Failed: {e}")

                status.update(label="🚀 系统就绪 (System Ready)", state="complete", expanded=False)
                time.sleep(1) 
                st.rerun()

               

# === TAB 2: 单词模块 ===
with tab2:
    if not st.session_state.data_cards:
        st.info("⏳ 记忆解析正在后台运行中...")
    else:
        # --- 1. 顶部工具栏：导出功能 ---
        words = st.session_state.data_cards['words']
        
        col_t1, col_t2 = st.columns([4, 1])
        with col_t2:
            # 准备 DataFrame
            df = pd.DataFrame(words)
            # 转换为 CSV
            csv = df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="📥 导出 CSV (Anki)",
                data=csv,
                file_name=f'vocab_session_{st.session_state.session_id}.csv',
                mime='text/csv',
                use_container_width=True
            )

        st.divider()

        # --- 2. 单词卡片展示 ---
        cols = st.columns(3)
        for idx, w in enumerate(words):
            with cols[idx % 3]:
                with st.container(border=True):
                    # 标题栏：单词 + 发音按钮
                    c_title, c_spk = st.columns([4, 1])
                    with c_title:
                        st.markdown(f"### {w['word']}")
                    with c_spk:
                        # 唯一的 key 非常重要，防止 ID 冲突
                        if st.button("🔊", key=f"tts_tab2_{idx}"):
                            play_audio(w['word'])
                    
                    st.caption(w['meaning'])
                    st.markdown(f"**Root:** `{w['root']}`")
                    st.markdown(f"_{w['imagery']}_")


# === TAB 3: ⚔️ BOSS BATTLE (实战演练) ===
with tab3:
    if not st.session_state.data_quiz:
        st.info("⏳ 正在扫描 Boss 弱点 (生成题目中)...")
    else:
        quizzes = st.session_state.data_quiz['quizzes']
        
        # 初始化 Boss 血量 (如果是新的一组题)
        # 简单算法：Boss血量 = 题目数量 * 20
        total_damage_needed = len(quizzes) * 20
        if st.session_state.game['boss_max_hp'] != total_damage_needed and st.session_state.game['boss_hp'] == 100:
             st.session_state.game['boss_max_hp'] = total_damage_needed
             st.session_state.game['boss_hp'] = total_damage_needed

        # 胜利判定
        if st.session_state.game['boss_hp'] <= 0:
            st.balloons()
            st.success("🏆 VICTORY! 你击败了这篇文章！")
            st.markdown(f"### 战利品:\n- 💰 金币 +50\n- 🔰 经验 +100")
            if st.button("收下奖励并寻找下一个猎物"):
                st.session_state.game['gold'] += 50
                st.session_state.game['xp'] += 100
                st.session_state.data_quiz = None # 清空题目，强制去生成新的
                st.session_state.game['boss_hp'] = 100 # 重置 Boss
                st.rerun()
        else:
            # 战斗进行中
            col_tip, col_shop = st.columns([3, 1])
            with col_tip:
                st.caption(f"⚔️ 战斗回合: 请通过答题削减 Boss 的 {st.session_state.game['boss_hp']} 点护甲")
            
            # 遍历题目
            for i, q in enumerate(quizzes):
                # 如果这道题已经“打过”了（答对了），就锁定状态，显示为绿色
                # 这里我们需要一个小技巧：用 session_state 记录每道题的状态
                q_status_key = f"q_status_{st.session_state.session_id}_{i}_{st.session_state.quiz_version}"
                if q_status_key not in st.session_state:
                    st.session_state[q_status_key] = "active" # active, defeated, failed

                status = st.session_state[q_status_key]

                with st.container(border=True):
                    st.markdown(f"**Q{i+1}: {q['question']}**")
                    
                    if status == "defeated":
                        st.success(f"✅ 已击破! (Boss 受到 20 点伤害)")
                        continue # 跳过这道题的渲染
                    
                    # 选项渲染
                    unique_key = f"radio_{q_status_key}"
                    options = q['options']
                    
                    # 如果这道题之前答错了，我们应该禁用它或者扣更多血？
                    # 简化版：允许重选，但不会造成伤害了，或者直接判定失败
                    
                    choice = st.radio("你的攻击策略:", options, key=unique_key, index=None)
                    
                    if choice:
                        # 提交按钮 (为了模拟回合制，防止误触)
                        if st.button(f"⚔️ 发动攻击 (Q{i+1})", key=f"btn_{unique_key}"):
                            if choice == q['answer']:
                                # --- 暴击逻辑 ---
                                damage = 20
                                st.session_state.game['boss_hp'] -= damage
                                st.session_state.game['gold'] += 5 # 掉落金币
                                st.session_state[q_status_key] = "defeated"
                                add_log(f"你对 Boss 造成 {damage} 点逻辑伤害！(Q{i+1})", "combat")
                                st.rerun()
                            else:
                                # --- 受伤逻辑 ---
                                player_dmg = 15
                                st.session_state.game['hp'] -= player_dmg
                                add_log(f"Boss 反击！你受到 {player_dmg} 点精神伤害！答案是 {q['answer']}", "damage")
                                st.error(f"❌ 攻击偏离！Boss 对你造成 {player_dmg} 点伤害。")
                                # 答错不锁定，允许重试，但会一直扣血！这很肉鸽！

# === TAB 4: 莱特纳复习系统 (Full Leitner) ===
# === TAB 4: 莱特纳复习系统 (Full Leitner) ===
with tab4:
    st.caption("🧠 莱特纳间隔重复系统 (Spaced Repetition System)")
    
    # 1. 顶部统计数据 (只负责显示统计，不要在这里写按钮)
    with st.session_state.db._get_conn() as conn: 
        c = conn.cursor()
        # 统计今日待复习
        c.execute("SELECT count(*) FROM session_words WHERE next_review <= date('now') AND box < 6")
        due_count = c.fetchone()[0]
        # 统计已掌握
        c.execute("SELECT count(*) FROM session_words WHERE box = 6")
        mastered_count = c.fetchone()[0]

    # 显示统计栏
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        st.metric("📅 今日待复习 (Due)", due_count, delta="加油！")
    with col_stat2:
        st.metric("🏆 已完全掌握 (Mastered)", mastered_count)

    st.divider()

    # 2. 队列初始化
    if 'review_queue' not in st.session_state:
        st.session_state.review_queue = []

    # 3. 核心复习界面逻辑
    # 场景 A: 队列为空 (要么没开始，要么复习完了)
    if not st.session_state.review_queue:
        if due_count > 0:
            col_center = st.columns([1, 2, 1])
            with col_center[1]:
                if st.button("🚀 开始今日复习 (Start Review)", type="primary", use_container_width=True):
                    # 加载数据到内存队列
                    st.session_state.review_queue = st.session_state.db.get_due_cards()
                    st.session_state.review_index = 0
                    st.rerun()
        else:
            st.balloons()
            st.success("🎉 恭喜！今天的复习任务已全部完成！请明天再来。")
            st.caption("(间隔重复系统的核心就是：不到时间不复习。去休息吧！)")
            
            # (可选) 强制复习按钮
            if st.button("♻️ 强制复习所有未退休单词 (Test Mode)"):
                 st.session_state.review_queue = st.session_state.db.get_due_cards() # 这里其实可以写个获取全部的SQL，暂时复用
                 st.session_state.review_index = 0
                 st.rerun()

    # 场景 B: 正在复习中
    else:
        # 边界检查：防止索引越界
        if st.session_state.review_index >= len(st.session_state.review_queue):
            st.success("🎉 本轮队列已清空！")
            if st.button("🔄 刷新状态"):
                st.session_state.review_queue = [] # 清空队列
                st.rerun()
        else:
            # -------------------------------------------------------
            # 🔥 关键点：必须先获取 current_word，才能渲染后面的按钮
            # -------------------------------------------------------
            current_word = st.session_state.review_queue[st.session_state.review_index]
            box_lv = current_word.get('box', 1)
            
            # 显示进度条
            progress = (st.session_state.review_index + 1) / len(st.session_state.review_queue)
            st.progress(progress, text=f"Progress: {st.session_state.review_index + 1}/{len(st.session_state.review_queue)}")

            # === 卡片容器 ===
            card_container = st.container(border=True)
            with card_container:
                # 顶部 Badge
                st.markdown(f"<small style='color: #888'>📦 当前等级: Box {box_lv}</small>", unsafe_allow_html=True)
                
                # 正面 (单词)
                st.markdown(f"<h1 style='text-align: center; color: #00f3ff; margin-top: 20px;'>{current_word['word']}</h1>", unsafe_allow_html=True)
                
                # 居中显示发音按钮
                c_spk_l, c_spk_c, c_spk_r = st.columns([1, 1, 1])
                with c_spk_c:
                    if st.button("🔊 听发音", key=f"tts_review_{current_word['id']}", use_container_width=True):
                        play_audio(current_word['word'])
                
                # 反面 (详情)
                if st.session_state.show_card_back:
                    st.markdown("---")
                    c_info, c_img = st.columns([2, 1])
                    with c_info:
                        st.markdown(f"**释义:** {current_word['meaning']}")
                        st.markdown(f"**词根:** `{current_word['root']}`")
                    with c_img:
                        st.caption(f"🧠 {current_word['imagery']}")
                
                st.write("") # Spacer

            # === 操作按钮区 (现在这里的 current_word 是安全的) ===
            col_b1, col_b2, col_b3 = st.columns([1, 0.5, 1])
            
            if not st.session_state.show_card_back:
                # 阶段 1: 翻面
                with col_b2:
                    if st.button("🔍 翻看背面", key="btn_flip", use_container_width=True):
                        st.session_state.show_card_back = True
                        st.rerun()
            else:
                # 阶段 2: 判定
                with col_b1:
                    if st.button("❌ 忘了 (Reset)", key="btn_forget", use_container_width=True):
                        # 1. 扣血 (游戏化)
                        st.session_state.game['hp'] -= 5
                        add_log("记忆模糊... HP -5", "damage")

                        # 2. 算法降级
                        new_box, next_date = st.session_state.db.process_review(current_word['id'], box_lv, False)
                        
                        st.toast(f"已重置回 Box 1", icon="💪")
                        st.session_state.review_index += 1
                        st.session_state.show_card_back = False
                        st.rerun()
                        
                with col_b3:
                    if st.button("✅ 记得 (Upgrade)", key="btn_remember", type="primary", use_container_width=True):
                        # 1. 加钱 (游戏化)
                        st.session_state.game['gold'] += 10
                        add_log("记忆清晰！金币 +10", "gold")

                        # 2. 算法升级
                        new_box, next_date = st.session_state.db.process_review(current_word['id'], box_lv, True)
                        
                        if new_box > 5:
                            st.session_state.game['xp'] += 50
                            st.toast("太强了！该词已永久毕业 (Mastered)！", icon="🏆")
                        else:
                            st.toast(f"升级成功！晋升至 Box {new_box}", icon="📅")
                            
                        st.session_state.review_index += 1
                        st.session_state.show_card_back = False
                        st.rerun()