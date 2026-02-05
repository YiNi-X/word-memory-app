# ==========================================
# 🖥️ 页面渲染器 - v5.3 修复版
# ==========================================
import sys
from pathlib import Path

_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

import streamlit as st
import random
import time
from typing import Callable

from models import (
    GamePhase, NodeType, Player, BossState, 
    CardType, WordCard, Enemy, CombatPhase, CardCombatState
)
from config import (
    HAND_SIZE, MIN_ATTACK_CARDS, ATTACK_DAMAGE, ATTACK_BACKFIRE,
    DEFENSE_BLOCK, UTILITY_DRAW, ENEMY_HP_BASE, ENEMY_ATTACK, ENEMY_ACTION_TIMER
)
from registries import EventRegistry, ShopRegistry
from ai_service import CyberMind, MockGenerator
from ui.components import (
    play_audio, render_word_card, render_card_slot, render_enemy,
    render_hand, render_learning_popup, render_quiz_test
)


def render_lobby(start_run_callback: Callable):
    """大厅页面"""
    st.title("🏰 单词尖塔 (Spire of Vocab)")
    st.caption("🎴 Word = Card 战斗系统 v5.3")
    
    db_player = st.session_state.get('db_player', {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🏆 胜利次数", db_player.get("victories", 0))
    with col2:
        st.metric("🎮 总场次", db_player.get("total_runs", 0))
    with col3:
        st.metric("💰 初始金币", "50G")
    
    st.divider()
    
    st.markdown("### 📝 输入今天要攻克的生词")
    st.caption("用逗号分隔 (5-20 个词)，这些词将成为你的**红色攻击弹药** 🟥")
    
    default_words = "Ephemeral, Serendipity, Oblivion, Resilience, Cacophony, Luminous, Solitude, Epiphany, Nostalgia, Ethereal"
    user_input = st.text_area("Spellbook", default_words, height=100)
    
    if st.button("🩸 献祭单词并开始", type="primary", use_container_width=True):
        start_run_callback(user_input)


def render_map_select(enter_node_callback: Callable):
    """地图选择页面"""
    st.header("🛤️ 选择你的路径")
    
    options = st.session_state.game_map.next_options
    cols = st.columns(len(options))
    
    for i, node in enumerate(options):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {node.type.value}")
                st.caption(f"Floor {node.level}")
                
                if st.button(f"前往", key=f"node_sel_{i}", use_container_width=True):
                    enter_node_callback(node)


def render_combat(resolve_node_callback: Callable, check_death_callback: Callable):
    """卡牌战斗渲染"""
    # 初始化战斗状态
    if 'card_combat' not in st.session_state:
        word_pool = st.session_state.word_pool
        
        cards = []
        for w in word_pool.new_words:
            cards.append(WordCard(
                word=w['word'],
                meaning=w['meaning'],
                tier=w.get('tier', 0)
            ))
        for w in word_pool.review_words:
            cards.append(WordCard(
                word=w['word'],
                meaning=w['meaning'],
                tier=w.get('tier', 2)
            ))
        
        st.session_state.card_combat = CardCombatState(
            word_pool=cards,
            enemy=Enemy(hp=ENEMY_HP_BASE, max_hp=ENEMY_HP_BASE, 
                       attack=ENEMY_ATTACK, action_timer=ENEMY_ACTION_TIMER,
                       current_timer=ENEMY_ACTION_TIMER)
        )
    
    cs = st.session_state.card_combat
    
    if cs.phase == CombatPhase.LOADING:
        _render_loading_phase(cs)
    elif cs.phase == CombatPhase.BATTLE:
        _render_battle_phase(cs, resolve_node_callback, check_death_callback)
    elif cs.phase == CombatPhase.VICTORY:
        st.balloons()
        st.success("🎉 战斗胜利！")
        if st.button("🎁 获取战利品 (+30G)", type="primary"):
            st.session_state.player.add_gold(30)
            st.session_state.player.advance_room()
            if 'card_combat' in st.session_state:
                del st.session_state.card_combat
            resolve_node_callback()


def _render_loading_phase(cs: CardCombatState):
    """装填阶段 - 只显示颜色，不显示单词"""
    st.markdown("## ⚙️ 装填阶段")
    st.caption("选择卡牌装入弹仓。红色新词需要先学习！**装填后卡牌顺序将被打乱**")
    
    # 学习弹窗
    if 'learning_card' in st.session_state:
        card = st.session_state.learning_card
        if render_learning_popup(card):
            card.learned = True
            cs.load_card(card)
            del st.session_state.learning_card
            st.rerun()
        return
    
    col_pool, col_hand = st.columns([2, 1])
    
    with col_pool:
        st.markdown("### 📚 词库")
        
        attack_cards = [c for c in cs.word_pool if c.card_type == CardType.ATTACK and c not in cs.hand]
        defense_cards = [c for c in cs.word_pool if c.card_type == CardType.DEFENSE and c not in cs.hand]
        utility_cards = [c for c in cs.word_pool if c.card_type == CardType.UTILITY and c not in cs.hand]
        
        # 红色区 - 只显示颜色
        if attack_cards:
            st.markdown("#### 🟥 红色弹药（攻击）")
            cols = st.columns(min(4, len(attack_cards)))
            for i, card in enumerate(attack_cards[:4]):
                with cols[i]:
                    # show_word=False 隐藏单词
                    if render_word_card(card, i, onclick_key=f"load_attack_{i}", 
                                       show_word=False, show_meaning=False):
                        if len(cs.hand) < HAND_SIZE:
                            st.session_state.learning_card = card
                            st.rerun()
        
        # 蓝色区
        if defense_cards:
            st.markdown("#### 🟦 蓝色弹药（防御）")
            cols = st.columns(min(4, len(defense_cards)))
            for i, card in enumerate(defense_cards[:4]):
                with cols[i]:
                    if render_word_card(card, i + 100, onclick_key=f"load_defense_{i}",
                                       show_word=False, show_meaning=False):
                        if len(cs.hand) < HAND_SIZE:
                            cs.load_card(card)
                            st.rerun()
        
        # 金色区
        if utility_cards:
            st.markdown("#### 🟨 金色弹药（功能）")
            cols = st.columns(min(4, len(utility_cards)))
            for i, card in enumerate(utility_cards[:4]):
                with cols[i]:
                    if render_word_card(card, i + 200, onclick_key=f"load_utility_{i}",
                                       show_word=False, show_meaning=False):
                        if len(cs.hand) < HAND_SIZE:
                            cs.load_card(card)
                            st.rerun()
    
    with col_hand:
        st.markdown("### 🔫 弹仓")
        st.caption(f"{len(cs.hand)}/{HAND_SIZE} | 红卡: {cs.count_attack_cards()}/{MIN_ATTACK_CARDS}")
        
        for i in range(HAND_SIZE):
            card = cs.hand[i] if i < len(cs.hand) else None
            if render_card_slot(i, card, on_remove=True):
                cs.unload_card(card)
                st.rerun()
        
        st.divider()
        can_start = cs.can_start_battle()
        
        if not can_start:
            if len(cs.hand) < HAND_SIZE:
                st.warning(f"需要装满 {HAND_SIZE} 张牌")
            elif cs.count_attack_cards() < MIN_ATTACK_CARDS:
                st.warning(f"至少需要 {MIN_ATTACK_CARDS} 张红卡")
        
        if st.button("⚔️ 开始战斗！", type="primary", disabled=not can_start, use_container_width=True):
            # 打乱卡牌顺序！
            random.shuffle(cs.hand)
            cs.start_battle()
            st.rerun()


def _render_battle_phase(cs: CardCombatState, resolve_node_callback, check_death_callback):
    """战斗阶段"""
    player = st.session_state.player
    
    if cs.enemy.is_dead():
        cs.phase = CombatPhase.VICTORY
        st.rerun()
        return
    
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        render_enemy(cs.enemy)
        st.markdown(f"**回合:** {cs.turns}")
    
    with col_right:
        if cs.current_card:
            _render_card_test(cs, player, check_death_callback)
        else:
            st.markdown("### ⚔️ 选择出牌")
            st.info("选择一张牌打出，你将看到中文释义需要选择对应英文！")
    
    st.divider()
    if not cs.current_card:
        clicked = render_hand(cs.hand, on_play=True)
        if clicked is not None:
            card = cs.hand[clicked]
            cs.play_card(card)
            all_words = [c.word for c in cs.word_pool]
            options = random.sample([w for w in all_words if w != card.word], min(3, len(all_words) - 1))
            options.append(card.word)
            random.shuffle(options)
            cs.current_options = options
            st.rerun()
    else:
        st.caption(f"剩余手牌: {len(cs.hand)}")


def _render_card_test(cs: CardCombatState, player, check_death_callback):
    """渲染出牌测试"""
    card = cs.current_card
    options = cs.current_options
    
    st.markdown(f"### 🎴 {card.card_type.icon} {card.card_type.name_cn}卡")
    
    answer = render_quiz_test(card, options)
    
    if answer:
        correct = answer == card.word
        
        db = st.session_state.get('db')
        player_id = st.session_state.db_player.get('id')
        current_room = player.current_room
        if db and player_id:
            db.update_word_tier(player_id, card.word, correct, current_room)
        
        if correct:
            st.success(f"✅ 正确！")
            _apply_card_effect(card, cs, player, correct=True)
        else:
            st.error(f"❌ 错误！正确答案: {card.word}")
            _apply_card_effect(card, cs, player, correct=False)
            if check_death_callback():
                return
        
        intent = cs.enemy.tick()
        if intent == "attack":
            damage = cs.enemy.attack
            player.change_hp(-damage)
            st.warning(f"👹 敌人攻击！造成 {damage} 伤害")
            if check_death_callback():
                return
        
        cs.current_card = None
        cs.current_options = None
        cs.turns += 1
        player.reset_block()
        
        time.sleep(1)
        st.rerun()


def _apply_card_effect(card: WordCard, cs: CardCombatState, player, correct: bool):
    """应用卡牌效果"""
    if correct:
        if card.card_type == CardType.ATTACK:
            damage = card.damage
            cs.enemy.take_damage(damage)
            st.toast(f"⚔️ 造成 {damage} 伤害！", icon="💥")
        elif card.card_type == CardType.DEFENSE:
            block = card.block
            player.add_block(block)
        elif card.card_type == CardType.UTILITY:
            st.toast("✨ 下次攻击双倍伤害！", icon="⚡")
    else:
        if card.card_type == CardType.ATTACK:
            backfire = card.backfire
            player.change_hp(-backfire)
            st.error(f"💥 施法失败！反噬 {backfire} HP")


def render_boss(resolve_node_callback: Callable, check_death_callback: Callable):
    """Boss 战渲染 - 使用缓存的文章"""
    node = st.session_state.game_map.current_node
    
    if 'boss_state' not in st.session_state:
        word_pool = st.session_state.get('word_pool')
        all_words = word_pool.get_all_encountered() if word_pool else []
        boss_hp = max(50, len(all_words) * 10)
        
        st.session_state.boss_state = BossState(
            boss_hp=boss_hp,
            boss_max_hp=boss_hp
        )
        node.data['enemies'] = all_words
    
    bs = st.session_state.boss_state
    enemies = node.data.get('enemies', [])
    
    st.markdown(f"## 👹 The Syntax Colossus")
    boss_pct = max(0, bs.boss_hp / bs.boss_max_hp)
    st.progress(boss_pct, f"Boss HP: {bs.boss_hp}/{bs.boss_max_hp}")
    
    # 使用缓存的文章
    if bs.phase == 'loading':
        cache = st.session_state.get('boss_article_cache')
        
        if cache:
            bs.article = cache.get('article')
            bs.quizzes = cache.get('quizzes')
            bs.phase = 'article'
            st.rerun()
        else:
            st.info("📝 Boss 正在觉醒...")
            with st.spinner("生成中..."):
                ai = st.session_state.get('ai') or CyberMind()
                article = ai.generate_article(enemies)
                
                if article and article.get('article_english'):
                    bs.article = article
                    bs.quizzes = ai.generate_quiz(enemies, article['article_english'])
                else:
                    bs.article = MockGenerator.generate_article(enemies)
                    bs.quizzes = MockGenerator.generate_quiz(enemies)
                
                bs.phase = 'article'
                st.rerun()
    
    elif bs.phase == 'article':
        if bs.article:
            with st.expander("📜 Boss 本体", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**English**")
                    st.markdown(bs.article.get('article_english', ''), unsafe_allow_html=True)
                with col2:
                    st.markdown("**中文**")
                    st.markdown(bs.article.get('article_chinese', ''))
        
        if st.button("⚔️ 准备战斗", type="primary"):
            bs.phase = 'quiz'
            st.rerun()
    
    elif bs.phase == 'quiz':
        quizzes = bs.quizzes.get('quizzes', []) if bs.quizzes else []
        
        if bs.boss_hp <= 0:
            bs.phase = 'victory'
            st.rerun()
            return
        
        if bs.quiz_idx >= len(quizzes):
            if st.button("🔄 再战"):
                bs.quiz_idx = 0
                st.rerun()
            return
        
        q = quizzes[bs.quiz_idx]
        
        with st.container(border=True):
            st.markdown(f"**{q['question']}**")
            choice = st.radio("选择:", q['options'], key=f"boss_q_{bs.quiz_idx}")
            
            if st.button("✨ 释放", type="primary"):
                if choice == q['answer']:
                    bs.boss_hp -= 30
                    st.toast("💥 暴击！", icon="⚡")
                else:
                    st.session_state.player.change_hp(-20)
                    st.error(f"❌ 正确答案: {q['answer']}")
                    if check_death_callback():
                        return
                
                bs.quiz_idx += 1
                time.sleep(1)
                st.rerun()
    
    elif bs.phase == 'victory':
        st.balloons()
        st.success("🏆 Boss 已被击败！")
        if st.button("🎁 获取奖励 (+100G)", type="primary"):
            st.session_state.player.add_gold(100)
            st.session_state.player.advance_room()
            resolve_node_callback()


def render_event(resolve_node_callback: Callable):
    """事件页面"""
    node = st.session_state.game_map.current_node
    event_data = node.data.get('event')
    
    if not event_data:
        event_id, event_config = EventRegistry.get_random()
        node.data['event'] = {'id': event_id, 'config': event_config}
        event_data = node.data['event']
    
    config = event_data.get('config')
    if not config:
        st.error("事件错误")
        if st.button("离开"):
            resolve_node_callback()
        return
    
    st.markdown(f"### {config.icon} {config.name}")
    st.info(config.description)
    
    for i, choice in enumerate(config.choices):
        disabled = choice.cost_gold > 0 and st.session_state.player.gold < choice.cost_gold
        
        if st.button(choice.text, key=f"event_{i}", disabled=disabled, use_container_width=True):
            _apply_event_effect(choice)
            st.session_state.player.advance_room()
            resolve_node_callback()


def _apply_event_effect(choice):
    """应用事件效果"""
    player = st.session_state.player
    
    if choice.cost_gold > 0:
        player.gold -= choice.cost_gold
    
    effect = choice.effect
    value = choice.value
    
    if effect == "heal":
        player.change_hp(value)
    elif effect == "damage":
        player.change_hp(value)
    elif effect == "gold":
        player.add_gold(value)
    elif effect == "max_hp":
        player.max_hp += value
    elif effect == "full_heal":
        player.hp = player.max_hp
    elif effect == "relic":
        from registries import RelicRegistry
        if value == "random":
            relic_id, relic = RelicRegistry.get_random()
            player.relics.append(relic_id)
            st.toast(f"获得: {relic.name}", icon="🏆")
        else:
            player.relics.append(value)


def render_shop(resolve_node_callback: Callable):
    """商店页面"""
    st.header("🛒 商店")
    st.caption(f"💰 {st.session_state.player.gold}G")
    
    if 'shop_items' not in st.session_state:
        st.session_state.shop_items = ShopRegistry.get_random_selection(4)
    
    items = st.session_state.shop_items
    cols = st.columns(len(items))
    
    for i, (item_id, item) in enumerate(items.items()):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {item.icon} {item.name}")
                st.caption(item.description)
                st.markdown(f"💰 {item.price}G")
                
                can_buy = st.session_state.player.gold >= item.price
                
                if st.button("购买", key=f"shop_{item_id}", disabled=not can_buy):
                    st.session_state.player.gold -= item.price
                    _apply_shop_item(item)
                    st.rerun()
    
    if st.button("🚪 离开", use_container_width=True):
        if 'shop_items' in st.session_state:
            del st.session_state.shop_items
        st.session_state.player.advance_room()
        resolve_node_callback()


def _apply_shop_item(item):
    """应用商店物品"""
    player = st.session_state.player
    
    if item.effect == "heal":
        player.change_hp(item.value)
    elif item.effect == "max_hp":
        player.max_hp += item.value
    elif item.effect == "relic":
        player.relics.append(item.value)
        st.toast(f"获得圣遗物！", icon="🏆")


def render_rest(resolve_node_callback: Callable):
    """休息页面"""
    st.header("🔥 营地")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("😴 休息 (+30 HP)", use_container_width=True):
            st.session_state.player.change_hp(30)
            st.session_state.player.advance_room()
            resolve_node_callback()
    with col2:
        if st.button("🏃 跳过", use_container_width=True):
            st.session_state.player.advance_room()
            resolve_node_callback()
