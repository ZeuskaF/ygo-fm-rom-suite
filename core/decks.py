"""
Duelist Deck Reader/Writer for Yu-Gi-Oh! Forbidden Memories.

Maps the 39 CPU opponent decks stored in WA_MRG.MRG starting at 0x00B85000.
Each deck contains exactly 40 card IDs stored as uint16 little-endian values.
The deck table replicates across all 7 duel arenas (stride = 0x75800).

Also handles the per-duelist difficulty/fusion-aggression byte table stored
in SLUS at offset 0x082090 (one byte per opponent, 0-100 scale).
"""

import struct
from typing import List, Optional
from core.card_data import OPPONENT_NAMES

# WA_MRG layout
DECK_TABLE_BASE    = 0x00B85000   # First duelist's deck (Simon Muran)
DECK_CARD_COUNT    = 40            # Cards per deck
DECK_ENTRY_SIZE    = DECK_CARD_COUNT * 2   # 80 bytes per deck (uint16 LE each)
NUM_DUELISTS       = 39

# The deck table is mirrored across all 7 duel arenas
ARENA_STRIDE       = 0x75800
NUM_ARENAS         = 7

# SLUS layout
DIFFICULTY_TABLE_OFF  = 0x082090   # 39 bytes, one per duelist (0-100 aggression %)
DIFFICULTY_TABLE_SIZE = NUM_DUELISTS


class DuelistDeck:
    """Represents one CPU duelist's 40-card deck and AI difficulty setting."""

    def __init__(self, duelist_id: int):
        self.duelist_id: int = duelist_id          # 1-based (1..39)
        self.name: str = OPPONENT_NAMES[duelist_id - 1]
        self.cards: List[int] = [0] * DECK_CARD_COUNT   # card IDs 1-722
        self.difficulty: int = 0                   # 0-100 fusion aggression %

    def __repr__(self) -> str:
        return f"DuelistDeck({self.duelist_id}, {self.name!r}, diff={self.difficulty}, cards={self.cards[:4]}...)"


class DeckDatabase:
    """
    Reads and writes all 39 duelist decks from WA_MRG.MRG and their
    difficulty settings from SLUS_014.11.
    """

    def __init__(self):
        self.decks: List[DuelistDeck] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_from_wa_and_exe(self, wa_bytes: bytes, exe_bytes: bytes) -> int:
        """
        Parses all 39 duelist decks and difficulty bytes.
        Returns the number of decks successfully loaded.
        """
        self.decks = []
        loaded = 0

        # 1. Load difficulty bytes from SLUS
        difficulties: List[int] = [0] * NUM_DUELISTS
        if len(exe_bytes) >= DIFFICULTY_TABLE_OFF + DIFFICULTY_TABLE_SIZE:
            for i in range(NUM_DUELISTS):
                difficulties[i] = exe_bytes[DIFFICULTY_TABLE_OFF + i]

        # 2. Load decks from WA_MRG arena 0 (canonical source)
        for i in range(NUM_DUELISTS):
            deck = DuelistDeck(i + 1)
            deck.difficulty = difficulties[i]

            off = DECK_TABLE_BASE + i * DECK_ENTRY_SIZE
            if off + DECK_ENTRY_SIZE <= len(wa_bytes):
                for j in range(DECK_CARD_COUNT):
                    card_id = struct.unpack_from('<H', wa_bytes, off + j * 2)[0]
                    # Clamp to valid range; zero means unset
                    deck.cards[j] = card_id if 1 <= card_id <= 722 else 0
                loaded += 1

            self.decks.append(deck)

        return loaded

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save_to_wa_and_exe(self, wa_bytes: bytearray, exe_bytes: bytearray) -> int:
        """
        Writes all 39 duelist decks into all 7 arenas in WA_MRG.MRG and
        writes difficulty bytes back into SLUS_014.11.
        Returns the number of arenas updated.
        """
        arenas_updated = 0

        # 1. Write difficulty bytes to SLUS
        if len(exe_bytes) >= DIFFICULTY_TABLE_OFF + DIFFICULTY_TABLE_SIZE:
            for i, deck in enumerate(self.decks):
                exe_bytes[DIFFICULTY_TABLE_OFF + i] = max(0, min(100, deck.difficulty))

        # 2. Write decks across all 7 arenas
        for arena in range(NUM_ARENAS):
            arena_base = DECK_TABLE_BASE + arena * ARENA_STRIDE
            for i, deck in enumerate(self.decks):
                off = arena_base + i * DECK_ENTRY_SIZE
                if off + DECK_ENTRY_SIZE > len(wa_bytes):
                    break
                for j, card_id in enumerate(deck.cards):
                    struct.pack_into('<H', wa_bytes, off + j * 2, card_id & 0xFFFF)
            arenas_updated += 1

        return arenas_updated

    # ------------------------------------------------------------------
    # Import from mod
    # ------------------------------------------------------------------

    def import_from_mod(self, mod_wa: bytes, mod_exe: bytes) -> int:
        """
        Imports deck compositions and difficulty values from a mod ISO.
        Only overwrites decks where all 40 cards are valid (1-722),
        to avoid importing corrupted data.
        Returns the number of decks updated.
        """
        updated = 0
        if not self.decks:
            self.decks = [DuelistDeck(i + 1) for i in range(NUM_DUELISTS)]

        # Read mod difficulties
        mod_difficulties: List[int] = [0] * NUM_DUELISTS
        if len(mod_exe) >= DIFFICULTY_TABLE_OFF + DIFFICULTY_TABLE_SIZE:
            for i in range(NUM_DUELISTS):
                mod_difficulties[i] = mod_exe[DIFFICULTY_TABLE_OFF + i]

        for i, deck in enumerate(self.decks):
            off = DECK_TABLE_BASE + i * DECK_ENTRY_SIZE
            if off + DECK_ENTRY_SIZE > len(mod_wa):
                continue

            mod_cards = []
            all_valid = True
            for j in range(DECK_CARD_COUNT):
                cid = struct.unpack_from('<H', mod_wa, off + j * 2)[0]
                if not (1 <= cid <= 722):
                    all_valid = False
                    break
                mod_cards.append(cid)

            if all_valid and len(mod_cards) == DECK_CARD_COUNT:
                deck.cards = mod_cards
                deck.difficulty = mod_difficulties[i]
                updated += 1

        return updated

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get(self, duelist_id: int) -> Optional[DuelistDeck]:
        """Return deck by 1-based duelist ID (1..39)."""
        idx = duelist_id - 1
        if 0 <= idx < len(self.decks):
            return self.decks[idx]
        return None
