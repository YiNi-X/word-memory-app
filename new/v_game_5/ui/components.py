# -*- coding: utf-8 -*-
import sys
from pathlib import Path

_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

import streamlit as st
import streamlit.components.v1 as components
from models import WordTier, CardType, WordCard, CARD_STATS, CombatPhase


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

    col_stats, col_deck = st.columns([2, 1])

    cs = st.session_state.get('card_combat')
    in_combat = bool(cs) and getattr(cs, 'phase', None) == CombatPhase.BATTLE
    with st.sidebar:
        render_backpack_panel(player.relics, player.inventory, in_combat, cs)

    with col_stats:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])

            with c1:
                hp_ratio = player.hp / player.max_hp
                st.progress(hp_ratio, f"❤️ 生命 {player.hp}/{player.max_hp}")

            with c2:
                if player.armor > 0:
                    st.write(f"🛡️ 护甲 {player.armor}")
                else:
                    st.write(f"🗺️ 第{game_map.floor}层")

            with c3:
                st.write(f"🪙 金币 {player.gold}")

            with c4:
                st.write(f"🃏 卡牌 {len(player.deck)}")

    with col_deck:
        render_deck_viewer(player.deck)


def render_backpack_panel(relics: list, inventory: list, in_combat: bool, combat_state=None):
    """背包面板：圣遗物 + 道具"""
    from collections import Counter
    from registries import RelicRegistry, ShopRegistry

    with st.container(border=True):
        st.markdown("**背包**")

        st.markdown("**圣遗物**")
        if not relics:
            st.caption("暂无")
        else:
            for relic_id in relics:
                relic = RelicRegistry.get(relic_id)
                if relic:
                    with st.expander(f"{relic.icon} {relic.name}"):
                        st.caption(relic.description)
                else:
                    st.caption(f"未知圣遗物: {relic_id}")

        st.divider()
        st.markdown("**道具**")
        if not inventory:
            st.caption("暂无")
        else:
            counts = Counter(inventory)
            for item_id, count in counts.items():
                item = ShopRegistry.get(item_id)
                if not item:
                    st.caption(f"未知道具: {item_id}")
                    continue
                label = f"{item.icon} {item.name} x{count}"
                with st.expander(label):
                    st.caption(item.description)
                    supported = {"heal", "shield", "damage_reduce", "hint", "max_hp"}
                    in_answer_phase = bool(in_combat and combat_state and getattr(combat_state, "current_card", None))
                    if in_combat:
                        can_use = item.consumable and item.effect in supported and not in_answer_phase
                    else:
                        can_use = item.consumable and item.effect in {"heal", "max_hp"}
                    if st.button("使用", key=f"use_item_{item_id}", disabled=not can_use):
                        inv = st.session_state.player.inventory
                        if item_id in inv:
                            inv.remove(item_id)
                        if item.effect == "heal":
                            st.session_state.player.change_hp(item.value)
                        elif item.effect == "shield":
                            st.session_state._item_shield = True
                        elif item.effect == "damage_reduce":
                            current = st.session_state.get("_item_damage_reduce", 0)
                            value = item.value if item.value else 5
                            st.session_state._item_damage_reduce = max(current, value)
                        elif item.effect == "hint":
                            st.session_state._item_hint = st.session_state.get("_item_hint", 0) + 1
                        elif item.effect == "max_hp":
                            st.session_state.player.max_hp += item.value
                            st.session_state.player.hp = min(
                                st.session_state.player.hp + item.value, st.session_state.player.max_hp
                            )
                        if in_combat:
                            st.session_state._end_turn_due_to_item = True
                        st.rerun()


