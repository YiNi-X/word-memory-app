import streamlit as st
import json
import sqlite3
import re
from datetime import datetime
from openai import OpenAI

# ==========================================
# 1. API 配置
# ==========================================
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf"
BASE_URL = "https://api.moonshot.cn/v1"
MODEL_ID = "kimi-k2.5"

# ==========================================
# 2. 数据库逻辑
# ==========================================
DB_NAME = 'neural_vocab_lazy.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS learning_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  words_input TEXT,
                  article_english TEXT,
                  article_chinese TEXT,
                  created_at TIMESTAMP)''')
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

def create_empty_session(words_str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO learning_sessions (words_input, created_at) VALUES (?, ?)", (words_str, current_time))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def update_session_article(session_id, en, cn):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE learning_sessions SET article_english = ?, article_chinese = ? WHERE id = ?", (en, cn, session_id))
    conn.commit()
    conn.close()

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
# 3. AI 交互核心
# ==========================================
def get_stream_response(system_prompt, user_content):
    client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)
    stream = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=1,
        stream=True,
        response_format={"type": "json_object"}
    )
    return stream

def clean_json_string(s):
    s = re.sub(r'^```json\s*', '', s)
    s = re.sub(r'^```\s*', '', s)
    s = re.sub(r'\s*```$', '', s)
    return s.strip()

PROMPT_ARTICLE = """
你是一个英语小说家。请根据用户提供的单词，写一篇 CET-6 难度的短文。
要求：
1. 必须包含所有单词，并用 <span class='highlight-word'>单词</span> 包裹。
2. 返回 JSON: {"article_english": "...", "article_chinese": "..."}
"""

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
# 4. 页面 UI 设置
# ==========================================
st.set_page_config(page_title="NEURAL_MODULAR_SYSTEM_V11", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #050505; color: #e0e0e0; font-family: 'Courier New', monospace; }
    /* 🔴 改了这里：标题颜色变成品红，用于验证你的文件是否更新 */
    h1 { color: #ff00ff !important; text-shadow: 0 0 10px #ff00ff; }
    h2, h3 { color: #00f3ff !important; text-shadow: 0 0 5px #00f3ff; }
    
    .status-box { border: 1px solid #333; padding: 10px; background: #111; margin-bottom: 10px; border-left: 5px solid #00f3ff; }
    .highlight-word { color: #ff00ff; font-weight: bold; text-decoration: underline; }
    div.stButton > button { border: 1px solid #39ff14; color: #39ff14; background: transparent; }
    
    .step-indicator { padding: 5px; margin: 5px 0; border-radius: 4px; font-size: 0.8em; text-align: center; }
    .step-done { background: #004400; color: #39ff14; border: 1px solid #39ff14; }
    .step-active { background: #002244; color: #00f3ff; border: 1px solid #00f3ff; animation: pulse 1.5s infinite; }
    .step-waiting { background: #222; color: #666; border: 1px solid #444; }
    
    @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }
</style>
""", unsafe_allow_html=True)

# State 初始化
if 'pipeline_status' not in st.session_state: st.session_state['pipeline_status'] = 'idle'
if 'current_words_list' not in st.session_state: st.session_state['current_words_list'] = []
if 'session_id' not in st.session_state: st.session_state['session_id'] = None
if 'data_article' not in st.session_state: st.session_state['data_article'] = None
if 'data_cards' not in st.session_state: st.session_state['data_cards'] = None
if 'data_quiz' not in st.session_state: st.session_state['data_quiz'] = None

# 侧边栏
with st.sidebar:
    st.title("🧩 模块化中枢 V11")
    user_input = st.text_area("输入数据流:", value="ephemeral, serendipity", height=100)
    if st.button("📥 注入数据 (Initialize)"):
        words = [w.strip() for w in user_input.split(',') if w.strip()]
        st.session_state['current_words_list'] = words
        st.session_state['pipeline_status'] = 'ready'
        st.session_state['data_article'] = None
        st.session_state['data_cards'] = None
        st.session_state['data_quiz'] = None
        sess_id = create_empty_session(user_input)
        st.session_state['session_id'] = sess_id
        st.success(f"✅ 数据已挂载! ID: {sess_id}")

# 顶栏状态
st.title("⚡ NEURAL MODULAR SYSTEM")
status = st.session_state['pipeline_status']

# 辅助函数：计算状态样式
def get_class(target, current):
    order = ['idle', 'ready', 'generating_article', 'generating_cards', 'generating_quiz', 'done']
    try:
        curr_idx = order.index(current)
        target_idx = order.index(target)
        if current == 'done' or curr_idx > target_idx: return "step-done"
        if current == target: return "step-active"
        return "step-waiting"
    except: return "step-waiting"

c1, c2, c3 = st.columns(3)
with c1: st.markdown(f"<div class='step-indicator {get_class('generating_article', status)}'>1. ARTICLE (文章)</div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='step-indicator {get_class('generating_cards', status)}'>2. MEMORY (记忆)</div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='step-indicator {get_class('generating_quiz', status)}'>3. COMBAT (演练)</div>", unsafe_allow_html=True)

st.divider()

if status == 'ready':
    if st.button("🚀 启动神经链路 (START SEQUENCE)", use_container_width=True):
        st.session_state['pipeline_status'] = 'generating_article'
        st.rerun()

# ==========================================
# 5. 统一渲染逻辑
# ==========================================
tab_article, tab_cards, tab_quiz = st.tabs(["📜 阅读 (READ)", "🧩 记忆 (MEMORY)", "⚔️ 演练 (COMBAT)"])

# --- Tab 1: Article ---
with tab_article:
    if status == 'generating_article':
        st.info("⚡ 正在接收文章数据流...")
        stream_box = st.empty()
        full_text = ""
        try:
            stream = get_stream_response(PROMPT_ARTICLE, f"单词: {st.session_state['current_words_list']}")
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                full_text += content
                stream_box.code(full_text, language='json')
            
            clean_text = clean_json_string(full_text)
            data = json.loads(clean_text)
            st.session_state['data_article'] = data
            update_session_article(st.session_state['session_id'], data['article_english'], data['article_chinese'])
            
            st.session_state['pipeline_status'] = 'generating_cards'
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    elif st.session_state['data_article']:
        data = st.session_state['data_article']
        col_en, col_cn = st.columns(2)
        with col_en:
            st.markdown("### English Stream")
            st.markdown(f"{data['article_english']}", unsafe_allow_html=True)
        with col_cn:
            st.markdown("### 中文译文")
            st.markdown(f"<span style='color:#aaa'>{data['article_chinese']}</span>", unsafe_allow_html=True)
            
    else:
        st.markdown("*等待链路启动...*")


# --- Tab 2: Cards ---
with tab_cards:
    if status == 'generating_cards':
        st.info("🧠 正在解析记忆碎片...")
        stream_box = st.empty()
        full_text = ""
        try:
            stream = get_stream_response(PROMPT_CARDS, f"单词: {st.session_state['current_words_list']}")
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                full_text += content
                stream_box.code(full_text, language='json')
            
            clean_text = clean_json_string(full_text)
            data = json.loads(clean_text)
            st.session_state['data_cards'] = data
            save_words(st.session_state['session_id'], data['words'])
            
            st.session_state['pipeline_status'] = 'generating_quiz'
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    elif st.session_state['data_cards']:
        for w in st.session_state['data_cards']['words']:
            with st.container(border=True):
                st.subheader(w['word'])
                st.markdown(f"**含义:** {w['meaning']} | **词根:** <span style='color:#39ff14'>{w['root']}</span>", unsafe_allow_html=True)
                st.write(f"**画面:** {w['imagery']}")
                
    else:
        st.markdown("*等待文章模块完成...*")


# --- Tab 3: Quiz ---
with tab_quiz:
    if status == 'generating_quiz':
        st.info("⚔️ 正在构建战场...")
        stream_box = st.empty()
        full_text = ""
        try:
            stream = get_stream_response(PROMPT_QUIZ, f"单词: {st.session_state['current_words_list']}")
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                full_text += content
                stream_box.code(full_text, language='json')
            
            clean_text = clean_json_string(full_text)
            data = json.loads(clean_text)
            st.session_state['data_quiz'] = data
            
            st.session_state['pipeline_status'] = 'done'
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    elif st.session_state['data_quiz']:
        for i, q in enumerate(st.session_state['data_quiz']['quizzes']):
            st.markdown(f"**Q{i+1}: {q['question']}**")
            choice = st.radio("选择:", q['options'], key=f"q_{i}", index=None)
            if choice:
                if choice == q['answer']: st.success("✅ 正确")
                else: st.error(f"❌ 错误。答案是: {q['answer']}")
                st.caption(f"解析: {q['explanation']}")
            st.divider()
    else:
        st.markdown("*等待记忆模块完成...*")