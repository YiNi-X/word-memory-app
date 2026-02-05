# ==========================================
# 📦 数据模型 - Word=Card 战斗系统
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
    """节点类型"""
    COMBAT = "⚔️ 战斗"
    ELITE = "☠️ 精英"
    EVENT = "❓ 事件"
    REST = "🔥 营地"
    SHOP = "🛒 商店"
    BOSS = "👹 Boss"


class WordTier(IntEnum):
    """莱特纳熟练度等级"""
    UNKNOWN = 0       # 未接触
    BLURRY = 1        # 模糊
    CLEAR = 2         # 清晰
    MASTERED = 3      # 掌握
    INTERNALIZED = 4  # 内化
    ARCHIVED = 5      # 封存
    
    @property
    def display_name(self) -> str:
        names = {0: "未接触", 1: "模糊", 2: "清晰", 3: "掌握", 4: "内化", 5: "封存"}
        return names.get(self.value, "未知")
    
    @property
    def color(self) -> str:
        colors = {0: "#666666", 1: "#ff6b6b", 2: "#feca57", 3: "#48dbfb", 4: "#1dd1a1", 5: "#a29bfe"}
        return colors.get(self.value, "#ffffff")


# 复习间隔配置
REVIEW_INTERVALS = {
    WordTier.BLURRY: (1, 3),
    WordTier.CLEAR: (5, 10),
    WordTier.MASTERED: (15, 25),
    WordTier.INTERNALIZED: (30, 50),
}


# ==========================================
# 🎴 卡牌系统
# ==========================================
class CardType(Enum):
    """卡牌类型"""
    ATTACK = "attack"     # 🟥 红 - 攻击
    DEFENSE = "defense"   # 🟦 蓝 - 防御
    UTILITY = "utility"   # 🟨 金 - 功能
    
    @property
    def color(self) -> str:
        colors = {"attack": "#e74c3c", "defense": "#3498db", "utility": "#f39c12"}
        return colors.get(self.value, "#ffffff")
    
    @property
    def icon(self) -> str:
        icons = {"attack": "🟥", "defense": "🟦", "utility": "🟨"}
        return icons.get(self.value, "⬜")
    
    @property
    def name_cn(self) -> str:
        names = {"attack": "攻击", "defense": "防御", "utility": "功能"}
        return names.get(self.value, "未知")
    
    @staticmethod
    def from_tier(tier: int) -> 'CardType':
        """根据熟练度返回卡牌类型"""
        if tier <= 1:
            return CardType.ATTACK
        elif tier <= 3:
            return CardType.DEFENSE
        else:
            return CardType.UTILITY


@dataclass
class WordCard:
    """单词卡牌"""
    word: str
    meaning: str
    tier: int
    card_type: CardType = None
    learned: bool = False  # 是否已学习（红卡需要）
    
    def __post_init__(self):
        if self.card_type is None:
            self.card_type = CardType.from_tier(self.tier)
    
    @property
    def damage(self) -> int:
        """攻击伤害"""
        if self.card_type == CardType.ATTACK:
            return 25
        return 5
    
    @property
    def block(self) -> int:
        """护甲值"""
        if self.card_type == CardType.DEFENSE:
            return 10
        return 0
    
    @property
    def backfire(self) -> int:
        """答错反噬"""
        if self.card_type == CardType.ATTACK:
            return 15
        return 0
    
    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "meaning": self.meaning,
            "tier": self.tier,
            "card_type": self.card_type.value,
            "learned": self.learned
        }


@dataclass
class Enemy:
    """敌人"""
    name: str = "词汇魔物"
    hp: int = 100
    max_hp: int = 100
    attack: int = 10
    action_timer: int = 3      # 几回合后攻击
    current_timer: int = 3     # 当前计时
    intent: str = "attack"     # attack, charge, defend
    
    def tick(self) -> str:
        """回合推进，返回意图"""
        self.current_timer -= 1
        if self.current_timer <= 0:
            self.current_timer = self.action_timer
            return "attack"
        return "charge"
    
    def take_damage(self, amount: int):
        self.hp = max(0, self.hp - amount)
    
    def is_dead(self) -> bool:
        return self.hp <= 0


