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
import html
from typing import Callable

from models import (
    GamePhase, NodeType, Player, BossState, 
    CardType, WordCard, Enemy, CombatPhase, CardCombatState, CARD_STATS
)
from state_utils import reset_combat_flags
from config import HAND_SIZE, ENEMY_HP_BASE, ENEMY_ATTACK, ENEMY_ACTION_TIMER, UI_PAUSE_EXTRA, SHOP_PRICE_SURCHARGE
from registries import EventRegistry, ShopRegistry
from systems.trigger_bus import TriggerBus, TriggerContext
from systems.combat_engine import CombatEngine
from systems.combat_events import CombatEvent
from systems.run_flow_utils import convert_event_node_to_combat, rollback_purchase_counts
from ai_service import CyberMind, MockGenerator, BossPreloader
from ui.components import (
    play_audio, render_word_card, render_card_slot, render_enemy,
    render_hand, render_learning_popup, render_quiz_test
)


def render_combat_events(events: list):
    for ev in events:
        level = getattr(ev, "level", "toast")
        text = getattr(ev, "text", "")
        icon = getattr(ev, "icon", None)
        if level == "success":
            st.success(text)
        elif level == "warning":
            st.warning(text)
        elif level == "error":
            st.error(text)
        else:
            st.toast(text, icon=icon)


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
        forced_enemy = st.session_state.get("forced_enemy")

        def _select_enemy():
            if forced_enemy:
                forced_enemy.is_elite = True
                return forced_enemy
            return Enemy(
                level=st.session_state.game_map.current_node.level,
                is_elite=(st.session_state.game_map.current_node.type == NodeType.ELITE),
            )

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
                    enemy=_select_enemy(),
                    deck=selected_deck
                )
        else:
            # 自动全带
            st.session_state.card_combat = CardCombatState(
                player=player,
                enemy=_select_enemy(),
                deck=player.deck.copy()
            )

        if forced_enemy:
            del st.session_state.forced_enemy

    cs = st.session_state.card_combat
    
    # v6.0 直接进入战斗，不再有 Loading 阶段
    if cs.phase == CombatPhase.LOADING:
        result = CombatEngine.start_battle(cs, player, st.session_state)
        render_combat_events(result.events)
        if result.should_rerun:
            st.rerun()
            return

    if cs.phase == CombatPhase.BATTLE:
        _render_battle_phase(cs, resolve_node_callback, check_death_callback)
    elif cs.phase == CombatPhase.VICTORY:
        st.balloons()

        is_elite = cs.enemy.is_elite

        if is_elite and st.session_state.get("elite_relic_pending"):
            _render_elite_relic_reward(cs, resolve_node_callback)
            return

        # 记录战斗完成
        game_map = st.session_state.get('game_map')
        if game_map and 'combat_recorded' not in st.session_state:
            game_map.record_combat_completed(NodeType.ELITE if is_elite else NodeType.COMBAT)
            st.session_state.combat_recorded = True

        if not st.session_state.get("combat_victory_rewarded"):
            reward_count = 2 if is_elite else 1
            reward_cards = _take_cards_from_pool(reward_count, prefer_red_only=True)
            if reward_cards:
                for card in reward_cards:
                    st.session_state.player.add_card_to_deck(card)
                st.toast(f"🎴 获得 {len(reward_cards)} 张红卡！", icon="🟥")
            else:
                st.info("词池中没有可用红卡")
            st.session_state.combat_victory_rewarded = True

            if is_elite:
                st.session_state.elite_relic_pending = True
                st.rerun()
                return

        if st.button("继续", type="primary", use_container_width=True):
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
    
    # 记录本局使用过的卡牌，供下局轮换
    if 'card_combat' in st.session_state:
        used_words = {c.word for c in st.session_state.card_combat.discard}
        used_words.update(c.word for c in st.session_state.card_combat.hand if hasattr(c, 'word'))
        st.session_state._last_used_cards = used_words
        del st.session_state.card_combat

    for key in ("combat_victory_rewarded", "reward_cards", "selected_rewards", "combat_recorded"):
        if key in st.session_state:
            del st.session_state[key]
    
    # 重置护甲
    st.session_state.player.armor = 0
    
    resolve_node_callback()


CURSED_RELIC_IDS = {"CURSED_BLOOD", "MONKEY_PAW", "UNDYING_CURSE", "CURSE_MASK"}


def _apply_relic_on_gain(player, relic_id: str):
    if relic_id in CURSED_RELIC_IDS:
        st.warning("你深深地感到不安")
    if relic_id == "UNDYING_CURSE":
        for c in player.deck:
            c.is_blackened = True
            c.temp_level = "black"
    if relic_id == "MONKEY_PAW":
        if player.max_hp > 50:
            player.max_hp = 50
            player.hp = min(player.hp, player.max_hp)


