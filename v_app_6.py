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
# 2. 数据库逻辑 (升级版：支持会话、文章与遗忘曲线)
# ==========================================
DB_NAME = 'neural_vocab_core.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 表1：学习会话 (LearningSession) - 你的"主线任务"
    c.execute('''CREATE TABLE IF NOT EXISTS learning_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  article_english TEXT,
                  article_chinese TEXT,
                  created_at TIMESTAMP)''')
                  
    # 表2：会话单词详情 (SessionWords) - 你的"单词档案"
    # status 字段用于记录：'new', 'remembered', 'forgot'
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

# [核心逻辑] 获取上次标记为"忘记"的单词
def get_forgotten_words():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 查找所有 status 为 'forgot' 的单词
    c.execute("SELECT word FROM session_words WHERE status = 'forgot'")
    words = [row[0] for row in c.fetchall()]
    conn.close()
    # 去重
    return list(set(words))

# [核心逻辑] 保存一次完整的学习会话
def save_study_session(article_data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # 1. 存文章 (Session)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute('''INSERT INTO learning_sessions (article_english, article_chinese, created_at) 
                     VALUES (?, ?, ?)''', 
                     (article_data['article_english'], article_data['article_chinese'], current_time))
        session_id = c.lastrowid
        
        # 2. 存单词 (Words)
        for w in article_data['words']:
            c.execute('''INSERT INTO session_words 
                         (session_id, word, meaning, root_explanation, imagery_desc, is_core, status) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                         (session_id, w['word'], w['meaning'], w['root'], w['imagery'], w['is_core'], 'new'))
        
        conn.commit()
        return session_id
    except Exception as e:
        st.error(f"DATABASE ERROR: {e}")
        return None
    finally:
        conn.close()

