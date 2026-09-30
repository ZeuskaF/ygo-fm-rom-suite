"""
Drop Tables Database and Probability Engine for Yu-Gi-Oh! Forbidden Memories.

Handles reading, modifying, calculating probabilities, normalizing, and saving
the drop tables of all 39 opponents across all 4 ranks (SA-POW, BCD-POW, SA-TEC, BCD-TEC).
Supports both 8-bit format (Vanilla) and 16-bit format (Dream Mod and modern mods).
"""

import struct
from typing import Dict, List, Optional, Tuple
from core.card_data import OPPONENT_NAMES, CARD_NAMES, get_card_name

# Offset in WA_MRG.MRG where drop tables begin
DROP_TABLE_BASE   = 0x00E9B000
DUELIST_STRIDE     = 0x1800        # 6,144 bytes (3 sectors) per duelist
NUM_DUELISTS       = 39
CARDS_PER_POOL     = 722
POOL_TARGET_SUM    = 2048          # RNG rolls 0..2047 (mod 2048)

# The 4 official rank drop pools
POOL_NAMES = ["SA-POW", "BCD-POW", "SA-TEC", "BCD-TEC"]

# Pool offsets relative to duelist base (base = DROP_TABLE_BASE + duelist_idx * DUELIST_STRIDE)
# 8-bit format (1 byte per card):
OFFSETS_8BIT = {
    "SA-POW":  0x0000,
    "BCD-POW": 0x02D2,   # +722
    "SA-TEC":  0x05B4,   # +1460
    "BCD-TEC": 0x0886,   # +2182
}

# 16-bit format (2 bytes per card, uint16 LE):
OFFSETS_16BIT = {
    "SA-POW":  0x0000,
    "SA-TEC":  0x05B4,   # +1460
    "BCD-POW": 0x0B68,   # +2920
    "BCD-TEC": 0x111C,   # +4380
}

# Calificaciones details for UI / Documentation
RANK_INFO = {
    "SA-POW": {
        "title": "S/A POW (Poder Absoluto)",
        "badge": "S/A POW",
        "description": "Se obtiene ganando el duelo de forma rápida y ofensiva (1-4 turnos, pocos o 0 fusiones, ataque directo demoledor).",
        "color": "#FF4444"
    },
    "BCD-POW": {
        "title": "B/C/D POW (Poder Regular)",
        "badge": "B/C/D POW",
        "description": "Se obtiene en victorias ofensivas pero que requirieron más turnos (5-8 turnos) o sufrieron más daño a los LP.",
        "color": "#FF8844"
    },
    "SA-TEC": {
        "title": "S/A TEC (Técnica Suprema)",
        "badge": "S/A TEC",
        "description": "Se obtiene mediante victoria técnica y defensiva (muchas fusiones, provocar activación de trampas/magias enemigas, deck-out con pocas cartas en mazo).",
        "color": "#00D2FF"
    },
    "BCD-TEC": {
        "title": "B/C/D TEC (Técnica Regular)",
        "badge": "B/C/D TEC",
        "description": "Se obtiene en victorias defensivas regulares con turnos medios y uso moderado de cartas mágicas/trampas.",
        "color": "#4488FF"
    }
}


