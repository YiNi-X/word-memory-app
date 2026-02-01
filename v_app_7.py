import streamlit as st
import json
import sqlite3
import random
from datetime import datetime
from openai import OpenAI

# ==========================================
# ⚠️ 1. API 配置
# ==========================================
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf" 
BASE_URL = "https://api.moonshot.cn/v1"

# ==========================================
# 2. 数据库逻辑 (升级版：支持 Quiz)
# ==========================================
DB_NAME = 'neural_vocab_core_v2.db' # 升级数据库名以防冲突

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 表1：学习会话
    c.execute('''CREATE TABLE IF NOT EXISTS learning_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  article_english TEXT,
                  article_chinese TEXT,
                  created_at TIMESTAMP)''')
                  
    # 表2：单词详情
    c.execute('''CREATE TABLE IF NOT EXISTS session_words
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER,
                  word TEXT,
                  meaning TEXT,
                  root_explanation TEXT,
                  imagery_desc TEXT,
                  is_core BOOLEAN,
                  status TEXT DEFAULT 'new',
                  FOREIGN KEY(session_id) REFERENCES learning_sessions(id))''')
    
    # 表3：测验题目 (新增)
    # options 字段我们将存为 JSON 字符串，因为 SQLite 不支持数组
    c.execute('''CREATE TABLE IF NOT EXISTS session_quizzes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER,
                  question TEXT,
                  options_json TEXT, 
                  correct_answer TEXT,
                  explanation TEXT,
                  FOREIGN KEY(session_id) REFERENCES learning_sessions(id))''')
                  
    conn.commit()
    conn.close()

def get_forgotten_words():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT word FROM session_words WHERE status = 'forgot'")
    words = [row[0] for row in c.fetchall()]
    conn.close()
    return list(set(words))

