"""
Fusion Database and Sync Engine for Yu-Gi-Oh! Forbidden Memories.
Manages the 64KB fusion tables across all 7 battle arenas in DATA/WA_MRG.MRG.
Supports parsing, querying, exporting, and 1-click importing of expanded fusion tables
from mods (such as Dream Mod 15x).
"""

import struct
from typing import Dict, List, Optional, Set, Tuple

WA_FUSION_ARENA_BASE = 0x0B87800
WA_ARENA_STEP = 0x75800
FUSION_TABLE_SIZE = 65536  # Exact 64 KB table matching MIPS SLUS_014.11 RAM buffer
NUM_ARENAS = 7
TOTAL_CARDS = 722


def serialize_card_fusions(recipes: List[Tuple[int, int]]) -> bytes:
    """
    Serializes a list of (partner, result) tuples into the official Konami PS1 5-byte packed format.
    """
    count = len(recipes)
    if count == 0:
        return b""
    out = bytearray()
    if count > 255:
        out.append(0)
        out.append(511 - count)
    else:
        out.append(count)
    for i in range(0, count, 2):
        p1, r1 = recipes[i]
        p2, r2 = recipes[i + 1] if i + 1 < count else (0, 0)
        b0 = (
            ((p1 >> 8) & 0x03)
            | (((r1 >> 8) & 0x03) << 2)
            | (((p2 >> 8) & 0x03) << 4)
            | (((r2 >> 8) & 0x03) << 6)
        )
        out.extend([b0, p1 & 0xFF, r1 & 0xFF, p2 & 0xFF, r2 & 0xFF])
    return bytes(out)


def decode_card_fusions(data: bytes, ptr: int) -> List[Tuple[int, int]]:
    """
    Decodes all (partner, result) pairs from a card's recipe list at ptr.
    """
    if ptr == 0 or ptr >= len(data):
        return []
    pos = ptr
    t0 = data[pos]
    pos += 1
    if t0 == 0:
        if pos >= len(data):
            return []
        cnt = 511 - data[pos]
        pos += 1
    else:
        cnt = t0
    recipes: List[Tuple[int, int]] = []
    while cnt > 0 and pos + 5 <= len(data):
        b0, b1, b2, b3, b4 = data[pos : pos + 5]
        pos += 5
        p1 = ((b0 & 0x03) << 8) | b1
        r1 = (((b0 >> 2) & 0x03) << 8) | b2
        if 1 <= p1 <= TOTAL_CARDS and 1 <= r1 <= TOTAL_CARDS:
            recipes.append((p1, r1))
        cnt -= 1
        if cnt > 0:
            p2 = (((b0 >> 4) & 0x03) << 8) | b3
            r2 = (((b0 >> 6) & 0x03) << 8) | b4
            if 1 <= p2 <= TOTAL_CARDS and 1 <= r2 <= TOTAL_CARDS:
                recipes.append((p2, r2))
            cnt -= 1
    return recipes


class Fusion:
    def __init__(self, card_a: int, card_b: int, result: int):
        # Guarantee card_a <= card_b for canonical ordering
        if card_a <= card_b:
            self.card_a = card_a
            self.card_b = card_b
        else:
            self.card_a = card_b
            self.card_b = card_a
        self.result = result

    def __repr__(self) -> str:
        return f"Fusion({self.card_a} + {self.card_b} -> {self.result})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Fusion):
            return False
        return self.card_a == other.card_a and self.card_b == other.card_b and self.result == other.result

    def __hash__(self) -> int:
        return hash((self.card_a, self.card_b, self.result))


