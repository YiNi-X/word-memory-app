# ==========================================
# 📦 数据模型 - v5.4 系统升级
# ==========================================
from __future__ import annotations
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import random
import streamlit as st
from config import HAND_SIZE, GOLD_CARD_USES


class GamePhase(Enum):
    """游戏阶段"""
    MAIN_MENU = -1      # 主菜单
    WORD_LIBRARY = -2   # 单词图书馆
    LOBBY = 0           # 大厅 (旧)
    MAP_SELECT = 1      # 地图选择
    IN_NODE = 2         # 节点中
    DRAFTING = 3        # 战后抓牌
    GAME_OVER = 4       # 游戏结束
    VICTORY = 5         # 胜利
    TOWER_PREP = 6      # 爬塔前准备


class NodeType(Enum):
    """节点类型"""
    COMBAT = "⚔️ 战斗"
    ELITE = "☠️ 精英"
    EVENT = "❓ 事件"
    REST = "🔥 营地"
    SHOP = "🛒 商店"
    BOSS = "👹 首领"


class WordTier(IntEnum):
    """单词熟练度等级"""
    LV0 = 0  # 新词
    LV1 = 1  # 模糊
    LV2 = 2  # 清晰
    LV3 = 3  # 掌握
    LV4 = 4  # 精通
    LV5 = 5  # 封存


class WordPriority(Enum):
    """单词优先级"""
    PINNED = "pinned"   # 用户手动添加
    GHOST = "ghost"     # 历史失败
    NORMAL = "normal"   # 普通


# ==========================================
# 🎴 卡牌系统 v5.4
# ==========================================
class CardType(Enum):
    """卡牌类型 - v6.0"""
    RED_BERSERK = "red"      # Lv0-1: 狂暴攻击
    BLUE_HYBRID = "blue"     # Lv2-3: 混合型
    GOLD_SUPPORT = "gold"    # Lv4-5: 辅助型
    BLACK_CURSE = "black"    # 黑化卡牌（本局有效）
    
    @property
    def color(self) -> str:
        colors = {
            "red": "#e74c3c",
            "blue": "#3498db", 
            "gold": "#f39c12",
            "black": "#2c2c2c"
        }
        return colors.get(self.value, "#ffffff")
    
    @property
    def icon(self) -> str:
        icons = {"red": "🟥", "blue": "🟦", "gold": "🟨", "black": "🖤"}
        return icons.get(self.value, "⬜")
    
    @property
    def name_cn(self) -> str:
        names = {"red": "狂暴", "blue": "混合", "gold": "辅助", "black": "诅咒"}
        return names.get(self.value, "未知")
    
    @staticmethod
    def from_tier(tier: int) -> 'CardType':
        """根据熟练度返回卡牌类型"""
        if tier <= 1:
            return CardType.RED_BERSERK
        elif tier <= 3:
            return CardType.BLUE_HYBRID
        else:
            return CardType.GOLD_SUPPORT


# 卡牌属性配置
CARD_STATS = {
    CardType.RED_BERSERK: {
        "damage": 15,
        "block": 0,
        "penalty": 5,
        "draw": 0,
        "buff": None
    },
    CardType.BLUE_HYBRID: {
        "damage": 8,
        "block": 8,
        "penalty": 0,
        "draw": 0,
        "buff": None
    },
    CardType.GOLD_SUPPORT: {
        "damage": 5,
        "block": 0,
        "penalty": 0,
        "draw": 2,
        "buff": "next_card_x2"  # 下张卡效果翻倍
    },
    CardType.BLACK_CURSE: {
        "damage": 20,
        "block": 0,
        "penalty": 15,
        "draw": 0,
        "buff": None
    }
}


@dataclass
class WordCard:
    """单词卡牌"""
    word: str
    meaning: str
    tier: int
    _card_type: CardType = field(default=None, repr=False)
    learned: bool = False
    consecutive_correct: int = 0
    priority: str = "normal"
    wrong_streak: int = 0      # 本局连续错误计数（用于降级逻辑）
    is_blackened: bool = False # 是否已黑化（本局状态）
    temp_level: str = None     # 局内颜色状态 (red/blue/gold/black)
    is_temporary_buffed: bool = False # 蓝卡回血 5 Buff
    gold_uses_remaining: int = 0  # ????????(??????)
    
    @property
    def card_type(self) -> CardType:
        """根据黑化状态或 tier 计算卡牌类型"""
        if self.is_blackened:
            return CardType.BLACK_CURSE
        if self.temp_level:
            mapping = {"red": CardType.RED_BERSERK, "blue": CardType.BLUE_HYBRID, "gold": CardType.GOLD_SUPPORT, "black": CardType.BLACK_CURSE}
            return mapping.get(self.temp_level, CardType.from_tier(self.tier))
        return CardType.from_tier(self.tier)
    
    @property
    def icon(self) -> str:
        return self.card_type.icon
    
    @property
    def stats(self) -> dict:
        return CARD_STATS.get(self.card_type, {})
    
    @property
    def damage(self) -> int:
        return self.stats.get("damage", 0)
    
    @property
    def block(self) -> int:
        return self.stats.get("block", 0)

    @property
    def penalty(self) -> int:
        return self.stats.get("penalty", 0)
    
    @property
    def draw(self) -> int:
        return self.stats.get("draw", 0)
    
    @property
    def buff(self) -> Optional[str]:
        return self.stats.get("buff")
    
    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "meaning": self.meaning,
            "tier": self.tier,
            "card_type": self.card_type.value,
            "learned": self.learned,
            "consecutive_correct": self.consecutive_correct,
            "priority": self.priority
        }