def save_study_session(article_data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # 1. 存文章
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute('''INSERT INTO learning_sessions (article_english, article_chinese, created_at) 
                     VALUES (?, ?, ?)''', 
                     (article_data['article_english'], article_data['article_chinese'], current_time))
        session_id = c.lastrowid
        
        # 2. 存单词
        for w in article_data['words']:
            c.execute('''INSERT INTO session_words 
                         (session_id, word, meaning, root_explanation, imagery_desc, is_core, status) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                         (session_id, w['word'], w['meaning'], w['root'], w['imagery'], w['is_core'], 'new'))
        
        # 3. 存测验 (新增)
        if 'quizzes' in article_data:
            for q in article_data['quizzes']:
                # 把选项列表转为 JSON 字符串存储
                options_str = json.dumps(q['options']) 
                c.execute('''INSERT INTO session_quizzes 
                             (session_id, question, options_json, correct_answer, explanation) 
                             VALUES (?, ?, ?, ?, ?)''', 
                             (session_id, q['question'], options_str, q['answer'], q['explanation']))
        
        conn.commit()
        return session_id
    except Exception as e:
        st.error(f"DATABASE ERROR: {e}")
        return None
    finally:
        conn.close()

def update_word_status(word_text, new_status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE session_words SET status = ? WHERE word = ?", (new_status, word_text))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 检查表是否存在，防止首次运行报错
    try:
        c.execute("SELECT count(*) FROM session_words")
        total = c.fetchone()[0]
        c.execute("SELECT count(*) FROM session_words WHERE status='forgot'")
        forgot = c.fetchone()[0]
    except:
        total = 0
        forgot = 0
    conn.close()
    return total, forgot

init_db()

# ==========================================
# 3. 页面主逻辑
# ==========================================
st.set_page_config(page_title="NEURAL_VOCAB_V2", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    /* 赛博朋克基础风 */
    .stApp {
        background-color: #050505;
        background-image: linear-gradient(0deg, transparent 24%, rgba(0, 255, 65, .03) 25%, rgba(0, 255, 65, .03) 26%, transparent 27%, transparent 74%, rgba(0, 255, 65, .03) 75%, rgba(0, 255, 65, .03) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(0, 255, 65, .03) 25%, rgba(0, 255, 65, .03) 26%, transparent 27%, transparent 74%, rgba(0, 255, 65, .03) 75%, rgba(0, 255, 65, .03) 76%, transparent 77%, transparent);
        background-size: 50px 50px;
        color: #e0e0e0;
        font-family: 'Courier New', monospace;
    }
    h1, h2, h3 { color: #00f3ff !important; text-shadow: 0 0 10px #00f3ff; }
    
    /* 文章样式 */
    .article-box {
        background: #0a0a0a;
        border: 1px solid #333;
        border-left: 4px solid #00f3ff;
        padding: 20px;
        line-height: 1.6;
    }
    .highlight-word { color: #ff00ff; font-weight: bold; text-shadow: 0 0 5px #ff00ff; }
    
    /* 按钮样式 */
    div.stButton > button {
        background: transparent;
        border: 1px solid #39ff14;
        color: #39ff14;
        border-radius: 0;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background: #39ff14;
        color: #000;
        box-shadow: 0 0 15px #39ff14;
    }
    div.stButton > button[kind="primary"] { border-color: #ff00ff; color: #ff00ff; }
    
    /* Quiz 样式 */
    .quiz-container {
        border: 1px dashed #ffff00;
        padding: 15px;
        margin-bottom: 15px;
        background: rgba(255, 255, 0, 0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- 侧边栏 ---
with st.sidebar:
    st.title("🧠 神经中枢 V2")
    total_count, forgot_count = get_stats()
    st.metric("记忆库", f"{total_count}", delta="UNITS")
    st.metric("待修复 (Forgot)", f"{forgot_count}", delta_color="inverse")
    
    st.divider()
    st.markdown("### 📥 数据注入")
    user_input = st.text_area("输入单词:", value="ephemeral, serendipity", height=100)
    
    forgotten_cache = get_forgotten_words()
    if forgotten_cache:
        st.info(f"检测到 {len(forgotten_cache)} 个遗忘单词，将自动合并。")
            
    start_btn = st.button("🚀 启动神经链接", type="primary")

# --- Prompt 工程 (增加了 Quiz 请求) ---
SYSTEM_PROMPT = """
你是一个英语学习助手。
任务：根据提供的单词列表，完成以下任务：
1. 写一篇 CET-6 难度的短文（包含所有单词，加粗）。
2. 解析每个单词。
3. [重要] 基于文章内容和单词用法，出 2-3 道单项选择题（Quiz）。

请严格输出 JSON 格式，结构如下：
{
    "article_english": "包含HTML标签<span class='highlight-word'>...</span>的文章",
    "article_chinese": "中文翻译",
    "words": [
        {
            "word": "单词",
            "meaning": "释义",
            "root": "词根",
            "imagery": "画面",
            "is_core": true/false
        }
    ],
    "quizzes": [
        {
            "question": "题干，关键处用 ____ 代替",
            "options": ["选项A", "选项B", "选项C", "选项D"],
            "answer": "正确选项的内容",
            "explanation": "解析"
        }
    ]
}
"""

# --- 主逻辑 ---
if start_btn and user_input:
    final_word_list = list(set([w.strip() for w in user_input.split(',')] + forgotten_cache))
    
    with st.spinner(f"正在构建神经突触... (单词数: {len(final_word_list)})"):
        try:
            client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)
            response = client.chat.completions.create(
                model="kimi-k2-thinking",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"单词列表: {', '.join(final_word_list)}"}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            
            # 存库
            save_study_session(data)
            st.session_state['current_data'] = data
            
        except Exception as e:
            st.error(f"SYSTEM FAILURE: {e}")

# --- 渲染界面 ---
st.title("⚡ NEURAL LEARNING FLOW")

if 'current_data' in st.session_state:
    data = st.session_state['current_data']
    
    # 增加了一个 Tab: 实战演练
    tab1, tab2, tab3 = st.tabs(["📜 沉浸阅读", "🧩 记忆碎片", "⚔️ 实战演练"])
    
    # Tab 1: 文章
    with tab1:
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown(f"<div class='article-box'>{data['article_english']}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='article-box' style='color:#aaa;'>{data['article_chinese']}</div>", unsafe_allow_html=True)

    # Tab 2: 单词卡片
    with tab2:
        st.caption("点击 FORGOT 会将单词加入[待复习]队列，下次自动出现。")
        cols = st.columns(3)
        for idx, w in enumerate(data['words']):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"<h3 style='margin:0; color:#00f3ff'>{w['word']}</h3>", unsafe_allow_html=True)
                    if w['is_core']:
                        st.markdown("<span style='color:#39ff14; font-size:0.8em'>[CORE UNIT]</span>", unsafe_allow_html=True)
                    st.markdown(f"**释义:** {w['meaning']}")
                    st.markdown(f"**词根:** `{w['root']}`")
                    st.markdown(f"**画面:** *{w['imagery']}*")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("🔴 FORGOT", key=f"f_{idx}"):
                        update_word_status(w['word'], 'forgot')
                        st.toast(f"已标记 {w['word']} 为待复习", icon="🧠")
                    if c2.button("🟢 GOT IT", key=f"r_{idx}"):
                        update_word_status(w['word'], 'remembered')
    
    # Tab 3: 测验 (新增功能)
    with tab3:
        st.subheader("⚔️ COMBAT SIMULATION (QUIZ)")
        if 'quizzes' in data and data['quizzes']:
            for i, q in enumerate(data['quizzes']):
                st.markdown(f"<div class='quiz-container'>", unsafe_allow_html=True)
                st.markdown(f"**Q{i+1}: {q['question']}**")
                
                # 使用 radio 组件做单选
                user_choice = st.radio(f"Select Output Path:", q['options'], key=f"quiz_{i}", index=None)
                
                if user_choice:
                    if user_choice == q['answer']:
                        st.success("✅ ACCESS GRANTED (正确)")
                    else:
                        st.error(f"❌ ACCESS DENIED. 正确答案是: {q['answer']}")
                        st.info(f"解析: {q['explanation']}")
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("本次生成未包含战斗模拟数据。")

else:
    st.info("👈 请在左侧输入单词，开始本次神经链接。")