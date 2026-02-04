# ==========================================
# 📦 数据模型
# ==========================================
from enum import Enum, IntEnum
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


class WordTier(IntEnum):
    """
    莱特纳熟练度等级
    
    📝 算法说明：
    - 答对：tier += 1 (最高 5)
    - 答错：tier = max(1, tier - 1) (回退但不低于 1)
    - Lv 0 必须通过学习模式解锁
    """
    UNKNOWN = 0       # 未接触 - 完全陌生
    BLURRY = 1        # 模糊 - 刚学过/刚答错
    CLEAR = 2         # 清晰 - 连续答对 1-2 次
    MASTERED = 3      # 掌握 - 连续答对 3-4 次
    INTERNALIZED = 4  # 内化 - 长期未出错
    ARCHIVED = 5      # 封存 - 毕业词汇
    
    @property
    def display_name(self) -> str:
        names = {
            0: "未接触", 1: "模糊", 2: "清晰",
            3: "掌握", 4: "内化", 5: "封存"
        }
        return names.get(self.value, "未知")
    
    @property
    def color(self) -> str:
        colors = {
            0: "#666666", 1: "#ff6b6b", 2: "#feca57",
            3: "#48dbfb", 4: "#1dd1a1", 5: "#a29bfe"
        }
        return colors.get(self.value, "#ffffff")


# 复习间隔配置 (房间数)
REVIEW_INTERVALS = {
    WordTier.BLURRY: (1, 3),      # 1-3 房间内必须复现
    WordTier.CLEAR: (5, 10),      # 5-10 房间间隔
    WordTier.MASTERED: (15, 25),  # 15-25 房间间隔
    WordTier.INTERNALIZED: (30, 50),  # 30-50 房间间隔
}


@dataclass
class Word:
    """单词数据模型"""
    word: str
    meaning: str
    tier: WordTier = WordTier.UNKNOWN
    correct_streak: int = 0  # 连续答对次数
    last_seen_room: int = 0  # 上次出现的房间号
    next_review_room: int = 0  # 下次复习的房间号
    is_review: bool = False  # 是否为复习词
    
    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "meaning": self.meaning,
            "tier": self.tier.value,
            "correct_streak": self.correct_streak,
            "last_seen_room": self.last_seen_room,
            "next_review_room": self.next_review_room,
            "is_review": self.is_review
        }
    
    @staticmethod
    def from_dict(d: dict) -> 'Word':
        return Word(
            word=d["word"],
            meaning=d["meaning"],
            tier=WordTier(d.get("tier", 0)),
            correct_streak=d.get("correct_streak", 0),
            last_seen_room=d.get("last_seen_room", 0),
            next_review_room=d.get("next_review_room", 0),
            is_review=d.get("is_review", False)
        )


@dataclass
class Player:
    """玩家数据模型"""
    id: int = 1
    gold: int = 0
    hp: int = 100
    max_hp: int = 100
    inventory: List[str] = field(default_factory=list)  # 道具列表
    relics: List[str] = field(default_factory=list)     # 圣遗物列表
    current_room: int = 0  # 当前房间号 (用于复习调度)
    
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
    
    def advance_room(self):
        """推进房间计数"""
        self.current_room += 1


@dataclass
class Node:
    """地图节点"""
    type: NodeType
    level: int
    data: Dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"  # PENDING, ACTIVE, CLEARED


class CombatPhase(Enum):
    """战斗阶段"""
    LEARNING = "learning"   # 学习阶段 (新词先展示)
    TESTING = "testing"     # 考核阶段
    RESULT = "result"       # 结果展示


@dataclass
class CombatState:
    """战斗状态"""
    enemies: List[Dict]
    current_idx: int = 0
    phase: CombatPhase = CombatPhase.LEARNING  # 当前阶段
    flipped: bool = False
    options: Optional[List[str]] = None
    damage_per_wrong: int = 10
    gold_reward: int = 20
    learned_current: bool = False  # 当前词是否已学习
    
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
        self.phase = CombatPhase.LEARNING
        self.flipped = False
        self.options = None
        self.learned_current = False
    
    def mark_learned(self):
        """标记当前词已学习，进入考核"""
        self.learned_current = True
        self.phase = CombatPhase.TESTING


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
