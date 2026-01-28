import streamlit as st
import json
import sqlite3
import random
from datetime import datetime
from openai import OpenAI

# ==========================================
# 1. 配置区域
# ==========================================
KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf" # <--- 替换你的 Key
BASE_URL = "https://api.moonshot.cn/v1"

# ==========================================
# 2. 数据库逻辑 (升级版)
# ==========================================
def init_db():
    conn = sqlite3.connect('vocab_master.db') # 换个新名字，避免和旧表冲突
    c = conn.cursor()
    # 创建单词表：单词为主键(防止重复)，存入所有AI生成的细节
    c.execute('''CREATE TABLE IF NOT EXISTS flashcards
                 (word TEXT PRIMARY KEY, 
                  ipa TEXT,
                  meaning TEXT, 
                  memory_hack TEXT,
                  sentence TEXT,
                  added_at TEXT,
                  review_count INTEGER DEFAULT 0)''') # 预留字段：未来可以做复习次数统计
    conn.commit()
    conn.close()

def save_card_to_db(card_data):
    """将 AI 生成的单个卡片存入数据库"""
    conn = sqlite3.connect('vocab_master.db')
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # 使用 INSERT OR REPLACE，如果单词已存在，就更新它
        c.execute('''INSERT OR REPLACE INTO flashcards 
                     (word, ipa, meaning, memory_hack, sentence, added_at) 
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                     (card_data['word'], card_data['ipa'], card_data['meaning'], 
                      card_data['memory_hack'], card_data['sentence'], current_time))
        conn.commit()
    except Exception as e:
        print(f"Error saving card: {e}")
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
    """从数据库随机抽取N个单词用于复习"""
    conn = sqlite3.connect('vocab_master.db')
    conn.row_factory = sqlite3.Row # 让结果可以通过列名访问
    c = conn.cursor()
    c.execute("SELECT * FROM flashcards ORDER BY RANDOM() LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    # 转换为字典格式，适配前端渲染
    cards = []
    for row in rows:
        cards.append(dict(row))
    return cards

init_db()

# ==========================================
# 3. 页面逻辑
# ==========================================
st.set_page_config(page_title="Kimi 单词私教 Pro", page_icon="🧠", layout="wide")

# --- 侧边栏：状态与复习入口 ---
with st.sidebar:
    st.title("📊 学习进度")
    total_words = get_all_words_count()
    st.metric("已收录单词", f"{total_words} 个")
    
    st.divider()
    
    st.header("⚙️ 新词录入")
    default_words = "ephemeral, serendipity, ambiguous"
    user_input = st.text_area("输入新单词:", value=default_words, height=100)
    start_btn = st.button("🚀 生成新卡片", type="primary")

    st.divider()
    
    st.header("🔥 复习模式")
    review_btn = st.button("🎲 随机抽查 5 个旧词")
    if review_btn:
        st.session_state['mode'] = 'review'
        # 从数据库取数据
        cards = get_random_review_cards(5)
        if not cards:
            st.error("数据库是空的，先去学点新词吧！")
        else:
            st.session_state['current_cards'] = cards
            # 复习模式下，只要卡片，不需要做新题，但为了兼容渲染逻辑，我们可以把quizzes置空
            st.session_state['current_quizzes'] = [] 

# --- 提示词 (保持不变) ---
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

# --- 主逻辑：处理新词生成 ---
if start_btn and user_input:
    st.session_state['mode'] = 'learn'
    with st.spinner(f"Kimi 正在生成并存入数据库..."):
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
            
            # 关键步骤：把生成的卡片存入数据库
            for card in data['cards']:
                save_card_to_db(card)
            
            st.session_state['current_cards'] = data['cards']
            st.session_state['current_quizzes'] = data['quizzes']
            st.success(f"成功存入 {len(data['cards'])} 个新单词！")
            st.rerun()
            
        except Exception as e:
            st.error(f"出错: {e}")

# --- 渲染区域 (根据模式显示不同标题) ---
st.title("🧠 单词突击训练营")

if 'current_cards' in st.session_state:
    mode = st.session_state.get('mode', 'learn')
    
    if mode == 'review':
        st.warning("🎲 正在进行：随机复习模式 (数据来自你的历史库)")
    else:
        st.info("✨ 正在进行：新词学习模式")

    # 渲染卡片
    cols = st.columns(3)
    for idx, card in enumerate(st.session_state['current_cards']):
        with cols[idx % 3]: 
            with st.container(border=True):
                st.subheader(card['word'])
                st.caption(f"[{card['ipa']}]")
                # 默认遮挡释义，点击展开（适合复习）
                with st.expander("点击揭晓答案"):
                    st.markdown(f"**{card['meaning']}**")
                    st.info(f"🧠 {card['memory_hack']}")
                    st.text(f"📖 {card['sentence']}")
    
    # 只有在新学模式下才显示当堂测试
    if mode == 'learn' and st.session_state.get('current_quizzes'):
        st.divider()
        st.header("✍️ 当堂测试")
        for i, q in enumerate(st.session_state['current_quizzes']):
            st.markdown(f"**Q{i+1}: {q['question']}**")