def _render_elite_relic_reward(cs: CardCombatState, resolve_node_callback: Callable):
    """精英怪圣遗物奖励"""
    from registries import RelicRegistry

    player = st.session_state.player
    st.subheader("🏵️ 精英圣遗物奖励")
    st.caption("从 3 个圣遗物中选择 1 个，可跳过")

    if 'elite_relic_choices' not in st.session_state:
        pool = [rid for rid in RelicRegistry.get_pool("high") if rid not in player.relics]
        if not pool:
            st.info("暂无可用圣遗物")
            _clear_elite_relic_state()
            _complete_combat_victory(cs, resolve_node_callback)
            return
        st.session_state.elite_relic_choices = random.sample(pool, min(3, len(pool)))

    choices = st.session_state.get('elite_relic_choices', [])
    if not choices:
        st.info("暂无可用圣遗物")
        _clear_elite_relic_state()
        _complete_combat_victory(cs, resolve_node_callback)
        return

    cols = st.columns(len(choices))
    for i, rid in enumerate(choices):
        relic = RelicRegistry.get(rid)
        if not relic:
            continue
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {relic.icon} {relic.name}")
                st.caption(relic.description)
                if st.button("选择", key=f"elite_relic_{rid}"):
                    player.relics.append(rid)
                    _apply_relic_on_gain(player, rid)
                    st.toast("获得圣遗物")
                    _clear_elite_relic_state()
                    _complete_combat_victory(cs, resolve_node_callback)
                    return

    if st.button("跳过", use_container_width=True):
        _clear_elite_relic_state()
        _complete_combat_victory(cs, resolve_node_callback)
        return


def _clear_elite_relic_state():
    if 'elite_relic_pending' in st.session_state:
        del st.session_state.elite_relic_pending
    if 'elite_relic_choices' in st.session_state:
        del st.session_state.elite_relic_choices


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
        st.info("词池中没有可用红卡")
        return False
    card = cards[0]
    st.session_state.player.add_card_to_deck(card)
    st.toast(f"获得红卡（{reason}）") if reason else st.toast("获得红卡")
    return True


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
        result = CombatEngine.resolve_enemy_turn(cs, player, st.session_state)
        render_combat_events(result.events)
        if result.player_dead and check_death_callback():
            return
        if result.enemy_dead:
            CombatEngine.advance_phase_if_victory(cs)
        st.rerun()
        return
    
    # 检查是否被眩晕
    if st.session_state.get('_player_stunned'):
        result = CombatEngine.resolve_stun_turn(cs, player, st.session_state)
        render_combat_events(result.events)
        if result.player_dead and check_death_callback():
            return
        if result.enemy_dead:
            CombatEngine.advance_phase_if_victory(cs)
        _pause(1)
        st.rerun()
        return
    
    if CombatEngine.advance_phase_if_victory(cs):
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
        draw_result = CombatEngine.auto_draw_if_empty(cs, st.session_state)
        if draw_result.events:
            render_combat_events(draw_result.events)
        if draw_result.should_rerun:
            st.rerun()
            return

        allowed_types = None
        if cs.extra_action_only_red:
            allowed_types = {CardType.RED_BERSERK}
        clicked = render_hand(cs.hand, on_play=True, allowed_types=allowed_types)
        if clicked is not None:
            card = cs.hand[clicked]
            play_result = CombatEngine.start_card_play(cs, player, card, st.session_state)
            if play_result.events:
                render_combat_events(play_result.events)
            if play_result.should_rerun:
                st.rerun()
                return
    else:
        st.caption(f"剩余手牌: {len(cs.hand)} | 弃牌堆: {len(cs.discard)}")


def _render_card_test(cs: CardCombatState, player, check_death_callback):
    """Card test"""
    card = cs.current_card
    options = CombatEngine.get_quiz_options(cs, st.session_state)

    st.markdown(f"### 🎴 {card.card_type.icon} {card.card_type.name_cn}卡")

    answer = render_quiz_test(card, options)

    if answer:
        db = st.session_state.get('db')
        player_id = st.session_state.db_player.get('id')
        current_room = player.current_room

        result = CombatEngine.process_answer(
            cs=cs,
            player=player,
            card=card,
            answer=answer,
            db=db,
            player_id=player_id,
            current_room=current_room,
            session_state=st.session_state,
        )
        render_combat_events(result.events)

        if result.player_dead and check_death_callback():
            return

        if result.enemy_dead:
            CombatEngine.advance_phase_if_victory(cs)

        if result.should_rerun:
            st.rerun()
            return

        if result.should_enemy_turn:
            if cs.enemy.is_dead():
                CombatEngine.advance_phase_if_victory(cs)
                st.rerun()
                return
            turn_result = CombatEngine.resolve_enemy_turn(cs, player, st.session_state)
            render_combat_events(turn_result.events)
            if turn_result.player_dead and check_death_callback():
                return
            if turn_result.enemy_dead:
                CombatEngine.advance_phase_if_victory(cs)
            _pause(1)
            st.rerun()
            return


# ==========================================
# 其他页面
# ==========================================

def _boss_article_content(article: dict) -> str:
    if not isinstance(article, dict):
        return ""
    return str(article.get("content") or article.get("article_english") or "")


def _boss_article_summary(article: dict) -> str:
    if not isinstance(article, dict):
        return ""
    return str(article.get("summary_cn") or article.get("article_chinese") or "")


def _normalize_boss_article(article: dict, words: list) -> dict:
    normalized = CyberMind.normalize_article_payload(article, words) if isinstance(article, dict) else None
    if normalized:
        return normalized
    return MockGenerator.generate_article(words)


