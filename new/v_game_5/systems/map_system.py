# ==========================================
# 🗺️ 地图生成系统 - v6.0 强制战斗版
# ==========================================
"""
MapSystem v6.0 负责：
1. 生成每层的节点选项
2. 强制保证遇到指定数量的战斗
3. 管理楼层进度
"""

import random
import sys
from pathlib import Path
from typing import List, Optional

_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

from models import Node, NodeType
from config import (
    TOTAL_FLOORS,
    MANDATORY_NORMAL_COMBATS,
    MANDATORY_ELITE_COMBATS,
    MAX_NON_COMBAT_STREAK,
    UTILITY_OFFER_BASE,
    UTILITY_OFFER_DECAY,
    UTILITY_OFFER_MIN,
)


class MapSystem:
    """
    地图系统 v6.0
    
    强制战斗机制：
    - 必须遇到 8 只普通怪
    - 必须遇到 5 只精英怪
    - 不允许纯事件路线逃课
    """
    
    def __init__(self, total_floors: int = None):
        self.floor = 0
        self.total_floors = total_floors or TOTAL_FLOORS
        self.current_node: Optional[Node] = None
        self.next_options: List[Node] = []
        

        # 战斗计数器 初始化
        self.normal_combats_remaining = MANDATORY_NORMAL_COMBATS
        self.elite_combats_remaining = MANDATORY_ELITE_COMBATS
        self.normal_combats_completed = 0
        self.elite_combats_completed = 0
        self.boss_sequence_step = 0
        self.non_combat_streak = 0
    
    def generate_next_options(self) -> List[Node]:
        # 进入 Boss 阶段的强制序列
        if self.boss_sequence_step == 1:
            self.floor += 1
            self.boss_sequence_step = 2
            return [Node(type=NodeType.REST, level=self.floor)]
        if self.boss_sequence_step == 2:
            self.floor += 1
            return [Node(type=NodeType.BOSS, level=self.floor)]

        # 第一层固定 COMBAT
        if self.floor == 0:
            self.floor += 1
            return [Node(type=NodeType.COMBAT, level=self.floor)]

        # 战斗耗尽 -> 开启 Boss 阶段
        if self.normal_combats_remaining == 0 and self.elite_combats_remaining == 0:
            self.boss_sequence_step = 1
            return self.generate_next_options()

        # 生成分支：一个战斗 + 一个非战斗
        combat_options = self._combat_branch_options()

        # 硬限制：连续非战斗达到上限 -> 仅给战斗选项
        if self.non_combat_streak >= MAX_NON_COMBAT_STREAK:
            self.floor += 1
            return [Node(type=t, level=self.floor) for t in combat_options]

        # 软限制：连续非战斗越多，非战斗出现概率越低
        utility_chance = max(UTILITY_OFFER_MIN, UTILITY_OFFER_BASE - UTILITY_OFFER_DECAY * self.non_combat_streak)
        allow_utility = random.random() < utility_chance

        self.floor += 1
        if allow_utility:
            utility_type = self._pick_utility_type()
            return [
                Node(type=combat_options[0], level=self.floor),
                Node(type=utility_type, level=self.floor),
            ]

        return [Node(type=t, level=self.floor) for t in combat_options]

    
    def _generate_mandatory_combat_options(self) -> List[Node]:
        """生成强制战斗选项"""
        options = []
        
        # 优先填充需要的战斗类型
        if self.elite_combats_remaining > 0:
            options.append(Node(type=NodeType.ELITE, level=self.floor))
        if self.normal_combats_remaining > 0:
            options.append(Node(type=NodeType.COMBAT, level=self.floor))
        
        # 如果需要两个选项但只有一种战斗类型
        if len(options) == 1:
            options.append(Node(type=options[0].type, level=self.floor))
        elif len(options) == 0:
            # 所有战斗已完成，提供休息或商店
            options = [
                Node(type=NodeType.REST, level=self.floor),
                Node(type=NodeType.SHOP, level=self.floor)
            ]
        
        return options
    
    def _pick_combat_type(self) -> NodeType:
        if self.elite_combats_remaining <= 0:
            return NodeType.COMBAT
        if self.normal_combats_remaining <= 0:
            return NodeType.ELITE
        # 有两种都剩余时用权重
        return random.choices(
            [NodeType.COMBAT, NodeType.ELITE],
            weights=[0.7, 0.3]
        )[0]

    def _combat_branch_options(self) -> List[NodeType]:
        primary = self._pick_combat_type()
        if self.elite_combats_remaining > 0 and self.normal_combats_remaining > 0:
            secondary = NodeType.ELITE if primary == NodeType.COMBAT else NodeType.COMBAT
            return [primary, secondary]
        return [primary]

    def _pick_utility_type(self) -> NodeType:
        return random.choices(
            [NodeType.EVENT, NodeType.REST, NodeType.SHOP],
            weights=[0.6, 0.2, 0.2],
            k=1,
        )[0]

    def record_combat_completed(self, node_type: NodeType):
        """记录战斗完成（由外部调用）"""
        if node_type == NodeType.COMBAT:
            self.normal_combats_remaining = max(0, self.normal_combats_remaining - 1)
            self.normal_combats_completed += 1
        elif node_type == NodeType.ELITE:
            self.elite_combats_remaining = max(0, self.elite_combats_remaining - 1)
            self.elite_combats_completed += 1
    
    def _get_node_pool_for_floor(self, floor: int) -> List[NodeType]:
        """根据层数返回节点类型池"""
        # 早期阶段 (1-5层)
        if floor <= 3:
            return [
                NodeType.COMBAT, NodeType.COMBAT, NodeType.COMBAT,
                NodeType.EVENT,
            ]
        elif floor <= 6:
            return [
                NodeType.COMBAT, NodeType.COMBAT,
                NodeType.ELITE,
                NodeType.EVENT, NodeType.REST,
            ]
        elif floor <= 10:
            return [
                NodeType.COMBAT,
                NodeType.ELITE, NodeType.ELITE,
                NodeType.SHOP, NodeType.REST, NodeType.EVENT,
            ]
        elif floor <= 15:
            return [
                NodeType.COMBAT,
                NodeType.ELITE, NodeType.ELITE,
                NodeType.SHOP, NodeType.REST,
            ]
        else:
            # Boss 前最后几层
            return [
                NodeType.ELITE, NodeType.ELITE,
                NodeType.SHOP, NodeType.REST,
            ]
    
    def is_boss_floor(self) -> bool:
        return self.floor >= self.total_floors
    
    def get_progress_ratio(self) -> float:
        return self.floor / self.total_floors
    
    def get_combat_status(self) -> dict:
        """获取战斗进度状态"""
        return {
            "normal_completed": self.normal_combats_completed,
            "normal_remaining": self.normal_combats_remaining,
            "elite_completed": self.elite_combats_completed,
            "elite_remaining": self.elite_combats_remaining
        }
