import random


def apply_effects(relic, ctx) -> bool:
    effect = getattr(relic, "effect", None)
    if not effect:
        return False

    # Chance gate
    chance = effect.get("chance")
    if chance is not None and random.random() > float(chance):
        return False

    player = ctx.player
    enemy = ctx.enemy
    scale = 2 if "WIZARD_HAT" in getattr(player, "relics", []) else 1

    def _scale(val):
        if scale != 1 and isinstance(val, (int, float)):
            return val * scale
        return val

    if "heal" in effect:
        player.change_hp(_scale(effect["heal"]))

    if "gold" in effect:
        player.add_gold(_scale(effect["gold"]))

    if "armor_if_full" in effect:
        if player.hp >= player.max_hp:
            player.add_armor(_scale(effect["armor_if_full"]))

    if "elite_gold_bonus" in effect:
        if enemy and getattr(enemy, "is_elite", False) and "gold_reward" in ctx.data:
            bonus = int(ctx.data["gold_reward"] * _scale(effect["elite_gold_bonus"]))
            if bonus:
                ctx.data["gold_reward"] += bonus

    if "max_hp_penalty" in effect:
        player.max_hp += _scale(effect["max_hp_penalty"])
        player.hp = min(player.hp, player.max_hp)

    if "dodge_chance" in effect:
        if random.random() < float(effect["dodge_chance"]):
            ctx.data["negate_wrong_penalty"] = True

    return True
