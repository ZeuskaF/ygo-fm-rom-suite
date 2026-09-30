"""
Canonical Card Names, Types, and Guardian Stars for Yu-Gi-Oh! Forbidden Memories.
Covers all 722 official cards (IDs 001 to 722).
"""

from typing import Dict
from core.canonical_card_names import CANONICAL_CARD_NAMES

CARD_TYPES = [
    "Dragon",          # 0
    "Spellcaster",     # 1
    "Zombie",          # 2
    "Warrior",         # 3
    "Beast-Warrior",   # 4
    "Beast",           # 5
    "Winged Beast",    # 6
    "Fiend",           # 7
    "Fairy",           # 8
    "Insect",          # 9
    "Dinosaur",        # 10
    "Reptile",         # 11
    "Fish",            # 12
    "Sea Serpent",     # 13
    "Machine",         # 14
    "Thunder",         # 15
    "Aqua",            # 16
    "Pyro",            # 17
    "Rock",            # 18
    "Plant",           # 19
    "Magic",           # 20
    "Trap",            # 21
    "Ritual",          # 22
    "Equip"            # 23
]

CARD_TYPES_ES = [
    "Dragón", "Lanzador de Conjuros", "Zombi", "Guerrero", "Guerrero-Bestia", "Bestia",
    "Bestia Alada", "Demonio", "Hada", "Insecto", "Dinosaurio", "Reptil",
    "Pez", "Serpiente Marina", "Máquina", "Trueno", "Aqua", "Piro",
    "Roca", "Planta", "Mágica", "Trampa", "Ritual", "Equipo"
]

GUARDIAN_STARS = [
    "None",      # 0
    "Sun",       # 1
    "Mercury",   # 2
    "Venus",     # 3
    "Moon",      # 4
    "Mars",      # 5
    "Jupiter",   # 6
    "Saturn",    # 7
    "Uranus",    # 8
    "Pluto",     # 9
    "Neptune"    # 10
]

GUARDIAN_STARS_ES = [
    "Ninguna", "Sol", "Mercurio", "Venus", "Luna", "Marte",
    "Júpiter", "Saturno", "Urano", "Plutón", "Neptuno"
]

OPPONENT_NAMES = [
    "Simon Muran",               # 1
    "Teana",                     # 2
    "Jono",                      # 3
    "Villager 1",                # 4
    "Villager 2",                # 5
    "Villager 3",                # 6
    "Seto 1st",                  # 7
    "Heishin 1st",               # 8
    "Rex Raptor",                # 9
    "Weevil Underwood",          # 10
    "Mai Valentine",             # 11
    "Bandit Keith",              # 12
    "Shadi",                     # 13
    "Yami Bakura",               # 14
    "Pegasus J. Crawford",       # 15
    "Isis",                      # 16
    "Kaiba",                     # 17
    "Mage Soldier",              # 18
    "Jono 2nd",                  # 19
    "Teana 2nd",                 # 20
    "Ocean Mage",                # 21
    "High Mage Secmeton",        # 22
    "Forest Mage",               # 23
    "High Mage Anubisius",       # 24
    "Mountain Mage",             # 25
    "High Mage Atenza",          # 26
    "Desert Mage",               # 27
    "High Mage Martis",          # 28
    "Meadow Mage",               # 29
    "High Mage Kepura",          # 30
    "Labyrinth Mage",            # 31
    "Seto 2nd",                  # 32
    "Guardian Sebek",            # 33
    "Guardian Neku",             # 34
    "Heishin 2nd",               # 35
    "Seto 3rd",                  # 36
    "DarkNite",                  # 37
    "Nitemare",                  # 38
    "Duel Master K"              # 39
]

# Canonical 722 card names in Yu-Gi-Oh! Forbidden Memories (1..722)
CARD_NAMES: Dict[int, str] = CANONICAL_CARD_NAMES


def get_card_name(card_id: int) -> str:
    """Returns canonical card name or generic fallback."""
    if card_id in CARD_NAMES:
        return CARD_NAMES[card_id]
    return f"Card #{card_id:03d}"