class FusionDatabase:
    def __init__(self):
        # Raw table data
        self.raw_table: bytearray = bytearray(FUSION_TABLE_SIZE)
        # Parsed fusions: (card_a, card_b) -> result_card_id
        self.fusions: Dict[Tuple[int, int], int] = {}

    def load_from_wa(self, wa_bytes: bytes) -> int:
        """Loads fusion table from Arena 0 in WA_MRG.MRG and parses all recipes."""
        end = min(len(wa_bytes), WA_FUSION_ARENA_BASE + FUSION_TABLE_SIZE)
        self.raw_table = bytearray(wa_bytes[WA_FUSION_ARENA_BASE : end])
        if len(self.raw_table) < FUSION_TABLE_SIZE:
            self.raw_table.extend(b'\x00' * (FUSION_TABLE_SIZE - len(self.raw_table)))
        self._parse_fusions()
        return len(self.fusions)

    def _parse_fusions(self):
        """Decodes all fusions from raw_table using the game's 5-byte packed format."""
        self.fusions.clear()
        if len(self.raw_table) < 2000:
            return

        for card_a in range(1, TOTAL_CARDS + 1):
            if card_a * 2 + 2 > len(self.raw_table):
                break
            ptr = struct.unpack_from("<H", self.raw_table, card_a * 2)[0]
            if ptr == 0 or ptr >= len(self.raw_table):
                continue

            pos = ptr
            t0 = self.raw_table[pos]
            pos += 1
            if t0 == 0:
                if pos >= len(self.raw_table):
                    continue
                v1 = self.raw_table[pos]
                pos += 1
                count = 511 - v1
            else:
                count = t0

            while count > 0 and pos + 5 <= len(self.raw_table):
                b0 = self.raw_table[pos]
                b1 = self.raw_table[pos + 1]
                b2 = self.raw_table[pos + 2]
                b3 = self.raw_table[pos + 3]
                b4 = self.raw_table[pos + 4]
                pos += 5

                # Fusion 1
                p1 = ((b0 & 0x03) << 8) | b1
                r1 = (((b0 >> 2) & 0x03) << 8) | b2
                if 1 <= p1 <= TOTAL_CARDS and 1 <= r1 <= TOTAL_CARDS:
                    key = (min(card_a, p1), max(card_a, p1))
                    self.fusions[key] = r1
                count -= 1

                # Fusion 2
                if count > 0:
                    p2 = (((b0 >> 4) & 0x03) << 8) | b3
                    r2 = (((b0 >> 6) & 0x03) << 8) | b4
                    if 1 <= p2 <= TOTAL_CARDS and 1 <= r2 <= TOTAL_CARDS:
                        key = (min(card_a, p2), max(card_a, p2))
                        self.fusions[key] = r2
                    count -= 1

    def get_result(self, card_a: int, card_b: int) -> Optional[int]:
        key = (min(card_a, card_b), max(card_a, card_b))
        return self.fusions.get(key)

    def get_fusions_for_card(self, card_id: int) -> List[Fusion]:
        """Returns all fusions where card_id is one of the fusion materials."""
        results = []
        for (a, b), r in self.fusions.items():
            if a == card_id or b == card_id:
                results.append(Fusion(a, b, r))
        return results

    def modify_fusion(self, card_a: int, card_b: int, new_result: int) -> int:
        """
        Modifies the outcome of an existing fusion in raw_table and in-memory cache.
        Returns the number of occurrences updated in raw_table.
        """
        if not (1 <= card_a <= TOTAL_CARDS and 1 <= card_b <= TOTAL_CARDS and 1 <= new_result <= TOTAL_CARDS):
            return 0

        host = min(card_a, card_b)
        partner = max(card_a, card_b)
        modified = 0

        for target_card, part in [(host, partner), (partner, host)]:
            if target_card * 2 + 2 > len(self.raw_table):
                continue
            ptr = struct.unpack_from('<H', self.raw_table, target_card * 2)[0]
            if ptr == 0 or ptr >= len(self.raw_table):
                continue
            pos = ptr
            t0 = self.raw_table[pos]
            pos += 1
            if t0 == 0:
                if pos >= len(self.raw_table):
                    continue
                count = 511 - self.raw_table[pos]
                pos += 1
            else:
                count = t0
            while count > 0 and pos + 5 <= len(self.raw_table):
                b0, b1, b2, b3, b4 = self.raw_table[pos : pos + 5]
                p1 = ((b0 & 0x03) << 8) | b1
                if p1 == part:
                    new_b0 = (b0 & ~(0x03 << 2)) | (((new_result >> 8) & 0x03) << 2)
                    new_b2 = new_result & 0xFF
                    self.raw_table[pos] = new_b0
                    self.raw_table[pos + 2] = new_b2
                    modified += 1
                count -= 1
                if count > 0:
                    p2 = (((b0 >> 4) & 0x03) << 8) | b3
                    if p2 == part:
                        new_b0 = (b0 & ~(0x03 << 6)) | (((new_result >> 8) & 0x03) << 6)
                        new_b4 = new_result & 0xFF
                        self.raw_table[pos] = new_b0
                        self.raw_table[pos + 4] = new_b4
                        modified += 1
                    count -= 1
                pos += 5

        key = (host, partner)
        self.fusions[key] = new_result
        return modified

    def _find_fusion_table_gap(self, needed_size: int) -> Optional[int]:
        """Finds the first unallocated byte gap in raw_table that can hold needed_size bytes."""
        ranges = [[0, (TOTAL_CARDS + 1) * 2]]  # Reserve pointer table (bytes 0 to 1446)
        for cid in range(1, TOTAL_CARDS + 1):
            if cid * 2 + 2 > len(self.raw_table):
                continue
            p = struct.unpack_from('<H', self.raw_table, cid * 2)[0]
            if 0 < p < len(self.raw_table):
                h = self.raw_table[p]
                c = (511 - self.raw_table[p + 1]) if (h == 0 and p + 1 < len(self.raw_table)) else h
                sz = (2 if h == 0 else 1) + ((c + 1) // 2) * 5
                ranges.append([p, p + sz])

        ranges.sort()
        merged = []
        for s, e in ranges:
            if not merged or merged[-1][1] < s:
                merged.append([s, e])
            else:
                merged[-1][1] = max(merged[-1][1], e)

        for i in range(len(merged) - 1):
            gap_start = merged[i][1]
            gap_end = merged[i + 1][0]
            if gap_end - gap_start >= needed_size:
                return gap_start

        if merged and merged[-1][1] + needed_size <= FUSION_TABLE_SIZE:
            return merged[-1][1]

        return None

    def _add_fusion_to_host(self, host: int, partner: int, result: int) -> bool:
        """
        Registers or updates a fusion recipe in host card's fusion list in raw_table.
        Safely checks for existing/deleted slots before relocating to avoid corrupting
        tightly-packed overlapping card headers.
        """
        if host * 2 + 2 > len(self.raw_table):
            return False

        ptr = struct.unpack_from('<H', self.raw_table, host * 2)[0]
        if 0 < ptr < len(self.raw_table):
            pos = ptr
            t0 = self.raw_table[pos]
            pos += 1
            if t0 == 0:
                if pos >= len(self.raw_table):
                    return False
                count = 511 - self.raw_table[pos]
                pos += 1
            else:
                count = t0

            # 1. Modify in-place if partner already exists in host's chunks
            cur = pos
            c = count
            while c > 0 and cur + 5 <= len(self.raw_table):
                b0, b1, b2, b3, b4 = self.raw_table[cur : cur + 5]
                p1 = ((b0 & 0x03) << 8) | b1
                if p1 == partner:
                    new_b0 = (b0 & ~(0x03 << 2)) | (((result >> 8) & 0x03) << 2)
                    self.raw_table[cur] = new_b0
                    self.raw_table[cur + 2] = result & 0xFF
                    return True
                c -= 1
                if c > 0:
                    p2 = (((b0 >> 4) & 0x03) << 8) | b3
                    if p2 == partner:
                        new_b0 = (b0 & ~(0x03 << 6)) | (((result >> 8) & 0x03) << 6)
                        self.raw_table[cur] = new_b0
                        self.raw_table[cur + 4] = result & 0xFF
                        return True
                    c -= 1
                cur += 5

            # 2. Check for a deleted slot (partner == 0) within current chunks
            cur = pos
            c = count
            while c > 0 and cur + 5 <= len(self.raw_table):
                b0, b1, b2, b3, b4 = self.raw_table[cur : cur + 5]
                p1 = ((b0 & 0x03) << 8) | b1
                if p1 == 0:
                    new_b0 = (b0 & ~0x0F) | ((partner >> 8) & 0x03) | (((result >> 8) & 0x03) << 2)
                    self.raw_table[cur] = new_b0
                    self.raw_table[cur + 1] = partner & 0xFF
                    self.raw_table[cur + 2] = result & 0xFF
                    return True
                c -= 1
                if c > 0:
                    p2 = (((b0 >> 4) & 0x03) << 8) | b3
                    if p2 == 0:
                        new_b0 = (b0 & ~0xF0) | (((partner >> 8) & 0x03) << 4) | (((result >> 8) & 0x03) << 6)
                        self.raw_table[cur] = new_b0
                        self.raw_table[cur + 3] = partner & 0xFF
                        self.raw_table[cur + 4] = result & 0xFF
                        return True
                    c -= 1
                cur += 5

            # If no existing/deleted slot, unpack all current recipes to serialize into new gap
            recipes = decode_card_fusions(bytes(self.raw_table), ptr)
        else:
            recipes = []

        # 3. Append new recipe and relocate to a free unallocated gap
        recipes.append((partner, result))
        new_bytes = serialize_card_fusions(recipes)
        gap = self._find_fusion_table_gap(len(new_bytes))
        if gap is not None and gap + len(new_bytes) <= FUSION_TABLE_SIZE:
            self.raw_table[gap : gap + len(new_bytes)] = new_bytes
            struct.pack_into('<H', self.raw_table, host * 2, gap)
            return True

        return False

    def add_fusion(self, card_a: int, card_b: int, result: int) -> bool:
        """
        Adds a new fusion or updates existing fusion between card_a and card_b.
        The game's MIPS engine (at SLUS 0x80019a68) sorts card materials so host is
        ALWAYS min(card_a, card_b). We ensure the recipe is properly registered
        under host = min(card_a, card_b).
        """
        if not (1 <= card_a <= TOTAL_CARDS and 1 <= card_b <= TOTAL_CARDS and 1 <= result <= TOTAL_CARDS):
            return False

        host = min(card_a, card_b)
        partner = max(card_a, card_b)
        key = (host, partner)

        ok = self._add_fusion_to_host(host, partner, result)
        if ok:
            self.fusions[key] = result
        return ok

    def delete_fusion(self, card_a: int, card_b: int) -> bool:
        """Removes a fusion recipe from in-memory cache and zeroes its slot in raw table."""
        key = (min(card_a, card_b), max(card_a, card_b))
        if key not in self.fusions:
            return False

        del self.fusions[key]
        for target_card, partner in [(card_a, card_b), (card_b, card_a)]:
            if target_card * 2 + 2 > len(self.raw_table):
                continue
            ptr = struct.unpack_from('<H', self.raw_table, target_card * 2)[0]
            if ptr == 0 or ptr >= len(self.raw_table):
                continue
            pos = ptr
            t0 = self.raw_table[pos]
            pos += 1
            if t0 == 0:
                if pos >= len(self.raw_table):
                    continue
                count = 511 - self.raw_table[pos]
                pos += 1
            else:
                count = t0
            while count > 0 and pos + 5 <= len(self.raw_table):
                b0, b1, b2, b3, b4 = self.raw_table[pos : pos + 5]
                p1 = ((b0 & 0x03) << 8) | b1
                if p1 == partner:
                    b0 = b0 & ~0x0F
                    self.raw_table[pos] = b0
                    self.raw_table[pos + 1] = 0
                    self.raw_table[pos + 2] = 0
                count -= 1
                if count > 0:
                    p2 = (((b0 >> 4) & 0x03) << 8) | b3
                    if p2 == partner:
                        b0 = b0 & ~0xF0
                        self.raw_table[pos] = b0
                        self.raw_table[pos + 3] = 0
                        self.raw_table[pos + 4] = 0
                    count -= 1
                pos += 5
        return True

    def import_from_mod_wa(self, mod_wa_bytes: bytes) -> int:
        """
        Imports the fusion table from another mod's WA_MRG.MRG.
        Overwrites current table and re-parses all recipes.
        """
        if len(mod_wa_bytes) < WA_FUSION_ARENA_BASE + 2000:
            raise ValueError("Mod WA_MRG is too short to contain a valid fusion table.")

        end = min(len(mod_wa_bytes), WA_FUSION_ARENA_BASE + FUSION_TABLE_SIZE)
        self.raw_table = bytearray(mod_wa_bytes[WA_FUSION_ARENA_BASE : end])
        if len(self.raw_table) < FUSION_TABLE_SIZE:
            self.raw_table.extend(b'\x00' * (FUSION_TABLE_SIZE - len(self.raw_table)))
        self._parse_fusions()
        return len(self.fusions)

    def save_to_wa(self, wa_bytes: bytearray):
        """
        Synchronously writes the fusion table into all 7 battle arenas of WA_MRG.MRG.
        Guarantees that every arena in the game uses identical, non-corrupted fusion recipes
        and strictly limits write size to 65,536 bytes to protect adjacent sectors.
        """
        table_to_write = self.raw_table[:FUSION_TABLE_SIZE]
        for arena in range(NUM_ARENAS):
            arena_offset = WA_FUSION_ARENA_BASE + arena * WA_ARENA_STEP
            end = min(len(wa_bytes), arena_offset + len(table_to_write))
            slice_len = end - arena_offset
            if slice_len > 0:
                wa_bytes[arena_offset : end] = table_to_write[:slice_len]
