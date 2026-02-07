from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from registries import RelicRegistry
from systems.conditions import conditions_met
from systems.effects import apply_effects


@dataclass
class TriggerContext:
    player: Any
    enemy: Optional[Any] = None
    card: Optional[Any] = None
    combat_state: Optional[Any] = None
    data: Dict[str, Any] = field(default_factory=dict)


class TriggerBus:
    @staticmethod
    def trigger(trigger: str, ctx: TriggerContext) -> Dict[str, Any]:
        result = {"trigger": trigger, "applied": []}

        if ctx is None or ctx.player is None:
            return result

        relic_ids = getattr(ctx.player, "relics", [])
        for relic_id in relic_ids:
            relic = RelicRegistry.get(relic_id)
            if not relic:
                continue
            if relic.trigger != trigger:
                continue
            if not conditions_met(relic, ctx):
                continue
            if apply_effects(relic, ctx):
                result["applied"].append(relic_id)

        return result