def _normalize_boss_quizzes(quizzes: dict, words: list) -> dict:
    normalized = CyberMind.normalize_quiz_payload(quizzes) if isinstance(quizzes, dict) else None
    if normalized:
        return normalized
    return MockGenerator.generate_quiz(words)


def _build_boss_quiz_queue(quizzes: dict) -> list:
    vocab = list((quizzes or {}).get("vocab_attacks", []))
    reading = list((quizzes or {}).get("boss_ultimates", []))
    queue = []
    queue.extend(vocab[:3])
    queue.extend(reading[:2])

    if len(queue) < 5:
        extras = vocab[3:] + reading[2:]
        for item in extras:
            queue.append(item)
            if len(queue) >= 5:
                break

    if len(queue) < 5:
        fallback = MockGenerator.generate_quiz([])
        extras = fallback.get("vocab_attacks", []) + fallback.get("boss_ultimates", [])
        for item in extras:
            queue.append(item)
            if len(queue) >= 5:
                break

    return queue[:5]


def _boss_init_combat_state(bs: BossState) -> CardCombatState:
    if "boss_card_combat" in st.session_state:
        return st.session_state.boss_card_combat

    reset_combat_flags()
    player = st.session_state.player
    level = st.session_state.game_map.current_node.level if st.session_state.get("game_map") and st.session_state.game_map.current_node else 1
    enemy = Enemy(
        name="语法巨像",
        level=level,
        hp=bs.boss_hp,
        max_hp=bs.boss_max_hp,
        attack=bs.boss_attack_max,
        is_elite=True,
        is_boss=True,
        use_fixed_stats=True,
        fixed_attack=bs.boss_attack_max,
        fixed_timer=bs.boss_attack_interval,
        attack_interval=bs.boss_attack_interval,
    )
    st.session_state.boss_card_combat = CardCombatState(
        player=player,
        enemy=enemy,
        deck=player.deck.copy(),
    )
    return st.session_state.boss_card_combat


def _enforce_boss_death_lock(bs: BossState, cs: CardCombatState) -> bool:
    if cs.enemy.hp <= 0 and bs.quiz_asked < bs.death_lock_until_quiz_count:
        cs.enemy.hp = 1
        bs.boss_hp = 1
        bs.death_lock_active = True
        return True
    if bs.quiz_asked >= bs.death_lock_until_quiz_count:
        bs.death_lock_active = False
    return False


def _resolve_boss_enemy_turn(cs: CardCombatState, player: Player, bs: BossState):
    events = []
    if cs.bleed_turns > 0 and cs.bleed_damage > 0:
        cs.enemy.take_damage(cs.bleed_damage)
        cs.bleed_turns -= 1
        events.append(CombatEvent(level="toast", text=f"🩸 放血造成 {cs.bleed_damage} 伤害", icon="🩸"))

    interval = bs.frenzy_attack_interval if bs.frenzy_active else bs.boss_attack_interval
    interval = max(1, interval)
    attack_now = ((cs.turns + 1) % interval) == 0

    if attack_now and cs.enemy.hp > 0:
        low = bs.boss_attack_min + (bs.frenzy_attack_bonus if bs.frenzy_active else 0)
        high = bs.boss_attack_max + (bs.frenzy_attack_bonus if bs.frenzy_active else 0)
        damage = random.randint(low, high)
        player.change_hp(-damage)
        events.append(CombatEvent(level="warning", text=f"👹 首领攻击造成 {damage} 伤害"))

    cs.current_card = None
    cs.current_options = None
    cs.turns += 1
    bs.turn = cs.turns
    cs.nunchaku_used = False
    cs.extra_action_only_red = False
    return events


