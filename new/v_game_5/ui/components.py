# ==========================================
# 🔊 UI 组件 - v5.3 修复版
# ==========================================
import sys
from pathlib import Path

_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

import streamlit as st
import streamlit.components.v1 as components
from models import WordTier, CardType, WordCard


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
    """顶部状态栏 - 圣遗物显示修复"""
    player = st.session_state.player
    game_map = st.session_state.game_map
    
    col_relics, col_stats = st.columns([1, 3])
    
    # 左侧：圣遗物面板
    with col_relics:
        render_relic_panel(player.relics)
    
    # 右侧：状态栏
    with col_stats:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            
            with c1:
                hp_ratio = player.hp / player.max_hp
                st.progress(hp_ratio, f"❤️ {player.hp}/{player.max_hp}")
            
            with c2:
                if player.block > 0:
                    st.write(f"🛡️ {player.block}")
                else:
                    st.write(f"🗺️ F{game_map.floor}")
            
            with c3:
                st.write(f"💰 {player.gold}G")
            
            with c4:
                st.write(f"📦 {len(player.inventory)}")


def render_relic_panel(relics: list):
    """
    左上角圣遗物面板 - 修复版
    分条显示所有圣遗物效果
    """
    from registries import RelicRegistry
    
    with st.container(border=True):
        st.markdown("**🏆 圣遗物**")
        
        if not relics:
            st.caption("暂无圣遗物")
        else:
            for relic_id in relics:
                relic = RelicRegistry.get(relic_id)
                if relic:
                    # 每个圣遗物显示为一行
                    st.markdown(f"""
                    <div class="relic-item">
                        {relic.icon} <b>{relic.name}</b><br/>
                        <small style="color: #888;">{relic.description}</small>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # 未知圣遗物也显示
                    st.markdown(f"❓ {relic_id}")


def render_word_card(card: WordCard, idx: int, onclick_key: str = None, 
                     show_word: bool = True, show_meaning: bool = True):
    """
    渲染单词卡牌
    
    Args:
        card: 单词卡牌
        idx: 索引
        onclick_key: 点击按钮的 key
        show_word: 是否显示单词 (装填阶段隐藏)
        show_meaning: 是否显示释义
    """
    card_type = card.card_type
    border_color = card_type.color
    
    with st.container(border=True):
        # 顶部：类型标识
        st.markdown(f"""
        <div style="background: {border_color}; color: white; padding: 4px 8px; 
                    border-radius: 4px; font-size: 0.8em; text-align: center;">
            {card_type.icon} {card_type.name_cn}
        </div>
        """, unsafe_allow_html=True)
        
        # 卡面内容
        if show_word:
            st.markdown(f"### {card.word}")
        else:
            # 隐藏单词，只显示颜色
            st.markdown(f"### ???")
        
        if show_meaning and show_word:
            st.caption(card.meaning)
        else:
            st.caption("???")
        
        # 效果提示
        if card_type == CardType.ATTACK:
            st.markdown(f"⚔️ **{card.damage}** 伤害")
        elif card_type == CardType.DEFENSE:
            st.markdown(f"🛡️ **{card.block}** 护甲")
        else:
            st.markdown("✨ **抽 2 牌**")
        
        if onclick_key:
            return st.button("选择", key=onclick_key, use_container_width=True)
    
    return False


def render_card_slot(idx: int, card: WordCard = None, on_remove: bool = False):
    """渲染弹槽 - 只显示颜色，不显示单词"""
    with st.container(border=True):
        if card:
            st.markdown(f"""
            <div style="background: {card.card_type.color}; color: white; 
                        padding: 4px 8px; border-radius: 4px; font-size: 0.9em; text-align: center;">
                {card.card_type.icon} {card.card_type.name_cn}
            </div>
            """, unsafe_allow_html=True)
            # 不显示单词！
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
    """
    渲染手牌 - 战斗阶段只显示颜色
    """
    if not hand:
        st.info("手牌已用完！")
        return None
    
    st.markdown("### 🎴 手牌")
    
    cols = st.columns(len(hand))
    clicked = None
    
    for i, card in enumerate(hand):
        with cols[i]:
            # 战斗阶段不显示单词
            if on_play:
                if render_word_card(card, i, onclick_key=f"play_{i}", 
                                   show_word=False, show_meaning=False):
                    clicked = i
            else:
                render_word_card(card, i, show_word=True, show_meaning=True)
    
    return clicked


def render_learning_popup(card: WordCard):
    """学习弹窗 - 红卡强制学习"""
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
    """出牌测试 - 显示中文选英文"""
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