# [核心逻辑] 更新单词状态 (比如标记为 forgot)
def update_word_status(word_text, new_status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 这里我们简化逻辑：更新该单词在所有历史记录中的状态，或者只更新最近的
    # 为了实现"滚雪球"，我们只要确保数据库里有这个词标记为 forgot 即可
    c.execute("UPDATE session_words SET status = ? WHERE word = ?", (new_status, word_text))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM session_words")
    total = c.fetchone()[0]
    c.execute("SELECT count(*) FROM session_words WHERE status='forgot'")
    forgot = c.fetchone()[0]
    conn.close()
    return total, forgot

# 初始化数据库
init_db()

# ==========================================
# 3. 页面主逻辑 & 赛博朋克样式 (保持原味)
# ==========================================
st.set_page_config(page_title="NEURAL_VOCAB_CORE", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    /* 核心背景与字体 */
    .stApp {
        background-color: #050505;
        background-image: radial-gradient(#111 20%, transparent 20%), radial-gradient(#111 20%, transparent 20%);
        background-size: 20px 20px;
        color: #e0e0e0;
        font-family: 'Courier New', monospace;
    }
    h1, h2, h3 { color: #00f3ff !important; text-shadow: 0 0 10px #00f3ff; }
    
    /* 文章阅读区样式 */
    .article-box {
        background: #0a0a0a;
        border: 1px solid #333;
        border-left: 4px solid #00f3ff;
        padding: 20px;
        border-radius: 5px;
        font-size: 1.1em;
        line-height: 1.6;
    }
    .highlight-word {
        color: #ff00ff;
        font-weight: bold;
        text-shadow: 0 0 5px #ff00ff;
    }
    
    /* 按钮与交互 */
    div.stButton > button {
        background: transparent;
        border: 1px solid #39ff14;
        color: #39ff14;
        border-radius: 0;
    }
    div.stButton > button:hover {
        background: #39ff14;
        color: #000;
        box-shadow: 0 0 15px #39ff14;
    }
    div.stButton > button[kind="primary"] {
        border-color: #ff00ff;
        color: #ff00ff;
    }
    
    /* 状态指示器 */
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border: 1px solid #555;
        font-size: 0.8em;
        margin-right: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- 侧边栏 ---
with st.sidebar:
    st.title("🧠 神经中枢")
    total_count, forgot_count = get_stats()
    st.metric("已存储记忆单元", f"{total_count}")
    st.metric("待修复记忆 (Forgot)", f"{forgot_count}", delta_color="inverse")
    
    st.divider()
    st.markdown("### 📥 数据注入")
    user_input = st.text_area("输入新单词:", value="ephemeral, serendipity", height=100)
    
    # [逻辑点 1] 检查是否有遗忘单词
    forgotten_cache = get_forgotten_words()
    if forgotten_cache:
        st.warning(f"⚠️ 检测到 {len(forgotten_cache)} 个遗忘单词，将自动合并到本次训练。")
        with st.expander("查看遗忘列表"):
            st.write(", ".join(forgotten_cache))
            
    start_btn = st.button("🚀 启动神经链接 (Generate)", type="primary")

# --- Prompt 工程 (核心：要求 AI 写文章并返回结构化数据) ---
SYSTEM_PROMPT = """
你是一个英语学习助手。
任务：根据提供的单词列表，写一篇 CET-6 难度的短文（150词左右）。
要求：
1. 必须包含所有用户提供的单词。
2. 文章要逻辑通顺，分段（Section）。
3. 请严格输出 JSON 格式，结构如下：
{
    "article_english": "包含HTML标签的文章，请将目标单词用 <span class='highlight-word'>...</span> 包裹",
    "article_chinese": "文章的中文翻译",
    "words": [
        {
            "word": "单词原形",
            "meaning": "中文释义",
            "root": "词根词缀解释",
            "imagery": "记忆联想画面描述",
            "is_core": true/false (是否为核心常用词)
        }
    ]
}
注意：直接返回 JSON，不要 Markdown 标记。
"""

# --- 主逻辑处理 ---
if start_btn and user_input:
    # [逻辑点 2] 合并单词列表 (新词 + 遗忘词)
    final_word_list = list(set([w.strip() for w in user_input.split(',')] + forgotten_cache))
    
    with st.spinner(f"正在构建神经突触... (处理单词: {len(final_word_list)} 个)"):
        try:
            client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)
            response = client.chat.completions.create(
                model="moonshot-v1-8k",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"请使用这些单词写文章: {', '.join(final_word_list)}"}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            
            # [逻辑点 3] 存入数据库
            session_id = save_study_session(data)
            
            # 存入 Session State 用于展示
            st.session_state['current_data'] = data
            # 默认把遗忘列表里的词状态重置，因为我们这次学了
            # (这里为了简单，假设只要生成了新文章，这些词就暂时算"复习过"，状态可以改为 new 或 remembered，
            #  或者等待用户手动标记。为了体验闭环，我们先不自动改，让用户在下面手动点 '记住了')
            
        except Exception as e:
            st.error(f"SYSTEM FAILURE: {e}")

# --- 渲染界面 ---
st.title("⚡ NEURAL LEARNING FLOW")

if 'current_data' in st.session_state:
    data = st.session_state['current_data']
    
    # Tab 分页：阅读模式 vs 记忆模式
    tab1, tab2 = st.tabs(["📜 沉浸阅读 (Context)", "🧩 记忆碎片 (Details)"])
    
    with tab1:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("### ENGLISH LAYER")
            # 渲染带高亮 HTML 的文章
            st.markdown(f"<div class='article-box'>{data['article_english']}</div>", unsafe_allow_html=True)
        with col2:
            st.markdown("### CHINESE LAYER")
            st.markdown(f"<div class='article-box' style='color:#aaa; border-left-color:#555;'>{data['article_chinese']}</div>", unsafe_allow_html=True)

    with tab2:
        st.write("点击 `FORGOT` 会将单词加入待复习队列，下次生成时自动出现。")
        # 网格布局展示单词卡片
        cols = st.columns(3)
        for idx, w in enumerate(data['words']):
            with cols[idx % 3]:
                with st.container(border=True):
                    # 单词头
                    st.markdown(f"<h3 style='margin:0'>{w['word']}</h3>", unsafe_allow_html=True)
                    if w['is_core']:
                        st.markdown("<span class='status-badge' style='color:#39ff14; border-color:#39ff14'>CORE</span>", unsafe_allow_html=True)
                    st.divider()
                    
                    # 详细信息
                    st.markdown(f"**释义:** {w['meaning']}")
                    st.markdown(f"**🌱 词根:** {w['root']}")
                    st.markdown(f"**🖼️ 画面:** *{w['imagery']}*")
                    
                    st.divider()
                    # [逻辑点 4] 交互按钮：遗忘/记住
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🔴 FORGOT", key=f"f_{idx}"):
                            update_word_status(w['word'], 'forgot')
                            st.toast(f"已标记 {w['word']} 为待复习", icon="🧠")
                    with c2:
                        if st.button("🟢 GOT IT", key=f"r_{idx}"):
                            update_word_status(w['word'], 'remembered')
                            st.toast(f"记忆已强化: {w['word']}", icon="✅")

else:
    st.info("👈 请在左侧输入单词，开始本次神经链接。")
    st.markdown("""
    > **当前系统特性:**
    > 1. **自动回滚复习**: 左侧会自动检测你上次标记为 `Forgot` 的单词。
    > 2. **语境生成**: 不再是孤立的单词卡，而是生成一篇包含所有单词的**完整文章**。
    > 3. **记忆闭环**: 在右侧 Tab 中点击 `FORGOT`，该词会进入"待修复"池，下次自动加入学习列表。
    """)