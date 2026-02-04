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


def play_audio(text: str):
    """TTS 发音引擎"""
    js_code = f"""
        <script>
            window.speechSynthesis.cancel(); 
            var msg = new SpeechSynthesisUtterance("{text}");
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
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        
        with c1:
            hp_ratio = player.hp / player.max_hp
            st.progress(hp_ratio, f"HP: {player.hp}/{player.max_hp}")
        
        with c2:
            st.write(f"🗺️ Floor: {game_map.floor}/{game_map.total_floors}")
        
        with c3:
            st.write(f"💰 {player.gold}G")
        
        with c4:
            item_count = len(player.inventory)
            relic_count = len(player.relics)
            st.write(f"📦 {item_count} 🏆 {relic_count}")


def render_word_card(word: dict, idx: int, show_meaning: bool = False):
    """渲染单词卡片"""
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # 显示是新词还是复习词
            tag = "🔄" if word.get('is_review') else "✨"
            st.markdown(f"## {tag} {word['word']}")
        
        with col2:
            if st.button("🔊", key=f"tts_{idx}"):
                play_audio(word['word'])
        
        if show_meaning:
            st.divider()
            st.markdown(f"**释义:** {word['meaning']}")


def render_progress_bar(current: int, total: int, label: str = "Progress"):
    """进度条"""
    ratio = current / max(total, 1)
    st.progress(ratio, f"{label}: {current}/{total}")
