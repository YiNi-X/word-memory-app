# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CombatEvent:
    level: str
    text: str
    icon: Optional[str] = None


@dataclass
class CombatResult:
    events: List[CombatEvent] = field(default_factory=list)
    enemy_dead: bool = False
    player_dead: bool = False
    should_rerun: bool = False
    should_enemy_turn: bool = False