def render_relic_panel(relics: list):
    """圣遗物面板"""
    from registries import RelicRegistry

    with st.container(border=True):
        st.markdown("**🏵️ 圣遗物**")

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
    """右侧卡组查看"""
    with st.container(border=True):
        st.markdown("**🃏 卡组**")

        if not deck:
            st.caption("空")
            return

        red_count = sum(1 for c in deck if c.card_type == CardType.RED_BERSERK)
        blue_count = sum(1 for c in deck if c.card_type == CardType.BLUE_HYBRID)
        gold_count = sum(1 for c in deck if c.card_type == CardType.GOLD_SUPPORT)

        st.caption(f"🟥{red_count} 🟦{blue_count} 🟨{gold_count}")

        with st.expander("📖 查看卡组"):
            for card in deck:
                color = card.card_type.color
                st.markdown(
                    f"""
                <div style="border-left: 3px solid {color}; padding-left: 8px; margin: 4px 0;">
                    <b>{card.word}</b> - {card.meaning}
                </div>
                """,
                    unsafe_allow_html=True,
                )


def render_word_card(card: WordCard, idx: int, onclick_key: str = None,
                     show_word: bool = True, show_meaning: bool = True):
    """渲染单词卡牌"""
    card_type = card.card_type
    border_color = card_type.color

    with st.container(border=True):
        st.markdown(
            f"""
        <div style="background: {border_color}; color: white; padding: 4px 8px;
                    border-radius: 4px; font-size: 0.8em; text-align: center;">
            {card_type.icon} {card_type.name_cn}
        </div>
        """,
            unsafe_allow_html=True,
        )

        if show_word:
            st.markdown(f"### {card.word}")
        else:
            st.markdown("### ？？？")

        if show_meaning and show_word:
            st.caption(card.meaning)
        else:
            st.caption("（释义已隐藏）")

        if card_type == CardType.RED_BERSERK:
            st.markdown(f"⚔️ **{card.damage}** | 💥 **-{card.penalty}**")
        elif card_type == CardType.BLUE_HYBRID:
            st.markdown(f"⚔️ **{card.damage}** | 🛡️ **{card.block}**")
        elif card_type == CardType.GOLD_SUPPORT:
            st.markdown(f"⭐ **{card.damage}** | ✨ **随机效果**")
            if hasattr(card, 'gold_uses_remaining'):
                st.caption(f"耐久: {card.gold_uses_remaining}")

        if onclick_key:
            return st.button("选择", key=onclick_key, use_container_width=True)

    return False


def render_card_slot(idx: int, card: WordCard = None, on_remove: bool = False):
    """渲染卡槽"""
    with st.container(border=True):
        if card:
            st.markdown(
                f"""
            <div style="background: {card.card_type.color}; color: white;
                        padding: 4px 8px; border-radius: 4px; font-size: 0.9em; text-align: center;">
                {card.card_type.icon} {card.card_type.name_cn}
            </div>
            """,
                unsafe_allow_html=True,
            )
            st.markdown("**[ 已装填 ]**")

            if on_remove:
                return st.button("移除", key=f"remove_slot_{idx}", use_container_width=True)
        else:
            st.markdown("### 🧩")
            st.caption(f"槽位 {idx + 1}")

    return False


def render_enemy(enemy, show_intent: bool = True):
    """渲染敌人"""
    with st.container(border=True):
        st.markdown(f"## 👹 {enemy.name}")

        hp_ratio = enemy.hp / enemy.max_hp
        st.progress(hp_ratio, f"生命: {enemy.hp}/{enemy.max_hp}")

        if show_intent:
            if enemy.current_timer == 1:
                st.error(f"⚔️ **即将攻击**（{enemy.attack} 伤害）")
            elif enemy.current_timer == 2:
                st.warning(f"🔥 蓄力中...（{enemy.current_timer} 回合后攻击）")
            else:
                st.info(f"⏳ 准备中...（{enemy.current_timer} 回合后攻击）")


def render_hand(hand: list, on_play: bool = False):
    """渲染手牌"""
    if not hand:
        st.info("手牌已用完！")
        return None

    st.markdown("### 🃏 手牌")

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

        return st.button("✅ 注入魔力（确认已学习）", type="primary", use_container_width=True)


def render_quiz_test(card: WordCard, options: list):
    """出牌测试"""
    st.markdown("### 🧠 记忆提取")
    st.markdown(f"**{card.meaning}** 是哪个单词？")

    choice = st.radio(
        "选择正确的单词",
        options,
        key=f"quiz_{card.word}",
        label_visibility="collapsed",
    )

    if st.button("✅ 提交", type="primary", use_container_width=True):
        return choice

    return None
