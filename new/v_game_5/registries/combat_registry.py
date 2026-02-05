# ==========================================
# ⚔️ 战斗类型注册表 - Word=Card 版本
# ==========================================
"""
简化版战斗注册表
战斗逻辑已移至 CardCombatState
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class CombatConfig:
    """战斗配置"""
    name: str
    icon: str
    enemy_hp: int
    enemy_attack: int
    gold_reward: int
    description: str


COMBAT_TYPES: Dict[str, CombatConfig] = {
    "COMBAT": CombatConfig(
        name="普通战斗",
        icon="⚔️",
        enemy_hp=100,
        enemy_attack=10,
        gold_reward=30,
        description="选择弹药，击败词汇魔物！"
    ),
    
    "ELITE": CombatConfig(
        name="精英战斗",
        icon="☠️",
        enemy_hp=150,
        enemy_attack=15,
        gold_reward=50,
        description="强力敌人，需要更多策略！"
    ),
}


class CombatRegistry:
    """战斗注册表管理器"""
    
    @staticmethod
    def get(combat_id: str) -> Optional[CombatConfig]:
        return COMBAT_TYPES.get(combat_id)
    
    @staticmethod
    def get_all() -> Dict[str, CombatConfig]:
        return COMBAT_TYPES.copy()
