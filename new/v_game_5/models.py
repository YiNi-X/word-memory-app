# ==========================================
# 📦 数据模型
# ==========================================
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import streamlit as st


class GamePhase(Enum):
    """游戏阶段"""
    LOBBY = 0
    MAP_SELECT = 1
    IN_NODE = 2
    GAME_OVER = 3
    VICTORY = 4


class NodeType(Enum):
    """
    节点类型枚举
    
    📝 扩展指南：添加新节点类型
    1. 在此处添加枚举值
    2. 在 registries/combat_registry.py 或 event_registry.py 注册处理器
    """
    # 战斗类型
    COMBAT_NEW = "⚔️ 普通战斗"        # 新词战斗
    COMBAT_RECALL = "🔄 回溯战斗"      # 旧词战斗
    ELITE_MIXED = "☠️ 混合精英"        # 新旧混合
    ELITE_STRONG = "💀 强力精英"       # 仅新词高难度
    
    # 事件类型
    EVENT_QUIZ = "🎁 福利挑战"         # 答题事件
    EVENT_RANDOM = "❓ 随机事件"       # 随机事件
    REST = "🔥 营地休息"
    SHOP = "🛒 地精商店"
    
    # Boss
    BOSS = "👹 最终领主"


@dataclass
class Word:
    """单词数据模型"""
    word: str
    meaning: str
    is_review: bool = False  # 是否为复习词
    
    def to_dict(self) -> dict:
        return {"word": self.word, "meaning": self.meaning, "is_review": self.is_review}
    
    @staticmethod
    def from_dict(d: dict) -> 'Word':
        return Word(word=d["word"], meaning=d["meaning"], is_review=d.get("is_review", False))


@dataclass
class Player:
    """玩家数据模型"""
    id: int = 1
    gold: int = 0
    hp: int = 100
    max_hp: int = 100
    inventory: List[str] = field(default_factory=list)  # 道具列表
    relics: List[str] = field(default_factory=list)     # 圣遗物列表
    
    def change_hp(self, amount: int):
        self.hp += amount
        self.hp = max(0, min(self.hp, self.max_hp))
        if amount < 0:
            st.toast(f"💔 HP {amount}", icon="🩸")
        else:
            st.toast(f"💚 HP +{amount}", icon="🌿")
    
    def add_gold(self, amount: int):
        self.gold += amount
        st.toast(f"💰 金币 +{amount}")
    
    def is_dead(self) -> bool:
        return self.hp <= 0
    
    def has_item(self, item: str) -> bool:
        return item in self.inventory
    
    def use_item(self, item: str) -> bool:
        if item in self.inventory:
            self.inventory.remove(item)
            return True
        return False


@dataclass
class Node:
    """地图节点"""
    type: NodeType
    level: int
    data: Dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"  # PENDING, ACTIVE, CLEARED


@dataclass
class CombatState:
    """战斗状态"""
    enemies: List[Dict]
    current_idx: int = 0
    flipped: bool = False
    options: Optional[List[str]] = None
    damage_per_wrong: int = 10
    gold_reward: int = 20
    
    @property
    def is_complete(self) -> bool:
        return self.current_idx >= len(self.enemies)
    
    @property
    def current_enemy(self) -> Optional[Dict]:
        if self.is_complete:
            return None
        return self.enemies[self.current_idx]
    
    def advance(self):
        self.current_idx += 1
        self.flipped = False
        self.options = None


@dataclass
class BossState:
    """Boss 战状态"""
    phase: str = "loading"  # loading, article, quiz, victory
    article: Optional[Dict] = None
    quizzes: Optional[Dict] = None
    quiz_idx: int = 0
    boss_hp: int = 100
    boss_max_hp: int = 100
    api_error: Optional[str] = None
