# ==========================================
# 🏆 圣遗物注册表
# ==========================================
"""
📝 扩展指南：添加新圣遗物

在 RELICS 字典中添加:
"YOUR_RELIC_ID": Relic(
    name="圣遗物名称",
    icon="🔥",
    description="效果描述",
    effect="on_combat_start",  # 触发时机
    value={"heal": 5}          # 效果参数
)

支持的 trigger 时机:
- "on_combat_start": 战斗开始时
- "on_combat_end": 战斗结束时
- "on_floor_start": 进入新层时
- "on_correct_answer": 答对时
- "on_wrong_answer": 答错时
- "on_boss_start": Boss 战开始时
- "passive": 被动效果
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class Relic:
    """圣遗物配置"""
    name: str
    icon: str
    description: str
    trigger: str  # 触发时机
    effect: Dict[str, Any]  # 效果参数
    rarity: str = "common"  # common, rare, epic


# ==========================================
# 🎯 圣遗物定义 (在此添加新圣遗物)
# ==========================================
RELICS: Dict[str, Relic] = {
    
    "BLOOD_VIAL": Relic(
        name="血之瓶",
        icon="🩸",
        description="每次战斗结束后回复 5 HP",
        trigger="on_combat_end",
        effect={"heal": 5},
        rarity="common"
    ),
    
    "GOLD_IDOL": Relic(
        name="金色神像",
        icon="🗿",
        description="每次答对额外获得 2 金币",
        trigger="on_correct_answer",
        effect={"gold": 2},
        rarity="common"
    ),
    
    "BURNING_BLOOD": Relic(
        name="燃血",
        icon="🔥",
        description="每进入新层回复 10 HP",
        trigger="on_floor_start",
        effect={"heal": 10},
        rarity="rare"
    ),
    
    "ANCHOR": Relic(
        name="记忆之锚",
        icon="⚓",
        description="旧词战斗金币奖励翻倍",
        trigger="passive",
        effect={"review_gold_multiplier": 2},
        rarity="rare"
    ),
    
    "ORICHALCUM": Relic(
        name="奥利哈刚",
        icon="💠",
        description="战斗开始时如果满血，获得 10 护甲",
        trigger="on_combat_start",
        effect={"armor_if_full": 10},
        rarity="rare"
    ),
    
    "FUSION_HAMMER": Relic(
        name="融合之锤",
        icon="🔨",
        description="精英战斗金币 +50%，但无法休息回血",
        trigger="passive",
        effect={"elite_gold_bonus": 0.5, "no_rest_heal": True},
        rarity="epic"
    ),
    
    "PHILOSOPHERS_STONE": Relic(
        name="贤者之石",
        icon="💎",
        description="每层获得 20 金币，但最大 HP -20",
        trigger="on_floor_start",
        effect={"gold": 20, "max_hp_penalty": -20},
        rarity="epic"
    ),
    
    "DEAD_BRANCH": Relic(
        name="枯枝",
        icon="🌿",
        description="答错时有 25% 概率不扣血",
        trigger="on_wrong_answer",
        effect={"dodge_chance": 0.25},
        rarity="rare"
    ),
}


class RelicRegistry:
    """圣遗物注册表管理器"""
    
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
        """获取随机圣遗物"""
        import random
        pool = RELICS if not rarity else {k: v for k, v in RELICS.items() if v.rarity == rarity}
        relic_id = random.choice(list(pool.keys()))
        return relic_id, pool[relic_id]
    
    @staticmethod
    def register(relic_id: str, relic: Relic):
        """动态注册新圣遗物"""
        RELICS[relic_id] = relic
