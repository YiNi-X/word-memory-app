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
from config import TOTAL_FLOORS, MANDATORY_NORMAL_COMBATS, MANDATORY_ELITE_COMBATS


class MapSystem:
    """
    地图系统 v6.0
    
    强制战斗机制：
    - 必须遇到 10 只普通怪
    - 必须遇到 6 只精英怪
    - 不允许纯事件路线逃课
    """
    
    def __init__(self, total_floors: int = None):
        self.floor = 0
        self.total_floors = total_floors or TOTAL_FLOORS
        self.current_node: Optional[Node] = None
        self.next_options: List[Node] = []
        
        # v6.0 强制战斗列表 (Anti-Skip)
        self.node_queue = self._generate_queue()
        
        # 战斗计数器 初始化
        self.normal_combats_remaining = MANDATORY_NORMAL_COMBATS
        self.elite_combats_remaining = MANDATORY_ELITE_COMBATS
        self.normal_combats_completed = 0
        self.elite_combats_completed = 0
        self.boss_sequence_step = 0
    
    def _generate_queue(self) -> List[NodeType]:
        """生成整个流程的关卡队列 (10小怪 + 6精英 + 4随机 + 1Boss)"""
        queue = []
        # 1. 必经的小怪和精英
        combats = [NodeType.COMBAT] * (MANDATORY_NORMAL_COMBATS - 1) # 第1关固定小怪，不在列表内
        elites = [NodeType.ELITE] * MANDATORY_ELITE_COMBATS
        
        # 2. 填充随机事件 (商店、营地、随机事件)
        utilities = [NodeType.SHOP, NodeType.REST, NodeType.EVENT, NodeType.EVENT, NodeType.REST]
        
        # 3. 洗牌
        middle_part = combats + elites + utilities
        random.shuffle(middle_part)
        
        # 4. 组装全流程 (Floor 1 固定小怪)
        queue.append(NodeType.COMBAT)
        queue.extend(middle_part)
        
        # 5. 补足层数并添加 Boss
        while len(queue) < self.total_floors - 1:
            queue.append(random.choice([NodeType.EVENT, NodeType.REST]))
        
        queue.append(NodeType.BOSS)
        return queue

    def generate_next_options(self) -> List[Node]:
        """按顺序从队列中取出下一个关卡"""
        if self.floor >= len(self.node_queue):
            return []
        
        node_type = self.node_queue[self.floor]
        self.floor += 1
        
        # 为了 UI 保持一致，依然返回列表，但通常只有 1 个固定选项 (强制线性)
        # 或者可以提供 2 个相同类型的点选（模拟选择但路径唯一）
        return [Node(type=node_type, level=self.floor)]
    
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
