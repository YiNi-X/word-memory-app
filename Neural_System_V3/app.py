# app.py
import streamlit as st
import json
import time

# 导入配置和核心模块 (MVC 架构)
from config import DB_NAME
from core.database import NeuralDB
from core.ai_engine import CyberMind

# ==========================================
# 🖥️ UI SETUP & CSS
# ==========================================
st.set_page_config(page_title="NEURAL_SYSTEM_V3", page_icon="🧩", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #050505; color: #e0e0e0; font-family: 'Courier New'; }
    h1, h2, h3 { color: #00f3ff !important; text-shadow: 0 0 5px #00f3ff; }
    .status-box { border-left: 3px solid #39ff14; padding: 10px; background: #111; margin-bottom: 20px; }
    .highlight-word { color: #ff00ff; font-weight: bold; background: #220022; padding: 0 4px; border-radius: 4px; }
    div.stButton > button { border: 1px solid #39ff14; color: #39ff14; background: transparent; width: 100%; }
    div.stButton > button:hover { background: #39ff14; color: #000; box-shadow: 0 0 10px #39ff14; }
    .history-item { padding: 5px; border-bottom: 1px solid #333; cursor: pointer; font-size: 0.8em; color: #888; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🔌 INITIALIZATION (State Management)
# ==========================================

# 1. 初始化核心服务
if 'db' not in st.session_state: 
    st.session_state.db = NeuralDB(DB_NAME)
if 'ai' not in st.session_state: 
    st.session_state.ai = CyberMind()

# 2. 初始化会话状态
if 'session_id' not in st.session_state: st.session_state.session_id = None
if 'current_words' not in st.session_state: st.session_state.current_words = []

# 3. 初始化数据缓存
if 'data_article' not in st.session_state: st.session_state.data_article = None
if 'data_cards' not in st.session_state: st.session_state.data_cards = None
if 'data_quiz' not in st.session_state: st.session_state.data_quiz = None

# ==========================================
# 📂 SIDEBAR: INPUT & HISTORY
# ==========================================
with st.sidebar:
    st.title("🧩 NEURAL HUB V3.0")
    
    st.subheader("📡 新数据注入")
    user_input = st.text_area("Input Stream:", value="ephemeral, serendipity, cyberpunk", height=70)
    
    # --- 初始化按钮 ---
    if st.button("📥 初始化 (Initialize)"):
        words = [w.strip() for w in user_input.split(',') if w.strip()]
        if words:
            # 1. 写入 DB
            new_id = st.session_state.db.create_session(user_input)
            
            # 2. 更新状态
            st.session_state.session_id = new_id
            st.session_state.current_words = words
            
            # 3. 清空缓存 (准备迎接新内容)
            st.session_state.data_article = None
            st.session_state.data_cards = None
            st.session_state.data_quiz = None
            
            st.toast(f"系统初始化完成。Session ID: {new_id}", icon="✅")
            st.rerun()

    st.divider()
    
    # --- 历史记录回溯 ---
    st.subheader("⏳ 时间胶囊 (History)")
    history_list = st.session_state.db.get_history_list()
    
    for h_id, h_words, h_date in history_list:
        short_words = h_words[:20] + "..." if len(h_words) > 20 else h_words
        col_h1, col_h2 = st.columns([4, 1])
        with col_h1:
            st.caption(f"{h_date}\n**{short_words}**")
        with col_h2:
            if st.button("Load", key=f"load_{h_id}"):
                # 调用核心层的 load_session (已包含字段修复逻辑)
                full_data = st.session_state.db.load_session(h_id)
                info = full_data['info']
                
                # 恢复核心状态
                st.session_state.session_id = h_id
                st.session_state.current_words = [w.strip() for w in info['words_input'].split(',') if w.strip()]
                
                # 恢复各模块缓存
                if info['article_english']:
                    st.session_state.data_article = {
                        "article_english": info['article_english'],
                        "article_chinese": info['article_chinese']
                    }
                else:
                    st.session_state.data_article = None

                if full_data['words']:
                    st.session_state.data_cards = {"words": full_data['words']}
                else:
                    st.session_state.data_cards = None
                    
                if info['quiz_data']:
                    st.session_state.data_quiz = json.loads(info['quiz_data'])
                else:
                    st.session_state.data_quiz = None
                    
                st.toast("时间线回溯成功！数据已重载。", icon="🔄")
                st.rerun()

# ==========================================
# 🎮 MAIN INTERFACE
# ==========================================

# --- 顶部导航栏 ---
col_header, col_btn = st.columns([5, 1], vertical_alignment="bottom")

with col_header:
    st.title("⚡ NEURAL MODULAR SYSTEM")

with col_btn:
    # "再来一组" 功能
    has_context = st.session_state.data_article is not None
    if st.button("🔄 再来一组", disabled=not has_context, help="基于当前文章生成一组新的测试题"):
        with st.spinner("正在重构战场..."):
            try:
                article_context = st.session_state.data_article['article_english']
                # 调用 AI 核心
                res_quiz = st.session_state.ai.generate_quiz(st.session_state.current_words, article_context)
                
                # 更新状态与数据库
                st.session_state.data_quiz = res_quiz
                st.session_state.db.update_quiz(st.session_state.session_id, json.dumps(res_quiz))
                
                st.toast("新题目已送达！", icon="⚔️")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

# --- 如果没有 Session，停止渲染 ---
if not st.session_state.session_id:
    st.warning("👈 请先在左侧侧边栏初始化数据或加载历史记录。")
    st.stop()

# --- 状态指示条 ---
st.markdown(f"""
<div class='status-box'>
    <div>🆔 <b>SESSION:</b> {st.session_state.session_id}</div>
    <div>📡 <b>DATA:</b> {', '.join(st.session_state.current_words)}</div>
</div>
""", unsafe_allow_html=True)

# --- 主要标签页 ---
tab1, tab2, tab3 = st.tabs(["📜 SYSTEM 2: 沉浸阅读", "🧩 SYSTEM 3: 记忆矩阵", "⚔️ SYSTEM 4: 实战演练"])

# === TAB 1: 文章模块 & 自动触发器 ===
with tab1:
    # 场景 A: 未生成文章
    if not st.session_state.data_article:
        st.info("等待指令... 神经网络处于待机状态。")
        
        if st.button("🚀 启动全链路序列 (Full Sequence)", use_container_width=True):
            with st.spinner("正在接收来自虚空的故事信号... (Step 1/3: Generating Article)"):
                try:
                    # 调用 AI 生成文章
                    res_article = st.session_state.ai.generate_article(st.session_state.current_words)
                    st.session_state.data_article = res_article
                    # 存入数据库
                    st.session_state.db.update_article(
                        st.session_state.session_id, 
                        res_article['article_english'], 
                        res_article['article_chinese']
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Article Generation Failed: {e}")

    # 场景 B: 已有文章 -> 显示文章并检查后续任务
    else:
        # 1. 渲染文章
        data = st.session_state.data_article
        c1, c2 = st.columns(2)
        with c1: 
            st.markdown("### English Stream")
            st.markdown(f"{data['article_english']}", unsafe_allow_html=True)
        with c2: 
            st.markdown("### 中文解析")
            st.markdown(f"<div style='color:#aaa'>{data['article_chinese']}</div>", unsafe_allow_html=True)

        st.divider()

        # 2. 自动触发链 (Auto-Trigger Chain)
        # 检查是否还有缺失的模块 (单词卡 或 题目)
        if not st.session_state.data_cards or not st.session_state.data_quiz:
            with st.status("🤖 正在后台进行全系统神经重构...", expanded=False) as status:
                
                # Sub-Task 1: 单词分析
                if not st.session_state.data_cards:
                    st.write("Step 1: 正在提取记忆碎片 (Memory Analysis)...")
                    try:
                        res_words = st.session_state.ai.analyze_words(st.session_state.current_words)
                        st.session_state.data_cards = res_words
                        st.session_state.db.save_words(st.session_state.session_id, res_words['words'])
                        st.write("✅ 记忆碎片提取完成")
                    except Exception as e:
                        st.error(f"Memory Analysis Failed: {e}")

                # Sub-Task 2: 题目生成
                if not st.session_state.data_quiz:
                    st.write("Step 2: 正在构建实战模拟 (Quiz Generation)...")
                    try:
                        article_context = st.session_state.data_article['article_english']
                        res_quiz = st.session_state.ai.generate_quiz(st.session_state.current_words, article_context)
                        st.session_state.data_quiz = res_quiz
                        st.session_state.db.update_quiz(st.session_state.session_id, json.dumps(res_quiz))
                        st.write("✅ 战场生成完毕")
                    except Exception as e:
                        st.error(f"Quiz Generation Failed: {e}")

                status.update(label="✅ 所有模块加载完毕 (Tabs Ready)", state="complete", expanded=False)

# === TAB 2: 单词模块 ===
with tab2:
    if not st.session_state.data_cards:
        st.info("⏳ 记忆解析正在后台运行中...")
    else:
        words = st.session_state.data_cards['words']
        cols = st.columns(3)
        for idx, w in enumerate(words):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"### {w['word']}")
                    st.caption(w['meaning'])
                    st.markdown(f"**Root:** `{w['root']}`")
                    st.markdown(f"_{w['imagery']}_")

# === TAB 3: 测验模块 ===
with tab3:
    if not st.session_state.data_quiz:
        st.info("⏳ 战场数据正在生成中...")
    else:
        st.caption("🎯 点击右上角 [再来一组] 可刷新题目")
        for i, q in enumerate(st.session_state.data_quiz['quizzes']):
            st.markdown(f"#### Q{i+1}: {q['question']}")
            
            # 使用内存地址生成简单且唯一的 Key，防止 Key 重复报错
            unique_key = f"quiz_{id(st.session_state.data_quiz)}_{i}"
            
            choice = st.radio("Select Option:", q['options'], key=unique_key, index=None)
            
            if choice:
                if choice == q['answer']:
                    st.success(f"✅ Correct! {q['explanation']}")
                else:
                    st.error(f"❌ Incorrect. Answer: {q['answer']}")
                    st.info(f"解析: {q['explanation']}")
            st.divider()