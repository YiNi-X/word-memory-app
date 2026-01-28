import streamlit as st
import json
import sqlite3
from datetime import datetime
from openai import OpenAI

# ==========================================
# 1. 配置区域 (直接在这里填入你的 Key)
# ==========================================

KIMI_API_KEY = "sk-tqxUlkDlyX2N2Ka2fJzjv0aDKr5B8hJGVDhFD9N56vGBjlZf" # <--- 在这里替换你的真实 Key
BASE_URL = "https://api.moonshot.cn/v1"

# ==========================================
# 2. 数据库逻辑 (SQLite)
# ==========================================
def init_db():
    """初始化数据库，如果不存在则创建"""
    conn = sqlite3.connect('vocab_history.db')
    c = conn.cursor()
    # 创建一个表：包含 id, 单词内容, 查询时间
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  words TEXT, 
                  query_time TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(words):
    """保存用户输入的单词到数据库"""
    conn = sqlite3.connect('vocab_history.db')
    c = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO history (words, query_time) VALUES (?, ?)", (words, current_time))
    conn.commit()
    conn.close()

def get_history():
    """读取最近的10条历史记录"""
    conn = sqlite3.connect('vocab_history.db')
    c = conn.cursor()
    c.execute("SELECT words, query_time FROM history ORDER BY id DESC LIMIT 10")
    data = c.fetchall()
    conn.close()
    return data

# 初始化数据库 (每次运行都会检查一次)
init_db()

# ==========================================
# 3. 页面与逻辑
# ==========================================
st.set_page_config(page_title="Kimi 单词私教 (Dev)", page_icon="🌙", layout="wide")
st.title("🌙 Kimi 单词突击训练营 (开发版)")

# --- 侧边栏 ---
with st.sidebar:
    st.header("📝 输入区域")
    
    # 默认单词
    default_words = "procrastinate, mitigate, pragmatic"
    user_input = st.text_area("输入单词 (逗号分隔):", value=default_words, height=150)
    
    start_btn = st.button("🚀 开始生成教材", type="primary")

    st.divider()
    
    # --- 显示数据库历史 ---
    st.subheader("📜 历史记录 (Database)")
    history_data = get_history()
    if history_data:
        for words, time_str in history_data:
            with st.expander(f"{time_str[5:-3]} - {words[:10]}..."):
                st.caption(f"时间: {time_str}")
                st.text(words)
    else:
        st.caption("暂无记录")

# --- 提示词 ---
SYSTEM_PROMPT = """
你是一个专业的英语词汇老师。请根据用户提供的单词列表，生成一个严格的 JSON 数据用于前端渲染。
JSON 结构必须严格包含以下字段：
{
    "cards": [
        {
            "word": "单词拼写",
            "ipa": "音标",
            "meaning": "精简的中文释义",
            "memory_hack": "一个具体的、好记的助记法或谐音梗",
            "sentence": "一个包含该单词的英文例句"
        }
    ],
    "quizzes": [
        {
            "question": "一道关于这些单词的选择题描述",
            "options": ["选项A", "选项B", "选项C", "选项D"],
            "answer_idx": 0, // 正确选项的索引 (0-3)
            "explanation": "中文解析，为什么选这个"
        }
    ]
}
请确保返回的是纯 JSON 字符串，不要包含 Markdown 标记。
"""

# --- 主逻辑 ---
if start_btn:
    if not user_input:
        st.error("请输入单词！")
    else:
        # 1. 先存入数据库
        save_to_db(user_input)
        
        # 2. 调用 AI
        with st.spinner(f"Kimi 正在生成教材..."):
            try:
                client = OpenAI(
                    api_key=KIMI_API_KEY, # 使用顶部定义的常量
                    base_url=BASE_URL,
                )

                response = client.chat.completions.create(
                    model="moonshot-v1-8k",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"请处理这些单词: {user_input}"}
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )

                raw_content = response.choices[0].message.content
                data = json.loads(raw_content)
                st.session_state['learning_data'] = data
                st.rerun() # 重新运行以刷新侧边栏的历史记录

            except Exception as e:
                st.error(f"发生错误: {e}")

# --- 渲染结果 ---
if 'learning_data' in st.session_state:
    data = st.session_state['learning_data']
    
    tab1, tab2 = st.tabs(["🗂️ 单词闪卡", "📝 实战测试"])

    with tab1:
        cols = st.columns(3)
        for idx, card in enumerate(data['cards']):
            with cols[idx % 3]: 
                with st.container(border=True):
                    st.markdown(f"### {card['word']}")
                    st.caption(f"[{card['ipa']}]")
                    st.markdown(f"**{card['meaning']}**")
                    st.divider()
                    with st.expander("查看助记与例句"):
                        st.info(f"🧠 {card['memory_hack']}")
                        st.text(f"📖 {card['sentence']}")

    with tab2:
        for i, q in enumerate(data['quizzes']):
            st.markdown(f"**Q{i+1}: {q['question']}**")
            user_choice = st.radio("请选择:", q['options'], index=None, key=f"quiz_{i}", label_visibility="collapsed")
            if user_choice:
                choice_idx = q['options'].index(user_choice)
                if choice_idx == q['answer_idx']:
                    st.success("✅ 回答正确！")
                    st.caption(f"解析: {q['explanation']}")
                else:
                    st.error("❌ 错误")