# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Dict, Optional, Any
import random


@dataclass
class ShopItem:
    name: str
    icon: str
    description: str
    price: int
    effect: str
    value: Any = 0
    consumable: bool = True


SHOP_ITEMS: Dict[str, ShopItem] = {
    "POTION_SMALL": ShopItem(
        name="小型生命药水",
        icon="🧪",
        description="恢复 30 生命",
        price=20,
        effect="heal",
        value=30,
    ),
    "POTION_LARGE": ShopItem(
        name="大型生命药水",
        icon="🧪",
        description="恢复 60 生命",
        price=40,
        effect="heal",
        value=60,
    ),
    "SHIELD": ShopItem(
        name="护盾卷轴",
        icon="🛡️",
        description="下一次敌人攻击伤害为 0",
        price=50,
        effect="shield",
        value=1,
    ),
    "HINT_SCROLL": ShopItem(
        name="智慧卷轴",
        icon="📜",
        description="下一次战斗可使用一次提示",
        price=40,
        effect="hint",
        value=1,
    ),
    "SCROLL": ShopItem(
        name="提示卷轴",
        icon="🧾",
        description="战斗中移除 2 个错误选项",
        price=0,
        effect="hint",
        value=1,
    ),
    "MAX_HP_UP": ShopItem(
        name="生命精华",
        icon="❤️",
        description="永久增加 10 最大生命",
        price=60,
        effect="max_hp",
        value=10,
        consumable=False,
    ),
    "DAMAGE_REDUCE": ShopItem(
        name="坚韧护符",
        icon="🧿",
        description="下一次敌人攻击伤害 -5",
        price=45,
        effect="damage_reduce",
        value=5,
    ),
    "GOLD_BOOST": ShopItem(
        name="财运符文",
        icon="💰",
        description="本局金币获取 +50%",
        price=35,
        effect="gold_boost",
        value=0.5,
    ),
    "RELIC_PHILOSOPHERS_STONE": ShopItem(
        name="哲学家之石",
        icon="🪨",
        description="获得圣遗物：哲学家之石",
        price=90,
        effect="grant_relic",
        value="PHILOSOPHERS_STONE",
        consumable=False,
    ),
    "RELIC_BLOOD_CRYSTAL": ShopItem(
        name="血之水晶",
        icon="💎",
        description="获得圣遗物：血之水晶",
        price=70,
        effect="grant_relic",
        value="BLOOD_CRYSTAL",
        consumable=False,
    ),
    "RELIC_GOLD_CHARM": ShopItem(
        name="金币护符",
        icon="🧿",
        description="获得圣遗物：金币护符",
        price=60,
        effect="grant_relic",
        value="GOLD_CHARM",
        consumable=False,
    ),
    "RELIC_WINE": ShopItem(
        name="酒",
        icon="🍶",
        description="获得圣遗物：酒",
        price=50,
        effect="grant_relic",
        value="WINE",
        consumable=False,
    ),
    "RELIC_CURSED_BLOOD": ShopItem(
        name="诅咒之血",
        icon="🧛",
        description="获得圣遗物：诅咒之血",
        price=60,
        effect="grant_relic",
        value="CURSED_BLOOD",
        consumable=False,
    ),
    "RELIC_FIGHTER_SOUL": ShopItem(
        name="格斗家之魂",
        icon="🥊",
        description="获得圣遗物：格斗家之魂",
        price=70,
        effect="grant_relic",
        value="FIGHTER_SOUL",
        consumable=False,
    ),
    "RELIC_MONKEY_PAW": ShopItem(
        name="猴爪",
        icon="🐒",
        description="获得圣遗物：猴爪",
        price=80,
        effect="grant_relic",
        value="MONKEY_PAW",
        consumable=False,
    ),
    "RELIC_UNDYING_CURSE": ShopItem(
        name="不死诅咒",
        icon="☠️",
        description="获得圣遗物：不死诅咒",
        price=60,
        effect="grant_relic",
        value="UNDYING_CURSE",
        consumable=False,
    ),
    "RELIC_AGANG_WRATH": ShopItem(
        name="阿刚之怒",
        icon="💢",
        description="获得圣遗物：阿刚之怒",
        price=70,
        effect="grant_relic",
        value="AGANG_WRATH",
        consumable=False,
    ),
}


class ShopRegistry:
    @staticmethod
    def get(item_id: str) -> Optional[ShopItem]:
        return SHOP_ITEMS.get(item_id)

    @staticmethod
    def get_all() -> Dict[str, ShopItem]:
        return SHOP_ITEMS.copy()

    @staticmethod
    def get_random_selection(count: int = 3) -> Dict[str, ShopItem]:
        keys = random.sample(list(SHOP_ITEMS.keys()), min(count, len(SHOP_ITEMS)))
        return {k: SHOP_ITEMS[k] for k in keys}

    @staticmethod
    def get_shop_inventory(total_slots: int = 4, relic_chance: float = 0.2, exclude_relics: Optional[set] = None) -> Dict[str, Any]:
        from registries import RelicRegistry
        exclude_relics = exclude_relics or set()
        low_pool = set(RelicRegistry.get_pool("low"))
        relic_ids = [
            k for k, v in SHOP_ITEMS.items()
            if v.effect == "grant_relic" and v.value in low_pool and v.value not in exclude_relics
        ]
        normal_ids = [k for k, v in SHOP_ITEMS.items() if v.effect != "grant_relic"]

        inventory = {"relic_slots": [], "other_slots": []}

        if relic_ids:
            picks = random.sample(relic_ids, min(3, len(relic_ids)))
            inventory["relic_slots"] = [(rid, SHOP_ITEMS[rid]) for rid in picks]
            relic_ids = [rid for rid in relic_ids if rid not in picks]

        slots_to_fill = max(0, total_slots - 1)
        for _ in range(slots_to_fill):
            pool = normal_ids
            if not pool:
                break
            pick = random.choice(pool)
            inventory["other_slots"].append((pick, SHOP_ITEMS[pick]))
            if pick in normal_ids:
                normal_ids.remove(pick)

        return inventory

    @staticmethod
    def get_card_price(card_type: str, buy_count: int) -> int:
        from config import SHOP_RED_CARD_BASE_PRICE, SHOP_BLUE_CARD_BASE_PRICE, SHOP_GOLD_CARD_PRICE
        if card_type == "red":
            return SHOP_RED_CARD_BASE_PRICE * (buy_count + 1)
        if card_type == "blue":
            return SHOP_BLUE_CARD_BASE_PRICE * (buy_count + 1)
        if card_type == "gold":
            return SHOP_GOLD_CARD_PRICE
        return 0

    @staticmethod
    def register(item_id: str, item: ShopItem):
        SHOP_ITEMS[item_id] = item
