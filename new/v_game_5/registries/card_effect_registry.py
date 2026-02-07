# Card effect registry
import random
from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class EffectContext:
    player: Any
    enemy: Any
    cs: Any
    card: Any
    st: Any


@dataclass
class CardEffect:
    name: str
    icon: str
    description: str
    on_correct: Callable[[EffectContext], None] = None
    on_wrong: Callable[[EffectContext], None] = None


def _red_heavy_strike(ctx: EffectContext):
    damage = ctx.card.damage
    if "START_BURNING_BLOOD" in getattr(ctx.player, "relics", []):
        if ctx.player.hp < 50:
            damage *= 1.5
    if "WIZARD_HAT" in getattr(ctx.player, "relics", []):
        damage *= 0.7
    if ctx.cs.next_card_multiplier > 1:
        damage *= ctx.cs.next_card_multiplier
        ctx.cs.next_card_multiplier = 1
    damage = int(damage)
    ctx.enemy.take_damage(damage)
    ctx.st.toast(f"造成 {damage} 伤害")

    if "START_BURNING_BLOOD" in getattr(ctx.player, "relics", []) and ctx.player.hp < 50:
        leech = 5
        if "WIZARD_HAT" in getattr(ctx.player, "relics", []):
            leech *= 2
        ctx.enemy.take_damage(leech)
        ctx.player.change_hp(leech)


def _red_self_harm(ctx: EffectContext):
    penalty = ctx.card.penalty
    if "START_BURNING_BLOOD" in getattr(ctx.player, "relics", []):
        if ctx.player.hp < 50:
            penalty *= 1.5
    if "PAIN_ARMOR" in getattr(ctx.player, "relics", []):
        penalty *= 0.5
    penalty = int(penalty)
    ctx.player.change_hp(-penalty)
    ctx.st.error(f"反噬 {penalty}")


RED_EFFECTS = CardEffect(
    name="重击",
    icon="*",
    description="红卡效果",
    on_correct=_red_heavy_strike,
    on_wrong=_red_self_harm,
)


def _blue_hybrid_attack(ctx: EffectContext):
    damage = ctx.card.damage
    armor = ctx.card.block
    if "WIZARD_HAT" in getattr(ctx.player, "relics", []):
        damage *= 0.7
        armor *= 0.7
    if "PAIN_ARMOR" in getattr(ctx.player, "relics", []):
        armor *= 1.5
    if ctx.cs.next_card_multiplier > 1:
        damage *= ctx.cs.next_card_multiplier
        armor *= ctx.cs.next_card_multiplier
        ctx.cs.next_card_multiplier = 1
    damage = int(damage)
    armor = int(armor)
    ctx.enemy.take_damage(damage)
    ctx.player.add_armor(armor)
    ctx.st.toast(f"造成 {damage} 伤害，获得 {armor} 护甲")

    if hasattr(ctx.card, "is_temporary_buffed") and ctx.card.is_temporary_buffed:
        heal = 5
        if "WIZARD_HAT" in getattr(ctx.player, "relics", []):
            heal *= 0.7
        ctx.player.change_hp(int(heal))


def _blue_no_penalty(ctx: EffectContext):
    pass


BLUE_EFFECTS = CardEffect(
    name="混合打击",
    icon="*",
    description="蓝卡效果",
    on_correct=_blue_hybrid_attack,
    on_wrong=_blue_no_penalty,
)


def _gold_random_effect(ctx: EffectContext):
    has_hat = "WIZARD_HAT" in getattr(ctx.player, "relics", [])
    multiplier = 4 if has_hat else 2
    draw_count = 4 if has_hat else 2
    direct_damage = 50 if has_hat else 25

    if has_hat:
        ctx.cs.extra_actions += 1

    effect = random.choice(["mult", "draw", "damage"])
    if effect == "mult":
        ctx.cs.next_card_multiplier = multiplier
        ctx.st.toast(f"金卡效果：下一张数值 x{multiplier}")
    elif effect == "draw":
        drawn_count = 0
        for _ in range(draw_count):
            if ctx.cs.draw_card():
                drawn_count += 1
        if drawn_count:
            ctx.st.toast(f"金卡效果：抽 {drawn_count} 张牌")
        else:
            ctx.st.toast("金卡效果：没有可抽的牌")
    else:
        ctx.enemy.take_damage(direct_damage)
        ctx.st.toast(f"金卡效果：直接造成 {direct_damage} 伤害")


def _gold_no_penalty(ctx: EffectContext):
    pass


GOLD_EFFECTS = CardEffect(
    name="随机强化",
    icon="*",
    description="金卡随机效果",
    on_correct=_gold_random_effect,
    on_wrong=_gold_no_penalty,
)


def _black_curse_attack(ctx: EffectContext):
    damage = ctx.card.damage
    if ctx.cs.next_card_multiplier > 1:
        damage *= ctx.cs.next_card_multiplier
        ctx.cs.next_card_multiplier = 1
    damage = int(damage)
    ctx.enemy.take_damage(damage)
    ctx.st.toast(f"诅咒造成 {damage} 伤害")


def _black_curse_backfire(ctx: EffectContext):
    penalty = ctx.card.penalty
    if "PAIN_ARMOR" in getattr(ctx.player, "relics", []):
        penalty *= 0.5
    penalty = int(penalty)
    ctx.player.change_hp(-penalty)
    ctx.st.error(f"诅咒反噬 {penalty}")


BLACK_EFFECTS = CardEffect(
    name="诅咒打击",
    icon="*",
    description="黑卡效果",
    on_correct=_black_curse_attack,
    on_wrong=_black_curse_backfire,
)


class CardEffectRegistry:
    EFFECTS = {
        "RED_BERSERK": RED_EFFECTS,
        "BLUE_HYBRID": BLUE_EFFECTS,
        "GOLD_SUPPORT": GOLD_EFFECTS,
        "BLACK_CURSE": BLACK_EFFECTS,
    }

    @classmethod
    def get_effect(cls, card_type_name: str) -> CardEffect:
        return cls.EFFECTS.get(card_type_name)

    @classmethod
    def apply_effect(cls, card_type_name: str, ctx: EffectContext, correct: bool):
        if ctx.enemy.is_boss:
            if correct:
                dmg = 10
                if ctx.cs.next_card_multiplier > 1:
                    dmg *= ctx.cs.next_card_multiplier
                    ctx.cs.next_card_multiplier = 1
                ctx.enemy.take_damage(dmg)
                ctx.st.toast(f"首领受到 {dmg} 伤害")
            else:
                penalty = 25
                ctx.player.change_hp(-penalty)
                ctx.st.error(f"答错惩罚 {penalty}")
            return

        effect = cls.get_effect(card_type_name)
        if not effect:
            return
        if correct and effect.on_correct:
            effect.on_correct(ctx)
        elif not correct and effect.on_wrong:
            effect.on_wrong(ctx)

    @classmethod
    def register(cls, card_type_name: str, effect: CardEffect):
        cls.EFFECTS[card_type_name] = effect
