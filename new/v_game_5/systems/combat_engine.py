# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional, List
import random

from models import CardType, WordCard, CardCombatState, CombatPhase
from registries import CardEffectRegistry, EffectContext
from systems.trigger_bus import TriggerBus, TriggerContext
from systems.combat_events import CombatEvent, CombatResult


class CombatEngine:
    @staticmethod
    def _emit(events, level: str, text: str, icon: str = None):
        events.append(CombatEvent(level=level, text=text, icon=icon))

    @staticmethod
    def _notify_factory(events):
        def notify(level: str, text: str, icon: str = None):
            CombatEngine._emit(events, level, text, icon)
        return notify

    @staticmethod
    def advance_phase_if_victory(cs: CardCombatState) -> bool:
        if cs.enemy.is_dead():
            cs.phase = CombatPhase.VICTORY
            return True
        return False

    @staticmethod
    def start_battle(cs: CardCombatState, player, session_state: Dict[str, Any]) -> CombatResult:
        events = []
        notify = CombatEngine._notify_factory(events)
        cs.start_battle()
        TriggerBus.trigger(
            "on_combat_start",
            TriggerContext(player=player, enemy=cs.enemy, combat_state=cs, notify=notify),
        )
        if "OLD_ARMOR" in getattr(player, "relics", []):
            player.add_armor(5, notify=notify)
        cs.ensure_black_in_hand()
        while len(cs.hand) < cs.hand_size:
            cs.draw_card()
        return CombatResult(events=events, should_rerun=True)

    @staticmethod
    def record_play(cs: CardCombatState, pre_type: CardType, relics: list):
        if pre_type == CardType.RED_BERSERK:
            cs.red_streak += 1
            cs.blue_streak = 0
            if cs.agang_active:
                cs.agang_red_count += 1
        elif pre_type == CardType.BLUE_HYBRID:
            cs.blue_streak += 1
            cs.red_streak = 0
            if cs.agang_active:
                cs.agang_active = False
                cs.agang_red_count = 0
        elif pre_type == CardType.GOLD_SUPPORT:
            cs.red_streak = 0
            cs.blue_streak = 0
            if "AGANG_WRATH" in relics:
                cs.agang_active = True
                cs.agang_red_count = 0
        else:
            cs.red_streak = 0
            cs.blue_streak = 0
            if cs.agang_active:
                cs.agang_active = False
                cs.agang_red_count = 0

        if pre_type in (CardType.RED_BERSERK, CardType.BLUE_HYBRID, CardType.GOLD_SUPPORT):
            cs.color_sequence.append(pre_type)
            if len(cs.color_sequence) > 3:
                cs.color_sequence = cs.color_sequence[-3:]
        else:
            cs.color_sequence = []

    @staticmethod
    def apply_correct_combo_effects(cs: CardCombatState, player, enemy, relics: list, pre_type: CardType, events, notify):
        if pre_type == CardType.RED_BERSERK:
            if "BLEEDING_DAGGER" in relics and cs.red_streak >= 2:
                cs.bleed_damage = (cs.red_streak - 1) * 2
                cs.bleed_turns = 2
                CombatEngine._emit(events, "toast", f"🩸 放血：造成 {cs.bleed_damage} 伤害，持续 2 回合")
            if (
                "SCHOLAR_WRATH" in relics
                and cs.color_sequence == [CardType.GOLD_SUPPORT, CardType.BLUE_HYBRID, CardType.RED_BERSERK]
            ):
                enemy.take_damage(10)
                CombatEngine._emit(events, "toast", "📘 博学者之怒：直接造成 10 伤害")
            if "NUNCHAKU" in relics and not cs.nunchaku_used:
                cs.extra_actions += 1
                cs.extra_action_only_red = True
                cs.nunchaku_used = True
                CombatEngine._emit(events, "toast", "🥋 双截棍：获得 1 次额外红卡行动")
        elif pre_type == CardType.BLUE_HYBRID:
            if "OLD_ARMOR" in relics and cs.blue_streak >= 2:
                player.add_armor(5, notify=notify)

    @staticmethod
    def _take_cards_from_pool(session_state: Dict[str, Any], count: int, prefer_red_only: bool = False) -> list:
        pool = session_state.get("game_word_pool") or []
        deck_words = {c.word for c in session_state.player.deck}
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

        session_state.game_word_pool = pool
        return picked

    @staticmethod
    def _grant_red_card_from_pool(session_state: Dict[str, Any], events, reason: str = "") -> bool:
        cards = CombatEngine._take_cards_from_pool(session_state, 1, prefer_red_only=True)
        if not cards:
            CombatEngine._emit(events, "toast", "词池中没有可用红卡")
            return False
        card = cards[0]
        session_state.player.add_card_to_deck(card)
        msg = f"获得红卡（{reason}）" if reason else "获得红卡"
        CombatEngine._emit(events, "toast", msg, "🟥")
        return True

    @staticmethod
    def _set_current_options(cs: CardCombatState, card: WordCard) -> list:
        all_words = [c.word for c in cs.word_pool if c.word != card.word]
        pick_count = min(3, len(all_words))
        options = random.sample(all_words, pick_count) if pick_count > 0 else []
        options.append(card.word)
        random.shuffle(options)
        cs.current_options = options
        return options

    @staticmethod
    def auto_draw_if_empty(cs: CardCombatState, session_state: Dict[str, Any]) -> CombatResult:
        events = []
        if cs.current_card or len(cs.hand) > 0:
            return CombatResult(events=events)

        drawn = cs.draw_card()
        if drawn:
            CombatEngine._emit(events, "toast", "♻️ 弃牌堆已洗回，自动抽牌！", "🔄")
            return CombatResult(events=events, should_rerun=True)

        CombatEngine._emit(events, "warning", "⚠️ 无牌可抽！战斗陷入僵局...")
        return CombatResult(events=events, should_rerun=False)

    @staticmethod
    def start_card_play(cs: CardCombatState, player, card: WordCard, session_state: Dict[str, Any]) -> CombatResult:
        events = []
        removed = cs.play_card(card)
        if removed:
            CombatEngine._grant_red_card_from_pool(session_state, events, "金卡耐久耗尽")

        relics = getattr(player, "relics", [])
        if session_state.get("in_game_streak") is None:
            session_state.in_game_streak = {}
        if len(cs.hand) == 0:
            if card.card_type == CardType.RED_BERSERK and "START_BURNING_BLOOD" in relics and player.hp < 50:
                cs.draw_with_preference([CardType.RED_BERSERK], 2)
            elif card.card_type == CardType.BLUE_HYBRID and "PAIN_ARMOR" in relics:
                drawn = []
                drawn += cs.draw_with_preference([CardType.RED_BERSERK], 1)
                drawn += cs.draw_with_preference([CardType.BLUE_HYBRID], 1)
                if len(drawn) < 2:
                    cs.draw_with_preference([CardType.RED_BERSERK, CardType.BLUE_HYBRID], 2 - len(drawn))

        CombatEngine._set_current_options(cs, card)
        return CombatResult(events=events, should_rerun=True)

    @staticmethod
    def get_quiz_options(cs: CardCombatState, session_state: Dict[str, Any]) -> list:
        options = cs.current_options or []
        if not cs.current_card:
            return options

        hint_left = session_state.get("_item_hint", 0)
        if hint_left > 0 and options:
            wrong_opts = [o for o in options if o != cs.current_card.word]
            if wrong_opts:
                remove_count = 2 if len(wrong_opts) >= 2 else 1
                to_remove = random.sample(wrong_opts, remove_count)
                options = [o for o in options if o not in to_remove]
                cs.current_options = options
            session_state._item_hint = max(0, hint_left - 1)

        return options

    @staticmethod
    def process_answer(
        cs: CardCombatState,
        player,
        card: WordCard,
        answer: str,
        db,
        player_id: Optional[int],
        current_room: int,
        session_state: Dict[str, Any],
    ) -> CombatResult:
        events = []
        notify = CombatEngine._notify_factory(events)
        pre_type = card.card_type
        correct = answer == card.word
        word = card.word
        relics = getattr(player, "relics", [])
        old_tier = card.tier
        rewarded_this_answer = False

        CombatEngine.record_play(cs, pre_type, relics)

        agang_triggered = bool(
            "AGANG_WRATH" in relics
            and cs.agang_active
            and cs.agang_red_count >= 3
            and pre_type == CardType.RED_BERSERK
        )

        # 更新数据库进度
        result = None
        if db and player_id:
            result = db.update_word_progress(player_id, card.word, correct, current_room)
            if result and result.get("upgraded"):
                CombatEngine._emit(events, "success", f"🌟 {card.word} 升级！")
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
                    if not rewarded_this_answer and old_tier in (2, 3) and new_tier >= 4:
                        CombatEngine._grant_red_card_from_pool(session_state, events, "蓝升金")
                        rewarded_this_answer = True

        def apply_permanent_tier(new_tier: int, level: str, label: str, icon: str):
            card.tier = new_tier
            if not card.is_blackened:
                card.temp_level = None
            for c in player.deck:
                if c.word == card.word:
                    c.tier = new_tier
                    if not c.is_blackened:
                        c.temp_level = None
            if db and player_id:
                db.set_word_tier(player_id, card.word, new_tier, current_room)
            CombatEngine._emit(events, level, label, icon)

        if correct:
            CombatEngine._emit(events, "success", "✅ 正确！")
            ctx = EffectContext(
                player=player,
                enemy=cs.enemy,
                cs=cs,
                card=card,
                events=events,
                notify=notify,
            )
            CardEffectRegistry.apply_effect(card.card_type.name, ctx, correct=True)
            TriggerBus.trigger(
                "on_correct_answer",
                TriggerContext(player=player, enemy=cs.enemy, card=card, combat_state=cs, notify=notify),
            )

            if card.is_blackened or card.card_type == CardType.BLACK_CURSE:
                black_streak = session_state.get("black_correct_streak", {})
                black_streak[word] = black_streak.get(word, 0) + 1
                if black_streak[word] >= 5:
                    if card in player.deck:
                        player.deck.remove(card)
                    cs._remove_from_all_piles(card)
                    cs.word_pool = [c for c in cs.word_pool if c.word != word]
                    CombatEngine._grant_red_card_from_pool(session_state, events, "黑卡净化")
                    del black_streak[word]
                    CombatEngine._emit(events, "success", f"✅ 黑卡净化成功，已从本局移除：{word}")
                    cs.current_card = None
                    cs.current_options = None
                session_state.black_correct_streak = black_streak

            card.wrong_streak = 0

            CombatEngine.apply_correct_combo_effects(cs, player, cs.enemy, relics, pre_type, events, notify)

            from config import RED_TO_BLUE_UPGRADE_THRESHOLD, BLUE_TO_GOLD_UPGRADE_THRESHOLD
            streak = session_state.get("in_game_streak")
            streak[word] = streak.get(word, 0) + 1
            db_upgraded = bool(result and result.get("upgraded"))

            if pre_type == CardType.RED_BERSERK:
                if not db_upgraded and streak[word] >= RED_TO_BLUE_UPGRADE_THRESHOLD:
                    apply_permanent_tier(2, "toast", f"升级为蓝卡：{word}", "🟦")
                    streak[word] = 0
            elif pre_type == CardType.BLUE_HYBRID:
                if not db_upgraded and streak[word] >= BLUE_TO_GOLD_UPGRADE_THRESHOLD:
                    apply_permanent_tier(4, "toast", f"升级为金卡：{word}", "🟨")
                    if not rewarded_this_answer:
                        CombatEngine._grant_red_card_from_pool(session_state, events, "蓝升金")
                        rewarded_this_answer = True
                    streak[word] = 0
        else:
            CombatEngine._emit(events, "error", f"❌ 错误！正确答案：{card.word}")
            ctx = TriggerContext(player=player, enemy=cs.enemy, card=card, combat_state=cs, notify=notify)
            TriggerBus.trigger("on_wrong_answer", ctx)
            if not ctx.data.get("negate_wrong_penalty"):
                effect_ctx = EffectContext(
                    player=player,
                    enemy=cs.enemy,
                    cs=cs,
                    card=card,
                    events=events,
                    notify=notify,
                )
                CardEffectRegistry.apply_effect(card.card_type.name, effect_ctx, correct=False)

            if card.is_blackened or card.card_type == CardType.BLACK_CURSE:
                black_streak = session_state.get("black_correct_streak", {})
                black_streak[word] = 0
                session_state.black_correct_streak = black_streak

            if not card.is_blackened:
                card.wrong_streak += 1

                ctype = card.card_type
                if ctype == CardType.GOLD_SUPPORT and card.wrong_streak >= 1:
                    apply_permanent_tier(2, "warning", "🌟 金卡遗忘，降级为蓝卡", "🟦")
                    card.wrong_streak = 0
                elif ctype == CardType.BLUE_HYBRID and card.wrong_streak >= 2:
                    apply_permanent_tier(0, "warning", "🌟 蓝卡遗忘，降级为红卡", "🟥")
                    card.wrong_streak = 0
                elif ctype == CardType.RED_BERSERK and card.wrong_streak >= 2:
                    card.is_blackened = True
                    card.temp_level = "black"
                    CombatEngine._emit(events, "error", "💥 红卡黑化！变为诅咒卡")
                    card.wrong_streak = 0

            if cs.enemy.is_elite and random.random() < 0.33:
                session_state._player_stunned = True

            streak = session_state.get("in_game_streak")
            if streak is not None and card.word in streak:
                streak[card.word] = 0

        cs.last_card_type = pre_type
        if agang_triggered:
            cs.agang_active = False
            cs.agang_red_count = 0

        if cs.extra_actions > 0:
            cs.extra_actions -= 1
            if cs.extra_action_only_red:
                cs.extra_action_only_red = False
            cs.current_card = None
            cs.current_options = None
            return CombatResult(
                events=events,
                enemy_dead=cs.enemy.is_dead(),
                player_dead=player.is_dead(),
                should_rerun=True,
                should_enemy_turn=False,
            )

        return CombatResult(
            events=events,
            enemy_dead=cs.enemy.is_dead(),
            player_dead=player.is_dead(),
            should_rerun=False,
            should_enemy_turn=True,
        )

    @staticmethod
    def resolve_enemy_turn(cs: CardCombatState, player, session_state: Dict[str, Any]) -> CombatResult:
        events = []
        notify = CombatEngine._notify_factory(events)

        if session_state.get("_end_turn_due_to_item"):
            session_state._end_turn_due_to_item = False

        if cs.bleed_turns > 0 and cs.bleed_damage > 0:
            cs.enemy.take_damage(cs.bleed_damage)
            cs.bleed_turns -= 1
            CombatEngine._emit(events, "toast", f"🩸 放血造成 {cs.bleed_damage} 伤害")
            if cs.enemy.is_dead():
                cs.current_card = None
                cs.current_options = None
                cs.turns += 1
                return CombatResult(events=events, enemy_dead=True, player_dead=player.is_dead(), should_rerun=True)

        intent = cs.enemy.tick()
        if intent == "dead":
            cs.current_card = None
            cs.current_options = None
            cs.turns += 1
            cs.nunchaku_used = False
            cs.extra_action_only_red = False
            return CombatResult(
                events=events,
                enemy_dead=True,
                player_dead=player.is_dead(),
                should_rerun=True,
            )
        if intent == "attack":
            damage = cs.enemy.attack
            if session_state.get("_item_shield", False):
                session_state._item_shield = False
                damage = 0
                CombatEngine._emit(events, "toast", "🛡️ 护盾抵消了本次攻击", "🛡️")
            else:
                reduce = session_state.get("_item_damage_reduce", 0)
                if reduce:
                    damage = max(0, damage - reduce)
                    session_state._item_damage_reduce = 0

            if damage > 0:
                before_hp = player.hp
                before_armor = player.armor
                player.change_hp(-damage, notify=notify)
                if (
                    "OLD_SHIELD" in player.relics
                    and player.hp == before_hp
                    and before_armor > player.armor
                ):
                    player.add_armor(10, notify=notify)
                CombatEngine._emit(events, "warning", f"👹 敌人攻击！造成 {damage} 伤害")
            else:
                CombatEngine._emit(events, "toast", "🛡️ 本次伤害被抵消", "🛡️")

        cs.current_card = None
        cs.current_options = None
        cs.turns += 1
        cs.nunchaku_used = False
        cs.extra_action_only_red = False

        return CombatResult(
            events=events,
            enemy_dead=cs.enemy.is_dead(),
            player_dead=player.is_dead(),
            should_rerun=True,
        )

    @staticmethod
    def resolve_stun_turn(cs: CardCombatState, player, session_state: Dict[str, Any]) -> CombatResult:
        events = []

        if session_state.get("_player_stunned"):
            session_state._player_stunned = False
            CombatEngine._emit(events, "warning", "😵 你被眩晕了，跳过本回合！")

        if cs.bleed_turns > 0 and cs.bleed_damage > 0:
            cs.enemy.take_damage(cs.bleed_damage)
            cs.bleed_turns -= 1
            CombatEngine._emit(events, "toast", f"🩸 放血造成 {cs.bleed_damage} 伤害")
            if cs.enemy.is_dead():
                cs.current_card = None
                cs.current_options = None
                cs.turns += 1
                cs.nunchaku_used = False
                cs.extra_action_only_red = False
                return CombatResult(events=events, enemy_dead=True, player_dead=player.is_dead(), should_rerun=True)

        intent = cs.enemy.tick()
        if intent == "dead":
            cs.current_card = None
            cs.current_options = None
            cs.turns += 1
            cs.nunchaku_used = False
            cs.extra_action_only_red = False
            return CombatResult(
                events=events,
                enemy_dead=True,
                player_dead=player.is_dead(),
                should_rerun=True,
            )
        cs.turns += 1
        cs.nunchaku_used = False
        cs.extra_action_only_red = False

        return CombatResult(events=events, enemy_dead=cs.enemy.is_dead(), player_dead=player.is_dead(), should_rerun=True)
