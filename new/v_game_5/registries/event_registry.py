# ==========================================
# ❓ 事件注册表
# ==========================================
"""
📝 扩展指南：添加新事件

在 EVENTS 字典中添加:
"YOUR_EVENT_ID": EventConfig(
    name="事件名称",
    icon="🎭",
    description="事件描述",
    choices=[
        EventChoice(text="选项文本", effect="heal", value=20),
        EventChoice(text="选项文本", effect="damage", value=-10),
    ]
)

支持的 effect 类型:
- "heal": 回复 HP (value > 0)
- "damage": 扣除 HP (value < 0)
- "gold": 获得/扣除金币
- "max_hp": 增加最大 HP
- "item": 获得道具 (value 为道具 ID)
- "relic": 获得圣遗物 (value 为圣遗物 ID)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class EventChoice:
    """事件选项"""
    text: str
    effect: str  # "heal", "damage", "gold", "max_hp", "item", "relic"
    value: Any = 0
    cost_gold: int = 0  # 需要消耗的金币
    condition: Optional[str] = None  # 条件 (如 "gold >= 30")


@dataclass
class EventConfig:
    """事件配置"""
    name: str
    icon: str
    description: str
    choices: List[EventChoice] = field(default_factory=list)
    flavor_text: str = ""  # 背景故事


# ==========================================
# 🎯 事件定义 (v6.0 更新)
# ==========================================
EVENTS: Dict[str, EventConfig] = {
    
    "FOUNTAIN": EventConfig(
        name="遗忘之泉",
        icon="🌊",
        description="泉水中浮现出一个单词的影子...",
        flavor_text="或许答对了可以拯救一张黑卡。",
        choices=[
            EventChoice(text="填写单词 (成功可恢复黑卡)", effect="fill_blank_test"),
            EventChoice(text="离开", effect="none", value=0),
        ]
    ),
    
    "SCROLL": EventConfig(
        name="古老卷轴",
        icon="📜",
        description="你发现了一张破损的卷轴，上面写满了神秘符文...",
        choices=[
            EventChoice(text="阅读卷轴 (-10 HP, +50 金币)", effect="trade", value={"hp": -10, "gold": 50}),
            EventChoice(text="带走卷轴 (获得道具)", effect="item", value="SCROLL"),
            EventChoice(text="离开", effect="none", value=0),
        ]
    ),
    
    "MERCHANT": EventConfig(
        name="神秘商人",
        icon="🎭",
        description="一个戴面具的商人出现在你面前...",
        choices=[
            EventChoice(text="购买强化 (30G → +10 最大HP)", effect="max_hp", value=10, cost_gold=30),
            EventChoice(text="购买药水 (20G → +40 HP)", effect="heal", value=40, cost_gold=20),
            EventChoice(text="拒绝", effect="none", value=0),
        ]
    ),
    
    "SHRINE": EventConfig(
        name="祭坛祈愿",
        icon="⛩️",
        description="古老的祭坛似乎蕴含着某种力量...",
        choices=[
            EventChoice(text="献祭生命 (-20 HP, 获得随机圣遗物)", effect="relic", value="random", cost_gold=0),
            EventChoice(text="献祭金币 (50G, 回满 HP)", effect="full_heal", value=0, cost_gold=50),
            EventChoice(text="离开", effect="none", value=0),
        ]
    ),
    
    "TREASURE": EventConfig(
        name="遗忘宝箱",
        icon="📦",
        description="一个被遗忘的宝箱静静躺在角落...似乎有危险的气息。",
        choices=[
            EventChoice(text="打开宝箱 (50%概率: -20HP / +30-50金币)", effect="risky_treasure"),
            EventChoice(text="谨慎离开", effect="none", value=0),
        ]
    ),
    
    "REST_UPGRADE": EventConfig(
        name="铁匠营地",
        icon="⚒️",
        description="一个流浪铁匠在此扎营...",
        choices=[
            EventChoice(text="休息 (+30 HP)", effect="heal", value=30),
            EventChoice(text="升级蓝卡 (100G, 蓝卡附加回血效果)", effect="upgrade_blue_cards", cost_gold=100),
            EventChoice(text="快速离开", effect="none", value=0),
        ]
    ),
    
    # v6.0 新增事件
    "FALLEN_ADVENTURER": EventConfig(
        name="勇者之尸",
        icon="💀",
        description="前面似乎趴着一个人...",
        flavor_text="不知道发生了什么，但包里可能有好东西。",
        choices=[
            EventChoice(text="迅速远离", effect="none", value=0),
            EventChoice(text="翻翻背包有什么", effect="adventurer_loot"),
        ]
    ),
    
    "MYSTERIOUS_BOOK": EventConfig(
        name="神秘书籍",
        icon="📕",
        description="有一本书静静地躺在你前面...",
        flavor_text="书页间似乎飘散着奇异的气息。",
        choices=[
            EventChoice(text="翻阅", effect="book_read"),
            EventChoice(text="离开", effect="none", value=0),
        ]
    ),
}


class EventRegistry:
    """事件注册表管理器"""
    
    @staticmethod
    def get(event_id: str) -> Optional[EventConfig]:
        return EVENTS.get(event_id)
    
    @staticmethod
    def get_all() -> Dict[str, EventConfig]:
        return EVENTS.copy()
    
    @staticmethod
    def get_random() -> tuple:
        import random
        event_id = random.choice(list(EVENTS.keys()))
        return event_id, EVENTS[event_id]
    
    @staticmethod
    def register(event_id: str, config: EventConfig):
        """动态注册新事件"""
        EVENTS[event_id] = config
