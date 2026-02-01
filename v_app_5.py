import streamlit as st
import json
import sqlite3
import random
from datetime import datetime
from openai import OpenAI

# ==========================================
# ⚠️ 1. API 配置 (保持不变)
# ==========================================
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf" 
BASE_URL = "https://api.moonshot.cn/v1"

# ==========================================
# 2. 数据库逻辑 (保持不变)
# ==========================================
def init_db():
    conn = sqlite3.connect('vocab_master.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS flashcards
                 (word TEXT PRIMARY KEY, 
                  ipa TEXT,
                  meaning TEXT, 
                  memory_hack TEXT,
                  sentence TEXT,
                  added_at TEXT)''')
    conn.commit()
    conn.close()

def save_card_to_db(card_data):
    conn = sqlite3.connect('vocab_master.db')
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        c.execute('''INSERT OR REPLACE INTO flashcards 
                     (word, ipa, meaning, memory_hack, sentence, added_at) 
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                     (card_data['word'], card_data['ipa'], card_data['meaning'], 
                      card_data['memory_hack'], card_data['sentence'], current_time))
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

def get_all_words_count():
    conn = sqlite3.connect('vocab_master.db')
    c = conn.cursor()
    c.execute("SELECT count(*) FROM flashcards")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_random_review_cards(limit=5):
    conn = sqlite3.connect('vocab_master.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM flashcards ORDER BY RANDOM() LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# 初始化数据库
init_db()

# ==========================================
# 3. 页面主逻辑 & 赛博朋克样式注入
# ==========================================
st.set_page_config(page_title="NEURAL_VOCAB_2077", page_icon="💾", layout="wide")

# --- 注入赛博朋克 CSS ---
st.markdown("""
<style>
    /* 全局字体与背景 - 黑色网格背景 */
    .stApp {
        background-color: #050505;
        background-image: linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px);
        background-size: 20px 20px;
        color: #e0e0e0;
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* 标题样式 - 故障风 */
    h1, h2, h3 {
        color: #00f3ff !important;
        text-shadow: 2px 2px 0px #ff00ff;
        font-weight: 800;
        letter-spacing: -1px;
    }
    
    /* 侧边栏样式 */
    section[data-testid="stSidebar"] {
        background-color: #0a0a0a;
        border-right: 2px solid #00f3ff;
    }
    
    /* 按钮样式 - 霓虹边框 */
    div.stButton > button {
        background-color: transparent !important;
        border: 2px solid #00f3ff !important;
        color: #00f3ff !important;
        border-radius: 0px !important; /* 硬边角 */
        transition: all 0.3s ease;
        font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #00f3ff !important;
        color: #000 !important;
        box-shadow: 0 0 15px #00f3ff;
    }
    div.stButton > button:active {
        transform: scale(0.98);
    }
    
    /* 主按钮 (Primary) - 洋红色 */
    div.stButton > button[kind="primary"] {
        border: 2px solid #ff00ff !important;
        color: #ff00ff !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #ff00ff !important;
        color: #000 !important;
        box-shadow: 0 0 15px #ff00ff;
    }

    /* 输入框样式 */
    .stTextArea textarea {
        background-color: #000 !important;
        color: #00f3ff !important;
        border: 1px solid #333 !important;
        border-left: 5px solid #ff00ff !important;
    }
    
    /* 数据指标 Metric */
    div[data-testid="stMetric"] {
        background-color: #111;
        border: 1px dashed #39ff14;
        padding: 10px;
    }
    div[data-testid="stMetricValue"] {
        color: #39ff14 !important;
        font-family: 'Orbitron', monospace;
    }
    
    /* 卡片容器 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #333;
        background: rgba(0,0,0,0.6);
    }
    
    /* Expander 样式 */
    .streamlit-expanderHeader {
        color: #ffff00 !important;
        border-bottom: 1px solid #333;
    }
    
    /* 成功/错误信息 */
    .stAlert {
        background-color: #111 !important;
        border: 1px solid;
    }
</style>
""", unsafe_allow_html=True)

# --- 侧边栏 (控制台) ---
with st.sidebar:
    st.title("📟 神经控制台")
    st.markdown("`SYSTEM_STATUS: ONLINE`")
    
    st.metric("MEMORY_BANK (词汇量)", f"{get_all_words_count()} UNITS")
    
    st.divider()
    st.markdown("### 💾 数据录入")
    user_input = st.text_area("输入源代码 (单词):", value="ephemeral, serendipity", height=100, help="在此输入需要上传到神经植入物的单词")
    start_btn = st.button("🚀 执行注入程序", type="primary")
    
    st.divider()
    st.markdown("### 🎲 记忆回溯")
    review_btn = st.button("⚡ 随机检索测试")
    if review_btn:
        st.session_state['mode'] = 'review'
        st.session_state['current_cards'] = get_random_review_cards(5)
        st.session_state['current_quizzes'] = [] 

# --- 核心提示词 (保持不变) ---
SYSTEM_PROMPT = """
你是一个专业的英语词汇老师。请根据用户提供的单词列表，生成严格的 JSON。
JSON 结构：
{
    "cards": [
        {
            "word": "单词原形",
            "ipa": "音标",
            "meaning": "精简中文释义",
            "memory_hack": "助记法",
            "sentence": "英文例句"
        }
    ],
    "quizzes": [
        {
            "question": "选择题描述",
            "options": ["A", "B", "C", "D"],
            "answer_idx": 0,
            "explanation": "解析"
        }
    ]
}
不要包含 Markdown 标记。
"""

# --- 处理逻辑 ---
if start_btn and user_input:
    st.session_state['mode'] = 'learn'
    with st.spinner("⚠️ 正在连接神经网络... AI 思考中..."):
        try:
            client = OpenAI(api_key=KIMI_API_KEY, base_url=BASE_URL)
            response = client.chat.completions.create(
                model="moonshot-v1-8k",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"请处理: {user_input}"}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            
            for card in data['cards']:
                save_card_to_db(card)
            
            st.session_state['current_cards'] = data['cards']
            st.session_state['current_quizzes'] = data['quizzes']
            st.rerun()
            
        except Exception as e:
            st.error(f"SYSTEM FAILURE: {e}")
            if "401" in str(e):
                st.error("⚠️ 访问权限拒绝：API Key 无效，请检查代码第 12 行！")

# --- 渲染界面 ---
st.title("⚡ NEURAL VOCAB_2077")
st.markdown("`>> 初始化学习模块... [OK]`")

if 'current_cards' in st.session_state:
    # 渲染卡片
    cols = st.columns(3)
    for idx, card in enumerate(st.session_state['current_cards']):
        with cols[idx % 3]: 
            # 使用 container 模拟全息卡片
            with st.container(border=True):
                st.markdown(f"<h2 style='color:#39ff14; margin-bottom:0;'>{card['word']}</h2>", unsafe_allow_html=True)
                st.markdown(f"<span style='color:#00f3ff; font-family:sans-serif;'>[{card['ipa']}]</span>", unsafe_allow_html=True)
                st.divider()
                with st.expander("🔓 解码数据 (查看答案)"):
                    st.markdown(f"**📝 释义:** `{card['meaning']}`")
                    st.markdown(f"**🧠 骇入技巧:** *{card['memory_hack']}*")
                    st.markdown(f"**📖 数据样本:** {card['sentence']}")
    
    # 渲染测试 (仅学习模式)
    if st.session_state.get('mode') == 'learn' and st.session_state.get('current_quizzes'):
        st.markdown("---")
        st.subheader("⚔️ 战斗模拟 (QUIZ)")
        for i, q in enumerate(st.session_state['current_quizzes']):
            st.markdown(f"**MISSION_{i+1}: {q['question']}**")
            user_choice = st.radio(f"选择行动路径 (Q{i+1}):", q['options'], key=f"q_{i}", index=None)
            if user_choice:
                if q['options'].index(user_choice) == q['answer_idx']:
                    st.success("✅ 目标击破！(CORRECT)")
                else:
                    st.error(f"❌ 任务失败。(WRONG) // 数据解析：{q['explanation']}")

elif get_all_words_count() == 0:
    st.info("👈 数据库为空。请在左侧终端输入数据以初始化。")
else:
    st.write("👈 等待指令。点击左侧按钮执行 [复习] 或 [新数据录入]。")