class CombatPhase(Enum):
    """战斗阶段"""
    LOADING = "loading"   # 装填阶段
    BATTLE = "battle"     # 战斗阶段
    VICTORY = "victory"   # 胜利
    DEFEAT = "defeat"     # 失败


@dataclass
class CardCombatState:
    """卡牌战斗状态"""
    # 词库
    word_pool: List[WordCard] = field(default_factory=list)
    
    # 弹仓 (已装填)
    hand: List[WordCard] = field(default_factory=list)
    hand_size: int = 6
    
    # 敌人
    enemy: Enemy = None
    
    # 玩家状态
    player_block: int = 0
    
    # 当前阶段
    phase: CombatPhase = CombatPhase.LOADING
    
    # 当前出牌
    current_card: Optional[WordCard] = None
    current_options: Optional[List[str]] = None
    
    # 统计
    turns: int = 0
    
    def __post_init__(self):
        if self.enemy is None:
            self.enemy = Enemy()
    
    def load_card(self, card: WordCard) -> bool:
        """装填卡牌到弹仓"""
        if len(self.hand) >= self.hand_size:
            return False
        self.hand.append(card)
        return True
    
    def unload_card(self, card: WordCard):
        """移除卡牌"""
        if card in self.hand:
            self.hand.remove(card)
    
    def count_attack_cards(self) -> int:
        """统计红卡数量"""
        return sum(1 for c in self.hand if c.card_type == CardType.ATTACK)
    
    def can_start_battle(self) -> bool:
        """检查能否开始战斗"""
        return len(self.hand) == self.hand_size and self.count_attack_cards() >= 3
    
    def start_battle(self):
        """开始战斗"""
        self.phase = CombatPhase.BATTLE
        self.turns = 0
    
    def play_card(self, card: WordCard):
        """出牌"""
        self.current_card = card
        if card in self.hand:
            self.hand.remove(card)


@dataclass
class Player:
    """玩家"""
    id: int = 1
    gold: int = 0
    hp: int = 100
    max_hp: int = 100
    block: int = 0
    inventory: List[str] = field(default_factory=list)
    relics: List[str] = field(default_factory=list)
    current_room: int = 0
    
    def change_hp(self, amount: int):
        # 先扣护甲
        if amount < 0 and self.block > 0:
            absorbed = min(self.block, -amount)
            self.block -= absorbed
            amount += absorbed
            if absorbed > 0:
                st.toast(f"🛡️ 护甲吸收 {absorbed}", icon="🛡️")
        
        self.hp += amount
        self.hp = max(0, min(self.hp, self.max_hp))
        
        if amount < 0:
            st.toast(f"💔 HP {amount}", icon="🩸")
        elif amount > 0:
            st.toast(f"💚 HP +{amount}", icon="🌿")
    
    def add_block(self, amount: int):
        self.block += amount
        st.toast(f"🛡️ +{amount} 护甲", icon="🛡️")
    
    def add_gold(self, amount: int):
        self.gold += amount
        st.toast(f"💰 +{amount}G")
    
    def is_dead(self) -> bool:
        return self.hp <= 0
    
    def reset_block(self):
        """回合结束重置护甲"""
        self.block = 0
    
    def advance_room(self):
        self.current_room += 1


@dataclass
class Node:
    """地图节点"""
    type: NodeType
    level: int
    data: Dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"


@dataclass
class BossState:
    """Boss 战状态"""
    phase: str = "loading"
    article: Optional[Dict] = None
    quizzes: Optional[Dict] = None
    quiz_idx: int = 0
    boss_hp: int = 100
    boss_max_hp: int = 100
    api_error: Optional[str] = None
