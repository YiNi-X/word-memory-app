# ==========================================
# 🗺️ 地图生成系统 - Word=Card 版本
# ==========================================
"""
MapSystem 负责：
1. 生成每层的节点选项
2. 控制节点类型出现概率
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
from config import TOTAL_FLOORS


class MapSystem:
    """
    地图系统
    
    简化版NodeType：
    - COMBAT: 普通战斗
    - ELITE: 精英战斗
    - EVENT: 随机事件
    - REST: 休息
    - SHOP: 商店
    - BOSS: Boss战
    """
    
    def __init__(self, total_floors: int = None):
        self.floor = 0
        self.total_floors = total_floors or TOTAL_FLOORS
        self.current_node: Optional[Node] = None
        self.next_options: List[Node] = []
    
    def generate_next_options(self) -> List[Node]:
        """生成下一层的节点选项"""
        self.floor += 1
        
        # 最后一层强制 Boss
        if self.floor >= self.total_floors:
            return [Node(type=NodeType.BOSS, level=self.floor)]
        
        node_pool = self._get_node_pool_for_floor(self.floor)
        
        # 生成 2 个不同选项
        options = []
        type1 = random.choice(node_pool)
        options.append(Node(type=type1, level=self.floor))
        
        remaining_pool = [t for t in node_pool if t != type1]
        if remaining_pool:
            type2 = random.choice(remaining_pool)
        else:
            type2 = type1
        options.append(Node(type=type2, level=self.floor))
        
        return options
    
    def _get_node_pool_for_floor(self, floor: int) -> List[NodeType]:
        """根据层数返回节点类型池"""
        
        if floor == 1:
            return [
                NodeType.COMBAT,
                NodeType.COMBAT,
                NodeType.COMBAT,
                NodeType.EVENT,
            ]
        
        elif floor == 2:
            return [
                NodeType.COMBAT,
                NodeType.COMBAT,
                NodeType.EVENT,
                NodeType.REST,
            ]
        
        elif floor == 3:
            return [
                NodeType.COMBAT,
                NodeType.ELITE,
                NodeType.EVENT,
                NodeType.REST,
            ]
        
        elif floor == 4:
            return [
                NodeType.COMBAT,
                NodeType.ELITE,
                NodeType.ELITE,
                NodeType.SHOP,
                NodeType.REST,
            ]
        
        else:
            # Boss 前
            return [
                NodeType.ELITE,
                NodeType.SHOP,
                NodeType.REST,
            ]
    
    def is_boss_floor(self) -> bool:
        return self.floor >= self.total_floors
    
    def get_progress_ratio(self) -> float:
        return self.floor / self.total_floors
