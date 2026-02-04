# ==========================================
# 🔊 可复用 UI 组件
# ==========================================
import sys
from pathlib import Path

# 添加父目录到路径
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

import streamlit as st
import streamlit.components.v1 as components
from models import WordTier


def play_audio(text: str):
    """TTS 发音引擎"""
    # 转义特殊字符
    safe_text = text.replace("'", "\\'").replace('"', '\\"')
    js_code = f"""
        <script>
            window.speechSynthesis.cancel(); 
            var msg = new SpeechSynthesisUtterance("{safe_text}");
            msg.lang = 'en-US';
            msg.rate = 0.9;
            window.speechSynthesis.speak(msg);
        </script>
    """
    components.html(js_code, height=0, width=0)


def render_hud():
    """顶部状态栏"""
    player = st.session_state.player
    game_map = st.session_state.game_map
    
    with st.container(border=True):
        # 第一行：HP, Floor, Gold
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        
        with c1:
            hp_ratio = player.hp / player.max_hp
            st.progress(hp_ratio, f"HP: {player.hp}/{player.max_hp}")
        
        with c2:
            st.write(f"🗺️ F{game_map.floor}/{game_map.total_floors}")
        
        with c3:
            st.write(f"💰 {player.gold}G")
        
        with c4:
            st.write(f"📦 {len(player.inventory)}")
        
        # 第二行：圣遗物显示
        if player.relics:
            render_relics_row(player.relics)


def render_relics_row(relics: list):
    """渲染圣遗物行（带 Tooltip）"""
    from registries import RelicRegistry
    
    # 使用 HTML 渲染带 tooltip 的圣遗物图标
    relic_html = '<div style="display: flex; gap: 8px; margin-top: 4px;">'
    
    for relic_id in relics:
        relic = RelicRegistry.get(relic_id)
        if relic:
            # 创建带 tooltip 的圣遗物图标
            relic_html += f'''
            <div class="relic-icon" title="{relic.name}: {relic.description}">
                <span style="font-size: 1.5em; cursor: help;">{relic.icon}</span>
            </div>
            '''
    
    relic_html += '</div>'
    
    st.markdown(relic_html, unsafe_allow_html=True)


def render_word_card_learning(word: dict, idx: int):
    """
    渲染学习阶段的单词卡片
    用于 Flashcard 模式：展示单词+释义+发音
    """
    tier = word.get('tier', 0)
    tier_enum = WordTier(tier) if isinstance(tier, int) else tier
    
    with st.container(border=True):
        # 标题行
        col1, col2 = st.columns([3, 1])
        with col1:
            tag = "🔄 复习词" if word.get('is_review') else "✨ 新词"
            tier_badge = f'<span style="color: {tier_enum.color}; font-size: 0.8em;">Lv{tier_enum.value} {tier_enum.display_name}</span>'
            st.markdown(f"{tag} {tier_badge}", unsafe_allow_html=True)
        
        # 单词
        st.markdown(f"# 📖 {word['word']}")
        
        # 发音按钮
        if st.button("🔊 听发音", key=f"tts_learn_{idx}"):
            play_audio(word['word'])
        
        st.divider()
        
        # 释义展示
        st.markdown(f"### 📝 释义")
        st.info(f"**{word['meaning']}**")
        
        # 可以添加例句（如果有的话）
        if word.get('example'):
            st.markdown(f"**例句:** {word['example']}")


def render_word_card_testing(word: dict, idx: int, show_meaning: bool = False):
    """
    渲染考核阶段的单词卡片
    """
    tier = word.get('tier', 0)
    tier_enum = WordTier(tier) if isinstance(tier, int) else tier
    
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            tag = "🔄" if word.get('is_review') else "✨"
            st.markdown(f"## 👻 {tag} 怪物")
            st.caption(f"Lv{tier_enum.value} {tier_enum.display_name}")
        
        with col2:
            if st.button("🔊", key=f"tts_test_{idx}"):
                play_audio(word['word'])
        
        st.markdown(f"# {word['word']}")
        
        if show_meaning:
            st.divider()
            st.markdown(f"**释义:** {word['meaning']}")


def render_tier_badge(tier: WordTier):
    """渲染熟练度徽章"""
    return f'<span style="background: {tier.color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Lv{tier.value} {tier.display_name}</span>'


def render_progress_bar(current: int, total: int, label: str = "Progress"):
    """进度条"""
    ratio = current / max(total, 1)
    st.progress(ratio, f"{label}: {current}/{total}")
