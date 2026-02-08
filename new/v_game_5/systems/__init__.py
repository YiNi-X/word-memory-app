# ==========================================
# Systems 包初始化
# ==========================================
import sys
from pathlib import Path

# 添加父目录到路径
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

from systems.word_pool import WordPool
from systems.map_system import MapSystem
from systems.trigger_bus import TriggerBus, TriggerContext
from systems.combat_engine import CombatEngine
from systems.combat_events import CombatEvent, CombatResult

__all__ = [
    'WordPool',
    'MapSystem',
    'TriggerBus',
    'TriggerContext',
    'CombatEngine',
    'CombatEvent',
    'CombatResult',
]
