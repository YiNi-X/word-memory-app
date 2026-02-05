# ==========================================
# 🛒 商店物品注册表
# ==========================================
"""
📝 扩展指南：添加新商店物品

在 SHOP_ITEMS 字典中添加:
"YOUR_ITEM_ID": ShopItem(
    name="物品名称",
    icon="🧪",
    description="物品描述",
    price=30,
    effect="heal",  # 效果类型
    value=50,       # 效果值
    consumable=True # 是否消耗品
)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any


@dataclass
class ShopItem:
    """商店物品配置"""
    name: str
    icon: str
    description: str
    price: int
    effect: str  # "heal", "max_hp", "shield", "hint", "damage_reduce"
    value: Any = 0
    consumable: bool = True  # 是否为消耗品


# ==========================================
# 🎯 商店物品定义 (在此添加新物品)
# ==========================================
SHOP_ITEMS: Dict[str, ShopItem] = {
    
    "POTION_SMALL": ShopItem(
        name="小型生命药水",
        icon="🧪",
        description="恢复 30 HP",
        price=20,
        effect="heal",
        value=30
    ),
    
    "POTION_LARGE": ShopItem(
        name="大型生命药水",
        icon="🧴",
        description="恢复 60 HP",
        price=40,
        effect="heal",
        value=60
    ),
    
    "SHIELD": ShopItem(
        name="逻辑护盾",
        icon="🛡️",
        description="Boss 战第一次伤害免疫",
        price=50,
        effect="shield",
        value=1
    ),
    
    "HINT_SCROLL": ShopItem(
        name="智慧卷轴",
        icon="📚",
        description="下次战斗可查看一次提示",
        price=40,
        effect="hint",
        value=1
    ),
    
    "MAX_HP_UP": ShopItem(
        name="生命精华",
        icon="❤️",
        description="永久增加 10 最大 HP",
        price=60,
        effect="max_hp",
        value=10,
        consumable=False  # 永久效果
    ),
    
    "DAMAGE_REDUCE": ShopItem(
        name="坚韧护符",
        icon="🔮",
        description="本局受到伤害 -5",
        price=45,
        effect="damage_reduce",
        value=5
    ),
    
    "GOLD_BOOST": ShopItem(
        name="财运符文",
        icon="💎",
        description="本局金币获取 +50%",
        price=35,
        effect="gold_boost",
        value=0.5
    ),
    
    # v6.0 新增：圣遗物销售
    "RELIC_PHILOSOPHERS_STONE": ShopItem(
        name="贤者之石",
        icon="💠",
        description="每次战斗结束回复 10 HP",
        price=125,
        effect="grant_relic",
        value="PHILOSOPHERS_STONE",
        consumable=False
    ),
    
    "RELIC_BLOOD_CRYSTAL": ShopItem(
        name="血之水晶",
        icon="🔴",
        description="答对卡牌时有 20% 概率回复 5 HP",
        price=100,
        effect="grant_relic",
        value="BLOOD_CRYSTAL",
        consumable=False
    ),
    
    "RELIC_GOLD_CHARM": ShopItem(
        name="金币护符",
        icon="🪙",
        description="每场战斗额外获得 15 金币",
        price=80,
        effect="grant_relic",
        value="GOLD_CHARM",
        consumable=False
    ),
}


class ShopRegistry:
    """商店物品注册表管理器"""
    
    @staticmethod
    def get(item_id: str) -> Optional[ShopItem]:
        return SHOP_ITEMS.get(item_id)
    
    @staticmethod
    def get_all() -> Dict[str, ShopItem]:
        return SHOP_ITEMS.copy()
    
    @staticmethod
    def get_random_selection(count: int = 3) -> Dict[str, ShopItem]:
        """获取随机商品列表"""
        import random
        keys = random.sample(list(SHOP_ITEMS.keys()), min(count, len(SHOP_ITEMS)))
        return {k: SHOP_ITEMS[k] for k in keys}
    
    @staticmethod
    def get_card_price(card_type: str, buy_count: int) -> int:
        """获取卡牌购买价格（递增）"""
        from config import SHOP_RED_CARD_BASE_PRICE, SHOP_BLUE_CARD_BASE_PRICE, SHOP_GOLD_CARD_PRICE
        
        if card_type == "red":
            return SHOP_RED_CARD_BASE_PRICE * (buy_count + 1)  # 25, 50, 75...
        elif card_type == "blue":
            return SHOP_BLUE_CARD_BASE_PRICE * (buy_count + 1)  # 50, 100, 150...
        elif card_type == "gold":
            return SHOP_GOLD_CARD_PRICE  # 固定 100G
        return 0
    
    @staticmethod
    def register(item_id: str, item: ShopItem):
        """动态注册新物品"""
        SHOP_ITEMS[item_id] = item
