# ==========================================
# 🖥️ 页面渲染器 - v5.4
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
    CardType, WordCard, Enemy, CombatPhase, CardCombatState, CARD_STATS
)
from state_utils import reset_combat_flags
from config import HAND_SIZE, ENEMY_HP_BASE, ENEMY_ATTACK, ENEMY_ACTION_TIMER, UI_PAUSE_EXTRA
from registries import EventRegistry, ShopRegistry
from systems.trigger_bus import TriggerBus, TriggerContext
from ai_service import CyberMind, MockGenerator, BossPreloader
from ui.components import (
    play_audio, render_word_card, render_card_slot, render_enemy,
    render_hand, render_learning_popup, render_quiz_test
)


def _pause(seconds: float):
    time.sleep(seconds + UI_PAUSE_EXTRA)


# ==========================================
# 主菜单
# ==========================================
def render_main_menu(start_callback, continue_callback, library_callback):
    """主菜单"""
    st.markdown("""
    <div style="text-align: center; padding: 40px 0;">
        <h1>🏰 单词尖塔</h1>
        <p style="font-size: 1.2em; color: #888;">单词尖塔 v5.4</p>
    </div>
    """, unsafe_allow_html=True)
    
    db_player = st.session_state.get('db_player', {})
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🏆 胜利", db_player.get("victories", 0))
    with col2:
        st.metric("🎮 总场次", db_player.get("total_runs", 0))
    with col3:
        # 检查是否有存档
        save = st.session_state.db.get_continue_state(db_player.get('id'))
        if save:
            st.metric("📂 存档", f"第{save.get('floor', 0)}层")
        else:
            st.metric("📂 存档", "-")
    
    st.divider()
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        with st.container(border=True):
            st.markdown("### 🎮 开始新游戏")
            st.caption("初始卡组: 5🟥 + 2🟦 + 1🟨")
            if st.button("开始", key="btn_start", type="primary", use_container_width=True):
                start_callback()
    
    with col_b:
        with st.container(border=True):
            st.markdown("### 📂 继续游戏")
            save = st.session_state.db.get_continue_state(db_player.get('id'))
            if save:
                st.caption(f"进度: 第{save.get('floor', 0)}层")
                if st.button("继续", key="btn_continue", use_container_width=True):
                    continue_callback()
            else:
                st.caption("暂无存档")
                st.button("继续", key="btn_continue", disabled=True, use_container_width=True)
    
    with col_c:
        with st.container(border=True):
            st.markdown("### 📚 单词图书馆")
            st.caption("管理你的词库")
            if st.button("进入", key="btn_library", use_container_width=True):
                library_callback()


# ==========================================
# 单词图书馆
# ==========================================
def render_word_library(back_callback):
    """单词图书馆"""
    st.markdown("## 📚 单词图书馆")
    
    if st.button("← 返回主菜单"):
        back_callback()
    
    st.divider()
    
    player_id = st.session_state.db_player.get('id')
    db = st.session_state.db
    
    # 添加新词
    with st.expander("➕ 添加新词", expanded=True):
        st.caption("输入新单词（逗号分隔），将自动设为 Lv0 红色卡牌")
        new_words = st.text_area("新词输入", placeholder="word1, word2, word3...")
        
        if st.button("📥 添加到词库", type="primary"):
            if new_words:
                words = [w.strip() for w in new_words.split(',') if w.strip()]
                
                # 使用 AI 获取释义
                with st.spinner("🧠 获取释义..."):
                    ai = st.session_state.get('ai') or CyberMind()
                    analysis = ai.analyze_words(words)
                    
                    if analysis and analysis.get('words'):
                        for w in analysis['words']:
                            db.add_word(player_id, w['word'], w.get('meaning', ''), 
                                       tier=0, priority='pinned')
                        st.success(f"✅ 已添加 {len(analysis['words'])} 个词！")
                    else:
                        for w in words:
                            db.add_word(player_id, w, '', tier=0, priority='pinned')
                        st.warning(f"⚠️ 已添加 {len(words)} 个词（无释义）")
                
                st.rerun()
    
    # 按颜色显示词库
    all_words = db.get_all_words(player_id)
    
    tab_red, tab_blue, tab_gold = st.tabs([
        f"🟥 红色 Lv0-1 ({len(all_words['red'])})",
        f"🟦 蓝色 Lv2-3 ({len(all_words['blue'])})",
        f"🟨 金色 Lv4-5 ({len(all_words['gold'])})"
    ])
    
    with tab_red:
        if all_words['red']:
            for w in all_words['red']:
                priority_badge = "📌" if w.get('priority') == 'pinned' else ("👻" if w.get('priority') == 'ghost' else "")
                st.markdown(f"**{w['word']}** {priority_badge} - {w.get('meaning', '无释义')}")
        else:
            st.info("暂无红色卡牌")
    
    with tab_blue:
        if all_words['blue']:
            for w in all_words['blue']:
                streak = w.get('consecutive_correct', 0)
                st.markdown(f"**{w['word']}** (🔥{streak}) - {w.get('meaning', '')}")
        else:
            st.info("暂无蓝色卡牌")
    
    with tab_gold:
        if all_words['gold']:
            for w in all_words['gold']:
                st.markdown(f"**{w['word']}** ⭐ - {w.get('meaning', '')}")
        else:
            st.info("暂无金色卡牌")


