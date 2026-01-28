import streamlit as st
import json
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List

# 1. 配置界面
st.set_page_config(page_title="AI 单词私教", layout="centered")
st.title("📚 智能单词卡 & 测试生成器")

# 初始化 OpenAI (这里需要配置你的 key)
# client = OpenAI(api_key="sk-...") 

# 2. 定义数据结构 (这是解决不稳定的核心！)
# 使用 Pydantic 定义我们强制模型返回的格式，这一步锁死了模型的输出结构。
class Flashcard(BaseModel):
    word: str
    pronunciation: str
    meaning: str
    mnemonic: str = Field(description="一个好记的助记法或谐音梗")
    example_en: str
    example_cn: str

class Quiz(BaseModel):
    question: str
    options: List[str] = Field(description="4个选项列表")
    correct_option_index: int = Field(description="正确选项的索引(0-3)")
    explanation: str

class LearningMaterial(BaseModel):
    cards: List[Flashcard]
    quizzes: List[Quiz]

# 3. 侧边栏输入
with st.sidebar:
    user_words = st.text_area("输入单词 (逗号分隔)", "ephemeral, serendipity, ambiguous")
    generate_btn = st.button("生成学习内容")

# 4. 核心逻辑
if generate_btn and user_words:
    with st.spinner('AI 正在编写教材...'):
        try:
            # 伪代码：这里调用 OpenAI 的 Structured Outputs 功能
            # 实际调用时，请确保使用支持 response_format 的模型 (如 gpt-4o 或 gpt-3.5-turbo-0125)
            
            # --- 模拟 AI 返回的 JSON 数据 (为了演示无需 Key 即可运行) ---
            # 真实场景中，你会把 json_schema 传给 API
            mock_response = """
            {
                "cards": [
                    {
                        "word": "Ephemeral",
                        "pronunciation": "/əˈfem(ə)rəl/",
                        "meaning": "短暂的，朝生暮死的",
                        "mnemonic": "记忆钩子：e-phe-mer-al -> '一飞没了' -> 转瞬即逝",
                        "example_en": "Fashions are ephemeral, changing with every season.",
                        "example_cn": "时尚是短暂的，每一季都在变。"
                    }
                ],
                "quizzes": [
                    {
                        "question": "Which scenario best describes something 'ephemeral'?",
                        "options": [
                            "A mountain standing for milions of years.",
                            "A cherry blossom falling in the wind.",
                            "A heavy gold bar.",
                            "A long-lasting friendship."
                        ],
                        "correct_option_index": 1,
                        "explanation": "Ephemeral means lasting for a very short time."
                    }
                ]
            }
            """
            # ----------------------------------------------------------
            
            # 将 JSON 转换为 Python 对象
            data = json.loads(mock_response)
            st.session_state['material'] = data # 存入 Session 保持状态
            
        except Exception as e:
            st.error(f"生成失败: {e}")

# 5. 渲染区域 (完全由代码控制 UI)
if 'material' in st.session_state:
    data = st.session_state['material']
    
    # --- Tab 1: 单词卡片 ---
    tab1, tab2 = st.tabs(["📖 闪卡学习", "✍️ 随堂测试"])
    
    with tab1:
        for card in data['cards']:
            # 使用 Streamlit 的 container 和 expander 模拟卡片翻转效果
            with st.container(border=True):
                st.subheader(card['word'])
                st.text(f"音标: {card['pronunciation']}")
                
                # "点击查看背面" 的效果
                with st.expander("查看释义与助记"):
                    st.markdown(f"**含义:** {card['meaning']}")
                    st.info(f"💡 {card['mnemonic']}")
                    st.markdown(f"*{card['example_en']}*")
                    st.caption(card['example_cn'])

    # --- Tab 2: 交互式测试 ---
    with tab2:
        for idx, quiz in enumerate(data['quizzes']):
            st.write(f"**Q{idx+1}: {quiz['question']}**")
            
            # 渲染单选框
            user_choice = st.radio(f"选择题 {idx}", quiz['options'], index=None, key=f"q{idx}")
            
            if user_choice:
                # 自动判断正误
                chosen_index = quiz['options'].index(user_choice)
                if chosen_index == quiz['correct_option_index']:
                    st.success("✅ 回答正确！")
                else:
                    st.error("❌ 再想一下...")
                    with st.expander("查看解析"):
                        st.write(quiz['explanation'])
            st.divider()