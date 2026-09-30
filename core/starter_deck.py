"""
Starter Deck Database and Authentic PS1 Probability Engine for Yu-Gi-Oh! Forbidden Memories.

The authentic PS1 starter deck generation engine (located in the Name Entry scene
overlay at DATA/WA_MRG.MRG sector 7983, base offset 0x00F97800, RAM 0x8016a930)
generates the player's 40-card initial deck by rolling across 7 distinct probability pools:

- Pool 0 (Monstruos Menores): 16 draws (sum weights = 2,048)
- Pool 1 (Monstruos Medios): 16 draws (sum weights = 2,048)
- Pool 2 (Monstruos Mayores): 4 draws (sum weights = 2,048)
- Pool 3 (Monstruos Clave / Jefes): 1 draw (sum weights = 2,048)
- Pool 4 (Magias de Limpieza - Raigeki / Dark Hole): 1 draw (sum weights = 2,048)
- Pool 5 (Magias de Campo): 1 draw (sum weights = 2,048)
- Pool 6 (Magias de Equipo): 1 draw (sum weights = 2,048)

Total draws: 16 + 16 + 4 + 1 + 1 + 1 + 1 = 40 cards!

In addition, a 1,024-slot lookup table is maintained and synchronized for
backwards compatibility with legacy consumers and SLUS-based tooling.
"""

import base64
import math
import struct
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any

from core.card_data import get_card_name
from core.starter_deck_data import DEFAULT_VANILLA_POOLS_B64, DEFAULT_VANILLA_STARTER_B64

# Backward-compatible exports
__all__ = [
    "STARTER_DECK_OFFSET",
    "STARTER_DECK_SLOTS",
    "STARTER_DECK_BYTES",
    "WA_SECTOR_START",
    "WA_BASE_OFFSET",
    "NUM_CARDS",
    "POOL_TARGET_SUM",
    "POOL_METADATA",
    "StarterDeckPool",
    "StarterDeckDatabase",
    "DEFAULT_VANILLA_STARTER_B64",
    "DEFAULT_VANILLA_POOLS_B64",
]

# Legacy SLUS offset & slot constants
STARTER_DECK_OFFSET = 0x089E3A
STARTER_DECK_SLOTS  = 1024
STARTER_DECK_BYTES  = STARTER_DECK_SLOTS * 2  # 2,048 bytes

# Authentic PS1 WA_MRG constants
WA_SECTOR_START   = 7983
WA_BASE_OFFSET    = WA_SECTOR_START * 2048  # 16,349,184 / 0x00F97800
NUM_CARDS         = 722
POOL_TARGET_SUM   = 2048
POOL_DATA_BYTES   = 2 + NUM_CARDS * 2  # 1,446 bytes per pool
POOL_STRIDE_BYTES = 1464

# Pool definitions in the Name Entry overlay (relative to overlay start / RAM 0x80144800)
POOL_METADATA = [
    {"index": 0, "name": "Monstruos Menores", "overlay_offset": 0x263d4, "draws": 16},
    {"index": 1, "name": "Monstruos Medios",  "overlay_offset": 0x2698c, "draws": 16},
    {"index": 2, "name": "Monstruos Mayores", "overlay_offset": 0x26f44, "draws": 4},
    {"index": 3, "name": "Monstruos Clave / Jefes", "overlay_offset": 0x274fc, "draws": 1},
    {"index": 4, "name": "Magias de Limpieza", "overlay_offset": 0x27ab4, "draws": 1},
    {"index": 5, "name": "Magias de Campo",    "overlay_offset": 0x2806c, "draws": 1},
    {"index": 6, "name": "Magias de Equipo",   "overlay_offset": 0x28624, "draws": 1},
]


