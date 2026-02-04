import streamlit as st
import json
import sqlite3
import re
import time
from datetime import datetime
from openai import OpenAI

# ==========================================
# 1. API 配置
# ==========================================
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf"
BASE_URL = "https://api.moonshot.cn/v1"
MODEL_ID = "kimi-k2.5"

# ==========================================
# 2. 数据库逻辑 (保持不变)
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
# 3. AI 交互核心 (全流式)
# ==========================================

# 统一的流式请求函数
def get_stream_response(system_prompt, user_content):
    client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)
    stream = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=1, # 保持为 1
        stream=True,   # ⚠️ 关键：开启流式
        response_format={"type": "json_object"}
    )
    return stream

def clean_json_string(s):
    s = re.sub(r'^```json\s*', '', s)
    s = re.sub(r'^```\s*', '', s)
    s = re.sub(r'\s*```$', '', s)
    return s.strip()

# Prompt 1: 文章
PROMPT_ARTICLE = """
你是一个英语小说家。请根据用户提供的单词，写一篇 CET-6 难度的短文。
要求：
1. 必须包含所有单词，并用 <span class='highlight-word'>单词</span> 包裹。
2. 返回 JSON: {"article_english": "...", "article_chinese": "..."}
"""

# Prompt 2: 单词卡
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