class DuelistDrops:
    """Represents the drop tables for one CPU opponent (all 4 rank pools)."""

    def __init__(self, duelist_id: int):
        self.duelist_id: int = duelist_id  # 1-based (1..39)
        self.name: str = OPPONENT_NAMES[duelist_id - 1]
        # Pools dictionary: pool_name -> list of 722 weights (card 1 at index 0)
        self.pools: Dict[str, List[int]] = {
            p: [0] * CARDS_PER_POOL for p in POOL_NAMES
        }

    def get_pool_sum(self, pool_name: str) -> int:
        """Returns the sum of all weights in the pool (should be 2048)."""
        return sum(self.pools.get(pool_name, []))

    def get_card_weight(self, pool_name: str, card_id: int) -> int:
        """Returns the drop weight of a card (0..2048) in the given pool."""
        if 1 <= card_id <= CARDS_PER_POOL:
            return self.pools[pool_name][card_id - 1]
        return 0

    def get_card_percentage(self, pool_name: str, card_id: int) -> float:
        """Returns the exact drop probability percentage (weight / 2048 * 100%)."""
        w = self.get_card_weight(pool_name, card_id)
        return (w / float(POOL_TARGET_SUM)) * 100.0

    def set_card_weight(self, pool_name: str, card_id: int, new_weight: int) -> None:
        """Sets the drop weight of a card in the given pool."""
        if 1 <= card_id <= CARDS_PER_POOL and pool_name in self.pools:
            self.pools[pool_name][card_id - 1] = max(0, min(POOL_TARGET_SUM, new_weight))

    def get_active_drops(self, pool_name: str) -> List[Tuple[int, str, int, float]]:
        """
        Returns list of (card_id, card_name, weight, percentage)
        for all cards with weight > 0 in this pool, sorted descending by weight.
        """
        drops = []
        if pool_name not in self.pools:
            return drops
        for idx, weight in enumerate(self.pools[pool_name]):
            if weight > 0:
                cid = idx + 1
                name = get_card_name(cid)
                pct = (weight / float(POOL_TARGET_SUM)) * 100.0
                drops.append((cid, name, weight, pct))
        drops.sort(key=lambda x: (x[2], x[0]), reverse=True)
        return drops

    def normalize_pool(self, pool_name: str) -> bool:
        """
        Auto-balances the pool weights so their total sum is exactly 2048.
        Preserves non-zero relative proportions.
        """
        if pool_name not in self.pools:
            return False
        curr_sum = sum(self.pools[pool_name])
        if curr_sum == 0:
            return False
        if curr_sum == POOL_TARGET_SUM:
            return True

        # Scale non-zero items
        non_zeros = [(i, w) for i, w in enumerate(self.pools[pool_name]) if w > 0]
        if not non_zeros:
            return False

        new_weights = [0] * CARDS_PER_POOL
        accum = 0
        for i, (idx, w) in enumerate(non_zeros):
            scaled = int(round((w * POOL_TARGET_SUM) / float(curr_sum)))
            if scaled < 1:
                scaled = 1
            new_weights[idx] = scaled
            accum += scaled

        # Adjust difference on the highest weight item
        diff = POOL_TARGET_SUM - accum
        if diff != 0:
            best_idx = max(non_zeros, key=lambda x: x[1])[0]
            new_weights[best_idx] = max(1, new_weights[best_idx] + diff)

        self.pools[pool_name] = new_weights
        return True


