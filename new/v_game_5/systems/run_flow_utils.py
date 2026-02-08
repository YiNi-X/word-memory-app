from typing import Any, Dict


MAP_STATE_FIELDS = (
    "normal_combats_remaining",
    "elite_combats_remaining",
    "normal_combats_completed",
    "elite_combats_completed",
    "boss_sequence_step",
    "non_combat_streak",
)


def dump_map_state(game_map: Any) -> Dict[str, int]:
    if game_map is None:
        return {}
    return {field: int(getattr(game_map, field, 0) or 0) for field in MAP_STATE_FIELDS}


def restore_map_state(game_map: Any, state: Dict[str, Any] | None) -> None:
    if game_map is None:
        return
    payload = state or {}
    for field in MAP_STATE_FIELDS:
        if field in payload:
            setattr(game_map, field, int(payload[field] or 0))


def convert_event_node_to_combat(node: Any, combat_node_type: Any) -> None:
    if node is None:
        return
    node.type = combat_node_type
    node.data = {}


def rollback_purchase_counts(purchase_counts: Dict[str, int], pending_type: str) -> Dict[str, int]:
    updated = dict(purchase_counts or {})
    if pending_type in ("red", "blue"):
        updated[pending_type] = max(0, int(updated.get(pending_type, 0)) - 1)
    elif pending_type == "gold":
        updated["gold"] = 0
    return updated
