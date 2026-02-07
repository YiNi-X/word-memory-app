# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class EventChoice:
    text: str
    effect: str
    value: Any = 0
    cost_gold: int = 0
    condition: Optional[str] = None


@dataclass
class EventConfig:
    name: str
    icon: str
    description: str
    choices: List[EventChoice] = field(default_factory=list)
    flavor_text: str = ""


EVENTS: Dict[str, EventConfig] = {
    "FOUNTAIN": EventConfig(
        name="遗忘之泉",
        icon="⛲",
        description="泉水中浮现出一个单词的影子...",
        flavor_text="或许答对了可以拯救一张黑卡。",
        choices=[
            EventChoice(text="填写单词（成功可恢复黑卡）", effect="fill_blank_test"),
            EventChoice(text="离开", effect="none", value=0),
        ],
    ),
    "SCROLL": EventConfig(
        name="古老卷轴",
        icon="📜",
        description="你发现了一张破损的卷轴，上面写满了神秘符文...",
        choices=[
            EventChoice(text="阅读卷轴（-10 生命，+50 金币）", effect="trade", value={"hp": -10, "gold": 50}),
            EventChoice(text="带走卷轴（获得道具）", effect="item", value="SCROLL"),
            EventChoice(text="离开", effect="none", value=0),
        ],
    ),
    "MERCHANT": EventConfig(
        name="神秘商人",
        icon="🧙",
        description="一个戴面具的商人出现在你面前...",
        choices=[
            EventChoice(text="购买强化（30 金币 → +10 最大生命）", effect="max_hp", value=10, cost_gold=30),
            EventChoice(text="购买药水（20 金币 → +40 生命）", effect="heal", value=40, cost_gold=20),
            EventChoice(text="拒绝", effect="none", value=0),
        ],
    ),
    "SHRINE": EventConfig(
        name="祭坛祈愿",
        icon="⛩️",
        description="古老的祭坛似乎蕴含着某种力量...",
        choices=[
            EventChoice(text="献祭生命（-20 生命，获得随机圣遗物）", effect="relic", value="random", cost_gold=0),
            EventChoice(text="献祭金币（50 金币，回满生命）", effect="full_heal", value=0, cost_gold=50),
            EventChoice(text="离开", effect="none", value=0),
        ],
    ),
    "TREASURE": EventConfig(
        name="遗忘宝箱",
        icon="🧰",
        description="一个被遗忘的宝箱静静躺在角落...似乎有危险的气息。",
        choices=[
            EventChoice(text="打开宝箱（50% 概率：-20 生命 / +30~50 金币）", effect="risky_treasure"),
            EventChoice(text="谨慎离开", effect="none", value=0),
        ],
    ),
    "REST_UPGRADE": EventConfig(
        name="铁匠营地",
        icon="⚒️",
        description="一个流浪铁匠在此扎营...",
        choices=[
            EventChoice(text="休息（+30 生命）", effect="heal", value=30),
            EventChoice(text="升级蓝卡（100 金币，蓝卡附加回血效果）", effect="upgrade_blue_cards", cost_gold=100),
            EventChoice(text="快速离开", effect="none", value=0),
        ],
    ),
    "FALLEN_ADVENTURER": EventConfig(
        name="倒下的冒险者",
        icon="🧍",
        description="前方似乎躺着一个人...",
        flavor_text="不知发生了什么，但包里可能有好东西。",
        choices=[
            EventChoice(text="迅速远离", effect="none", value=0),
            EventChoice(text="翻找背包", effect="adventurer_loot"),
        ],
    ),
    "MYSTERIOUS_BOOK": EventConfig(
        name="神秘书卷",
        icon="📖",
        description="一本古旧的书静静躺在你面前...",
        flavor_text="书页间似乎飘散着奇异的气息。",
        choices=[
            EventChoice(text="翻阅", effect="book_read"),
            EventChoice(text="离开", effect="none", value=0),
        ],
    ),
}


class EventRegistry:
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
        EVENTS[event_id] = config
