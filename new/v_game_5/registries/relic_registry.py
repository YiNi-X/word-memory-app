# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class Relic:
    name: str
    icon: str
    description: str
    trigger: str
    effect: Dict[str, Any]
    rarity: str = "common"


RELICS: Dict[str, Relic] = {
    "BLOOD_VIAL": Relic(
        name="血之瓶",
        icon="🩸",
        description="每次战斗结束恢复 5 生命",
        trigger="on_combat_end",
        effect={"heal": 5},
        rarity="common",
    ),
    "GOLD_IDOL": Relic(
        name="金币神像",
        icon="🗿",
        description="每次答对额外获得 2 金币",
        trigger="on_correct_answer",
        effect={"gold": 2},
        rarity="common",
    ),
    "BURNING_BLOOD": Relic(
        name="燃烧之血",
        icon="🔥",
        description="每进入新楼层恢复 10 生命",
        trigger="on_floor_start",
        effect={"heal": 10},
        rarity="rare",
    ),
    "ANCHOR": Relic(
        name="记忆之锚",
        icon="⚓",
        description="复习战斗金币奖励翻倍",
        trigger="passive",
        effect={"review_gold_multiplier": 2},
        rarity="rare",
    ),
    "ORICHALCUM": Relic(
        name="奥利哈钢",
        icon="🛡️",
        description="战斗开始时若满血，获得 10 护甲",
        trigger="on_combat_start",
        effect={"armor_if_full": 10},
        rarity="rare",
    ),
    "FUSION_HAMMER": Relic(
        name="融合之锤",
        icon="🔨",
        description="精英战斗金币 +50%，但无法休息回血",
        trigger="passive",
        effect={"elite_gold_bonus": 0.5, "no_rest_heal": True},
        rarity="epic",
    ),
    "PHILOSOPHERS_STONE": Relic(
        name="哲学家之石",
        icon="🪨",
        description="每层获得 20 金币，但最大生命 -20",
        trigger="on_floor_start",
        effect={"gold": 20, "max_hp_penalty": -20},
        rarity="epic",
    ),
    "DEAD_BRANCH": Relic(
        name="枯枝",
        icon="🌿",
        description="答错时有 25% 概率不扣生命",
        trigger="on_wrong_answer",
        effect={"dodge_chance": 0.25},
        rarity="rare",
    ),
    "BLOOD_CRYSTAL": Relic(
        name="血之水晶",
        icon="💎",
        description="答对时有 20% 概率恢复 5 生命",
        trigger="on_correct_answer",
        effect={"heal": 5, "chance": 0.2},
        rarity="rare",
    ),
    "GOLD_CHARM": Relic(
        name="金币护符",
        icon="🧿",
        description="每场战斗结束额外获得 15 金币",
        trigger="on_combat_end",
        effect={"gold": 15},
        rarity="common",
    ),
    "START_BURNING_BLOOD": Relic(
        name="燃烧之血",
        icon="🩸",
        description=(
            "生命<50：红卡伤害与反噬 +50%；"
            "红卡答对吸血 5；"
            "出牌后手牌为 0 且最后一张为红卡时抽 2（红优先）"
        ),
        trigger="passive",
        effect={},
        rarity="rare",
    ),
    "PAIN_ARMOR": Relic(
        name="苦痛之甲",
        icon="🪖",
        description=(
            "蓝卡护甲 +50%；所有回血 -50%；非蓝卡反噬 -50%；"
            "出牌后手牌为 0 且最后一张为蓝卡时抽 2（优先红+蓝）"
        ),
        trigger="passive",
        effect={},
        rarity="rare",
    ),
    "WIZARD_HAT": Relic(
        name="巫师之帽",
        icon="🎩",
        description=(
            "红/蓝正向效果 -30%（反噬不变）；金卡效果翻倍；金卡耐久=2；"
            "圣遗物数值效果翻倍；金卡后额外出牌 1 次"
        ),
        trigger="passive",
        effect={},
        rarity="epic",
    ),
    "WINE": Relic(
        name="酒",
        icon="🍶",
        description="本局红卡伤害 +2",
        trigger="passive",
        effect={"red_damage_bonus": 2},
        rarity="common",
    ),
    "CURSED_BLOOD": Relic(
        name="诅咒之血",
        icon="🧛",
        description="黑卡伤害 +3；本局无法通过道具/事件回血",
        trigger="passive",
        effect={"black_damage_bonus": 3, "no_item_heal": True, "no_event_heal": True},
        rarity="common",
    ),
    "FIGHTER_SOUL": Relic(
        name="格斗家之魂",
        icon="🥊",
        description="蓝卡后接红卡有 20% 暴击（额外伤害 +3）",
        trigger="passive",
        effect={"crit_chance": 0.2, "crit_bonus": 3},
        rarity="common",
    ),
    "MONKEY_PAW": Relic(
        name="猴爪",
        icon="🐒",
        description="最大生命上限为 50；抵御一次致命伤害",
        trigger="passive",
        effect={"max_hp_cap": 50},
        rarity="common",
    ),
    "UNDYING_CURSE": Relic(
        name="不死诅咒",
        icon="☠️",
        description="所有卡牌视为黑卡；负面效果翻倍；不良事件几率大幅提高",
        trigger="passive",
        effect={"negative_multiplier": 2, "bad_event_chance": 0.8},
        rarity="rare",
    ),
    "AGANG_WRATH": Relic(
        name="阿刚之怒",
        icon="💢",
        description="出过金卡后连续 3 张红卡，最后一张红卡伤害翻倍",
        trigger="passive",
        effect={"red_chain": 3, "red_multiplier": 2},
        rarity="rare",
    ),
    "CURSE_MASK": Relic(
        name="诅咒面具",
        icon="🎭",
        description="黑卡反噬伤害转化为等值护甲",
        trigger="passive",
        effect={},
        rarity="epic",
    ),
    "SCHOLAR_WRATH": Relic(
        name="博学者之怒",
        icon="📚",
        description="连续使用金卡→蓝卡→红卡后，直接造成 10 点伤害",
        trigger="passive",
        effect={"sequence_damage": 10},
        rarity="epic",
    ),
    "BLEEDING_DAGGER": Relic(
        name="放血刀",
        icon="🗡️",
        description="连续红卡触发放血：每回合 (x-1)*2 伤害，持续 2 回合（可叠加）",
        trigger="passive",
        effect={"bleed_duration": 2, "bleed_damage_step": 2},
        rarity="epic",
    ),
    "NUNCHAKU": Relic(
        name="双截棍",
        icon="🥋",
        description="每回合可额外使用 1 张红卡",
        trigger="passive",
        effect={"extra_red_per_turn": 1},
        rarity="epic",
    ),
    "OLD_SHIELD": Relic(
        name="斑驳旧盾",
        icon="🛡️",
        description="护甲完全抵挡怪物攻击时，立刻获得 10 护甲",
        trigger="passive",
        effect={"block_armor_bonus": 10},
        rarity="epic",
    ),
    "OLD_ARMOR": Relic(
        name="斑驳旧甲",
        icon="🥾",
        description="战斗开始获得 5 护甲；连续使用两张蓝卡额外获得 5 护甲",
        trigger="passive",
        effect={"start_armor": 5, "blue_combo_armor": 5},
        rarity="epic",
    ),
}

