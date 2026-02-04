import streamlit as st
import json
from openai import OpenAI

# --- 1. 页面基础配置 ---
st.set_page_config(page_title="Kimi 单词私教", page_icon="🌙", layout="wide")

st.title("🌙 Kimi 单词突击训练营")
st.markdown("输入单词，Kimi 帮你生成 **闪卡** + **真题级测试**")

# --- 2. 侧边栏配置 (输入 Key 和 单词) ---
with st.sidebar:
    st.header("⚙️ 设置")
    # 建议：实际部署时可以将 Key 放入环境变量
    api_key = st.text_input("请输入 Kimi API Key", type="password", placeholder="sk-...")
    
    st.divider()
    
    # 默认单词
    default_words = "procrastinate, mitigate, pragmatic"
    user_input = st.text_area("输入要背的单词 (逗号分隔):", value=default_words, height=150)
    
    start_btn = st.button("🚀 开始生成教材", type="primary")

# --- 3. 定义 Prompt (这是核心指令) ---
# 我们要求 Kimi 必须返回符合 JSON 语法的字符串
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
请确保返回的是纯 JSON 字符串，不要包含 Markdown 标记（如 ```json）。
"""

# --- 4. 处理逻辑 ---
if start_btn:
    if not api_key:
        st.error("请先在左侧填入 Kimi API Key！")
    elif not user_input:
        st.error("请输入单词！")
    else:
        # 显示加载动画
        with st.spinner(f"Kimi 正在大脑风暴分析 '{user_input}'..."):
            try:
                # === Kimi API 对接核心部分 ===
                client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.moonshot.cn/v1",  # 必须完全一致，不能少 /v1, # 关键：指向 Kimi 的服务器
                )

                response = client.chat.completions.create(
                    model="moonshot-v1-8k", # 使用 Kimi 模型
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"请处理这些单词: {user_input}"}
                    ],
                    temperature=0.3, # 降低随机性，保证格式稳定
                    response_format={"type": "json_object"} # 关键：强制 Kimi 输出 JSON
                )

                # 解析返回的数据
                raw_content = response.choices[0].message.content
                data = json.loads(raw_content)
                
                # 将数据存入 Session State 防止刷新丢失
                st.session_state['learning_data'] = data
                st.success("生成完毕！请查看右侧内容 👉")

            except Exception as e:
                st.error(f"发生错误: {e}")
                st.warning("如果提示 JSON 解析错误，请重试一次。")

# --- 5. 渲染 UI (如果数据存在) ---
if 'learning_data' in st.session_state:
    data = st.session_state['learning_data']
    
    # 创建两个标签页
    tab1, tab2 = st.tabs(["🗂️ 单词闪卡", "📝 实战测试"])

    # === Tab 1: 闪卡展示 ===
    with tab1:
        # 使用列布局，一行放3个卡片
        cols = st.columns(3)
        for idx, card in enumerate(data['cards']):
            # 循环使用列
            with cols[idx % 3]: 
                with st.container(border=True):
                    st.markdown(f"### {card['word']}")
                    st.caption(f"[{card['ipa']}]")
                    st.markdown(f"**{card['meaning']}**")
                    st.divider()
                    # 隐藏内容，点击展开
                    with st.expander("查看助记与例句"):
                        st.info(f"🧠 {card['memory_hack']}")
                        st.text(f"📖 {card['sentence']}")

    # === Tab 2: 测试展示 ===
    with tab2:
        st.subheader("看看你掌握了多少？")
        for i, q in enumerate(data['quizzes']):
            st.markdown(f"**Q{i+1}: {q['question']}**")
            
            # 这里的 key 很重要，保证每个题目状态独立
            user_choice = st.radio(
                "请选择:", 
                q['options'], 
                index=None, 
                key=f"quiz_{i}",
                label_visibility="collapsed"
            )


            
            
            if user_choice:
                # 获取用户选了第几个
                choice_idx = q['options'].index(user_choice)
                
                if choice_idx == q['answer_idx']:
                    st.success("✅ 回答正确！")
                    st.caption(f"解析: {q['explanation']}")
                else:
                    st.error("❌ 错误")