# ==========================================
# 战后抓牌
# ==========================================
def render_drafting(complete_callback: Callable):
    """战后抓牌 (3选1) - 从本局词池抽取"""
    st.markdown("## 🎁 战利品！选择一张卡牌加入卡组")
    
    # 从本局词池抽取候选 (优先红牌，概率递减)
    if 'draft_candidates' not in st.session_state:
        game_pool = st.session_state.get('game_word_pool', [])
        
        if not game_pool:
            st.session_state.draft_candidates = []
        else:
            import random
            
            # 按颜色分类
            red_cards = [c for c in game_pool if c.card_type == CardType.RED_BERSERK]
            blue_cards = [c for c in game_pool if c.card_type == CardType.BLUE_HYBRID]
            gold_cards = [c for c in game_pool if c.card_type == CardType.GOLD_SUPPORT]
            
            candidates = []
            for _ in range(3):
                # 70% 红, 25% 蓝, 5% 金
                roll = random.random()
                if roll < 0.70 and red_cards:
                    card = random.choice(red_cards)
                    red_cards.remove(card)
                elif roll < 0.95 and blue_cards:
                    card = random.choice(blue_cards)
                    blue_cards.remove(card)
                elif gold_cards:
                    card = random.choice(gold_cards)
                    gold_cards.remove(card)
                elif red_cards:
                    card = random.choice(red_cards)
                    red_cards.remove(card)
                elif blue_cards:
                    card = random.choice(blue_cards)
                    blue_cards.remove(card)
                else:
                    break
                
                candidates.append({
                    'word': card.word,
                    'meaning': card.meaning,
                    'tier': card.tier,
                    'priority': card.priority
                })
            
            st.session_state.draft_candidates = candidates
    
    
    candidates = st.session_state.draft_candidates
    
    if not candidates:
        st.warning("词库已空！请在单词图书馆添加更多单词")
        if st.button("跳过", use_container_width=True):
            complete_callback(None)
        return
    
    cols = st.columns(len(candidates))
    
    for i, w in enumerate(candidates):
        with cols[i]:
            with st.container(border=True):
                # 显示完整信息（强制预览）
                card_type = CardType.from_tier(w.get('tier', 0))
                
                st.markdown(f"""
                <div style="background: {card_type.color}; color: white; 
                            padding: 8px; border-radius: 4px; text-align: center;">
                    {card_type.icon} {card_type.name_cn}
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"### {w['word']}")
                
                # 显示释义（强制学习）
                st.info(w.get('meaning', '无释义'))
                
                # 显示属性
                stats = CARD_STATS.get(card_type, {})
                st.caption(f"⚔️ {stats.get('damage', 0)} | 🛡️ {stats.get('block', 0)}")
                
                priority = w.get('priority', 'normal')
                if priority == 'pinned':
                    st.caption("📌 新添加")
                elif priority == 'ghost':
                    st.caption("👻 需要复习")
                
                if st.button("选择", key=f"draft_{i}", type="primary", use_container_width=True):
                    # 创建卡牌
                    new_card = WordCard(
                        word=w['word'],
                        meaning=w.get('meaning', ''),
                        tier=w.get('tier', 0),
                        priority=priority
                    )
                    
                    # 从游戏池移除已选卡
                    game_pool = st.session_state.get('game_word_pool', [])
                    st.session_state.game_word_pool = [c for c in game_pool if c.word != new_card.word]
                    
                    complete_callback(new_card)


def render_map_select(enter_node_callback: Callable):
    """地图选择"""
    st.header("🛤️ 选择你的路径")
    
    options = st.session_state.game_map.next_options
    cols = st.columns(len(options))
    
    for i, node in enumerate(options):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {node.type.value}")
                st.caption(f"第{node.level}层")
                
                if st.button(f"前往", key=f"node_sel_{i}", use_container_width=True):
                    enter_node_callback(node)


def render_combat(resolve_node_callback: Callable, check_death_callback: Callable):
    """卡牌战斗"""
    player = st.session_state.player
    if 'card_combat' not in st.session_state:
        reset_combat_flags()
        
        # 检测是否精英战
        node = st.session_state.game_map.current_node
        is_elite = node and node.type.name == "ELITE"
        
        # 从玩家卡组构建战斗词池，添加轮换机制
        cards = player.deck.copy() if player.deck else []
        
        # 跟踪上一局使用的卡，优先使用未使用过的
        last_used = st.session_state.get('_last_used_cards', set())
        unused_cards = [c for c in cards if c.word not in last_used]
        used_cards = [c for c in cards if c.word in last_used]
        
        # 优先放入未使用的卡，然后是使用过的
        random.shuffle(unused_cards)
        random.shuffle(used_cards)
        rotated_pool = unused_cards + used_cards
        
        # 根据怪物类型设置属性
        from config import ENEMY_HP_ELITE
        if len(player.deck) > player.deck_limit:
            if 'preparation_selected' not in st.session_state:
                _render_preparation()
                return
            else:
                # 使用选择好的卡组初始化战斗
                selected_deck = st.session_state.preparation_selected
                del st.session_state.preparation_selected
                st.session_state.card_combat = CardCombatState(
                    player=player,
                    enemy=Enemy(level=st.session_state.game_map.current_node.level, is_elite=(st.session_state.game_map.current_node.type == NodeType.ELITE)),
                    deck=selected_deck
                )
        else:
            # 自动全带
            st.session_state.card_combat = CardCombatState(
                player=player,
                enemy=Enemy(level=st.session_state.game_map.current_node.level, is_elite=(st.session_state.game_map.current_node.type == NodeType.ELITE)),
                deck=player.deck.copy()
            )

    cs = st.session_state.card_combat
    
    # v6.0 直接进入战斗，不再有 Loading 阶段
    if cs.phase == CombatPhase.LOADING:
        cs.start_battle()
        TriggerBus.trigger("on_combat_start", TriggerContext(player=player, enemy=cs.enemy, combat_state=cs))
        cs.ensure_black_in_hand()
        # 初始填充手牌
        while len(cs.hand) < cs.hand_size:
            cs.draw_card()
        st.rerun()
        return

    if cs.phase == CombatPhase.BATTLE:
        _render_battle_phase(cs, resolve_node_callback, check_death_callback)
    elif cs.phase == CombatPhase.VICTORY:
        st.balloons()
        
        # v6.0 卡牌奖励选择
        is_elite = cs.enemy.is_elite
        pick_count = 2 if is_elite else 1
        
        # 记录战斗完成
        game_map = st.session_state.get('game_map')
        if game_map and 'combat_recorded' not in st.session_state:
            game_map.record_combat_completed(NodeType.ELITE if is_elite else NodeType.COMBAT)
            st.session_state.combat_recorded = True
        
        # 生成奖励卡牌选项
        if 'reward_cards' not in st.session_state:
            word_pool = st.session_state.get('game_word_pool') or []
            player_deck_words = {c.word for c in st.session_state.player.deck}
            available_cards = [c for c in word_pool if c.word not in player_deck_words]
            
            if len(available_cards) >= 3:
                st.session_state.reward_cards = random.sample(available_cards, 3)
            else:
                st.session_state.reward_cards = available_cards
            st.session_state.selected_rewards = []
        
        reward_cards = st.session_state.reward_cards
        selected = st.session_state.selected_rewards
        
        if reward_cards and len(selected) < pick_count:
            st.subheader(f"🎴 选择卡牌奖励 ({len(selected)}/{pick_count})")
            st.caption("精英怪可选 2 张，普通怪可选 1 张")
            
            cols = st.columns(len(reward_cards))
            for i, card in enumerate(reward_cards):
                with cols[i]:
                    already_selected = card in selected
                    with st.container(border=True):
                        st.markdown(f"### {card.card_type.icon} {card.word}")
                        st.caption(card.meaning)
                        if already_selected:
                            st.success("✓ 已选择")
                        elif st.button("选择", key=f"reward_{i}"):
                            selected.append(card)
                            st.rerun()
            
            if len(selected) >= pick_count:
                if st.button("✅ 确认选择", type="primary"):
                    for card in selected:
                        st.session_state.player.add_card_to_deck(card)
                    pool = st.session_state.get('game_word_pool', [])
                    selected_words = {c.word for c in selected}
                    st.session_state.game_word_pool = [c for c in pool if c.word not in selected_words]
                    st.toast(f"🎴 获得 {len(selected)} 张卡牌！", icon="✨")
                    # 清理奖励状态
                    del st.session_state.reward_cards
                    del st.session_state.selected_rewards
                    if 'combat_recorded' in st.session_state:
                        del st.session_state.combat_recorded
                    _complete_combat_victory(cs, resolve_node_callback)
        else:
            # 无可用奖励卡牌
            if st.button("🎁 获取战利品（+30金币）", type="primary"):
                if 'combat_recorded' in st.session_state:
                    del st.session_state.combat_recorded
                _complete_combat_victory(cs, resolve_node_callback)


def _complete_combat_victory(cs: CardCombatState, resolve_node_callback: Callable):
    """完成战斗胜利流程"""
    gold_reward = 50 if cs.enemy.is_elite else 30
    player = st.session_state.player
    ctx = TriggerContext(player=player, enemy=cs.enemy, combat_state=cs, data={"gold_reward": gold_reward})
    TriggerBus.trigger("on_combat_end", ctx)
    gold_reward = ctx.data.get("gold_reward", gold_reward)
    player.add_gold(gold_reward)
    player.advance_room()
    
    # 如果接近 Boss 层，启动后台预加载
    game_map = st.session_state.get('game_map')
    if game_map:
        from config import TOTAL_FLOORS
        if game_map.floor >= TOTAL_FLOORS - 1:
            player = st.session_state.player
            words = [{"word": c.word, "meaning": c.meaning} for c in player.deck]
            BossPreloader.start_preload(words)
    
    # 记录本局使用过的卡牌，供下局轮换
    if 'card_combat' in st.session_state:
        used_words = {c.word for c in st.session_state.card_combat.discard}
        used_words.update(c.word for c in st.session_state.card_combat.hand if hasattr(c, 'word'))
        st.session_state._last_used_cards = used_words
        del st.session_state.card_combat
    
    # 重置护甲
    st.session_state.player.armor = 0
    
    resolve_node_callback()


def _take_cards_from_pool(count: int, prefer_red_only: bool = False) -> list:
    pool = st.session_state.get('game_word_pool') or []
    deck_words = {c.word for c in st.session_state.player.deck}
    pool = [c for c in pool if c.word not in deck_words]
    if count <= 0 or not pool:
        return []

    red_cards = [c for c in pool if c.card_type == CardType.RED_BERSERK]
    other_cards = [c for c in pool if c.card_type != CardType.RED_BERSERK]
    picked = []

    for _ in range(count):
        source = red_cards if red_cards else ([] if prefer_red_only else other_cards)
        if not source:
            break
        card = random.choice(source)
        picked.append(card)
        if card in pool:
            pool.remove(card)
        if card in red_cards:
            red_cards.remove(card)
        if card in other_cards:
            other_cards.remove(card)

    st.session_state.game_word_pool = pool
    return picked


def _grant_red_card_from_pool(reason: str = "") -> bool:
    cards = _take_cards_from_pool(1, prefer_red_only=True)
    if not cards:
        return False
    card = cards[0]
    st.session_state.player.add_card_to_deck(card)
    st.toast(f"获得红卡（{reason}）") if reason else st.toast("获得红卡")
    return True


def _count_upgrade_for_red_reward():
    counter = st.session_state.get("upgrade_red_counter", 0) + 1
    if counter >= 2:
        _grant_red_card_from_pool("升级累计")
        counter = max(0, counter - 2)
    st.session_state.upgrade_red_counter = counter


def _render_preparation():
    """战前准备：查看卡组并确认出发"""
    st.header("🧭 战前准备")
    player = st.session_state.player

    st.markdown("### 当前卡组")
    st.caption(f"当前卡组共 {len(player.deck)} 张卡牌")

    current_red = sum(1 for c in player.deck if c.card_type in [CardType.RED_BERSERK, CardType.BLACK_CURSE])
    current_blue = sum(1 for c in player.deck if c.card_type == CardType.BLUE_HYBRID)
    current_gold = sum(1 for c in player.deck if c.card_type == CardType.GOLD_SUPPORT)

    st.markdown("**卡组统计**")
    m1, m2, m3 = st.columns(3)
    m1.metric("红卡数", f"{current_red}")
    m2.metric("蓝卡数", f"{current_blue}")
    m3.metric("金卡数", f"{current_gold}")

    with st.expander(f"查看卡组详情（{len(player.deck)}）", expanded=True):
        deck_cols = st.columns(3)
        for i, card in enumerate(player.deck):
            with deck_cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"**{card.icon} {card.word}**")
                    st.caption(card.meaning)

    if st.button("确认出发", type="primary", use_container_width=True):
        st.session_state.preparation_selected = player.deck
        if 'prep_indices' in st.session_state:
            del st.session_state.prep_indices
        st.rerun()

def _render_loading_phase(cs: CardCombatState):
    """装填阶段"""
    st.markdown("## ⚙️ 装填阶段")
    st.caption("选择卡牌装入弹仓。红色新词需要先学习！")
    
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
        
        red_cards = [c for c in cs.word_pool if c.card_type == CardType.RED_BERSERK and c not in cs.hand]
        blue_cards = [c for c in cs.word_pool if c.card_type == CardType.BLUE_HYBRID and c not in cs.hand]
        gold_cards = [c for c in cs.word_pool if c.card_type == CardType.GOLD_SUPPORT and c not in cs.hand]
        
        if red_cards:
            st.markdown("#### 🟥 红色 (狂暴)")
            cols = st.columns(min(4, len(red_cards)))
            for i, card in enumerate(red_cards[:4]):
                with cols[i]:
                    if render_word_card(card, i, onclick_key=f"load_red_{i}", show_word=False):
                        if len(cs.hand) < HAND_SIZE:
                            st.session_state.learning_card = card
                            st.rerun()
        
        if blue_cards:
            st.markdown("#### 🟦 蓝色 (混合)")
            cols = st.columns(min(4, len(blue_cards)))
            for i, card in enumerate(blue_cards[:4]):
                with cols[i]:
                    if render_word_card(card, i + 100, onclick_key=f"load_blue_{i}", show_word=False):
                        if len(cs.hand) < HAND_SIZE:
                            cs.load_card(card)
                            st.rerun()
        
        if gold_cards:
            st.markdown("#### 🟨 金色 (辅助)")
            cols = st.columns(min(4, len(gold_cards)))
            for i, card in enumerate(gold_cards[:4]):
                with cols[i]:
                    if render_word_card(card, i + 200, onclick_key=f"load_gold_{i}", show_word=False):
                        if len(cs.hand) < HAND_SIZE:
                            cs.load_card(card)
                            st.rerun()
    
    with col_hand:
        st.markdown("### 🔫 弹仓")
        red_count = cs.count_by_type(CardType.RED_BERSERK)
        st.caption(f"{len(cs.hand)}/{HAND_SIZE} | 红卡: {red_count}/3")
        
        for i in range(HAND_SIZE):
            card = cs.hand[i] if i < len(cs.hand) else None
            if render_card_slot(i, card, on_remove=True):
                cs.unload_card(card)
                st.rerun()
        
        st.divider()
        can_start = cs.can_start_battle()
        
        if not can_start:
            st.warning(f"需要至少 3 张牌（当前 {len(cs.hand)} 张）")
        
        if st.button("⚔️ 开始战斗！", type="primary", disabled=not can_start, use_container_width=True):
            random.shuffle(cs.hand)
            cs.start_battle()
            st.rerun()


def _render_battle_phase(cs: CardCombatState, resolve_node_callback, check_death_callback):
    """战斗阶段"""
    player = st.session_state.player

    if st.session_state.get("_end_turn_due_to_item"):
        st.session_state._end_turn_due_to_item = False
        _resolve_enemy_turn(cs, player, check_death_callback)
        return
    
    # 检查是否被眩晕
    if st.session_state.get('_player_stunned'):
        st.warning("💥 你被眩晕了，跳过本回合！")
        st.session_state._player_stunned = False
        
        # 敌人攻击（眩晕回合敌人不攻击，但伤害递增）
        intent = cs.enemy.tick()
        cs.turns += 1
        _pause(1)
        st.rerun()
        return
    
    if cs.enemy.is_dead():
        cs.phase = CombatPhase.VICTORY
        st.rerun()
        return
    
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        render_enemy(cs.enemy)
        st.markdown(f"**回合:** {cs.turns}")
        if cs.next_card_multiplier and cs.next_card_multiplier > 1:
            st.success(f"⚡ 下一张数值 x{cs.next_card_multiplier}")
    
    with col_right:
        if cs.current_card:
            _render_card_test(cs, player, check_death_callback)
        else:
            st.markdown("### ⚔️ 选择出牌")
            st.info("选择一张牌，中文选英文测试！")
    
    st.divider()
    if not cs.current_card:
        # 手牌为空时自动抽牌
        if len(cs.hand) == 0:
            drawn = cs.draw_card()
            if drawn:
                st.toast("♻️ 弃牌堆已洗回，自动抽牌！", icon="🔄")
                st.rerun()
            else:
                st.warning("⚠️ 无牌可抽！战斗陷入僵局...")
        
        clicked = render_hand(cs.hand, on_play=True)
        if clicked is not None:
            card = cs.hand[clicked]
            removed = cs.play_card(card)
            if removed:
                _grant_red_card_from_pool("移除")
            if len(cs.hand) == 0:
                if (
                    card.card_type == CardType.RED_BERSERK
                    and "START_BURNING_BLOOD" in getattr(player, "relics", [])
                    and player.hp < 50
                ):
                    cs.draw_with_preference([CardType.RED_BERSERK], 2)
                elif card.card_type == CardType.BLUE_HYBRID and "PAIN_ARMOR" in getattr(player, "relics", []):
                    drawn = []
                    drawn += cs.draw_with_preference([CardType.RED_BERSERK], 1)
                    drawn += cs.draw_with_preference([CardType.BLUE_HYBRID], 1)
                    if len(drawn) < 2:
                        cs.draw_with_preference([CardType.RED_BERSERK, CardType.BLUE_HYBRID], 2 - len(drawn))
            all_words = [c.word for c in cs.word_pool]
            options = random.sample([w for w in all_words if w != card.word], min(3, len(all_words) - 1))
            options.append(card.word)
            random.shuffle(options)
            cs.current_options = options
            st.rerun()
    else:
        st.caption(f"剩余手牌: {len(cs.hand)} | 弃牌堆: {len(cs.discard)}")


def _render_card_test(cs: CardCombatState, player, check_death_callback):
    """出牌测试"""
    card = cs.current_card
    options = cs.current_options

    # 使用提示道具：移除错误选项
    if st.session_state.get('_item_hint', 0) and options:
        wrong_opts = [o for o in options if o != card.word]
        if wrong_opts:
            remove_count = 2 if len(wrong_opts) >= 2 else 1
            to_remove = random.sample(wrong_opts, remove_count)
            options = [o for o in options if o not in to_remove]
            cs.current_options = options
        st.session_state._item_hint = max(0, st.session_state.get("_item_hint", 0) - 1)
    
    st.markdown(f"### 🎴 {card.card_type.icon} {card.card_type.name_cn}卡")
    
    answer = render_quiz_test(card, options)
    
    if answer:
        pre_type = card.card_type
        correct = answer == card.word
        word = card.word
        
        db = st.session_state.get('db')
        player_id = st.session_state.db_player.get('id')
        current_room = player.current_room
        
        # 更新进度
        result = None
        if db and player_id:
            result = db.update_word_progress(player_id, card.word, correct, current_room)
            if result and result.get('upgraded'):
                st.success(f"⬆️ {card.word} 升级!")
                new_tier = result.get("new_tier")
                if new_tier is not None:
                    card.tier = new_tier
                    if not card.is_blackened:
                        card.temp_level = None
                    for c in player.deck:
                        if c.word == card.word:
                            c.tier = new_tier
                            if not c.is_blackened:
                                c.temp_level = None
        db = st.session_state.get('db')
        player_id = st.session_state.db_player.get('id')
        
        if correct:
            st.success(f"✅ 正确！")
            _apply_card_effect(card, cs, player, correct=True)
            TriggerBus.trigger("on_correct_answer", TriggerContext(player=player, enemy=cs.enemy, card=card, combat_state=cs))

            if card.is_blackened or card.card_type == CardType.BLACK_CURSE:
                black_streak = st.session_state.get("black_correct_streak", {})
                black_streak[word] = black_streak.get(word, 0) + 1
                if black_streak[word] >= 5:
                    if card in player.deck:
                        player.deck.remove(card)
                    cs._remove_from_all_piles(card)
                    cs.word_pool = [c for c in cs.word_pool if c.word != word]
                    del black_streak[word]
                    st.success(f"✨ 黑卡净化成功，已从本局移除：{word}")
                    cs.current_card = None
                    cs.current_options = None
                st.session_state.black_correct_streak = black_streak
            
            # v6.0 正确清空错误计数
            card.wrong_streak = 0

            if result and result.get('upgraded'):
                _count_upgrade_for_red_reward()
            
            # 局内熟练度追踪
            from config import RED_TO_BLUE_UPGRADE_THRESHOLD, BLUE_TO_GOLD_UPGRADE_THRESHOLD
            streak = st.session_state.in_game_streak
            streak[word] = streak.get(word, 0) + 1
            
            # 达到阈值则升级卡牌 (temp_level)
            if pre_type == CardType.RED_BERSERK:
                if streak[word] >= RED_TO_BLUE_UPGRADE_THRESHOLD:
                    card.temp_level = "blue"
                    st.toast(f"升级为蓝卡：{word}", icon="🟦")
                    _count_upgrade_for_red_reward()
                    streak[word] = 0  # 重置计数
            elif pre_type == CardType.BLUE_HYBRID:
                if streak[word] >= BLUE_TO_GOLD_UPGRADE_THRESHOLD:
                    card.temp_level = "gold"
                    st.toast(f"升级为金卡：{word}", icon="🟨")
                    _count_upgrade_for_red_reward()
                    streak[word] = 0  # 重置计数
        else:
            st.error(f"❌ 错误！正确答案: {card.word}")
            ctx = TriggerContext(player=player, enemy=cs.enemy, card=card, combat_state=cs)
            TriggerBus.trigger("on_wrong_answer", ctx)
            if not ctx.data.get('negate_wrong_penalty'):
                _apply_card_effect(card, cs, player, correct=False)

            if card.is_blackened or card.card_type == CardType.BLACK_CURSE:
                black_streak = st.session_state.get("black_correct_streak", {})
                black_streak[word] = 0
                st.session_state.black_correct_streak = black_streak
            
            # ==========================================
            # v6.0 精简降级路径：金(1) -> 蓝(2) -> 红(3) -> 黑
            # ==========================================
            if not card.is_blackened:
                card.wrong_streak += 1
                
                ctype = card.card_type
                if ctype == CardType.GOLD_SUPPORT and card.wrong_streak >= 1:
                    card.temp_level = "blue"
                    st.warning("⬇️ 金卡遗忘！降级为蓝卡")
                    card.wrong_streak = 0
                elif ctype == CardType.BLUE_HYBRID and card.wrong_streak >= 2:
                    card.temp_level = "red"
                    st.warning("⬇️ 蓝卡遗忘！降级为红卡")
                    card.wrong_streak = 0
                elif ctype == CardType.RED_BERSERK and card.wrong_streak >= 2:
                    card.is_blackened = True
                    card.temp_level = "black"
                    st.error("💀 红卡黑化！变为诅咒卡")
                    card.wrong_streak = 0
            
            # 精英怪眩晕机制：1/3 概率
            if cs.enemy.is_elite and random.random() < 0.33:
                st.warning("💫 你被眩晕了！跳过一回合")
                st.session_state._player_stunned = True
            
            # 错误时重置连击
            if card.word in st.session_state.in_game_streak:
                st.session_state.in_game_streak[card.word] = 0
            
            if check_death_callback():
                return
        
        if cs.extra_actions > 0:
            cs.extra_actions -= 1
            cs.current_card = None
            cs.current_options = None
            st.rerun()
            return
        _resolve_enemy_turn(cs, player, check_death_callback)


def _resolve_enemy_turn(cs: CardCombatState, player, check_death_callback):
    intent = cs.enemy.tick()
    if intent == "attack":
        damage = cs.enemy.attack
        if st.session_state.get('_item_shield', False):
            st.session_state._item_shield = False
            damage = 0
            st.toast("🛡️ 护盾抵消了本次攻击", icon="🛡️")
        else:
            reduce = st.session_state.get('_item_damage_reduce', 0)
            if reduce:
                damage = max(0, damage - reduce)
                st.session_state._item_damage_reduce = 0
        if damage > 0:
            player.change_hp(-damage)
            st.warning(f"👹 敌人攻击！造成 {damage} 伤害")
        else:
            st.toast("🛡️ 本次伤害被抵消", icon="🛡️")
        if check_death_callback():
            return

    cs.current_card = None
    cs.current_options = None
    cs.turns += 1
    # v6.0 护甲每局重置，不再自动清零（玩家需要手动获得护甲）
    # 这里的 player.reset_block() 应该被移除，因为 Player 类现在有 armor

    _pause(1)
    st.rerun()


def _apply_card_effect(card: WordCard, cs: CardCombatState, player, correct: bool):
    """应用卡牌效果 (使用效果注册表)"""
    from registries import CardEffectRegistry, EffectContext
    
    # 创建效果上下文
    ctx = EffectContext(
        player=player,
        enemy=cs.enemy,
        cs=cs,
        card=card,
        st=st
    )
    
    # 通过注册表执行效果
    card_type_name = card.card_type.name  # "RED_BERSERK", "BLUE_HYBRID", "GOLD_SUPPORT"
    CardEffectRegistry.apply_effect(card_type_name, ctx, correct)


# ==========================================
# 其他页面
# ==========================================

def render_boss(resolve_node_callback: Callable, check_death_callback: Callable):
    """首领战"""
    if 'boss_state' not in st.session_state:
        player = st.session_state.player
        boss_hp = max(100, len(player.deck) * 15)
        st.session_state.boss_state = BossState(boss_hp=boss_hp, boss_max_hp=boss_hp)
    
    bs = st.session_state.boss_state
    
    st.markdown("## 👹 语法巨像")
    st.progress(max(0, bs.boss_hp / bs.boss_max_hp), f"生命: {bs.boss_hp}/{bs.boss_max_hp}")
    
    if bs.phase == 'loading':
        # 优先使用预加载的结果
        preloaded = BossPreloader.get_result()
        cache = st.session_state.get('boss_article_cache')
        
        if preloaded:
            bs.article = preloaded.get('article')
            bs.quizzes = preloaded.get('quizzes')
            bs.phase = 'article'
            BossPreloader.reset()
            st.rerun()
        elif cache:
            bs.article = cache.get('article')
            bs.quizzes = cache.get('quizzes')
            bs.phase = 'article'
            st.rerun()
        elif st.session_state.get('boss_generation_status') == 'generating':
            # 后台线程仍在生成中
            st.info("🔄 首领故事正在创作中，请稍候...")
            st.caption("AI 正在为你编写独一无二的冒险故事...")
            _pause(2)
            st.rerun()
        elif BossPreloader.is_loading():
            st.info("🔄 首领正在觉醒...")
            _pause(1)
            st.rerun()
        else:
            # 没有预加载，使用当前卡组生成 (Mock)
            with st.spinner("首领觉醒中..."):
                player = st.session_state.player
                words = [{"word": c.word, "meaning": c.meaning} for c in player.deck] if player.deck else []
                bs.article = MockGenerator.generate_article(words)
                bs.quizzes = MockGenerator.generate_quiz(words)
                bs.phase = 'article'
                st.rerun()
    
    elif bs.phase == 'article':
        if bs.article:
            with st.expander("📜 首领本体", expanded=True):
                # v6.0 移除译文，仅展示英文文本
                st.markdown("**英文原文**")
                st.markdown(bs.article.get('article_english', ''), unsafe_allow_html=True)
        
        if st.button("⚔️ 准备战斗", type="primary"):
            bs.phase = 'quiz'
            bs.turn = 0
            st.rerun()
    
    elif bs.phase == 'quiz':
        quizzes = bs.quizzes.get('quizzes', []) if bs.quizzes else []
        
        # 狂暴机制：题目耗尽后逻辑
        is_frenzy = bs.quiz_idx >= len(quizzes)
        
        if bs.boss_hp <= 0 and not is_frenzy:
             # 这里理论上不应该发生，因为有斩杀保护
             bs.phase = 'victory'
             st.rerun()
             return

        # 渲染 Boss 状态
        col_hp, col_armor = st.columns(2)
        with col_hp:
            st.progress(max(0, bs.boss_hp / bs.boss_max_hp), f"❤️ 生命: {bs.boss_hp}/{bs.boss_max_hp}")
        with col_armor:
            st.metric("🛡️ 首领护甲", bs.armor)

        if not is_frenzy:
            q = quizzes[bs.quiz_idx]
            with st.container(border=True):
                st.markdown(f"**{q['question']}**")
                choice = st.radio("选择:", q['options'], key=f"boss_q_{bs.quiz_idx}")
                
                if st.button("✨ 释放", type="primary"):
                    if choice == q['answer']:
                        damage = 10  # v6.0 Fixed Damage
                        # 检查斩杀保护：若题目未出完且 Boss 即将死亡，赋予 50 护甲
                        if bs.boss_hp <= damage and bs.quiz_idx < len(quizzes) - 1:
                            bs.armor += 50
                            st.warning("🛡️ 首领感到威胁，生成了临时护甲！")
                        
                        # 扣除护甲或 HP
                        if bs.armor > 0:
                            absorbed = min(bs.armor, damage)
                            bs.armor -= absorbed
                            damage -= absorbed
                        bs.boss_hp = max(0, bs.boss_hp - damage)
                        if damage > 0:
                            st.toast(f"💥 命中！造成 {damage} 伤害", icon="⚡")
                        else:
                            st.toast("🛡️ 伤害被护甲吸收", icon="🛡️")
                        
                        # 阶段保护：首次 HP < 100 时，立即获得 100 护甲
                        if bs.boss_hp < 100 and not bs.triggered_100hp_shield:
                            bs.armor += 100
                            bs.triggered_100hp_shield = True
                            st.error("⚠️ 首领进入二阶段，护甲激增！")
                    else:
                        st.session_state.player.change_hp(-25) # v6.0 Wrong Penalty
                        st.error(f"❌ 正确答案: {q['answer']}")
                        if check_death_callback():
                            return
                    
                    bs.quiz_idx += 1
                    bs.turn += 1
                    _pause(1)
                    st.rerun()
        else:
            # 狂暴期：题目耗尽
            st.error("🔥 首领进入狂暴状态！题目已耗尽，护甲清零，每回合造成递增伤害！")
            bs.armor = 0
            
            # 狂暴伤害计算：20, 30, 40... (每回合增加 10)
            frenzy_turn = bs.turn - len(quizzes)
            current_damage = 20 + (frenzy_turn * 10)
            
            st.markdown(f"### 👹 首领蓄势待发... (当前威胁: {current_damage})")
            st.progress(max(0, bs.boss_hp / bs.boss_max_hp), f"生命: {bs.boss_hp}/{bs.boss_max_hp}")

            if st.button("💪 用意志抵挡并反击（10伤害）", key="boss_frenzy_attack"):
                bs.boss_hp -= 10
                
                # v6.0 Frenzy: 每回合攻击
                st.session_state.player.change_hp(-current_damage)
                st.toast(f"💥 首领狂暴攻击！造成 {current_damage} 伤害", icon="🔥")
                
                bs.turn += 1
                if bs.boss_hp <= 0:
                    bs.phase = 'victory'
                
                if check_death_callback():
                    return
                st.rerun()
    
    elif bs.phase == 'victory':
        st.balloons()
        st.success("🏆 首领已被击败！")
        if st.button("🎁 获取奖励（+100金币）", type="primary"):
            st.session_state.player.add_gold(100)
            st.session_state.player.advance_room()
            resolve_node_callback()


def render_event(resolve_node_callback: Callable):
    """事件 v6.0"""
    node = st.session_state.game_map.current_node
    player = st.session_state.player
    
    # 确保事件数据已加载或生成
    if 'event_data' not in node.data:
        # 优化随机算法：袋子机制 (Bag Randomization)
        # 避免重复遇到相同的事件，直到所有事件都遇到过一次
        if 'seen_events' not in st.session_state:
            st.session_state.seen_events = set()
            
        all_events = EventRegistry.get_all()
        available_ids = [eid for eid in all_events.keys() if eid not in st.session_state.seen_events]
        
        # 如果所有事件都遇到过了，重置袋子
        if not available_ids:
            st.session_state.seen_events = set()
            available_ids = list(all_events.keys())
        
        event_id = random.choice(available_ids)
        st.session_state.seen_events.add(event_id)
        
        node.data['event_id'] = event_id
        node.data['event_data'] = EventRegistry.get(event_id)
    
    event_data = node.data['event_data']
    event_id = node.data['event_id']

    st.markdown(f"## {event_data.icon} {event_data.name}")
    
    # 子阶段处理
    subphase = st.session_state.get('event_subphase')
    if subphase == "fill_blank":
        _render_fountain_test(resolve_node_callback)
        return
    elif subphase == "adventurer_loot":
        _render_adventurer_loot(resolve_node_callback)
        return
    elif subphase == "book_read":
        _render_mysterious_book(resolve_node_callback)
        return

    st.markdown(event_data.description)
    if event_data.flavor_text:
        st.caption(event_data.flavor_text)
    
    # 渲染选项 (v6.0 匹配 EventRegistry 结构)
    for i, choice in enumerate(event_data.choices):
        with st.container(border=True):
            st.markdown(f"### {choice.text}")
            
            can_afford = True
            if choice.cost_gold and player.gold < choice.cost_gold:
                can_afford = False
                st.warning(f"💰 需要 {choice.cost_gold} 金币")
            
            if st.button("选择这份命运", key=f"evt_btn_{event_id}_{i}", disabled=not can_afford):
                if choice.cost_gold:
                    player.gold -= choice.cost_gold
                
                # 处理效果
                effect = choice.effect
                value = choice.value
                
                if effect == "heal":
                    player.change_hp(value)
                elif effect == "damage":
                    player.change_hp(value)
                elif effect == "gold":
                    if isinstance(value, tuple) and len(value) == 2:
                        amt = random.randint(value[0], value[1])
                        player.add_gold(amt)
                    else:
                        player.add_gold(value)
                elif effect == "max_hp":
                    player.max_hp += value
                    player.hp = min(player.hp, player.max_hp)
                elif effect == "full_heal":
                    player.hp = player.max_hp
                    st.success("💖 生命完全恢复！")
                elif effect == "relic":
                    if value == "random":
                        from registries import RelicRegistry
                        player.change_hp(-20)
                        rid, r = RelicRegistry.get_random()
                        player.relics.append(rid)
                        st.toast(f"🎁 获得随机圣遗物: {r.name}", icon="🏆")
                    else:
                        player.relics.append(value)
                elif effect == "trade":
                    if isinstance(value, dict):
                        if "hp" in value: player.change_hp(value["hp"])
                        if "gold" in value: player.add_gold(value["gold"])
                elif effect == "item":
                    player.inventory.append(value)
                
                # v6.0 特殊子阶段效果
                elif effect == "fill_blank_test":
                    st.session_state.event_subphase = "fill_blank"
                    st.rerun()
                    return
                elif effect == "adventurer_loot":
                    st.session_state.event_subphase = "adventurer_loot"
                    st.rerun()
                    return
                elif effect == "book_read":
                    st.session_state.event_subphase = "book_read"
                    st.rerun()
                    return
                elif effect == "risky_treasure":
                    if random.random() < 0.5:
                        player.change_hp(-20)
                        st.error("💥 陷阱！你受到了 20 伤害")
                    else:
                        gold = random.randint(30, 50)
                        player.add_gold(gold)
                        st.success(f"💰 成功！获得了 {gold} 金币")
                    _pause(1)
                elif effect == "upgrade_blue_cards":
                    player.blue_card_heal_buff = True
                    st.success("⚒️ 铁匠对你的蓝卡进行了加持！")
                
                # 如果没进子阶段，完成事件
                if st.session_state.get('event_subphase') is None:
                    player.advance_room()
                    resolve_node_callback()
                    st.rerun()

def _render_fountain_test(resolve_node_callback):
    """遗忘之泉：黑卡恢复测试"""
    st.subheader("🌊 填空测试")
    player = st.session_state.player
    black_cards = [c for c in player.deck if c.is_blackened]
    
    if not black_cards:
        st.info("你身上没有黑化的卡牌。泉水倒映出你平凡的面孔。")
        if st.button("离开"):
            st.session_state.event_subphase = None
            player.advance_room()
            resolve_node_callback()
            st.rerun()
        return

    # 让玩家选择要恢复的卡牌
    if len(black_cards) > 1:
        st.markdown("请选择一张要净化的卡牌：")
        cols = st.columns(min(3, len(black_cards)))
        for i, card in enumerate(black_cards):
            with cols[i % 3]:
                if st.button(f"{card.word}", key=f"fountain_{i}"):
                    st.session_state.fountain_target = card
                    st.rerun()
        
        target = st.session_state.get('fountain_target')
        if not target:
            return
    else:
        target = black_cards[0]

    st.markdown(f"请拼写出对应的单词以恢复卡牌: **{target.meaning}**")
    ans = st.text_input("单词拼写:", key="fountain_input").strip()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("确认净化", type="primary"):
            if ans.lower() == target.word.lower():
                target.is_blackened = False
                target.temp_level = "red"
                st.success(f"✨ 奇迹！{target.word} 已恢复为红卡！")
                if 'fountain_target' in st.session_state: del st.session_state.fountain_target
                _pause(1.5)
            else:
                st.error("❌ 失败了，泉水变得浑浊...")
                _pause(1)
            
            st.session_state.event_subphase = None
            player.advance_room()
            resolve_node_callback()
            st.rerun()
            
    with col2:
        if st.button("放弃并离开"):
            if 'fountain_target' in st.session_state: del st.session_state.fountain_target
            st.session_state.event_subphase = None
            player.advance_room()
            resolve_node_callback()
            st.rerun()

def _render_adventurer_loot(resolve_node_callback):
    """勇者之尸：翻包结果"""
    player = st.session_state.player
    st.subheader("🎒 翻找背包")
    
    if 'adv_loot_result' not in st.session_state:
        # 50% 战斗 / 50% 获得卡牌
        if random.random() < 0.5:
            st.session_state.adv_loot_result = "combat"
        else:
            st.session_state.adv_loot_result = "cards"
            # 生成 3 张奖励卡 (加权: 红>蓝>金)
            word_pool = st.session_state.get('game_word_pool') or []
            weights = []
            for c in word_pool:
                if c.card_type == CardType.RED_BERSERK: weights.append(0.6)
                elif c.card_type == CardType.BLUE_HYBRID: weights.append(0.3)
                elif c.card_type == CardType.GOLD_SUPPORT: weights.append(0.1)
                else: weights.append(0.1)
            
            # 抽取 3 张
            if word_pool:
                st.session_state.adv_cards = random.choices(word_pool, weights=weights, k=3)
            else:
                st.session_state.adv_cards = []

    result = st.session_state.adv_loot_result
    
    if result == "combat":
        st.error("👹 陷阱！尸体站了起来！此地不宜久留...")
        if st.button("进入战斗 (消耗一次小怪次数)"):
            # 逻辑上，我们应该把当前的 EVENT 节点变为 COMBAT
            # 且为了守恒，应该移除未来队列中的一个 COMBAT (如果实现复杂，暂且忽略移除，仅触发战斗)
            st.session_state.game_map.current_node.type = NodeType.COMBAT
            
            # v6.0 守恒定律：消耗一次未来的小怪配额 (从队列中移除一个 COMBAT)
            # 这样总战斗数保持不变 (10场)
            game_map = st.session_state.game_map
            if NodeType.COMBAT in game_map.node_queue[game_map.floor:]:
                 # 在剩余队列中找到第一个 COMBAT 并移除
                 # 注意 game_map.node_queue 是全量队列， game_map.floor 是当前索引
                 # 我们要移除 index >= floor 的第一个 COMBAT
                 for i in range(game_map.floor, len(game_map.node_queue)):
                     if game_map.node_queue[i] == NodeType.COMBAT:
                         game_map.node_queue.pop(i)
                         # 补一个 Filler (Event/Rest) 以保持总层数? 
                         # 用户没说，但保持层数一致比较好，或者层数减一？
                         # "Consist of exactly 10..."
                         # 如果移除了，那总层数变少。
                         # 我们补一个 EVENT 吧
                         game_map.node_queue.insert(i, NodeType.EVENT)
                         st.toast("⚠️ 未来的某场战斗被提前了...", icon="⚔️")
                         break
            
            del st.session_state.adv_loot_result
            st.session_state.event_subphase = None
            resolve_node_callback()
            st.rerun()
            
    elif result == "cards":
        st.success("💰 颇有收获！你发现了三张遗落的卡牌...")
        cards = st.session_state.get('adv_cards', [])
        
        cols = st.columns(3)
        for i, card in enumerate(cards):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"### {card.icon} {card.word}")
                    st.caption(card.meaning)
                    if st.button("拿走", key=f"loot_{i}"):
                        player.add_card_to_deck(card)
                        st.toast(f"获得了 {card.word}!", icon="🎉")
                        del st.session_state.adv_loot_result
                        if 'adv_cards' in st.session_state: del st.session_state.adv_cards
                        st.session_state.event_subphase = None
                        player.advance_room()
                        resolve_node_callback()
                        st.rerun()

def _render_mysterious_book(resolve_node_callback):
    """神秘书籍：分歧点"""
    player = st.session_state.player
    st.markdown("你翻阅书页，命运在暗中掷骰。")

    if st.button("翻阅"):
        if random.random() < 0.5:
            st.markdown("### 💀 诅咒之门")
            if random.random() < 0.5:
                for c in player.deck:
                    c.is_blackened = True
                    c.temp_level = "black"
                st.error("👿 整个卡组被黑暗侵蚀了！")
            else:
                st.success("🛡️ 你抵挡住了精神攻击，什么也没发生。")
        else:
            st.markdown("### 💰 贪婪之理")
            player.gold *= 2
            # 记录贪婪 Buff (增加一个受损翻倍的状态)
            # 后续需要在 change_hp 中检测此状态
            st.session_state._greedy_curse = True
            st.warning("🤑 财富涌入，但你的灵魂变得脆弱。")

        _pause(1.5)
        st.session_state.event_subphase = None
        player.advance_room()
        resolve_node_callback()
        st.rerun()


def render_shop(resolve_node_callback: Callable):
    """商店 v6.0"""
    st.header("🏪 商店")
    player = st.session_state.player
    st.caption(f"当前金币 {player.gold}")

    if 'shop_items' not in st.session_state or not isinstance(st.session_state.shop_items, dict) or 'relic_slot' not in st.session_state.shop_items:
        st.session_state.shop_items = ShopRegistry.get_shop_inventory(total_slots=4, relic_chance=0.2)

    inventory = st.session_state.shop_items
    relic_slot = inventory.get('relic_slot')
    other_slots = inventory.get('other_slots', [])

    if relic_slot:
        st.subheader("圣遗物")
        cols = st.columns(1)
        for i, (item_id, item) in enumerate([relic_slot]):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"### {item.icon} {item.name}")
                    st.caption(item.description)
                    st.markdown(f"{item.price} 金币")

                    can_buy = player.gold >= item.price
                    if st.button("购买", key=f"relic_{item_id}", disabled=not can_buy):
                        player.gold -= item.price
                        if item.effect == 'grant_relic':
                            player.relics.append(item.value)
                            st.toast("获得圣遗物")
                        st.rerun()

    st.subheader("道具 / 随机遗物")
    if not other_slots:
        st.info("暂无商品")
    else:
        cols = st.columns(len(other_slots))
        for i, (item_id, item) in enumerate(other_slots):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"### {item.icon} {item.name}")
                    st.caption(item.description)
                    st.markdown(f"{item.price} 金币")

                    can_buy = player.gold >= item.price
                    if st.button("购买", key=f"shop_{item_id}", disabled=not can_buy):
                        player.gold -= item.price
                        if item.consumable:
                            player.inventory.append(item_id)
                            st.toast("已放入背包")
                        else:
                            if item.effect == 'heal':
                                player.change_hp(item.value)
                            elif item.effect == 'max_hp':
                                player.max_hp += item.value
                                player.hp = min(player.hp + item.value, player.max_hp)
                                st.toast(f"最大生命 +{item.value}")
                            elif item.effect == 'grant_relic':
                                player.relics.append(item.value)
                                st.toast("获得圣遗物")
                            elif item.effect == 'relic':
                                player.relics.append(item.value)
                        st.rerun()

    st.subheader("卡牌购买")
    st.caption("购买后从卡池中选择一张加入牌组")

    card_cols = st.columns(3)

    with card_cols[0]:
        red_count = player.purchase_counts.get("red", 0)
        red_price = ShopRegistry.get_card_price("red", red_count)
        with st.container(border=True):
            st.markdown("### 红卡")
            st.caption(f"价格：{red_price} 金币")
            can_buy_red = player.gold >= red_price
            if st.button(f"购买 ({red_price} 金币)", key="buy_red_card", disabled=not can_buy_red):
                player.gold -= red_price
                player.purchase_counts["red"] = red_count + 1
                st.session_state.pending_card_purchase = "red"
                st.toast("请选择一张红卡加入牌组", icon="🟥")
                st.rerun()

    with card_cols[1]:
        blue_count = player.purchase_counts.get("blue", 0)
        blue_price = ShopRegistry.get_card_price("blue", blue_count)
        with st.container(border=True):
            st.markdown("### 蓝卡")
            st.caption(f"价格：{blue_price} 金币")
            can_buy_blue = player.gold >= blue_price
            if st.button(f"购买 ({blue_price} 金币)", key="buy_blue_card", disabled=not can_buy_blue):
                player.gold -= blue_price
                player.purchase_counts["blue"] = blue_count + 1
                st.session_state.pending_card_purchase = "blue"
                st.toast("请选择一张蓝卡加入牌组", icon="🟦")
                st.rerun()

    with card_cols[2]:
        gold_price = ShopRegistry.get_card_price("gold", 0)
        with st.container(border=True):
            st.markdown("### 金卡")
            st.caption("每局限购 1 次")
            can_buy_gold = player.gold >= gold_price and not player.purchase_counts.get("gold", 0) > 0
            status = "已售罄" if player.purchase_counts.get("gold", 0) > 0 else f"{gold_price} 金币"
            if st.button(f"购买 ({status})", key="buy_gold_card", disabled=not can_buy_gold):
                player.gold -= gold_price
                player.purchase_counts["gold"] = 1
                st.session_state.pending_card_purchase = "gold"
                st.toast("请选择一张金卡加入牌组", icon="🟨")
                st.rerun()

    if st.button("离开商店", use_container_width=True):
        if 'shop_items' in st.session_state:
            del st.session_state.shop_items
        player.advance_room()
        resolve_node_callback()

def render_rest(resolve_node_callback: Callable):
    """营地 v6.0"""
    st.header("🔥 铁匠营地")
    player = st.session_state.player
    
    if st.session_state.get('rest_phase') == 'upgrade':
        _render_camp_upgrade(resolve_node_callback)
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown("### 😴 休息")
            st.caption("恢复 30 生命")
            if st.button("选择休息", use_container_width=True):
                player.change_hp(30)
                player.advance_room()
                resolve_node_callback()
                st.rerun()

    with col2:
        with st.container(border=True):
            st.markdown("### ⚒️ 铁匠加持")
            st.caption("100金币 → 蓝卡获得回血增益")
            can_afford = player.gold >= 100 and not player.blue_card_heal_buff
            btn_text = "已拥有" if player.blue_card_heal_buff else "支付 100金币"
            if st.button(btn_text, disabled=not can_afford, use_container_width=True):
                player.gold -= 100
                player.blue_card_heal_buff = True
                st.success("⚒️ 蓝卡已升级！答对时额外回复 5 生命")
                count = 0
                for c in player.deck:
                    if c.card_type == CardType.BLUE_HYBRID:
                        c.is_temporary_buffed = True
                        count += 1
                st.success(f"🔨 强化成功！{count} 张蓝卡获得回血增益")
                _pause(1.5)
                player.advance_room()
                resolve_node_callback()
                st.rerun()

    with col3:
        with st.container(border=True):
            st.markdown("### 🆙 词汇淬炼")
            st.caption("通过拼写测试，永久提升卡牌阶级")
            if st.button("开始挑战", use_container_width=True):
                st.session_state.rest_phase = 'upgrade'
                st.rerun()

def _render_camp_upgrade(resolve_node_callback):
    """营地卡牌升阶逻辑"""
    st.subheader("🆙 词汇淬炼")
    player = st.session_state.player

    if st.button("结束锻造", use_container_width=True):
        if 'upgrade_target' in st.session_state:
            del st.session_state.upgrade_target
        st.session_state.rest_phase = None
        player.advance_room()
        resolve_node_callback()
        st.rerun()
    
    # 选择要升级的卡牌
    upgradable = [c for c in player.deck if c.tier < 4] # 金卡无法再升
    if not upgradable:
        st.warning("无可升级的卡牌！")
        if st.button("取消"):
            st.session_state.rest_phase = None
            st.rerun()
        return

    if 'upgrade_target' not in st.session_state:
        st.markdown("选择一张卡牌进行挑战 (拼写正确即可永久升阶)")
        cols = st.columns(min(4, len(upgradable)))
        for i, card in enumerate(upgradable[:8]):
            with cols[i % 4]:
                if st.button(f"{card.word} ({card.card_type.icon})", key=f"up_sel_{i}"):
                    st.session_state.upgrade_target = card
                    st.rerun()
    else:
        card = st.session_state.upgrade_target
        st.markdown(f"### 请输入单词: **{card.meaning}**")
        ans = st.text_input("拼写:").strip()
        
        if st.button("确认提交", type="primary"):
            if ans.lower() == card.word.lower():
                # 永久升阶
                card.tier = min(4, card.tier + 2) # 红(0)->蓝(2)->金(4)
                _count_upgrade_for_red_reward()
                st.success(f"🎊 成功！{card.word} 已永久升级！")
                del st.session_state.upgrade_target
                _pause(1.0)
                st.rerun()
            else:
                st.error("❌ 拼写错误，挑战失败！")
                st.session_state.rest_phase = None
                del st.session_state.upgrade_target
                player.advance_room()
                _pause(1.5)
                resolve_node_callback()
                st.rerun()
        
        if st.button("取消"):
             del st.session_state.upgrade_target
             st.rerun()


def render_tower_prep(complete_callback: Callable):
    """爬塔准备阶段 v6.0"""
    st.header("🏔️ 爬塔准备")

    st.subheader("初始圣遗物（三选一）")
    starter_relics = [
        (
            "START_BURNING_BLOOD",
            "燃烧之血",
            "生命<50：红卡伤害与反噬 +50%；红卡答对吸血 5；出牌后手牌为 0 且最后一张为红卡时抽 2（红优先）",
        ),
        (
            "PAIN_ARMOR",
            "苦痛之甲",
            "蓝卡护甲 +50%；所有回血 -50%；非蓝卡反噬 -50%；出牌后手牌为 0 且最后一张为蓝卡时抽 2（优先红+蓝）",
        ),
        (
            "WIZARD_HAT",
            "巫师之帽",
            "红/蓝正向效果 -30%（反噬不变）；金卡效果翻倍；金卡耐久=2；圣遗物数值效果翻倍；金卡后额外出牌 1 次",
        ),
    ]

    if "starter_relic_choice" not in st.session_state:
        st.session_state.starter_relic_choice = None

    cols = st.columns(3)
    for i, (rid, name, desc) in enumerate(starter_relics):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{name}**")
                st.caption(desc)
                if st.button("选择", key=f"starter_relic_{rid}"):
                    st.session_state.starter_relic_choice = rid

    if st.session_state.starter_relic_choice:
        selected_name = next(
            (name for rid, name, _ in starter_relics if rid == st.session_state.starter_relic_choice),
            st.session_state.starter_relic_choice,
        )
        st.info(f"已选择：{selected_name}")

    st.divider()

    pool = st.session_state.get('full_draft_pool', [])
    from config import INITIAL_DECK_SIZE
    limit = INITIAL_DECK_SIZE

    st.markdown("### 组建初始牌组")
    st.info(f"目标：{limit} 张 | 已选择 {len(st.session_state.get('prep_selected_indices', set()))} 张")

    if 'prep_selected_indices' not in st.session_state:
        st.session_state.prep_selected_indices = set(range(min(len(pool), limit)))

    selected_indices = st.session_state.prep_selected_indices

    c_red = 0
    c_blue = 0
    c_gold = 0

    for idx in selected_indices:
        if idx < len(pool):
            c = pool[idx]
            if c.card_type == CardType.RED_BERSERK:
                c_red += 1
            elif c.card_type == CardType.BLUE_HYBRID:
                c_blue += 1
            elif c.card_type == CardType.GOLD_SUPPORT:
                c_gold += 1

    c1, c2, c3 = st.columns(3)
    c1.metric("红卡", f"{c_red}")
    c2.metric("蓝卡", f"{c_blue}")
    c3.metric("金卡", f"{c_gold}")

    st.divider()

    cols = st.columns(4)
    for i, card in enumerate(pool):
        with cols[i % 4]:
            is_sel = i in selected_indices
            btn_type = "primary" if is_sel else "secondary"

            can_toggle = True
            if not is_sel and len(selected_indices) >= limit:
                can_toggle = False

            if st.button(f"{card.card_type.icon} {card.word}", key=f"tprep_{i}", type=btn_type, disabled=(not is_sel and not can_toggle)):
                if is_sel:
                    selected_indices.remove(i)
                else:
                    selected_indices.add(i)
                st.rerun()

    st.divider()

    has_relic_choice = bool(st.session_state.get("starter_relic_choice"))
    is_valid = (len(selected_indices) == limit) and has_relic_choice

    if st.button("✅ 开始爬塔", type="primary", disabled=not is_valid, use_container_width=True):
        selected_cards = [pool[i] for i in selected_indices]
        remaining_cards = [pool[i] for i in range(len(pool)) if i not in selected_indices]

        chosen = st.session_state.get("starter_relic_choice")
        if chosen and chosen not in st.session_state.player.relics:
            st.session_state.player.relics.append(chosen)
        if "starter_relic_choice" in st.session_state:
            del st.session_state.starter_relic_choice
        complete_callback(selected_cards, remaining_cards)
