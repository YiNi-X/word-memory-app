# ==========================================
# 🗺️ 地图生成系统
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

# 添加父目录到路径
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

from models import Node, NodeType
from config import TOTAL_FLOORS


class MapSystem:
    """
    地图系统
    
    层级结构：
    - Floor 1-2: 主要是普通战斗/回溯战斗
    - Floor 3-4: 精英怪开始出现，事件增多
    - Floor 5: 精英/事件/商店
    - Floor 6: Boss
    """
    
    def __init__(self, total_floors: int = None):
        self.floor = 0
        self.total_floors = total_floors or TOTAL_FLOORS
        self.current_node: Optional[Node] = None
        self.next_options: List[Node] = []
    
    def generate_next_options(self) -> List[Node]:
        """
        生成下一层的节点选项
        
        Returns:
            2-3 个可选节点
        """
        self.floor += 1
        
        # 最后一层强制 Boss
        if self.floor >= self.total_floors:
            return [Node(type=NodeType.BOSS, level=self.floor)]
        
        # 根据层数确定节点池
        node_pool = self._get_node_pool_for_floor(self.floor)
        
        # 生成 2 个不同选项
        options = []
        type1 = random.choice(node_pool)
        options.append(Node(type=type1, level=self.floor))
        
        # 确保第二个选项不同
        remaining_pool = [t for t in node_pool if t != type1]
        if remaining_pool:
            type2 = random.choice(remaining_pool)
        else:
            type2 = type1  # 如果池中只有一种类型
        options.append(Node(type=type2, level=self.floor))
        
        return options
    
    def _get_node_pool_for_floor(self, floor: int) -> List[NodeType]:
        """
        根据层数返回可能出现的节点类型池
        
        📝 扩展指南：修改节点出现概率
        调整列表中类型的出现次数来改变权重
        """
        
        if floor == 1:
            # 第一层：简单入门
            return [
                NodeType.COMBAT_NEW,
                NodeType.COMBAT_NEW,
                NodeType.COMBAT_RECALL,
                NodeType.EVENT_RANDOM,
            ]
        
        elif floor == 2:
            # 第二层：仍然以普通战斗为主
            return [
                NodeType.COMBAT_NEW,
                NodeType.COMBAT_NEW,
                NodeType.COMBAT_RECALL,
                NodeType.COMBAT_RECALL,
                NodeType.EVENT_RANDOM,
                NodeType.REST,
            ]
        
        elif floor == 3:
            # 第三层：精英开始出现
            return [
                NodeType.COMBAT_NEW,
                NodeType.COMBAT_RECALL,
                NodeType.ELITE_MIXED,
                NodeType.EVENT_RANDOM,
                NodeType.EVENT_QUIZ,
                NodeType.REST,
            ]
        
        elif floor == 4:
            # 第四层：精英概率增加，商店出现
            return [
                NodeType.COMBAT_NEW,
                NodeType.ELITE_MIXED,
                NodeType.ELITE_STRONG,
                NodeType.EVENT_QUIZ,
                NodeType.SHOP,
                NodeType.REST,
            ]
        
        else:
            # 第五层 (Boss 前): 最后准备
            return [
                NodeType.ELITE_MIXED,
                NodeType.ELITE_STRONG,
                NodeType.EVENT_QUIZ,
                NodeType.SHOP,
                NodeType.REST,
            ]
    
    def is_boss_floor(self) -> bool:
        """判断是否为 Boss 层"""
        return self.floor >= self.total_floors
    
    def get_progress_ratio(self) -> float:
        """获取进度比例 (0-1)"""
        return self.floor / self.total_floors
