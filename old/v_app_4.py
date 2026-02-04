import streamlit as st
import json
import sqlite3
import random
from datetime import datetime
from openai import OpenAI

# ==========================================
# ⚠️ 1. 必须修改这里：填入你的正确 Key
# ==========================================
# 确保引号内没有多余的空格，必须是 sk- 开头的长字符串
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf" 
BASE_URL = "https://api.moonshot.cn/v1"

# ==========================================
# 2. 数据库逻辑
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
# 3. 页面主逻辑
# ==========================================
st.set_page_config(page_title="Kimi 单词私教 Final", page_icon="🎓", layout="wide")

# --- 侧边栏 ---
with st.sidebar:
    st.title("📚 控制台")
    st.metric("当前词汇量", f"{get_all_words_count()} 个")
    
    st.divider()
    st.markdown("### 1. 录入新词")
    user_input = st.text_area("输入单词:", value="ephemeral, serendipity", height=100)
    start_btn = st.button("🚀 生成新卡片", type="primary")
    
    st.divider()
    st.markdown("### 2. 复习旧词")
    review_btn = st.button("🎲 随机抽查")
    if review_btn:
        st.session_state['mode'] = 'review'
        st.session_state['current_cards'] = get_random_review_cards(5)
        st.session_state['current_quizzes'] = [] 

# --- 核心提示词 ---
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
    with st.spinner("AI 正在思考中..."):
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
            st.error(f"出错: {e}")
            if "401" in str(e):
                st.error("⚠️ 你的 API Key 填写错误，请检查代码第 12 行！")

# --- 渲染界面 ---
st.title("🎓 单词突击训练营")

if 'current_cards' in st.session_state:
    # 渲染卡片
    cols = st.columns(3)
    for idx, card in enumerate(st.session_state['current_cards']):
        with cols[idx % 3]: 
            with st.container(border=True):
                st.subheader(card['word'])
                st.caption(f"[{card['ipa']}]")
                with st.expander("查看答案"):
                    st.markdown(f"**{card['meaning']}**")
                    st.info(f"💡 {card['memory_hack']}")
                    st.text(f"📖 {card['sentence']}")
    
    # 渲染测试 (仅学习模式)
    if st.session_state.get('mode') == 'learn' and st.session_state.get('current_quizzes'):
        st.divider()
        st.subheader("📝 当堂测试")
        for i, q in enumerate(st.session_state['current_quizzes']):
            st.markdown(f"**Q{i+1}: {q['question']}**")
            user_choice = st.radio("选择:", q['options'], key=f"q_{i}", index=None)
            if user_choice:
                if q['options'].index(user_choice) == q['answer_idx']:
                    st.success("正确！")
                else:
                    st.error(f"错误。解析：{q['explanation']}")

elif get_all_words_count() == 0:
    st.info("👈 请在左侧输入单词开始第一次学习！")
else:
    st.write("👈 点击左侧按钮开始复习或学习新词。")