import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEMS_DIR = ROOT / "systems"
if str(SYSTEMS_DIR) not in sys.path:
    sys.path.insert(0, str(SYSTEMS_DIR))

from run_flow_utils import (
    convert_event_node_to_combat,
    dump_map_state,
    restore_map_state,
    rollback_purchase_counts,
)


class DummyNode:
    def __init__(self, node_type, data):
        self.type = node_type
        self.data = data


class DummyMap:
    def __init__(self):
        self.normal_combats_remaining = 10
        self.elite_combats_remaining = 6
        self.normal_combats_completed = 0
        self.elite_combats_completed = 0
        self.boss_sequence_step = 0
        self.non_combat_streak = 0


class SmokeCases(unittest.TestCase):
    def test_shop_purchase_rollback(self):
        counts = {"red": 2, "blue": 1, "gold": 1}
        red_back = rollback_purchase_counts(counts, "red")
        self.assertEqual(red_back["red"], 1)
        self.assertEqual(red_back["blue"], 1)
        self.assertEqual(red_back["gold"], 1)

        gold_back = rollback_purchase_counts(counts, "gold")
        self.assertEqual(gold_back["gold"], 0)
        self.assertEqual(gold_back["red"], 2)

    def test_event_switches_to_combat(self):
        node = DummyNode(node_type="EVENT", data={"event_id": "FALLEN_ADVENTURER"})
        convert_event_node_to_combat(node, "COMBAT")
        self.assertEqual(node.type, "COMBAT")
        self.assertEqual(node.data, {})

    def test_map_state_roundtrip(self):
        src = DummyMap()
        src.normal_combats_remaining = 3
        src.elite_combats_remaining = 1
        src.normal_combats_completed = 7
        src.elite_combats_completed = 5
        src.boss_sequence_step = 1
        src.non_combat_streak = 2

        state = dump_map_state(src)

        dst = DummyMap()
        restore_map_state(dst, state)

        self.assertEqual(dst.normal_combats_remaining, 3)
        self.assertEqual(dst.elite_combats_remaining, 1)
        self.assertEqual(dst.normal_combats_completed, 7)
        self.assertEqual(dst.elite_combats_completed, 5)
        self.assertEqual(dst.boss_sequence_step, 1)
        self.assertEqual(dst.non_combat_streak, 2)


if __name__ == "__main__":
    unittest.main()
