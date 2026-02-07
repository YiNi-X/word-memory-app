# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Dict, Any, Optional


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
}


class RelicRegistry:
    @staticmethod
    def get(relic_id: str) -> Optional[Relic]:
        return RELICS.get(relic_id)

    @staticmethod
    def get_all() -> Dict[str, Relic]:
        return RELICS.copy()

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