class StarterDeckPool:
    """
    Represents one of the 7 authentic Starter Deck probability pools stored
    in DATA/WA_MRG.MRG at sector 7983.
    """

    def __init__(
        self,
        index: int,
        name: str,
        overlay_offset: int,
        draws: int,
        weights: Optional[List[int]] = None
    ):
        self.index = index
        self.name = name
        self.overlay_offset = overlay_offset
        self.wa_offset = WA_BASE_OFFSET + overlay_offset
        self.draws = draws
        self.weights: List[int] = list(weights) if weights is not None else [0] * NUM_CARDS

    @property
    def total_weight(self) -> int:
        return sum(self.weights)

    def get_card_weight(self, card_id: int) -> int:
        if 1 <= card_id <= NUM_CARDS:
            return self.weights[card_id - 1]
        return 0

    def set_card_weight(self, card_id: int, weight: int, normalize: bool = True) -> None:
        if not (1 <= card_id <= NUM_CARDS):
            return
        weight = max(0, min(POOL_TARGET_SUM, int(weight)))
        self.weights[card_id - 1] = weight
        if normalize:
            self.normalize(pinned_card=card_id)

    def normalize(self, pinned_card: Optional[int] = None) -> None:
        """
        Normalizes card weights in this pool to sum to exactly POOL_TARGET_SUM (2048),
        preserving the exact weight of pinned_card if provided.
        """
        target = POOL_TARGET_SUM
        active = [(cid, self.weights[cid - 1]) for cid in range(1, NUM_CARDS + 1) if self.weights[cid - 1] > 0]

        if not active:
            fallback = pinned_card if (pinned_card and 1 <= pinned_card <= NUM_CARDS) else 1
            self.weights = [0] * NUM_CARDS
            self.weights[fallback - 1] = target
            return

        if pinned_card is not None and 1 <= pinned_card <= NUM_CARDS:
            pw = self.weights[pinned_card - 1]
            if pw >= target:
                self.weights = [0] * NUM_CARDS
                self.weights[pinned_card - 1] = target
                return

            others = [(cid, w) for cid, w in active if cid != pinned_card]
            target_others = target - pw

            if not others:
                self.weights = [0] * NUM_CARDS
                self.weights[pinned_card - 1] = target
                return

            tot_others = sum(w for _, w in others)
            scaled = []
            acc = 0
            for cid, w in others:
                s = int(round((w * target_others) / float(tot_others)))
                if s < 1:
                    s = 1
                scaled.append((cid, s))
                acc += s

            diff = target_others - acc
            if diff != 0 and scaled:
                max_i = max(range(len(scaled)), key=lambda i: scaled[i][1])
                cid, s = scaled[max_i]
                scaled[max_i] = (cid, max(1, s + diff))

            self.weights = [0] * NUM_CARDS
            self.weights[pinned_card - 1] = pw
            for cid, s in scaled:
                self.weights[cid - 1] = s
        else:
            tot = sum(w for _, w in active)
            scaled = []
            acc = 0
            for cid, w in active:
                s = int(round((w * target) / float(tot)))
                if s < 1:
                    s = 1
                scaled.append((cid, s))
                acc += s

            diff = target - acc
            if diff != 0 and scaled:
                max_i = max(range(len(scaled)), key=lambda i: scaled[i][1])
                cid, s = scaled[max_i]
                scaled[max_i] = (cid, max(1, s + diff))

            self.weights = [0] * NUM_CARDS
            for cid, s in scaled:
                self.weights[cid - 1] = s

    def get_card_probability_in_pool(self, card_id: int) -> float:
        """Single-draw percentage in this pool (weight / 2048 * 100%)."""
        w = self.get_card_weight(card_id)
        tot = self.total_weight or POOL_TARGET_SUM
        return (w / float(tot)) * 100.0

    def get_card_draw_probability(self, card_id: int) -> float:
        """Probability of getting at least 1 copy from this pool's draws."""
        w = self.get_card_weight(card_id)
        tot = self.total_weight or POOL_TARGET_SUM
        if w <= 0:
            return 0.0
        if w >= tot:
            return 100.0
        p_none = (1.0 - (w / float(tot))) ** self.draws
        return max(0.0, min(100.0, (1.0 - p_none) * 100.0))

    def get_expected_copies_in_pool(self, card_id: int) -> float:
        """Expected number of copies of card_id drawn from this pool."""
        w = self.get_card_weight(card_id)
        tot = self.total_weight or POOL_TARGET_SUM
        return self.draws * (w / float(tot))