@dataclass
class Enemy:
    """敌人 v6.0 - 随层数动态增强"""
    name: str = "词汇魔物"
    level: int = 1
    hp: int = 100
    max_hp: int = 100
    attack: int = 10
    base_attack: int = 10  # 基础攻击力
    attack_count: int = 0  # 攻击次数（用于递增伤害）
    action_timer: int = 3  # ?3-5??????
    current_timer: int = 3
    turns_elapsed: int = 0  # ????
    intent: str = "attack"
    is_elite: bool = False  # 是否精英怪
    is_boss: bool = False   # 是否 Boss (虽然 Boss 战单独处理，但为了 registry 兼容需要此字段)
    use_fixed_stats: bool = False  # Use provided stats instead of scaling by level.
    max_turns: Optional[int] = None  # Auto-die after this many enemy turns.
    attack_interval: Optional[int] = None  # Fixed attack interval.
    fixed_attack: Optional[int] = None  # Fixed attack damage.
    fixed_timer: Optional[int] = None  # Initial countdown for fixed attacks.

    def __post_init__(self):
        from config import ENEMY_HP_BASE, ENEMY_HP_ELITE, ENEMY_HP_GROWTH, ENEMY_ATTACK
        if self.use_fixed_stats:
            if self.fixed_attack is None:
                self.fixed_attack = self.attack
            self.base_attack = self.attack
            self.attack = self.fixed_attack
            if self.fixed_timer is None:
                self.fixed_timer = self.action_timer
            if self.attack_interval is None:
                self.attack_interval = self.fixed_timer
            self.action_timer = self.fixed_timer
            self.current_timer = self.fixed_timer
            self.max_hp = max(self.max_hp, self.hp)
            self.turns_elapsed = 0
            return
        if self.is_elite:
            base_hp = ENEMY_HP_ELITE + max(0, self.level - 1) * ENEMY_HP_GROWTH
        else:
            base_hp = ENEMY_HP_BASE + max(0, self.level - 1) * ENEMY_HP_GROWTH
        self.base_attack = ENEMY_ATTACK
        self.hp = base_hp
        self.max_hp = base_hp
        self.attack = self.base_attack
        self.action_timer = random.randint(3, 5)
        self.current_timer = self.action_timer
        self.turns_elapsed = 0

    def tick(self) -> str:
        self.turns_elapsed += 1
        if self.max_turns is not None and self.turns_elapsed > self.max_turns:
            self.hp = 0
            return "dead"

        if self.use_fixed_stats:
            self.current_timer -= 1
            if self.current_timer <= 0:
                self.current_timer = self.attack_interval or self.fixed_timer or 1
                if self.fixed_attack is not None:
                    self.attack = self.fixed_attack
                return "attack"
            return "charge"

        self.current_timer -= 1
        if self.current_timer <= 0:
            self.current_timer = random.randint(3, 5)
            self.attack = self.base_attack + max(0, self.turns_elapsed - 3) * 3
            return "attack"
        return "charge"
    def take_damage(self, amount: int):
        self.hp = max(0, self.hp - amount)
    
    def is_dead(self) -> bool:
        return self.hp <= 0


class CombatPhase(Enum):
    """战斗阶段"""
    LOADING = "loading"
    BATTLE = "battle"
    VICTORY = "victory"
    DEFEAT = "defeat"