# ==========================================
# 圣遗物池（相互独立）
# ==========================================
STARTER_RELIC_POOL: List[str] = [
    "START_BURNING_BLOOD",
    "PAIN_ARMOR",
    "WIZARD_HAT",
]

LOW_TIER_RELIC_POOL: List[str] = [
    "WINE",
    "CURSED_BLOOD",
    "FIGHTER_SOUL",
    "MONKEY_PAW",
    "UNDYING_CURSE",
    "AGANG_WRATH",
    "BLOOD_VIAL",
    "GOLD_IDOL",
    "GOLD_CHARM",
    "BLOOD_CRYSTAL",
    "DEAD_BRANCH",
    "ANCHOR",
    "ORICHALCUM",
    "BURNING_BLOOD",
]

HIGH_TIER_RELIC_POOL: List[str] = [
    "CURSE_MASK",
    "SCHOLAR_WRATH",
    "BLEEDING_DAGGER",
    "NUNCHAKU",
    "OLD_SHIELD",
    "OLD_ARMOR",
    "FUSION_HAMMER",
    "PHILOSOPHERS_STONE",
]


class RelicRegistry:
    @staticmethod
    def get(relic_id: str) -> Optional[Relic]:
        return RELICS.get(relic_id)

    @staticmethod
    def get_all() -> Dict[str, Relic]:
        return RELICS.copy()

    @staticmethod
    def get_pool(pool_name: str) -> List[str]:
        if pool_name == "starter":
            return STARTER_RELIC_POOL.copy()
        if pool_name == "low":
            return LOW_TIER_RELIC_POOL.copy()
        if pool_name == "high":
            return HIGH_TIER_RELIC_POOL.copy()
        return []

    @staticmethod
    def get_by_rarity(rarity: str) -> Dict[str, Relic]:
        return {k: v for k, v in RELICS.items() if v.rarity == rarity}

    @staticmethod
    def get_random(rarity: str = None) -> tuple:
        import random
        pool = RELICS if not rarity else {k: v for k, v in RELICS.items() if v.rarity == rarity}
        relic_id = random.choice(list(pool.keys()))
        return relic_id, pool[relic_id]

    @staticmethod
    def register(relic_id: str, relic: Relic):
        RELICS[relic_id] = relic