class StarterDeckDatabase:
    """
    Manages the 7 authentic PS1 starter deck probability pools stored in
    DATA/WA_MRG.MRG at sector 7983, while maintaining a synchronized 1,024-entry
    lookup table for backward compatibility.
    """

    def __init__(self):
        self.pools: List[StarterDeckPool] = []
        self.slots: List[int] = [0] * STARTER_DECK_SLOTS
        self.reset_to_vanilla()

    # ------------------------------------------------------------------
    # Loading / Saving
    # ------------------------------------------------------------------

    def reset_to_vanilla(self) -> None:
        """Restores both authentic 7 pools and the 1,024 legacy table from vanilla defaults."""
        raw_pools = base64.b64decode(DEFAULT_VANILLA_POOLS_B64)
        self.pools = []
        for i, meta in enumerate(POOL_METADATA):
            off = i * POOL_DATA_BYTES
            draws = struct.unpack_from("<H", raw_pools, off)[0]
            weights = list(struct.unpack_from(f"<{NUM_CARDS}H", raw_pools, off + 2))
            pool = StarterDeckPool(
                index=meta["index"],
                name=meta["name"],
                overlay_offset=meta["overlay_offset"],
                draws=draws,
                weights=weights
            )
            self.pools.append(pool)

        # Restore 1,024 slots for backwards compatibility
        raw_slots = base64.b64decode(DEFAULT_VANILLA_STARTER_B64)
        self.slots = list(struct.unpack(f"<{STARTER_DECK_SLOTS}H", raw_slots))

    def load_from_wa(self, wa_bytes: bytes) -> int:
        """
        Loads all 7 authentic starter deck pools from DATA/WA_MRG.MRG at sector 7983.
        Returns the number of pools successfully loaded (7 on success, 0 on failure).
        """
        if len(wa_bytes) < WA_BASE_OFFSET + POOL_METADATA[-1]["overlay_offset"] + POOL_DATA_BYTES:
            return 0

        new_pools = []
        for meta in POOL_METADATA:
            off = WA_BASE_OFFSET + meta["overlay_offset"]
            draws = struct.unpack_from("<H", wa_bytes, off)[0]
            weights = list(struct.unpack_from(f"<{NUM_CARDS}H", wa_bytes, off + 2))

            sum_w = sum(weights)
            if sum_w < 100 or sum_w > 4096:
                return 0

            pool = StarterDeckPool(
                index=meta["index"],
                name=meta["name"],
                overlay_offset=meta["overlay_offset"],
                draws=draws,
                weights=weights
            )
            new_pools.append(pool)

        self.pools = new_pools
        self._sync_slots_from_pools()
        return len(self.pools)

    def save_to_wa(self, wa_bytes: bytearray) -> int:
        """
        Writes all 7 authentic starter deck pools into DATA/WA_MRG.MRG at sector 7983.
        Returns total bytes written across all 7 pools (10,122 bytes).
        """
        if len(wa_bytes) < WA_BASE_OFFSET + POOL_METADATA[-1]["overlay_offset"] + POOL_DATA_BYTES:
            return 0

        total_written = 0
        for pool in self.pools:
            pool.normalize()
            off = pool.wa_offset
            chunk = struct.pack("<H", pool.draws) + struct.pack(f"<{NUM_CARDS}H", *pool.weights)
            wa_bytes[off : off + len(chunk)] = chunk
            total_written += len(chunk)

        return total_written

    def load_from_exe(self, exe_bytes: bytes) -> int:
        """
        Loads the 1,024 starter deck table from SLUS_014.11 (backward compatibility).
        Returns the number of valid card slots loaded.
        """
        if len(exe_bytes) < STARTER_DECK_OFFSET + STARTER_DECK_BYTES:
            return 0

        chunk = exe_bytes[STARTER_DECK_OFFSET : STARTER_DECK_OFFSET + STARTER_DECK_BYTES]
        raw_slots = list(struct.unpack(f"<{STARTER_DECK_SLOTS}H", chunk))

        valid_count = sum(1 for cid in raw_slots if 1 <= cid <= NUM_CARDS)
        if valid_count < STARTER_DECK_SLOTS * 0.8:
            return 0

        self.slots = raw_slots
        self._sync_pools_from_slots()
        return valid_count

    def save_to_exe(self, exe_bytes: bytearray) -> int:
        """
        Writes the 1,024 starter deck slots back to SLUS_014.11.
        Returns the number of bytes written (2,048).
        """
        if len(exe_bytes) < STARTER_DECK_OFFSET + STARTER_DECK_BYTES:
            return 0

        if len(self.slots) != STARTER_DECK_SLOTS:
            self.normalize()

        packed = struct.pack(f"<{STARTER_DECK_SLOTS}H", *self.slots)
        exe_bytes[STARTER_DECK_OFFSET : STARTER_DECK_OFFSET + STARTER_DECK_BYTES] = packed
        return len(packed)

    def import_from_mod(self, mod_data: bytes, mod_exe: Optional[bytes] = None) -> int:
        """
        Imports starter deck from mod data (either WA_MRG.MRG or SLUS_014.11).
        Prioritizes authentic WA_MRG pools, falling back to SLUS table.
        """
        loaded_wa = self.load_from_wa(mod_data)
        if loaded_wa > 0:
            return STARTER_DECK_SLOTS

        if mod_exe is not None:
            loaded_exe = self.load_from_exe(mod_exe)
            if loaded_exe > 0:
                return loaded_exe

        return self.load_from_exe(mod_data)

    # ------------------------------------------------------------------
    # Synchronization between Pools and Slots
    # ------------------------------------------------------------------

    def _sync_slots_from_pools(self) -> None:
        """
        Synthesizes the 1,024-slot lookup table from the 7 authentic probability pools,
        allocating slots proportionally to each pool's draw count.
        """
        if not self.pools or len(self.pools) < 7:
            return

        slot_allocations = [410, 410, 102, 26, 25, 25, 26]  # Sum = 1024
        new_slots: List[int] = []

        for p_idx, pool in enumerate(self.pools):
            target_p_slots = slot_allocations[p_idx]
            active = [(cid, pool.weights[cid - 1]) for cid in range(1, NUM_CARDS + 1) if pool.weights[cid - 1] > 0]
            if not active:
                continue

            tot_w = sum(w for _, w in active)
            allocations = {}
            remainders = []
            acc = 0
            for cid, w in active:
                exact = (w * target_p_slots) / float(tot_w)
                base = int(exact)
                rem = exact - base
                allocations[cid] = base
                remainders.append((rem, cid))
                acc += base

            diff = target_p_slots - acc
            if diff > 0:
                remainders.sort(key=lambda x: x[0], reverse=True)
                for i in range(min(diff, len(remainders))):
                    allocations[remainders[i][1]] += 1
            elif diff < 0:
                sorted_by_base = sorted(allocations.items(), key=lambda x: x[1], reverse=True)
                for cid, b in sorted_by_base:
                    if diff == 0:
                        break
                    can_reduce = b - 1
                    reduce_amt = min(abs(diff), max(0, can_reduce))
                    allocations[cid] -= reduce_amt
                    diff += reduce_amt

            for cid, count in allocations.items():
                new_slots.extend([cid] * count)

        if len(new_slots) < STARTER_DECK_SLOTS:
            diff = STARTER_DECK_SLOTS - len(new_slots)
            fill_cid = new_slots[0] if new_slots else 1
            new_slots.extend([fill_cid] * diff)
        elif len(new_slots) > STARTER_DECK_SLOTS:
            new_slots = new_slots[:STARTER_DECK_SLOTS]

        self.slots = new_slots

    def _sync_pools_from_slots(self) -> None:
        """
        Maps frequencies from the 1,024 slots table back into the authentic 7 pools.
        Used when importing a legacy mod that only modified SLUS.
        """
        counts = self.get_counts()
        if not counts:
            return

        for pool in self.pools:
            pool.weights = [0] * NUM_CARDS

        for cid, cnt in counts.items():
            if not (1 <= cid <= NUM_CARDS):
                continue
            p_idx = self.route_card_to_pool(cid)
            pool = self.pools[p_idx]
            pool.weights[cid - 1] += cnt * 2

        for pool in self.pools:
            if sum(pool.weights) > 0:
                pool.normalize()

    # ------------------------------------------------------------------
    # Weights & Probabilities
    # ------------------------------------------------------------------

    def get_counts(self) -> Dict[int, int]:
        """Returns a dict mapping card_id -> count in the 1,024 slots."""
        return dict(Counter(self.slots))

    def get_weight(self, card_id: int, pool_index: Optional[int] = None) -> int:
        """
        Returns card weight:
          - If pool_index is provided: weight in that pool (0..2048).
          - If pool_index is None: count in the 1,024 legacy table (0..1024).
        """
        if pool_index is not None and 0 <= pool_index < len(self.pools):
            return self.pools[pool_index].get_card_weight(card_id)
        return sum(1 for c in self.slots if c == card_id)

    def get_pool_weight(self, card_id: int, pool_index: int) -> int:
        """Returns weight (0..2048) in a specific pool."""
        if 0 <= pool_index < len(self.pools):
            return self.pools[pool_index].get_card_weight(card_id)
        return 0

    def get_card_percentage(self, card_id: int, pool_index: Optional[int] = None) -> float:
        """
        Single-draw percentage:
          - If pool_index is provided: weight / 2048 * 100% in that pool.
          - If pool_index is None: weight / 1024 * 100% in legacy table.
        """
        if pool_index is not None and 0 <= pool_index < len(self.pools):
            return self.pools[pool_index].get_card_probability_in_pool(card_id)
        w = self.get_weight(card_id)
        return (w / float(STARTER_DECK_SLOTS)) * 100.0

    def get_card_probability_in_deck(self, card_id: int, draws: int = 40, use_authentic: bool = False) -> float:
        """
        Probability of receiving AT LEAST 1 copy of card_id in the starting deck.
        By default (use_authentic=False), evaluates against the 1,024 slots table
        for backward compatibility with existing tests.
        """
        if use_authentic:
            return self.get_authentic_probability_in_deck(card_id)

        w = self.get_weight(card_id)
        if w <= 0:
            return 0.0
        if w >= STARTER_DECK_SLOTS:
            return 100.0

        p_none = (1.0 - (w / float(STARTER_DECK_SLOTS))) ** draws
        return max(0.0, min(100.0, (1.0 - p_none) * 100.0))

    def get_authentic_probability_in_deck(self, card_id: int) -> float:
        """
        Exact mathematical probability of obtaining >= 1 copy of card_id
        in the player's 40 starting cards across all 7 authentic pools:
          P = 1.0 - PROD_{p=0..6} [ (1.0 - w_p / 2048) ^ draws_p ]
        """
        if not (1 <= card_id <= NUM_CARDS):
            return 0.0

        p_none = 1.0
        has_weight = False

        for pool in self.pools:
            w = pool.get_card_weight(card_id)
            if w > 0:
                has_weight = True
                tot = pool.total_weight or POOL_TARGET_SUM
                if w >= tot:
                    return 100.0
                p_none *= (1.0 - (w / float(tot))) ** pool.draws

        if not has_weight:
            return 0.0

        return max(0.0, min(100.0, (1.0 - p_none) * 100.0))

    def get_expected_copies(self, card_id: int, draws: int = 40, use_authentic: bool = False) -> float:
        """
        Expected average number of copies of card_id in 40 starting cards.
        """
        if use_authentic:
            return self.get_authentic_expected_copies(card_id)
        w = self.get_weight(card_id)
        return draws * (w / float(STARTER_DECK_SLOTS))

    def get_authentic_expected_copies(self, card_id: int) -> float:
        """Exact average number of copies across all 7 authentic pools."""
        if not (1 <= card_id <= NUM_CARDS):
            return 0.0
        expected = 0.0
        for pool in self.pools:
            w = pool.get_card_weight(card_id)
            if w > 0:
                tot = pool.total_weight or POOL_TARGET_SUM
                expected += pool.draws * (w / float(tot))
        return expected

    # ------------------------------------------------------------------
    # Card Routing & Editing
    # ------------------------------------------------------------------

    def route_card_to_pool(self, card_id: int, card_db: Optional[Any] = None) -> int:
        """
        Determines the authentic pool index (0..6) best suited for card_id:
          - If already present in a pool with weight > 0, returns that pool.
          - Field Spells (330..335) -> Pool 5 (Magias de Campo)
          - Board Wipes (336, 337) -> Pool 4 (Magias de Limpieza)
          - Equips & Utility Magic/Traps -> Pool 6 (Magias de Equipo)
          - Monsters by ATK:
              ATK < 1000  -> Pool 0 (Monstruos Menores)
              1000..1499  -> Pool 1 (Monstruos Medios)
              1500..1999  -> Pool 2 (Monstruos Mayores)
              ATK >= 2000 -> Pool 3 (Monstruos Clave / Jefes)
        """
        # If card is already in a pool, retain that pool
        for pool in self.pools:
            if pool.get_card_weight(card_id) > 0:
                return pool.index

        # Field spells
        if 330 <= card_id <= 335:
            return 5
        # Raigeki, Dark Hole
        if card_id in (336, 337):
            return 4

        # Check card_db attributes if provided
        if card_db is not None:
            c = card_db.get(card_id) if hasattr(card_db, 'get') else None
            if c:
                if getattr(c, 'type_id', 0) >= 20:
                    return 6
                atk = getattr(c, 'atk', 0)
                if atk < 1000:
                    return 0
                elif atk < 1500:
                    return 1
                elif atk < 2000:
                    return 2
                else:
                    return 3

        # Default heuristic based on canonical ranges
        if (301 <= card_id <= 380) or (651 <= card_id <= 722):
            return 6
        if card_id < 150:
            return 1
        elif card_id < 300:
            return 0
        elif card_id < 500:
            return 2
        else:
            return 3

    def set_card_weight(self, card_id: int, new_weight: int, pool_index: Optional[int] = None) -> None:
        """
        Sets frequency of card_id, synchronizing both the authentic pool
        and the 1,024 slots table.
        """
        if not (1 <= card_id <= NUM_CARDS):
            return

        # 1. Update 1,024 slots table
        new_slot_w = max(0, min(STARTER_DECK_SLOTS, int(new_weight)))
        counts = self.get_counts()
        if new_slot_w == 0:
            counts.pop(card_id, None)
        else:
            counts[card_id] = new_slot_w
        self._rebuild_slots_from_counts(counts, pinned_card=card_id)

        # 2. Update authentic pool
        if pool_index is not None and 0 <= pool_index < len(self.pools):
            target_pool = self.pools[pool_index]
        else:
            p_idx = self.route_card_to_pool(card_id)
            target_pool = self.pools[p_idx]

        # Calculate pool weight (out of 2048)
        if new_weight <= 0:
            pool_w = 0
        elif new_weight > STARTER_DECK_SLOTS:
            pool_w = min(POOL_TARGET_SUM, new_weight)
        else:
            pool_w = min(POOL_TARGET_SUM, int(round((new_weight / float(STARTER_DECK_SLOTS)) * POOL_TARGET_SUM)))
            if pool_w < 1 and new_weight > 0:
                pool_w = 1

        target_pool.set_card_weight(card_id, pool_w, normalize=True)

    def set_pool_card_weight(self, pool_index: int, card_id: int, new_weight: int, normalize: bool = True) -> None:
        """
        Directly sets weight (0..2048) in a specific authentic pool and synchronizes slots.
        """
        if not (0 <= pool_index < len(self.pools)) or not (1 <= card_id <= NUM_CARDS):
            return
        self.pools[pool_index].set_card_weight(card_id, new_weight, normalize=normalize)
        self._sync_slots_from_pools()

    def add_card(self, card_id: int, weight: int = 1, pool_index: Optional[int] = None) -> None:
        """Adds card_id to the pool or increases its weight."""
        if not (1 <= card_id <= NUM_CARDS):
            return
        curr = self.get_weight(card_id, pool_index=pool_index)
        self.set_card_weight(card_id, curr + weight, pool_index=pool_index)

    def remove_card(self, card_id: int, pool_index: Optional[int] = None) -> None:
        """Removes card_id completely from specified pool or all pools."""
        if not (1 <= card_id <= NUM_CARDS):
            return
        if pool_index is not None and 0 <= pool_index < len(self.pools):
            self.pools[pool_index].set_card_weight(card_id, 0, normalize=True)
            self._sync_slots_from_pools()
        else:
            for pool in self.pools:
                if pool.get_card_weight(card_id) > 0:
                    pool.set_card_weight(card_id, 0, normalize=True)
            self.set_card_weight(card_id, 0)

    def set_guaranteed_card(self, card_id: int, guaranteed_level: str = "high", pool_index: Optional[int] = None) -> None:
        """
        Virtually guarantees appearance in the starter deck:
          - 'high': 99.2% chance (weight 512 in pool / 120 in slots)
          - 'almost_certain': 99.8% chance (weight 1024 in pool / 160 in slots)
          - 'absolute': 100% guaranteed (weight 2048 in pool / 256 in slots)
        """
        slot_map = {"high": 120, "almost_certain": 160, "absolute": 256}
        pool_map = {"high": 512, "almost_certain": 1024, "absolute": 2048}

        sw = slot_map.get(guaranteed_level, 120)
        pw = pool_map.get(guaranteed_level, 512)

        if pool_index is None:
            pool_index = self.route_card_to_pool(card_id)

        self.pools[pool_index].set_card_weight(card_id, pw, normalize=True)
        self.set_card_weight(card_id, sw, pool_index=pool_index)

    def normalize(self, pool_index: Optional[int] = None) -> None:
        """Normalizes pool(s) to 2048 weights and slots to 1,024."""
        if pool_index is not None and 0 <= pool_index < len(self.pools):
            self.pools[pool_index].normalize()
        else:
            for pool in self.pools:
                pool.normalize()

        counts = self.get_counts()
        self._rebuild_slots_from_counts(counts)

    def _rebuild_slots_from_counts(self, counts: Dict[int, int], pinned_card: Optional[int] = None) -> None:
        """Reconstructs the 1,024 slots array from counts dict."""
        if not counts:
            self.reset_to_vanilla()
            return

        total_target = STARTER_DECK_SLOTS
        pinned_weight = 0

        if pinned_card is not None and pinned_card in counts:
            pinned_weight = counts[pinned_card]
            if pinned_weight >= total_target:
                self.slots = [pinned_card] * total_target
                return
            other_counts = {cid: w for cid, w in counts.items() if cid != pinned_card}
            target_for_others = total_target - pinned_weight
        else:
            other_counts = dict(counts)
            target_for_others = total_target

        other_sum = sum(other_counts.values())
        new_slots: List[int] = []

        if pinned_card is not None and pinned_weight > 0:
            new_slots.extend([pinned_card] * pinned_weight)

        if other_sum <= 0:
            rem = total_target - len(new_slots)
            fallback_cid = pinned_card if pinned_card else 1
            new_slots.extend([fallback_cid] * rem)
            self.slots = new_slots
            return

        scaled_items = []
        accum = 0
        for cid, w in other_counts.items():
            if w <= 0:
                continue
            scaled = int(round((w * target_for_others) / float(other_sum)))
            if scaled < 1:
                scaled = 1
            scaled_items.append([cid, scaled])
            accum += scaled

        diff = target_for_others - accum
        if diff != 0 and scaled_items:
            best = max(scaled_items, key=lambda x: x[1])
            best[1] = max(1, best[1] + diff)

        for cid, count in scaled_items:
            new_slots.extend([cid] * count)

        if len(new_slots) > total_target:
            new_slots = new_slots[:total_target]
        elif len(new_slots) < total_target:
            pad = total_target - len(new_slots)
            fill_cid = new_slots[0] if new_slots else 1
            new_slots.extend([fill_cid] * pad)

        self.slots = new_slots

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_active_cards(self, pool_filter: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Returns a sorted list of dictionaries representing active cards:
          - If pool_filter is specified: cards active in that specific pool.
          - If pool_filter is None: cards active across all 7 pools.
        """
        result = []

        if pool_filter is not None and 0 <= pool_filter < len(self.pools):
            pool = self.pools[pool_filter]
            for cid in range(1, NUM_CARDS + 1):
                w = pool.get_card_weight(cid)
                if w <= 0:
                    continue
                name = get_card_name(cid)
                pool_pct = pool.get_card_probability_in_pool(cid)
                deck_prob = pool.get_card_draw_probability(cid)
                expected = pool.get_expected_copies_in_pool(cid)
                slot_w = self.get_weight(cid)

                result.append({
                    "card_id": cid,
                    "name": name,
                    "pool_index": pool.index,
                    "pool_name": pool.name,
                    "weight": w,
                    "pool_pct": pool_pct,
                    "deck_prob_pct": deck_prob,
                    "expected_copies": expected,
                    "slots_count": slot_w,
                })
            result.sort(key=lambda x: (x["weight"], -x["card_id"]), reverse=True)
            return result

        # All pools aggregated
        seen_cids = set()
        for pool in self.pools:
            for cid in range(1, NUM_CARDS + 1):
                if pool.get_card_weight(cid) > 0:
                    seen_cids.add(cid)
        for cid in self.slots:
            if 1 <= cid <= NUM_CARDS:
                seen_cids.add(cid)

        for cid in sorted(seen_cids):
            # Find dominant pool for this card
            dominant_pool = max(self.pools, key=lambda p: p.get_card_weight(cid))
            pw = dominant_pool.get_card_weight(cid)
            name = get_card_name(cid)
            deck_prob = self.get_authentic_probability_in_deck(cid)
            expected = self.get_authentic_expected_copies(cid)
            slot_w = self.get_weight(cid)

            if pw > 0:
                p_idx = dominant_pool.index
                p_name = dominant_pool.name
                pool_pct = dominant_pool.get_card_probability_in_pool(cid)
                rep_weight = pw
            else:
                p_idx = self.route_card_to_pool(cid)
                p_name = self.pools[p_idx].name
                pool_pct = (slot_w / float(STARTER_DECK_SLOTS)) * 100.0
                rep_weight = int(round((slot_w / float(STARTER_DECK_SLOTS)) * POOL_TARGET_SUM))

            result.append({
                "card_id": cid,
                "name": name,
                "pool_index": p_idx,
                "pool_name": p_name,
                "weight": rep_weight,
                "pool_pct": pool_pct,
                "deck_prob_pct": deck_prob if deck_prob > 0 else self.get_card_probability_in_deck(cid),
                "expected_copies": expected if expected > 0 else self.get_expected_copies(cid),
                "slots_count": slot_w,
            })

        result.sort(key=lambda x: (x["weight"], x["slots_count"], -x["card_id"]), reverse=True)
        return result
