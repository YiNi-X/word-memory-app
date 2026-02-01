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
MODEL_ID = "kimi-k2.5"  # 使用最新模型，速度快且遵循指令强

# ==========================================
# 2. 数据库逻辑 (适配分步保存)
# ==========================================
DB_NAME = 'neural_vocab_lazy.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 主表：记录一次学习会话 (Session)
    c.execute('''CREATE TABLE IF NOT EXISTS learning_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  words_input TEXT,
                  article_english TEXT,
                  article_chinese TEXT,
                  created_at TIMESTAMP)''')
    # 子表：单词
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
    conn.commit()
    conn.close()

# 仅创建一个空的 Session（占位符）
def create_empty_session(words_str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO learning_sessions (words_input, created_at) VALUES (?, ?)", (words_str, current_time))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

# 更新 Session 的文章部分
def update_session_article(session_id, en, cn):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE learning_sessions SET article_english = ?, article_chinese = ? WHERE id = ?", (en, cn, session_id))
    conn.commit()
    conn.close()

# 插入单词
def save_words(session_id, words_data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for w in words_data:
        c.execute('''INSERT INTO session_words 
                     (session_id, word, meaning, root_explanation, imagery_desc, is_core) 
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                     (session_id, w['word'], w['meaning'], w['root'], w['imagery'], w['is_core']))
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. AI 交互函数 (分拆为三个微服务)
# ==========================================
def call_ai(system_prompt, user_content):
    client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=1,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# Prompt 1: 只生成文章
PROMPT_ARTICLE = """
你是一个英语小说家。请根据用户提供的单词，写一篇 CET-6 难度的短文。
要求：
1. 必须包含所有单词，并用 <span class='highlight-word'>单词</span> 包裹。
2. 返回 JSON: {"article_english": "...", "article_chinese": "..."}
"""

# Prompt 2: 只生成单词卡
PROMPT_CARDS = """
你是一个词源学家。请分析用户提供的单词。
要求：
1. 解析词根、提供联想画面、判断是否核心词。
2. 返回 JSON: 
{
  "words": [
    {"word": "...", "meaning": "...", "root": "...", "imagery": "...", "is_core": true/false}
  ]
}
"""

# Prompt 3: 只生成测验
PROMPT_QUIZ = """
你是一个出题老师。请根据用户提供的单词设计 2 道单项选择题。
要求：
1. 返回 JSON:
{
  "quizzes": [
    {"question": "...", "options": ["A", "B", "C", "D"], "answer": "正确选项内容", "explanation": "..."}
  ]
}
"""

# ==========================================
# 4. 页面主逻辑
# ==========================================
st.set_page_config(page_title="NEURAL_MODULAR_SYSTEM", page_icon="🧩", layout="wide")

# 保持你的赛博朋克样式
st.markdown("""
<style>
    .stApp { background-color: #050505; color: #e0e0e0; font-family: 'Courier New'; }
    h1, h2, h3 { color: #00f3ff !important; }
    .status-box { border: 1px solid #333; padding: 10px; background: #111; margin-bottom: 10px; }
    .highlight-word { color: #ff00ff; font-weight: bold; }
    div.stButton > button { border: 1px solid #39ff14; color: #39ff14; background: transparent; }
    div.stButton > button:hover { background: #39ff14; color: #000; }
</style>
""", unsafe_allow_html=True)

# --- Session State 初始化 (用于存储分步生成的数据) ---
if 'step_status' not in st.session_state:
    st.session_state['step_status'] = 'idle' # idle, ready
if 'current_words_list' not in st.session_state:
    st.session_state['current_words_list'] = []
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = None

# 数据缓存
if 'data_article' not in st.session_state: st.session_state['data_article'] = None
if 'data_cards' not in st.session_state: st.session_state['data_cards'] = None
if 'data_quiz' not in st.session_state: st.session_state['data_quiz'] = None

# --- 侧边栏：系统 1 (单词接收系统) ---
with st.sidebar:
    st.title("🧩 模块化中枢")
    st.markdown("### SYSTEM 1: 接收端")
    user_input = st.text_area("输入数据流:", value="ephemeral, serendipity", height=100)
    
    if st.button("📥 注入数据 (Initialize)"):
        # 1. 瞬间接收单词
        words = [w.strip() for w in user_input.split(',') if w.strip()]
        st.session_state['current_words_list'] = words
        st.session_state['step_status'] = 'ready'
        
        # 2. 清空旧缓存
        st.session_state['data_article'] = None
        st.session_state['data_cards'] = None
        st.session_state['data_quiz'] = None
        
        # 3. 数据库占位
        sess_id = create_empty_session(user_input)
        st.session_state['session_id'] = sess_id
        
        st.success(f"✅ 数据已挂载! ID: {sess_id}")

# --- 主界面 ---
st.title("⚡ NEURAL MODULAR SYSTEM")

if st.session_state['step_status'] == 'ready':
    # 显示当前挂载的单词
    st.markdown(f"<div class='status-box'>📡 当前挂载数据: <b>{', '.join(st.session_state['current_words_list'])}</b></div>", unsafe_allow_html=True)

    # 分页系统
    tab1, tab2, tab3 = st.tabs(["📜 系统2: 沉浸阅读", "🧩 系统3: 记忆碎片", "⚔️ 系统4: 实战演练"])

    # === 系统 2: 文章生成 ===
    with tab1:
        if st.session_state['data_article'] is None:
            st.info("等待指令... 文章模块处于待机状态。")
            if st.button("🚀 启动阅读引擎 (Generate Article)"):
                with st.spinner("正在编写故事..."):
                    try:
                        # 调用 AI
                        res = call_ai(PROMPT_ARTICLE, f"单词: {st.session_state['current_words_list']}")
                        st.session_state['data_article'] = res
                        # 存入数据库
                        update_session_article(st.session_state['session_id'], res['article_english'], res['article_chinese'])
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            # 渲染文章
            data = st.session_state['data_article']
            c1, c2 = st.columns(2)
            with c1: st.markdown(f"{data['article_english']}", unsafe_allow_html=True)
            with c2: st.markdown(f"<span style='color:#aaa'>{data['article_chinese']}</span>", unsafe_allow_html=True)

    # === 系统 3: 单词记忆 ===
    with tab2:
        if st.session_state['data_cards'] is None:
            st.info("等待指令... 记忆解析模块处于待机状态。")
            if st.button("🧠 启动记忆解析 (Analyze Words)"):
                with st.spinner("正在解析词源..."):
                    try:
                        res = call_ai(PROMPT_CARDS, f"单词: {st.session_state['current_words_list']}")
                        st.session_state['data_cards'] = res
                        # 存入数据库
                        save_words(st.session_state['session_id'], res['words'])
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            # 渲染卡片
            for w in st.session_state['data_cards']['words']:
                with st.container(border=True):
                    st.subheader(w['word'])
                    st.write(f"**含义:** {w['meaning']}")
                    st.write(f"**词根:** {w['root']}")
                    st.write(f"**画面:** {w['imagery']}")

    # === 系统 4: 测验系统 ===
    with tab3:
        if st.session_state['data_quiz'] is None:
            st.info("等待指令... 战斗模拟模块处于待机状态。")
            if st.button("⚔️ 启动实战演练 (Start Quiz)"):
                with st.spinner("正在生成战场..."):
                    try:
                        res = call_ai(PROMPT_QUIZ, f"单词: {st.session_state['current_words_list']}")
                        st.session_state['data_quiz'] = res
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            # 渲染题目
            for i, q in enumerate(st.session_state['data_quiz']['quizzes']):
                st.markdown(f"**Q{i+1}: {q['question']}**")
                choice = st.radio("选择:", q['options'], key=f"q_{i}", index=None)
                if choice:
                    if choice == q['answer']:
                        st.success("✅ 正确")
                    else:
                        st.error(f"❌ 错误。答案是: {q['answer']}")
                        st.info(q['explanation'])
                st.divider()

else:
    st.warning("👈 请先在左侧输入单词并点击 [注入数据] 以初始化系统。")