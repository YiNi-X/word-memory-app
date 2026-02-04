# ==========================================
# 📚 注册表包初始化
# ==========================================
import sys
from pathlib import Path

# 添加父目录到路径
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

from registries.combat_registry import CombatRegistry, COMBAT_TYPES
from registries.event_registry import EventRegistry, EVENTS
from registries.shop_registry import ShopRegistry, SHOP_ITEMS
from registries.relic_registry import RelicRegistry, RELICS

__all__ = [
    'CombatRegistry', 'COMBAT_TYPES',
    'EventRegistry', 'EVENTS',
    'ShopRegistry', 'SHOP_ITEMS',
    'RelicRegistry', 'RELICS'
]