@dataclass
class CardCombatState:
    """卡牌战斗状态 v6.0"""
    player: Player
    deck: List[WordCard]
    enemy: Enemy = None
    word_pool: List[WordCard] = field(default_factory=list) # 用于干扰项生成
    hand: List[WordCard] = field(default_factory=list)
    discard: List[WordCard] = field(default_factory=list)
    draw_pile: List[WordCard] = field(default_factory=list)
    exhausted: List[WordCard] = field(default_factory=list)
    hand_size: int = HAND_SIZE
    phase: CombatPhase = CombatPhase.LOADING
    current_card: Optional[WordCard] = None
    current_options: Optional[List[str]] = None
    turns: int = 0
    next_card_multiplier: int = 1  # 下张卡效果倍率
    extra_actions: int = 0  # 额外出牌次数（本回合）
    last_card_type: Optional[CardType] = None
    red_streak: int = 0
    blue_streak: int = 0
    color_sequence: List[CardType] = field(default_factory=list)
    agang_active: bool = False
    agang_red_count: int = 0
    bleed_damage: int = 0
    bleed_turns: int = 0
    nunchaku_used: bool = False
    extra_action_only_red: bool = False
    
    def __post_init__(self):
        if self.enemy is None:
            self.enemy = Enemy()

        # ????????
        if self.player:
            self.hand_size = self.player.hand_size

        # gold uses (wizard hat sets to 2)
        gold_uses = 2 if "WIZARD_HAT" in getattr(self.player, "relics", []) else GOLD_CARD_USES
        for c in self.deck:
            if c.card_type == CardType.GOLD_SUPPORT:
                c.gold_uses_remaining = gold_uses

        # ?????? (??)
        self.draw_pile = self.deck.copy()
        random.shuffle(self.draw_pile)

        # ????? (?????)
        self.word_pool = self.deck.copy()

        # ???????
        self.player.reset_block()

    def ensure_black_in_hand(self) -> bool:
        """若有黑卡，保证至少一张进入手牌"""
        if any(c.card_type == CardType.BLACK_CURSE for c in self.hand):
            return False
        for c in list(self.draw_pile):
            if c.card_type == CardType.BLACK_CURSE:
                self.draw_pile.remove(c)
                self.hand.append(c)
                return True
        return False

    def load_card(self, card: WordCard) -> bool:
        if len(self.hand) >= self.hand_size:
            return False
        self.hand.append(card)
        return True
    
    def unload_card(self, card: WordCard):
        if card in self.hand:
            self.hand.remove(card)
    
    def count_by_type(self, card_type: CardType) -> int:
        return sum(1 for c in self.hand if c.card_type == card_type)
    
    def can_start_battle(self) -> bool:
        # 移除红卡限制：只要有 3+ 张卡即可开战
        return len(self.hand) >= 3
    
    def start_battle(self):
        self.phase = CombatPhase.BATTLE
        self.turns = 0
    
    def _remove_from_all_piles(self, card: WordCard):
        for pile in (self.deck, self.draw_pile, self.discard, self.hand, self.exhausted):
            while card in pile:
                pile.remove(card)

    def play_card(self, card: WordCard) -> bool:
        self.current_card = card
        removed = False
        if card in self.hand:
            self.hand.remove(card)
            if card.card_type == CardType.GOLD_SUPPORT:
                if card.gold_uses_remaining > 0:
                    card.gold_uses_remaining -= 1
                if card.gold_uses_remaining <= 0:
                    removed = True
                    self._remove_from_all_piles(card)
                    return removed
            self.discard.append(card)  # discard after play
        return removed
    def recycle_discard(self) -> bool:
        """将弃牌堆洗回抽牌堆（杀戮尖塔机制）"""
        if not self.discard:
            return False
        import random
        self.draw_pile = self.discard.copy()
        random.shuffle(self.draw_pile)
        self.discard.clear()
        return True
    
    def draw_card(self) -> Optional[WordCard]:
        """???????????"""
        if not self.draw_pile:
            if not self.recycle_discard():
                return None

        if self.draw_pile:
            candidates = self.draw_pile
            weights = []
            for c in candidates:
                if c.card_type == CardType.RED_BERSERK:
                    base = 50
                elif c.card_type == CardType.BLUE_HYBRID:
                    base = 30
                elif c.card_type == CardType.GOLD_SUPPORT:
                    base = 20
                else:
                    base = 50

                if getattr(c, "wrong_streak", 0) > 0:
                    base *= 1.8
                if getattr(c, "priority", "") == "ghost":
                    base *= 1.5

                weights.append(base)

            selected = random.choices(candidates, weights=weights, k=1)[0]
            self.draw_pile.remove(selected)
            self.hand.append(selected)
            return selected
        return None

    def draw_with_preference(self, prefer_types: List[CardType], count: int) -> List[WordCard]:
        """Draw cards with preferred types first."""
        drawn: List[WordCard] = []
        for _ in range(count):
            if not self.draw_pile:
                if not self.recycle_discard():
                    break
            selected = None
            for t in prefer_types:
                candidates = [c for c in self.draw_pile if c.card_type == t]
                if candidates:
                    selected = random.choice(candidates)
                    break
            if selected is None:
                selected = self.draw_card()
                if selected is not None:
                    drawn.append(selected)
                continue
            self.draw_pile.remove(selected)
            self.hand.append(selected)
            drawn.append(selected)
        return drawn