def _render_boss_skill_interrupt_panel(bs: BossState, cs: CardCombatState, check_death_callback: Callable) -> bool:
    quiz = bs.active_quiz or {}
    quiz_type = str(quiz.get("type", "vocab"))
    label = "词汇破绽" if quiz_type == "vocab" else "首领终极技"
    options = quiz.get("options") or []
    if not options:
        bs.active_quiz = None
        return False

    token = f"{bs.quiz_asked}-{cs.turns}"
    panel_class = "boss-skill-vocab" if quiz_type == "vocab" else "boss-skill-reading"
    question = html.escape(str(quiz.get("question", "")))
    st.markdown(
        f"""
<div class="boss-interrupt-mask" data-token="{token}">
  <div class="boss-interrupt-pulse"></div>
</div>
<div class="boss-interrupt-shell {panel_class}" data-token="{token}">
  <div class="boss-interrupt-card">
    <div class="boss-interrupt-alert">技能打断</div>
    <div class="boss-interrupt-meta">{label} · 第 {bs.quiz_asked + 1}/{bs.death_lock_until_quiz_count} 题</div>
    <div class="boss-interrupt-question">{question}</div>
    <div class="boss-interrupt-tip">技能处理中，暂不可出牌，请先完成应对。</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    choice = st.radio(
        "应对选项",
        options,
        key=f"boss_skill_choice_{bs.quiz_asked}_{cs.turns}",
        label_visibility="collapsed",
    )
    if st.button(
        "立即应对",
        type="primary",
        key=f"boss_skill_submit_{bs.quiz_asked}_{cs.turns}",
        use_container_width=True,
    ):
        player = st.session_state.player
        correct = choice == quiz.get("answer")
        if quiz_type == "vocab":
            if correct:
                damage = int(quiz.get("damage_to_boss", 20))
                cs.enemy.take_damage(damage)
                st.success(f"命中首领弱点，造成 {damage} 伤害")
            else:
                st.warning("未能命中首领弱点")
        else:
            if correct:
                st.success("成功识破首领终极技")
            else:
                damage = int(quiz.get("damage_to_player", 10))
                player.change_hp(-damage)
                st.error(f"终极技命中你，受到 {damage} 伤害")
                if check_death_callback():
                    return True

        bs.quiz_asked += 1
        bs.active_quiz = None
        bs.next_quiz_turn += bs.quiz_interval_turns
        if _enforce_boss_death_lock(bs, cs):
            st.warning("尚未读完其真名，首领强行维持形体！")

        if bs.quiz_asked >= bs.death_lock_until_quiz_count and cs.enemy.hp > 0:
            bs.frenzy_active = True
            st.warning("首领进入狂暴收尾阶段")

        if cs.enemy.hp <= 0 and bs.quiz_asked >= bs.death_lock_until_quiz_count:
            cs.phase = CombatPhase.VICTORY
            bs.phase = "victory"

        _pause(0.6)
        st.rerun()
        return True
    return False


def _render_boss_card_test(cs: CardCombatState, bs: BossState, check_death_callback: Callable) -> bool:
    player = st.session_state.player
    card = cs.current_card
    options = CombatEngine.get_quiz_options(cs, st.session_state)

    st.markdown(f"### 🎴 {card.card_type.icon} {card.card_type.name_cn}卡")
    answer = render_quiz_test(card, options)
    if not answer:
        return False

    db = st.session_state.get("db")
    player_id = st.session_state.db_player.get("id")
    current_room = player.current_room
    result = CombatEngine.process_answer(
        cs=cs,
        player=player,
        card=card,
        answer=answer,
        db=db,
        player_id=player_id,
        current_room=current_room,
        session_state=st.session_state,
    )
    render_combat_events(result.events)

    if result.player_dead and check_death_callback():
        return True

    if result.enemy_dead and _enforce_boss_death_lock(bs, cs):
        st.warning("尚未读完其真名，首领强行维持形体！")

    if result.should_rerun:
        st.rerun()
        return True

    if result.should_enemy_turn:
        events = _resolve_boss_enemy_turn(cs, player, bs)
        render_combat_events(events)
        if player.is_dead() and check_death_callback():
            return True
        if cs.enemy.hp <= 0 and _enforce_boss_death_lock(bs, cs):
            st.warning("尚未读完其真名，首领强行维持形体！")
        if cs.enemy.hp <= 0 and bs.quiz_asked >= bs.death_lock_until_quiz_count:
            cs.phase = CombatPhase.VICTORY
            bs.phase = "victory"
        _pause(0.6)
        st.rerun()
        return True

    return False


def render_boss(resolve_node_callback: Callable, check_death_callback: Callable):
    """首领战：卡牌战斗 + 定期出题技能"""
    player = st.session_state.player
    if "boss_state" not in st.session_state:
        boss_hp = max(120, len(player.deck) * 15)
        st.session_state.boss_state = BossState(boss_hp=boss_hp, boss_max_hp=boss_hp)

    bs: BossState = st.session_state.boss_state

    if bs.phase == "loading":
        cache = st.session_state.get("boss_article_cache")
        preloaded = BossPreloader.get_result()
        payload = cache or preloaded

        if payload:
            deck_words = [c.word for c in player.deck]
            bs.article = _normalize_boss_article(payload.get("article"), deck_words)
            bs.quizzes = _normalize_boss_quizzes(payload.get("quizzes"), deck_words)
            bs.quiz_queue = _build_boss_quiz_queue(bs.quizzes)
            bs.phase = "article"
            if preloaded:
                BossPreloader.reset()
            st.rerun()
            return

        if st.session_state.get("boss_generation_status") == "generating" or BossPreloader.is_loading():
            st.info("首领正在觉醒，正在准备故事与题目...")
            _pause(1)
            st.rerun()
            return

        deck_words = [c.word for c in player.deck]
        bs.article = _normalize_boss_article(None, deck_words)
        bs.quizzes = _normalize_boss_quizzes(None, deck_words)
        bs.quiz_queue = _build_boss_quiz_queue(bs.quizzes)
        bs.phase = "article"
        st.rerun()
        return

    if bs.phase == "article":
        content = _boss_article_content(bs.article)
        title = (bs.article or {}).get("title", "Boss Chronicle")
        summary_cn = _boss_article_summary(bs.article)
        st.markdown("## 👹 语法巨像")
        with st.expander("首领本体", expanded=True):
            st.markdown(f"### {title}")
            st.markdown(content)
            if summary_cn:
                st.caption(summary_cn)
            missing = (bs.article or {}).get("missing_words") or []
            if missing:
                st.caption(f"未覆盖词数: {len(missing)}")

        if st.button("⚔️ 准备战斗", type="primary"):
            bs.phase = "battle"
            bs.turn = 0
            bs.vocab_idx = 0
            bs.reading_idx = 0
            bs.quiz_asked = 0
            bs.next_quiz_turn = bs.quiz_interval_turns
            bs.active_quiz = None
            bs.death_lock_active = False
            bs.frenzy_active = False
            if "boss_card_combat" in st.session_state:
                del st.session_state.boss_card_combat
            st.rerun()
        return

    if bs.phase == "battle":
        cs = _boss_init_combat_state(bs)
        if cs.phase == CombatPhase.LOADING:
            result = CombatEngine.start_battle(cs, player, st.session_state)
            render_combat_events(result.events)
            if result.should_rerun:
                st.rerun()
            return

        bs.boss_hp = cs.enemy.hp
        bs.boss_max_hp = max(bs.boss_max_hp, cs.enemy.max_hp)
        if cs.enemy.hp <= 0 and _enforce_boss_death_lock(bs, cs):
            st.warning("尚未读完其真名，首领强行维持形体！")
        if cs.enemy.hp <= 0 and bs.quiz_asked >= bs.death_lock_until_quiz_count:
            bs.phase = "victory"
            st.rerun()
            return

        if bs.quiz_asked >= bs.death_lock_until_quiz_count and cs.enemy.hp > 0:
            bs.frenzy_active = True

        st.markdown("## 👹 语法巨像")
        st.progress(max(0, bs.boss_hp / bs.boss_max_hp), f"生命: {bs.boss_hp}/{bs.boss_max_hp}")
        st.caption(
            f"题目进度 {bs.quiz_asked}/{bs.death_lock_until_quiz_count} | 普攻间隔 {bs.boss_attack_interval} 回合"
        )
        if bs.frenzy_active:
            st.warning("狂暴阶段：攻击频率提升")

        if st.session_state.get("_end_turn_due_to_item"):
            st.session_state._end_turn_due_to_item = False
            events = _resolve_boss_enemy_turn(cs, player, bs)
            render_combat_events(events)
            if player.is_dead() and check_death_callback():
                return
            if cs.enemy.hp <= 0 and _enforce_boss_death_lock(bs, cs):
                st.warning("尚未读完其真名，首领强行维持形体！")
            if cs.enemy.hp <= 0 and bs.quiz_asked >= bs.death_lock_until_quiz_count:
                bs.phase = "victory"
            st.rerun()
            return

        if st.session_state.get("_player_stunned"):
            st.session_state._player_stunned = False
            st.warning("你被眩晕，跳过本回合")
            events = _resolve_boss_enemy_turn(cs, player, bs)
            render_combat_events(events)
            if player.is_dead() and check_death_callback():
                return
            if cs.enemy.hp <= 0 and _enforce_boss_death_lock(bs, cs):
                st.warning("尚未读完其真名，首领强行维持形体！")
            _pause(0.6)
            st.rerun()
            return

        if bs.active_quiz is None and cs.turns >= bs.next_quiz_turn and bs.quiz_asked < bs.death_lock_until_quiz_count:
            if not bs.quiz_queue:
                bs.quiz_queue = _build_boss_quiz_queue(bs.quizzes)
            if bs.quiz_queue:
                bs.active_quiz = bs.quiz_queue.pop(0)

        if bs.active_quiz:
            if _render_boss_skill_interrupt_panel(bs, cs, check_death_callback):
                return
            return

        col_left, col_right = st.columns([1, 2])
        with col_left:
            render_enemy(cs.enemy)
            st.markdown(f"**回合:** {cs.turns}")
            if cs.next_card_multiplier and cs.next_card_multiplier > 1:
                st.success(f"下一张数值 x{cs.next_card_multiplier}")
        with col_right:
            if cs.current_card:
                if _render_boss_card_test(cs, bs, check_death_callback):
                    return
            else:
                st.markdown("### 选择出牌")
                st.info("正常出牌。每 2 回合会触发一次首领技能问答。")

        st.divider()
        if not cs.current_card:
            draw_result = CombatEngine.auto_draw_if_empty(cs, st.session_state)
            if draw_result.events:
                render_combat_events(draw_result.events)
            if draw_result.should_rerun:
                st.rerun()
                return

            allowed_types = None
            if cs.extra_action_only_red:
                allowed_types = {CardType.RED_BERSERK}
            clicked = render_hand(cs.hand, on_play=True, allowed_types=allowed_types)
            if clicked is not None:
                card = cs.hand[clicked]
                play_result = CombatEngine.start_card_play(cs, player, card, st.session_state)
                if play_result.events:
                    render_combat_events(play_result.events)
                if play_result.should_rerun:
                    st.rerun()
                    return
        else:
            st.caption(f"剩余手牌: {len(cs.hand)} | 弃牌堆: {len(cs.discard)}")
        return

    if bs.phase == "victory":
        st.balloons()
        st.success("首领已被击败")
        if st.button("获取奖励（+100金币）", type="primary"):
            player.add_gold(100)
            player.advance_room()
            if "boss_card_combat" in st.session_state:
                del st.session_state.boss_card_combat
            resolve_node_callback()


def render_event(resolve_node_callback: Callable):
    """事件 v6.0"""
    node = st.session_state.game_map.current_node
    player = st.session_state.player
    has_cursed_blood = "CURSED_BLOOD" in player.relics
    has_undying_curse = "UNDYING_CURSE" in player.relics
    
    # 确保事件数据已加载或生成
    if 'event_data' not in node.data:
        # 优化随机算法：袋子机制 (Bag Randomization)
        # 避免重复遇到相同的事件，直到所有事件都遇到过一次
        if 'seen_events' not in st.session_state:
            st.session_state.seen_events = set()
            
        all_events = EventRegistry.get_all()
        available_ids = [eid for eid in all_events.keys() if eid not in st.session_state.seen_events]
        
        def _is_cursed_relic(relic_id: str) -> bool:
            from registries import RelicRegistry
            if relic_id in CURSED_RELIC_IDS:
                return True
            if "CURSE" in relic_id.upper():
                return True
            relic = RelicRegistry.get(relic_id)
            if relic and "诅咒" in relic.name:
                return True
            return False

        def _pick_event_id() -> str:
            nonlocal available_ids
            if not available_ids:
                st.session_state.seen_events = set()
                available_ids = list(all_events.keys())

            good_available = [eid for eid in available_ids if all_events[eid].category == "good"]
            bad_available = [eid for eid in available_ids if all_events[eid].category == "bad"]

            good_weight = 1
            bad_weight = 1

            last_type = st.session_state.get("last_node_type")
            if last_type in (NodeType.COMBAT, NodeType.ELITE):
                good_weight += 1

            non_combat_streak = st.session_state.game_map.non_combat_streak
            if non_combat_streak >= 2:
                bad_weight += (non_combat_streak - 1)

            if any(_is_cursed_relic(rid) for rid in player.relics):
                bad_weight += 1

            if good_available and bad_available:
                category = random.choices(["good", "bad"], weights=[good_weight, bad_weight], k=1)[0]
                pool = good_available if category == "good" else bad_available
                return random.choice(pool)
            if good_available:
                return random.choice(good_available)
            if bad_available:
                return random.choice(bad_available)

            st.session_state.seen_events = set()
            available_ids = list(all_events.keys())
            return random.choice(available_ids)

        event_id = _pick_event_id()
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
    elif subphase == "graveyard":
        _render_graveyard(resolve_node_callback)
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
                    if has_cursed_blood:
                        st.warning("诅咒之血：无法通过事件回血")
                    else:
                        player.change_hp(value)
                elif effect == "damage":
                    dmg = value
                    if has_undying_curse and dmg < 0:
                        dmg *= 2
                    player.change_hp(dmg)
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
                    if has_cursed_blood:
                        st.warning("诅咒之血：无法通过事件回血")
                    else:
                        player.hp = player.max_hp
                        st.success("💖 生命完全恢复！")
                elif effect == "relic":
                    if value == "random":
                        from registries import RelicRegistry
                        hp_loss = -20
                        if has_undying_curse:
                            hp_loss *= 2
                        player.change_hp(hp_loss)
                        pool = RelicRegistry.get_pool("low") + RelicRegistry.get_pool("high")
                        pool = [rid for rid in pool if rid not in player.relics]
                        if pool:
                            rid = random.choice(pool)
                            r = RelicRegistry.get(rid)
                            player.relics.append(rid)
                            _apply_relic_on_gain(player, rid)
                            st.toast(f"🎁 获得随机圣遗物: {r.name}", icon="🏆")
                        else:
                            st.info("暂无可用圣遗物")
                    else:
                        player.relics.append(value)
                        _apply_relic_on_gain(player, value)
                elif effect == "trade":
                    if isinstance(value, dict):
                        if "hp" in value:
                            hp_delta = value["hp"]
                            if hp_delta > 0 and has_cursed_blood:
                                st.warning("诅咒之血：无法通过事件回血")
                            else:
                                if has_undying_curse and hp_delta < 0:
                                    hp_delta *= 2
                                player.change_hp(hp_delta)
                        if "gold" in value:
                            player.add_gold(value["gold"])
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
                elif effect == "graveyard_enter":
                    st.session_state.event_subphase = "graveyard"
                    st.session_state.graveyard_explore_count = 0
                    st.rerun()
                    return
                elif effect == "risky_treasure":
                    bad_chance = 0.5
                    if has_undying_curse:
                        from registries import RelicRegistry
                        relic = RelicRegistry.get("UNDYING_CURSE")
                        effect_data = relic.effect if relic else {}
                        bad_chance = max(bad_chance, effect_data.get("bad_event_chance", 0.8))
                    if random.random() < bad_chance:
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
        bad_chance = 0.5
        if "UNDYING_CURSE" in player.relics:
            from registries import RelicRegistry
            relic = RelicRegistry.get("UNDYING_CURSE")
            effect_data = relic.effect if relic else {}
            bad_chance = max(bad_chance, effect_data.get("bad_event_chance", 0.8))
        if random.random() < bad_chance:
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
            convert_event_node_to_combat(st.session_state.game_map.current_node, NodeType.COMBAT)
            st.toast("⚠️ 事件战斗触发", icon="⚔️")
            
            del st.session_state.adv_loot_result
            st.session_state.event_subphase = None
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
        bad_chance = 0.5
        if "UNDYING_CURSE" in player.relics:
            from registries import RelicRegistry
            relic = RelicRegistry.get("UNDYING_CURSE")
            effect_data = relic.effect if relic else {}
            bad_chance = max(bad_chance, effect_data.get("bad_event_chance", 0.8))
        if random.random() < bad_chance:
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


def _clear_graveyard_state():
    if 'graveyard_explore_count' in st.session_state:
        del st.session_state.graveyard_explore_count
    st.session_state.event_subphase = None


def _render_graveyard(resolve_node_callback):
    """乱葬岗：可多次探究"""
    player = st.session_state.player
    st.subheader("🪦 乱葬岗")
    st.caption("阴风阵阵，你能感觉到某种东西在暗中凝视。")

    explore_count = st.session_state.get('graveyard_explore_count', 0)
    st.caption(f"已探究次数：{explore_count}")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("探究", key="graveyard_explore", use_container_width=True):
            explore_count += 1
            st.session_state.graveyard_explore_count = explore_count
            ghost_chance = min(0.15 + 0.10 * (explore_count - 1), 0.70)

            if random.random() < ghost_chance:
                st.error("👻 幽灵现身！")
                _pause(0.8)
                _clear_graveyard_state()
                st.session_state.game_map.current_node.type = NodeType.ELITE
                st.session_state.forced_enemy = Enemy(
                    name="幽灵",
                    level=st.session_state.game_map.current_node.level,
                    hp=999,
                    max_hp=999,
                    attack=10,
                    is_elite=True,
                    use_fixed_stats=True,
                    fixed_attack=10,
                    fixed_timer=2,
                    attack_interval=2,
                    max_turns=10,
                )
                st.rerun()
                return

            roll = random.random()
            if roll < 0.05:
                from registries import RelicRegistry
                pool = [rid for rid in RelicRegistry.get_pool("low") if rid not in player.relics]
                if pool:
                    rid = random.choice(pool)
                    relic = RelicRegistry.get(rid)
                    player.relics.append(rid)
                    _apply_relic_on_gain(player, rid)
                    name = relic.name if relic else rid
                    st.toast(f"🏆 发现圣遗物：{name}", icon="🪙")
                else:
                    st.info("暂无可用圣遗物")
            elif roll < 0.40:
                gold = random.randint(15, 20)
                player.add_gold(gold)
                st.toast(f"💰 发现金币：{gold}", icon="💰")
            else:
                st.info("什么也没发生。")

            _pause(0.6)
            st.rerun()
            return

    with col_b:
        if st.button("逃跑", key="graveyard_escape", use_container_width=True):
            _clear_graveyard_state()
            player.advance_room()
            resolve_node_callback()
            st.rerun()


def _clear_pending_card_purchase_state():
    for key in ("pending_card_purchase", "pending_card_price", "shop_card_choices", "shop_card_choice_type"):
        if key in st.session_state:
            del st.session_state[key]


def _rollback_pending_card_purchase(player, pending_type: str):
    refund = int(st.session_state.get("pending_card_price", 0) or 0)
    if refund > 0:
        player.gold += refund
    player.purchase_counts = rollback_purchase_counts(player.purchase_counts, pending_type)
    _clear_pending_card_purchase_state()


def _render_pending_card_purchase() -> bool:
    pending = st.session_state.get("pending_card_purchase")
    if not pending:
        return False

    player = st.session_state.player
    target_map = {
        "red": CardType.RED_BERSERK,
        "blue": CardType.BLUE_HYBRID,
        "gold": CardType.GOLD_SUPPORT,
    }
    target_type = target_map.get(pending)
    if target_type is None:
        _clear_pending_card_purchase_state()
        return False

    if (
        "shop_card_choices" not in st.session_state
        or st.session_state.get("shop_card_choice_type") != pending
    ):
        deck_words = {c.word for c in player.deck}
        pool = st.session_state.get("game_word_pool") or []
        candidates = [c for c in pool if c.card_type == target_type and c.word not in deck_words]
        random.shuffle(candidates)
        st.session_state.shop_card_choices = candidates[: min(6, len(candidates))]
        st.session_state.shop_card_choice_type = pending

    choices = st.session_state.get("shop_card_choices", [])
    st.subheader("卡牌购买：选择一张加入牌组")
    st.caption("已完成扣款，请从候选卡牌中选择 1 张。")

    if not choices:
        _rollback_pending_card_purchase(player, pending)
        st.warning("该颜色在词池中无可购买卡牌，已自动退款。")
        st.rerun()
        return True

    cols = st.columns(min(3, len(choices)))
    for i, card in enumerate(choices):
        with cols[i % len(cols)]:
            with st.container(border=True):
                st.markdown(f"### {card.card_type.icon} {card.word}")
                st.caption(card.meaning)
                st.caption(f"阶级: {card.tier}")
                if st.button("购买这张", key=f"pick_shop_card_{pending}_{i}", type="primary", use_container_width=True):
                    player.add_card_to_deck(card)
                    pool = st.session_state.get("game_word_pool") or []
                    removed = False
                    next_pool = []
                    for item in pool:
                        if not removed and item.word == card.word and item.tier == card.tier:
                            removed = True
                            continue
                        next_pool.append(item)
                    if not removed:
                        next_pool = [item for item in pool if item.word != card.word]
                    st.session_state.game_word_pool = next_pool
                    _clear_pending_card_purchase_state()
                    st.toast(f"已购入 {card.word}", icon="🎴")
                    st.rerun()
                    return True

    if st.button("取消购买并退款", key=f"cancel_shop_card_purchase_{pending}", use_container_width=True):
        _rollback_pending_card_purchase(player, pending)
        st.toast("已取消并退款", icon="↩️")
        st.rerun()
        return True

    return True


def render_shop(resolve_node_callback: Callable):
    """商店 v6.0"""
    st.header("🏪 商店")
    player = st.session_state.player
    st.caption(f"当前金币 {player.gold}")

    if st.session_state.get("pending_card_purchase"):
        _render_pending_card_purchase()
        return

    if 'shop_items' not in st.session_state or not isinstance(st.session_state.shop_items, dict) or 'relic_slots' not in st.session_state.shop_items:
        st.session_state.shop_items = ShopRegistry.get_shop_inventory(
            total_slots=4,
            relic_chance=0.2,
            exclude_relics=set(player.relics),
        )

    inventory = st.session_state.shop_items
    relic_slots = inventory.get('relic_slots', [])
    other_slots = inventory.get('other_slots', [])

    if relic_slots:
        st.subheader("圣遗物")
        cols = st.columns(len(relic_slots))
        for i, (item_id, item) in enumerate(relic_slots):
            with cols[i]:
                with st.container(border=True):
                    price = item.price + SHOP_PRICE_SURCHARGE
                    st.markdown(f"### {item.icon} {item.name}")
                    st.caption(item.description)
                    st.markdown(f"{price} 金币")

                    can_buy = player.gold >= price
                    if st.button("购买", key=f"relic_{item_id}", disabled=not can_buy):
                        player.gold -= price
                        if item.effect == 'grant_relic':
                            player.relics.append(item.value)
                            _apply_relic_on_gain(player, item.value)
                            st.toast("获得圣遗物")
                        # 买一个少一个，不补充
                        st.session_state.shop_items["relic_slots"] = [
                            pair for pair in relic_slots if pair[0] != item_id
                        ]
                        st.rerun()

    st.subheader("道具")
    if not other_slots:
        st.info("暂无商品")
    else:
        cols = st.columns(len(other_slots))
        for i, (item_id, item) in enumerate(other_slots):
            with cols[i]:
                with st.container(border=True):
                    price = item.price + SHOP_PRICE_SURCHARGE
                    st.markdown(f"### {item.icon} {item.name}")
                    st.caption(item.description)
                    st.markdown(f"{price} 金币")

                    can_buy = player.gold >= price
                    if st.button("购买", key=f"shop_{item_id}", disabled=not can_buy):
                        player.gold -= price
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
                                _apply_relic_on_gain(player, item.value)
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
                st.session_state.pending_card_price = red_price
                if "shop_card_choices" in st.session_state:
                    del st.session_state.shop_card_choices
                st.session_state.shop_card_choice_type = "red"
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
                st.session_state.pending_card_price = blue_price
                if "shop_card_choices" in st.session_state:
                    del st.session_state.shop_card_choices
                st.session_state.shop_card_choice_type = "blue"
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
                st.session_state.pending_card_price = gold_price
                if "shop_card_choices" in st.session_state:
                    del st.session_state.shop_card_choices
                st.session_state.shop_card_choice_type = "gold"
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
        st.markdown("选择一张卡牌进行挑战（仅显示中文释义，拼写正确即可永久升阶）")
        cols = st.columns(min(4, len(upgradable)))
        for i, card in enumerate(upgradable[:8]):
            with cols[i % 4]:
                if st.button(f"{card.meaning}", key=f"up_sel_{i}"):
                    st.session_state.upgrade_target = card
                    st.rerun()
    else:
        card = st.session_state.upgrade_target
        st.markdown(f"### 请输入单词: **{card.meaning}**")
        ans = st.text_input("拼写:").strip()
        
        if st.button("确认提交", type="primary"):
            if ans.lower() == card.word.lower():
                # 永久升阶
                old_tier = card.tier
                card.tier = min(4, card.tier + 2) # 红(0)->蓝(2)->金(4)
                db = st.session_state.db
                current_room = st.session_state.game_map.floor if st.session_state.get("game_map") else 0
                db.set_word_tier(
                    st.session_state.player.id,
                    card.word,
                    card.tier,
                    current_room,
                    priority="normal",
                )
                if old_tier in (2, 3) and card.tier >= 4:
                    _grant_red_card_from_pool("蓝升金")
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
    from registries import RelicRegistry
    starter_relics = RelicRegistry.get_pool("starter")

    if "starter_relic_choice" not in st.session_state:
        st.session_state.starter_relic_choice = None

    cols = st.columns(3)
    for i, rid in enumerate(starter_relics):
        relic = RelicRegistry.get(rid)
        if not relic:
            continue
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{relic.name}**")
                st.caption(relic.description)
                if st.button("选择", key=f"starter_relic_{rid}"):
                    st.session_state.starter_relic_choice = rid

    if st.session_state.starter_relic_choice:
        relic = RelicRegistry.get(st.session_state.starter_relic_choice)
        selected_name = relic.name if relic else st.session_state.starter_relic_choice
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