# Prompt 3: 测验
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
st.set_page_config(page_title="NEURAL_MODULAR_SYSTEM", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #050505; color: #e0e0e0; font-family: 'Courier New', monospace; }
    h1, h2, h3 { color: #00f3ff !important; text-shadow: 0 0 5px #00f3ff; }
    .status-box { border: 1px solid #333; padding: 10px; background: #111; margin-bottom: 10px; border-left: 5px solid #00f3ff; }
    .highlight-word { color: #ff00ff; font-weight: bold; text-decoration: underline; }
    div.stButton > button { border: 1px solid #39ff14; color: #39ff14; background: transparent; transition: all 0.3s; }
    div.stButton > button:hover { background: #39ff14; color: #000; box-shadow: 0 0 10px #39ff14; }
    
    /* 进度条样式 */
    .step-indicator { padding: 5px; margin: 5px 0; border-radius: 4px; font-size: 0.8em; }
    .step-done { background: #004400; color: #39ff14; border: 1px solid #39ff14; }
    .step-active { background: #002244; color: #00f3ff; border: 1px solid #00f3ff; animation: pulse 1.5s infinite; }
    .step-waiting { background: #222; color: #666; border: 1px solid #444; }
    
    @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }
</style>
""", unsafe_allow_html=True)

# --- Session State 初始化 (状态机) ---
# pipeline_status: 'idle', 'generating_article', 'generating_cards', 'generating_quiz', 'done'
if 'pipeline_status' not in st.session_state: st.session_state['pipeline_status'] = 'idle'
if 'current_words_list' not in st.session_state: st.session_state['current_words_list'] = []
if 'session_id' not in st.session_state: st.session_state['session_id'] = None

# 数据缓存
if 'data_article' not in st.session_state: st.session_state['data_article'] = None
if 'data_cards' not in st.session_state: st.session_state['data_cards'] = None
if 'data_quiz' not in st.session_state: st.session_state['data_quiz'] = None

# --- 侧边栏 ---
with st.sidebar:
    st.title("🧩 模块化中枢")
    user_input = st.text_area("输入数据流:", value="ephemeral, serendipity", height=100)
    
    if st.button("📥 注入数据 (Initialize)"):
        words = [w.strip() for w in user_input.split(',') if w.strip()]
        st.session_state['current_words_list'] = words
        # 重置所有状态
        st.session_state['pipeline_status'] = 'ready'
        st.session_state['data_article'] = None
        st.session_state['data_cards'] = None
        st.session_state['data_quiz'] = None
        sess_id = create_empty_session(user_input)
        st.session_state['session_id'] = sess_id
        st.success(f"✅ 数据已挂载! ID: {sess_id}")

# --- 顶部状态监控 (Visual Feedback) ---
st.title("⚡ NEURAL MODULAR SYSTEM")

# 显示当前流水线状态
cols = st.columns(3)
status = st.session_state['pipeline_status']

# 定义状态样式辅助函数
def get_class(target_step, current_status):
    order = ['idle', 'ready', 'generating_article', 'generating_cards', 'generating_quiz', 'done']
    try:
        curr_idx = order.index(current_status)
        target_idx = order.index(target_step)
        if current_status == 'done': return "step-done"
        if current_status == target_step: return "step-active"
        if curr_idx > target_idx: return "step-done"
        return "step-waiting"
    except:
        return "step-waiting"

with cols[0]:
    c = get_class('generating_article', status)
    st.markdown(f"<div class='step-indicator {c}'>1. 文章生成模块 (ARTICLE)</div>", unsafe_allow_html=True)
with cols[1]:
    c = get_class('generating_cards', status)
    st.markdown(f"<div class='step-indicator {c}'>2. 记忆解析模块 (CARDS)</div>", unsafe_allow_html=True)
with cols[2]:
    c = get_class('generating_quiz', status)
    st.markdown(f"<div class='step-indicator {c}'>3. 战术演练模块 (QUIZ)</div>", unsafe_allow_html=True)

st.divider()

# ==========================================
# 5. 核心逻辑控制流 (自动接力)
# ==========================================

# 只有在 ready 状态下才显示启动按钮
if st.session_state['pipeline_status'] == 'ready':
    if st.button("🚀 启动神经链路 (START SEQUENCE)", use_container_width=True):
        st.session_state['pipeline_status'] = 'generating_article'
        st.rerun() # 立即刷新，进入 step 1

# --- 阶段 1: 生成文章 (Generating Article) ---
if st.session_state['pipeline_status'] == 'generating_article':
    st.info("📡 正在建立文章生成链路...")
    placeholder = st.empty()
    full_text = ""
    
    # 1. 发起流式请求
    stream = get_stream_response(PROMPT_ARTICLE, f"单词: {st.session_state['current_words_list']}")
    
    # 2. 逐字接收
    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        full_text += content
        # 实时显示 JSON 源码流 (Cyberpunk 风格)
        placeholder.code(full_text, language='json')
    
    # 3. 解析与保存
    try:
        clean_text = clean_json_string(full_text)
        data = json.loads(clean_text)
        st.session_state['data_article'] = data
        update_session_article(st.session_state['session_id'], data['article_english'], data['article_chinese'])
        
        # 4. ⚠️ 触发下一阶段 (Relay)
        st.session_state['pipeline_status'] = 'generating_cards'
        st.rerun() # 刷新页面，自动进入下一段逻辑
        
    except Exception as e:
        st.error(f"文章生成失败: {e}")
        st.stop()

# --- 阶段 2: 生成单词卡 (Generating Cards) ---
elif st.session_state['pipeline_status'] == 'generating_cards':
    # 此时界面上应该能看到文章已经好了，正在跑单词
    st.info("🧠 文章已就绪。正在解析记忆碎片...")
    placeholder = st.empty()
    full_text = ""
    
    stream = get_stream_response(PROMPT_CARDS, f"单词: {st.session_state['current_words_list']}")
    
    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        full_text += content
        placeholder.code(full_text, language='json')
        
    try:
        clean_text = clean_json_string(full_text)
        data = json.loads(clean_text)
        st.session_state['data_cards'] = data
        save_words(st.session_state['session_id'], data['words'])
        
        # 4. ⚠️ 触发下一阶段 (Relay)
        st.session_state['pipeline_status'] = 'generating_quiz'
        st.rerun()
        
    except Exception as e:
        st.error(f"单词解析失败: {e}")
        st.stop()

# --- 阶段 3: 生成测验 (Generating Quiz) ---
elif st.session_state['pipeline_status'] == 'generating_quiz':
    st.info("⚔️ 记忆已备份。正在构建实战演练...")
    placeholder = st.empty()
    full_text = ""
    
    stream = get_stream_response(PROMPT_QUIZ, f"单词: {st.session_state['current_words_list']}")
    
    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        full_text += content
        placeholder.code(full_text, language='json')
        
    try:
        clean_text = clean_json_string(full_text)
        data = json.loads(clean_text)
        st.session_state['data_quiz'] = data
        
        # 4. ⚠️ 完成所有任务
        st.session_state['pipeline_status'] = 'done'
        st.rerun()
        
    except Exception as e:
        st.error(f"测验生成失败: {e}")
        st.stop()

# ==========================================
# 6. 结果展示 (当状态不为生成中时显示)
# ==========================================

# 只要有数据就显示，不管当前在第几步 (实现"看着文章等后台跑"的效果)
tab1, tab2, tab3 = st.tabs(["📜 阅读 (READ)", "🧩 记忆 (MEMORY)", "⚔️ 演练 (COMBAT)"])

with tab1:
    if st.session_state['data_article']:
        data = st.session_state['data_article']
        c1, c2 = st.columns(2)
        with c1: 
            st.markdown("### English Stream")
            st.markdown(f"{data['article_english']}", unsafe_allow_html=True)
        with c2: 
            st.markdown("### 中文译文")
            st.markdown(f"<span style='color:#aaa'>{data['article_chinese']}</span>", unsafe_allow_html=True)
    else:
        st.markdown("*等待数据注入...*")

with tab2:
    if st.session_state['data_cards']:
        for w in st.session_state['data_cards']['words']:
            with st.container(border=True):
                st.subheader(w['word'])
                st.markdown(f"**含义:** {w['meaning']}")
                st.markdown(f"**词根:** <span style='color:#39ff14'>{w['root']}</span>", unsafe_allow_html=True)
                st.write(f"**画面:** {w['imagery']}")
        
        # 保留手动按钮 (强制要求不删除)
        if st.button("🧠 手动重刷记忆 (Re-Analyze)", key="btn_cards"):
             # 这里可以写手动触发逻辑，但在全自动流里一般用不到
             pass
    else:
        if st.session_state['pipeline_status'] in ['generating_article', 'generating_cards']:
            st.warning("⚠️ 神经链路正在后台解算中...")
        else:
            st.markdown("*等待链路启动...*")
            # 只有在完全没有数据且空闲时，才显示这个手动按钮
            if st.button("🧠 手动解析 (Analyze Words)", key="btn_manual_cards"):
                pass # 你可以在这里填回之前的单次调用逻辑

with tab3:
    if st.session_state['data_quiz']:
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
            
        # 保留手动按钮
        if st.button("⚔️ 手动重置战场 (Re-Generate)", key="btn_quiz"):
             pass
    else:
        if st.session_state['pipeline_status'] in ['generating_article', 'generating_cards', 'generating_quiz']:
             st.warning("⚠️ 战术数据正在加载...")
        else:
             st.markdown("*等待链路启动...*")
             if st.button("⚔️ 手动生成 (Start Quiz)", key="btn_manual_quiz"):
                pass