@dataclass
class Player:
    """玩家"""
    id: int = 1
    gold: int = 50
    hp: int = 100
    max_hp: int = 100
    armor: int = 0                    # 护甲值
    deck: List[WordCard] = field(default_factory=list)  # 当前卡组
    inventory: List[str] = field(default_factory=list)
    relics: List[str] = field(default_factory=list)
    current_room: int = 0
    # v6.0 新增属性
    hand_size: int = HAND_SIZE
    purchase_counts: Dict[str, int] = field(default_factory=lambda: {"red": 0, "blue": 0, "gold": 0})
    deck_limit: int = 9               # 卡组上限
    blue_card_heal_buff: bool = False # 蓝卡回血 Buff (兼容旧代码，新逻辑在卡牌上)
    gold_card_purchased: bool = False # 是否已购买金卡 (兼容旧字段)
    
    def change_hp(self, amount: int, notify=None):
        def emit(level: str, text: str, icon: str = None):
            if notify:
                notify(level, text, icon)
                return
            if level == "success":
                st.success(text)
            elif level == "warning":
                st.warning(text)
            elif level == "error":
                st.error(text)
            else:
                st.toast(text, icon=icon)

        if "MONKEY_PAW" in self.relics and self.max_hp > 50:
            self.max_hp = 50
            self.hp = min(self.hp, self.max_hp)
        # v6.0 ???????????
        if amount < 0 and st.session_state.get("_greedy_curse", False):
            amount *= 2
            emit("warning", "\u8d2a\u5a6a\u4e4b\u7406\uff1a\u53d7\u5230\u4f24\u5bb3\u7ffb\u500d")

        if amount > 0 and "PAIN_ARMOR" in self.relics:
            amount = int(amount * 0.5)

        # ??????
        if amount < 0 and self.armor > 0:
            absorbed = min(self.armor, -amount)
            self.armor -= absorbed
            amount += absorbed
            if absorbed > 0:
                emit("toast", f"\u62a4\u7532\u5438\u6536 {absorbed}")

        if amount < 0 and "MONKEY_PAW" in self.relics:
            if self.hp + amount <= 0 and not st.session_state.get("_monkey_paw_used", False):
                st.session_state._monkey_paw_used = True
                self.hp = 1
                emit("warning", "\u7334\u722a\u62b5\u5fa1\u81f4\u547d\u4f24\u5bb3")
                return

        self.hp += amount
        # ???? HP ???change_hp ??? [0, max_hp] ??
        self.hp = max(0, min(self.hp, self.max_hp))

        if self.hp <= 0:
            emit("error", "\u4f60\u5012\u4e0b\u4e86...")
        elif amount < 0:
            emit("warning", f"\u751f\u547d {amount}")
        elif amount > 0:
            emit("success", f"\u751f\u547d +{amount}")

    def add_armor(self, amount: int, notify=None):
        self.armor += amount
        if notify:
            notify("toast", f"\u62a4\u7532 +{amount}")
        else:
            st.toast(f"\u62a4\u7532 +{amount}")

    def add_gold(self, amount: int, notify=None):
        self.gold += amount
        if notify:
            notify("toast", f"\u91d1\u5e01 +{amount}")
        else:
            st.toast(f"\u91d1\u5e01 +{amount}")

    def is_dead(self) -> bool:
        return self.hp <= 0
    
    def reset_block(self):
        self.armor = 0
    
    def advance_room(self):
        self.current_room += 1
    
    def add_card_to_deck(self, card: WordCard):
        """添加卡牌到卡组"""
        if "UNDYING_CURSE" in self.relics:
            card.is_blackened = True
            card.temp_level = "black"
        self.deck.append(card)


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
    boss_hp: int = 200
    boss_max_hp: int = 200
    armor: int = 0
    phase: str = 'article'  # 'article', 'quiz', 'victory'
    article: dict = None
    quizzes: dict = None
    quiz_idx: int = 0
    turn: int = 0
    post_quiz_attack: int = 20 # 狂暴后基础伤害
    triggered_100hp_shield: bool = False # 是否触发过 100HP 护盾
    api_error: Optional[str] = None
    # v6.0 新增属性
    armor: int = 0                        # Boss 护甲
    triggered_100hp_shield: bool = False  # 是否已触发100血护甲
    turn: int = 0                         # 回合计数


@dataclass
class RunState:
    """存档状态"""
    player: Optional[Player] = None
    floor: int = 0
    total_floors: int = 6
    deck: List[dict] = field(default_factory=list)
    in_progress: bool = False
