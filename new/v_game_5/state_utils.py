import streamlit as st


COMBAT_FLAGS = [
    "_item_shield",
    "_item_damage_reduce",
    "_item_hint",
    "_greedy_curse",
    "_player_stunned",
]


def reset_combat_flags():
    """Clear transient combat-related session_state flags."""
    for key in COMBAT_FLAGS:
        if key in st.session_state:
            del st.session_state[key]
