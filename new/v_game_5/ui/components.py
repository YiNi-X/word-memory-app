# ==========================================
# 🔊 UI 组件 - v5.4
# ==========================================
import sys
from pathlib import Path

_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

import streamlit as st
import streamlit.components.v1 as components
from models import WordTier, CardType, WordCard, CARD_STATS


def play_audio(text: str):
    """TTS 发音引擎"""
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
    
    col_relics, col_stats, col_deck = st.columns([1, 2, 1])
    
    with col_relics:
        render_relic_panel(player.relics)
    
    with col_stats:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            
            with c1:
                hp_ratio = player.hp / player.max_hp
                st.progress(hp_ratio, f"❤️ {player.hp}/{player.max_hp}")
            
            with c2:
                if player.armor > 0:
                    st.write(f"🛡️ {player.armor}")
                else:
                    st.write(f"🗺️ F{game_map.floor}")
            
            with c3:
                st.write(f"💰 {player.gold}G")
            
            with c4:
                st.write(f"🎴 {len(player.deck)}")
    
    # 右侧：卡组查看按钮
    with col_deck:
        render_deck_viewer(player.deck)


def render_relic_panel(relics: list):
    """圣遗物面板"""
    from registries import RelicRegistry
    
    with st.container(border=True):
        st.markdown("**🏆 圣遗物**")
        
        if not relics:
            st.caption("暂无")
        else:
            for relic_id in relics:
                relic = RelicRegistry.get(relic_id)
                if relic:
                    st.markdown(f"{relic.icon} **{relic.name}**")
                else:
                    st.markdown(f"❓ {relic_id}")


def render_deck_viewer(deck: list):
    """右下角卡组查看器"""
    with st.container(border=True):
        st.markdown("**🎴 卡组**")
        
        if not deck:
            st.caption("空")
            return
        
        # 统计各类型卡牌
        red_count = sum(1 for c in deck if c.card_type == CardType.RED_BERSERK)
        blue_count = sum(1 for c in deck if c.card_type == CardType.BLUE_HYBRID)
        gold_count = sum(1 for c in deck if c.card_type == CardType.GOLD_SUPPORT)
        
        st.caption(f"🟥{red_count} 🟦{blue_count} 🟨{gold_count}")
        
        with st.expander("📖 查看卡组"):
            for card in deck:
                color = card.card_type.color
                st.markdown(f"""
                <div style="border-left: 3px solid {color}; padding-left: 8px; margin: 4px 0;">
                    <b>{card.word}</b> - {card.meaning}
                </div>
                """, unsafe_allow_html=True)


def render_word_card(card: WordCard, idx: int, onclick_key: str = None, 
                     show_word: bool = True, show_meaning: bool = True):
    """渲染单词卡牌 - v5.4"""
    card_type = card.card_type
    border_color = card_type.color
    
    with st.container(border=True):
        st.markdown(f"""
        <div style="background: {border_color}; color: white; padding: 4px 8px; 
                    border-radius: 4px; font-size: 0.8em; text-align: center;">
            {card_type.icon} {card_type.name_cn}
        </div>
        """, unsafe_allow_html=True)
        
        if show_word:
            st.markdown(f"### {card.word}")
        else:
            st.markdown(f"### ???")
        
        if show_meaning and show_word:
            st.caption(card.meaning)
        else:
            st.caption("???")
        
        # 效果提示 - 使用新的 CardType 枚举
        if card_type == CardType.RED_BERSERK:
            st.markdown(f"⚔️ **{card.damage}** | 💥 **-{card.penalty}**")
        elif card_type == CardType.BLUE_HYBRID:
            st.markdown(f"⚔️ **{card.damage}** | 🛡️ **{card.block}**")
        elif card_type == CardType.GOLD_SUPPORT:
            st.markdown(f"⚔️ **{card.damage}** | ⚡ **x2**")
        
        if onclick_key:
            return st.button("选择", key=onclick_key, use_container_width=True)
    
    return False


def render_card_slot(idx: int, card: WordCard = None, on_remove: bool = False):
    """渲染弹槽"""
    with st.container(border=True):
        if card:
            st.markdown(f"""
            <div style="background: {card.card_type.color}; color: white; 
                        padding: 4px 8px; border-radius: 4px; font-size: 0.9em; text-align: center;">
                {card.card_type.icon} {card.card_type.name_cn}
            </div>
            """, unsafe_allow_html=True)
            st.markdown("**[ 已装填 ]**")
            
            if on_remove:
                return st.button("❌", key=f"remove_slot_{idx}", use_container_width=True)
        else:
            st.markdown("### 🔲")
            st.caption(f"槽位 {idx + 1}")
    
    return False


def render_enemy(enemy, show_intent: bool = True):
    """渲染敌人"""
    with st.container(border=True):
        st.markdown(f"## 👹 {enemy.name}")
        
        hp_ratio = enemy.hp / enemy.max_hp
        st.progress(hp_ratio, f"HP: {enemy.hp}/{enemy.max_hp}")
        
        if show_intent:
            if enemy.current_timer == 1:
                st.error(f"⚠️ **即将攻击！** ({enemy.attack} 伤害)")
            elif enemy.current_timer == 2:
                st.warning(f"🔥 蓄力中... ({enemy.current_timer} 回合后攻击)")
            else:
                st.info(f"😴 准备中... ({enemy.current_timer} 回合后攻击)")


def render_hand(hand: list, on_play: bool = False):
    """渲染手牌"""
    if not hand:
        st.info("手牌已用完！")
        return None
    
    st.markdown("### 🎴 手牌")
    
    cols = st.columns(len(hand))
    clicked = None
    
    for i, card in enumerate(hand):
        with cols[i]:
            if on_play:
                if render_word_card(card, i, onclick_key=f"play_{i}", 
                                   show_word=False, show_meaning=False):
                    clicked = i
            else:
                render_word_card(card, i, show_word=True, show_meaning=True)
    
    return clicked


def render_learning_popup(card: WordCard):
    """学习弹窗"""
    with st.container(border=True):
        st.markdown("### 📖 学习新词")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown(f"## 🟥 {card.word}")
            if st.button("🔊 听发音", key="learn_tts"):
                play_audio(card.word)
        
        with col2:
            st.info(f"**释义:** {card.meaning}")
        
        st.divider()
        
        return st.button("✨ 注入魔力（确认已学习）", type="primary", use_container_width=True)


def render_quiz_test(card: WordCard, options: list):
    """出牌测试"""
    st.markdown("### ⚡ 记忆提取！")
    st.markdown(f"**{card.meaning}** 是哪个单词？")
    
    choice = st.radio(
        "选择正确的单词:",
        options,
        key=f"quiz_{card.word}",
        label_visibility="collapsed"
    )
    
    if st.button("🗡️ 释放！", type="primary", use_container_width=True):
        return choice
    
    return None
