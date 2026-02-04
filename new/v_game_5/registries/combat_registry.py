# ==========================================
# ⚔️ 战斗类型注册表
# ==========================================
"""
📝 扩展指南：添加新战斗类型

1. 定义战斗配置 (在 COMBAT_TYPES 字典中添加):
   "YOUR_COMBAT_ID": CombatConfig(
       name="显示名称",
       icon="🔥",
       word_source="new" | "review" | "mixed",
       word_count=(min, max),
       damage=伤害值,
       gold_reward=金币奖励,
       description="描述",
       special_rules={}  # 可选特殊规则
   )

2. 在 models.py 的 NodeType 枚举中添加对应类型

3. 在 map_system.py 的地图生成逻辑中添加该类型的出现条件
"""

from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional

# 导入配置
import sys
from pathlib import Path
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

from config import (
    COMBAT_NEW_WORD_COUNT, COMBAT_RECALL_WORD_COUNT,
    ELITE_MIXED_WORD_COUNT, ELITE_STRONG_WORD_COUNT,
    EVENT_QUIZ_WORD_COUNT,
    GOLD_COMBAT_NEW, GOLD_COMBAT_RECALL, GOLD_ELITE_MIXED, GOLD_ELITE_STRONG,
    DAMAGE_NORMAL, DAMAGE_ELITE
)


@dataclass
class CombatConfig:
    """战斗配置"""
    name: str
    icon: str
    word_source: str  # "new", "review", "mixed"
    word_count: Tuple[int, int]  # (min, max)
    damage: int
    gold_reward: int
    description: str
    special_rules: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.special_rules is None:
            self.special_rules = {}


# ==========================================
# 🎯 战斗类型定义 (在此添加新战斗类型)
# ==========================================
COMBAT_TYPES: Dict[str, CombatConfig] = {
    
    # ===== 普通战斗 =====
    "COMBAT_NEW": CombatConfig(
        name="普通战斗",
        icon="⚔️",
        word_source="new",
        word_count=COMBAT_NEW_WORD_COUNT,
        damage=DAMAGE_NORMAL,
        gold_reward=GOLD_COMBAT_NEW,
        description="击败新词小怪，学习新单词！"
    ),
    
    "COMBAT_RECALL": CombatConfig(
        name="回溯战斗",
        icon="🔄",
        word_source="review",
        word_count=COMBAT_RECALL_WORD_COUNT,
        damage=0,  # 答错不扣血
        gold_reward=GOLD_COMBAT_RECALL,
        description="复习旧词，答错不扣血！",
        special_rules={"no_damage": True}
    ),
    
    # ===== 精英战斗 =====
    "ELITE_MIXED": CombatConfig(
        name="混合精英",
        icon="☠️",
        word_source="mixed",
        word_count=ELITE_MIXED_WORD_COUNT,
        damage=DAMAGE_ELITE,
        gold_reward=GOLD_ELITE_MIXED,
        description="新旧词混合，考验综合能力！"
    ),
    
    "ELITE_STRONG": CombatConfig(
        name="强力精英",
        icon="💀",
        word_source="new",
        word_count=ELITE_STRONG_WORD_COUNT,
        damage=int(DAMAGE_ELITE * 1.5),  # 1.5 倍伤害
        gold_reward=GOLD_ELITE_STRONG,
        description="大量新词，高伤害高回报！",
        special_rules={"damage_multiplier": 1.5}
    ),
    
    # ===== 特殊事件战斗 =====
    "EVENT_QUIZ": CombatConfig(
        name="福利挑战",
        icon="🎁",
        word_source="review",
        word_count=EVENT_QUIZ_WORD_COUNT,
        damage=0,
        gold_reward=0,
        description="全对获得免费商品，答错扣半金币！",
        special_rules={
            "reward_type": "free_item",
            "penalty_type": "half_gold",
            "track_errors": True
        }
    ),
}


class CombatRegistry:
    """
    战斗注册表管理器
    
    用法:
        config = CombatRegistry.get("COMBAT_NEW")
        all_types = CombatRegistry.get_all()
    """
    
    @staticmethod
    def get(combat_id: str) -> Optional[CombatConfig]:
        """获取战斗配置"""
        return COMBAT_TYPES.get(combat_id)
    
    @staticmethod
    def get_all() -> Dict[str, CombatConfig]:
        """获取所有战斗配置"""
        return COMBAT_TYPES.copy()
    
    @staticmethod
    def get_by_source(source: str) -> Dict[str, CombatConfig]:
        """按词源类型筛选"""
        return {k: v for k, v in COMBAT_TYPES.items() if v.word_source == source}
    
    @staticmethod
    def register(combat_id: str, config: CombatConfig):
        """
        动态注册新战斗类型
        
        用法:
            CombatRegistry.register("MY_COMBAT", CombatConfig(...))
        """
        COMBAT_TYPES[combat_id] = config