class DropDatabase:
    """
    Complete Database of drops for all 39 duelists.
    Handles reading and writing from/to WA_MRG.MRG and mod format auto-detection.
    """

    def __init__(self):
        self.duelists: List[DuelistDrops] = [DuelistDrops(i + 1) for i in range(NUM_DUELISTS)]
        self.is_16bit: bool = False

    def get_duelist(self, duelist_id: int) -> Optional[DuelistDrops]:
        """Returns DuelistDrops by 1-based ID (1..39)."""
        if 1 <= duelist_id <= NUM_DUELISTS:
            return self.duelists[duelist_id - 1]
        return None

    # ------------------------------------------------------------------
    # Format Detection and Loading
    # ------------------------------------------------------------------

    @staticmethod
    def detect_format(wa_bytes: bytes, exe_bytes: Optional[bytes] = None) -> bool:
        """
        Detects whether drop tables are stored as 16-bit (Dream Mod) or 8-bit (Vanilla).
        Returns True for 16-bit, False for 8-bit.
        """
        # 1. Check SLUS instruction at 0x012058 if available
        if exe_bytes and len(exe_bytes) >= 0x01205C:
            inst = struct.unpack_from('<I', exe_bytes, 0x012058)[0]
            if inst == 0x96020000:  # lhu $v0, 0($s0)
                return True
            if inst == 0x92020000:  # lbu $v0, 0($s0)
                return False

        # 2. Check WA_MRG data directly at Simon Muran's block (0xE9B000)
        if len(wa_bytes) >= DROP_TABLE_BASE + CARDS_PER_POOL * 2:
            words = [
                struct.unpack_from('<H', wa_bytes, DROP_TABLE_BASE + i * 2)[0]
                for i in range(CARDS_PER_POOL)
            ]
            if sum(words) == POOL_TARGET_SUM:
                return True

        return False

    def load_from_wa(self, wa_bytes: bytes, exe_bytes: Optional[bytes] = None) -> int:
        """
        Parses all 39 duelist drop tables from WA_MRG.MRG.
        Returns the number of duelists loaded.
        """
        self.is_16bit = self.detect_format(wa_bytes, exe_bytes)
        offsets = OFFSETS_16BIT if self.is_16bit else OFFSETS_8BIT

        loaded = 0
        for d_idx in range(NUM_DUELISTS):
            duelist = self.duelists[d_idx]
            base = DROP_TABLE_BASE + d_idx * DUELIST_STRIDE

            if base + DUELIST_STRIDE > len(wa_bytes):
                break

            for pool_name, rel_off in offsets.items():
                p_off = base + rel_off
                if self.is_16bit:
                    weights = [
                        struct.unpack_from('<H', wa_bytes, p_off + i * 2)[0]
                        for i in range(CARDS_PER_POOL)
                    ]
                else:
                    weights = [
                        int(wa_bytes[p_off + i])
                        for i in range(CARDS_PER_POOL)
                    ]
                duelist.pools[pool_name] = weights

            loaded += 1

        return loaded

    # ------------------------------------------------------------------
    # Saving to WA_MRG (all 7 arenas)
    # ------------------------------------------------------------------

    def save_to_wa(self, wa_bytes: bytearray) -> int:
        """
        Serializes all 39 duelist drop tables into WA_MRG.MRG across all 7 arenas.
        Returns the number of arenas updated.
        """
        offsets = OFFSETS_16BIT if self.is_16bit else OFFSETS_8BIT
        arenas_updated = 0

        # In Yu-Gi-Oh Forbidden Memories, drop tables are located at DROP_TABLE_BASE.
        # Arena stride check: the main drop table is at 0x00E9B000.
        # We write to arena 0 and replicate to any subsequent arena copies if present.
        for d_idx in range(NUM_DUELISTS):
            duelist = self.duelists[d_idx]
            base = DROP_TABLE_BASE + d_idx * DUELIST_STRIDE
            if base + DUELIST_STRIDE > len(wa_bytes):
                break

            for pool_name, rel_off in offsets.items():
                p_off = base + rel_off
                weights = duelist.pools[pool_name]

                if self.is_16bit:
                    for i, w in enumerate(weights):
                        struct.pack_into('<H', wa_bytes, p_off + i * 2, max(0, min(POOL_TARGET_SUM, w)))
                else:
                    for i, w in enumerate(weights):
                        wa_bytes[p_off + i] = max(0, min(255, w))

        arenas_updated += 1
        return arenas_updated

    # ------------------------------------------------------------------
    # Reverse Card Search ("¿Quién da esta carta?")
    # ------------------------------------------------------------------

    def search_card_drops(self, card_id: int) -> List[Dict]:
        """
        Searches all 39 duelists and all 4 pools to find who drops the card,
        with what weight, percentage, and required rank.
        Returns sorted list of match dictionaries.
        """
        results = []
        if not (1 <= card_id <= CARDS_PER_POOL):
            return results

        card_name = get_card_name(card_id)

        for duelist in self.duelists:
            for pool_name in POOL_NAMES:
                weight = duelist.get_card_weight(pool_name, card_id)
                if weight > 0:
                    pct = (weight / float(POOL_TARGET_SUM)) * 100.0
                    results.append({
                        "duelist_id": duelist.duelist_id,
                        "duelist_name": duelist.name,
                        "pool_name": pool_name,
                        "rank_title": RANK_INFO[pool_name]["title"],
                        "rank_badge": RANK_INFO[pool_name]["badge"],
                        "weight": weight,
                        "percentage": pct,
                        "probability_str": f"{weight} / {POOL_TARGET_SUM} ({pct:.2f}%)",
                        "card_id": card_id,
                        "card_name": card_name
                    })

        # Sort descending by percentage
        results.sort(key=lambda x: x["percentage"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # Import Drops from Mod
    # ------------------------------------------------------------------

    def import_from_mod(self, mod_wa: bytes, mod_exe: Optional[bytes] = None) -> int:
        """
        Imports drop tables from a mod ISO/BIN into this database.
        Detects the mod's format (8-bit or 16-bit) and maps cards cleanly.
        Returns number of duelists imported.
        """
        mod_db = DropDatabase()
        loaded = mod_db.load_from_wa(mod_wa, mod_exe)
        if loaded > 0:
            for d_idx in range(min(len(self.duelists), len(mod_db.duelists))):
                src = mod_db.duelists[d_idx]
                dst = self.duelists[d_idx]
                for p_name in POOL_NAMES:
                    dst.pools[p_name] = list(src.pools[p_name])
            self.is_16bit = mod_db.is_16bit
        return loaded
