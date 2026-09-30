"""
Card Database and Models for Yu-Gi-Oh! Forbidden Memories.
Handles bitfield unpacking/packing for card stats in SLUS_014.11,
BCD password conversion and Star Chip costs in DATA/WA_MRG.MRG,
and text TBL encoding/decoding.
"""

import struct
from typing import Dict, List, Optional
from core.card_data import CARD_TYPES, GUARDIAN_STARS, CARD_NAMES

# Konami TBL Character Table for Card Names in SLUS_014.11
TBL_CHAR_TO_BYTE = {
    ' ': 0x00,
    'A': 0x18, 'B': 0x2D, 'C': 0x2B, 'D': 0x20, 'E': 0x25, 'F': 0x31, 'G': 0x29, 'H': 0x23,
    'I': 0x1A, 'J': 0x3B, 'K': 0x33, 'L': 0x2A, 'M': 0x1E, 'N': 0x2C, 'O': 0x21, 'P': 0x2F,
    'Q': 0x3E, 'R': 0x26, 'S': 0x1D, 'T': 0x1C, 'U': 0x35, 'V': 0x39, 'W': 0x22, 'X': 0x46,
    'Y': 0x24, 'Z': 0x3F,
    'a': 0x03, 'b': 0x15, 'c': 0x0F, 'd': 0x0C, 'e': 0x01, 'f': 0x13, 'g': 0x10, 'h': 0x09,
    'i': 0x05, 'j': 0x34, 'k': 0x16, 'l': 0x0A, 'm': 0x0E, 'n': 0x06, 'o': 0x04, 'p': 0x14,
    'q': 0x37, 'r': 0x08, 's': 0x07, 't': 0x02, 'u': 0x0D, 'v': 0x19, 'w': 0x12, 'x': 0x36,
    'y': 0x11, 'z': 0x32,
    '0': 0x38, '1': 0x3D, '2': 0x3A, '3': 0x41, '4': 0x4A, '5': 0x42, '6': 0x4E, '7': 0x45,
    '8': 0x57, '9': 0x59,
    '.': 0x0B, ',': 0x1F, '!': 0x17, '?': 0x2E, '-': 0x30, "'": 0x1B, '/': 0x28, '&': 0x43, '#': 0x3C, 'α': 0x55,
    '"': 0x40, ':': 0x48, ';': 0x48, '(': 0x28, ')': 0x28
}

TBL_BYTE_TO_CHAR = {v: k for k, v in TBL_CHAR_TO_BYTE.items()}
# Special alternate mappings
TBL_BYTE_TO_CHAR[0x27] = '&'
TBL_BYTE_TO_CHAR[0x55] = 'α'
TBL_BYTE_TO_CHAR[0x40] = '"'
TBL_BYTE_TO_CHAR[0x48] = ':'

# Offsets in SLUS_014.11 and WA_MRG.MRG
SLUS_STATS_OFFSET = 0x1C4A44             # 722 * 4 bytes = 2888 bytes
SLUS_NAMES_PTRS_OFFSET = 0x1C6000        # 1024 * 2 bytes = 2048 bytes (names & string pointer table)
SLUS_STRING_TABLE_BASE = 0x1C0800        # Base address for relative pointers in string table
SLUS_NAMES_OFFSET = 0x1C6800             # 0xFF-delimited names start
SLUS_NAMES_MAX_OFFSET = 0x1C9800         # 0x1C9800 is hard ceiling: font textures and glyph rendering tables begin here!
SLUS_DESCRIPTIONS_PTRS_OFFSET = 0x1B0A02 # 722 * 2 bytes = 1444 bytes (pointer table)
SLUS_DESCRIPTIONS_BASE = 0x1B0800        # Base address for relative pointers
SLUS_DESCRIPTIONS_FIRST_TEXT = 0x1B11F5  # Offset of first description string
SLUS_DESCRIPTIONS_MAX_OFFSET = 0x1C4800  # End of text area before next code section
WA_PASSWORDS_OFFSET = 0x0FB9808          # 722 * 8 bytes = 5776 bytes
TOTAL_CARDS = 722

import re
from core.card_data import CARD_TYPES, CARD_TYPES_ES, GUARDIAN_STARS, CARD_NAMES

# Mapping of type tags (in English, Spanish, and aliases) to 0xF8 0x0B type IDs
TYPE_TAG_TO_ID: Dict[str, int] = {}
for _i, _name in enumerate(CARD_TYPES):
    TYPE_TAG_TO_ID[_name.lower()] = _i
    TYPE_TAG_TO_ID[_name.lower().replace('-', ' ')] = _i
    TYPE_TAG_TO_ID[_name.lower().replace(' ', '-')] = _i
for _i, _name in enumerate(CARD_TYPES_ES):
    TYPE_TAG_TO_ID[_name.lower()] = _i
    TYPE_TAG_TO_ID[_name.lower().replace('-', ' ')] = _i
    TYPE_TAG_TO_ID[_name.lower().replace(' ', '-')] = _i
TYPE_TAG_TO_ID.update({
    'mago': 1, 'spell': 20, 'magica': 20, 'maquina': 14, 'dragon': 0, 'dragón': 0,
    'agua': 16, 'fuego': 17
})

TAG_RE = re.compile(r'\[([^\]]+)\]')

ACCENT_NORMALIZE = {
    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n',
    'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U', 'Ñ': 'N',
    '¿': '?', '¡': '!', '“': '"', '”': '"', '’': "'", '`': "'",
    '[': '(', ']': ')', '{': '(', '}': ')',
}


def decode_description(exe_bytes: bytes, ptr: int, base: int = SLUS_DESCRIPTIONS_BASE) -> str:
    """Decodes a Konami TBL description string at base + ptr, including 0xF8 0x0B <type_id> glyph tags."""
    pos = base + ptr
    chars = []
    while pos < len(exe_bytes):
        b = exe_bytes[pos]
        if b == 0xFF:
            break
        elif b == 0xFE:
            chars.append('\n')
            pos += 1
        elif b == 0xF8 and pos + 2 < len(exe_bytes) and exe_bytes[pos + 1] == 0x0B:
            type_id = exe_bytes[pos + 2]
            if 0 <= type_id < len(CARD_TYPES):
                chars.append(f"[{CARD_TYPES[type_id]}]")
            else:
                chars.append(f"[Type_{type_id}]")
            pos += 3
        else:
            chars.append(TBL_BYTE_TO_CHAR.get(b, ' '))
            pos += 1
    return "".join(chars)


def encode_description(text: str) -> bytes:
    """
    Encodes a string into Konami TBL bytes with 0xFE for newline,
    0xF8 0x0B <type_id> for inline type glyph tags (e.g. [Beast], [Bestia], [Warrior]),
    and 0xFF terminator.
    """
    out = []
    pos = 0
    text_len = len(text)
    while pos < text_len:
        m = TAG_RE.match(text, pos)
        if m:
            tag_content = m.group(1).strip().lower()
            if tag_content in TYPE_TAG_TO_ID:
                tid = TYPE_TAG_TO_ID[tag_content]
                out.extend([0xF8, 0x0B, tid])
                pos = m.end()
                continue
            elif tag_content.startswith(('type_', 'tipo_')) and tag_content[5:].isdigit():
                tid = int(tag_content[5:])
                out.extend([0xF8, 0x0B, tid])
                pos = m.end()
                continue
            elif tag_content.isdigit() and int(tag_content) < len(CARD_TYPES):
                tid = int(tag_content)
                out.extend([0xF8, 0x0B, tid])
                pos = m.end()
                continue

        ch = text[pos]
        pos += 1
        if ch in ACCENT_NORMALIZE:
            ch = ACCENT_NORMALIZE[ch]
        if ch == '\n':
            out.append(0xFE)
        elif ch in TBL_CHAR_TO_BYTE:
            out.append(TBL_CHAR_TO_BYTE[ch])
        elif ch.upper() in TBL_CHAR_TO_BYTE:
            out.append(TBL_CHAR_TO_BYTE[ch.upper()])
        elif ch.lower() in TBL_CHAR_TO_BYTE:
            out.append(TBL_CHAR_TO_BYTE[ch.lower()])
        else:
            out.append(0x00)
    out.append(0xFF)
    return bytes(out)


def encode_card_name(name: str, font_prefix: Optional[bytes] = None) -> bytes:
    """Encodes a card name into Konami TBL bytes, applying font prefix if explicitly present and 0xFF terminator."""
    out = []
    if font_prefix and len(font_prefix) >= 3 and font_prefix[0] == 0xF8:
        out.extend(font_prefix)

    for ch in name:
        if ch in ACCENT_NORMALIZE:
            ch = ACCENT_NORMALIZE[ch]
        if ch in TBL_CHAR_TO_BYTE:
            out.append(TBL_CHAR_TO_BYTE[ch])
        elif ch.upper() in TBL_CHAR_TO_BYTE:
            out.append(TBL_CHAR_TO_BYTE[ch.upper()])
        elif ch.lower() in TBL_CHAR_TO_BYTE:
            out.append(TBL_CHAR_TO_BYTE[ch.lower()])
        else:
            out.append(0x00)
    out.append(0xFF)
    return bytes(out)


class Card:
    def __init__(
        self,
        card_id: int,
        name: str,
        atk: int = 0,
        def_: int = 0,
        type_id: int = 0,
        gs1: int = 0,
        gs2: int = 0,
        password: str = "00000000",
        star_cost: int = 0,
        description: str = ""
    ):
        self.card_id = card_id
        self.name = name
        self.atk = atk
        self.def_ = def_
        self.type_id = max(0, min(23, type_id))
        self.gs1 = max(0, min(10, gs1))
        self.gs2 = max(0, min(10, gs2))
        self.password = password.zfill(8)[:8]
        self.star_cost = max(0, min(999999, star_cost))
        self.description = description

    @property
    def type_name(self) -> str:
        if 0 <= self.type_id < len(CARD_TYPES):
            return CARD_TYPES[self.type_id]
        return f"Unknown ({self.type_id})"

    @property
    def gs1_name(self) -> str:
        if 0 <= self.gs1 < len(GUARDIAN_STARS):
            return GUARDIAN_STARS[self.gs1]
        return f"Unknown ({self.gs1})"

    @property
    def gs2_name(self) -> str:
        if 0 <= self.gs2 < len(GUARDIAN_STARS):
            return GUARDIAN_STARS[self.gs2]
        return f"Unknown ({self.gs2})"

    def pack_stats(self) -> int:
        """Packs ATK, DEF, GS1, GS2, and Type into a 32-bit integer."""
        raw_atk = max(0, min(511, self.atk // 10))
        raw_def = max(0, min(511, self.def_ // 10))
        raw_gs2 = self.gs2 & 0xF
        raw_gs1 = self.gs1 & 0xF
        raw_type = self.type_id & 0x1F

        val = (raw_atk & 0x1FF)
        val |= (raw_def & 0x1FF) << 9
        val |= (raw_gs2 & 0xF) << 18
        val |= (raw_gs1 & 0xF) << 22
        val |= (raw_type & 0x1F) << 26
        return val & 0xFFFFFFFF

    @classmethod
    def unpack_stats(cls, raw: int) -> tuple:
        """Unpacks 32-bit stats integer into (atk, def, gs1, gs2, type_id)."""
        atk = (raw & 0x1FF) * 10
        def_ = ((raw >> 9) & 0x1FF) * 10
        gs2 = (raw >> 18) & 0xF
        gs1 = (raw >> 22) & 0xF
        type_id = (raw >> 26) & 0x1F
        return atk, def_, gs1, gs2, type_id

    def pack_password(self) -> bytes:
        """
        Packs 8-digit password into 4 bytes BCD (little-endian byte order).
        Example: '89631139' -> bytes [0x39, 0x11, 0x63, 0x89].
        """
        p = self.password.zfill(8)[:8]
        # In YGO FM:
        # byte 0 = int(p[6:8], 16)
        # byte 1 = int(p[4:6], 16)
        # byte 2 = int(p[2:4], 16)
        # byte 3 = int(p[0:2], 16)
        try:
            b0 = int(p[6:8], 16)
            b1 = int(p[4:6], 16)
            b2 = int(p[2:4], 16)
            b3 = int(p[0:2], 16)
        except ValueError:
            b0 = b1 = b2 = b3 = 0
        return bytes([b0, b1, b2, b3])

    @classmethod
    def unpack_password(cls, b: bytes) -> str:
        """
        Unpacks 4 bytes BCD into 8-digit password string.
        bytes [0x39, 0x11, 0x63, 0x89] -> '89631139'.
        """
        if len(b) < 4:
            return "00000000"
        return f"{b[3]:02x}{b[2]:02x}{b[1]:02x}{b[0]:02x}"

    def to_dict(self) -> dict:
        return {
            "id": self.card_id,
            "name": self.name,
            "atk": self.atk,
            "def": self.def_,
            "type_id": self.type_id,
            "type_name": self.type_name,
            "gs1": self.gs1,
            "gs1_name": self.gs1_name,
            "gs2": self.gs2,
            "gs2_name": self.gs2_name,
            "password": self.password,
            "star_cost": self.star_cost,
            "description": self.description
        }


class CardDatabase:
    def __init__(self):
        self.cards: Dict[int, Card] = {}
        self.raw_name_prefixes: Dict[int, bytes] = {}
        self.raw_names_ptrs: List[int] = []
        self.tail_names_data: bytes = b""
        self.orig_card_names_len: int = 0x1C92CD - SLUS_NAMES_OFFSET

    def get(self, card_id: int) -> Optional[Card]:
        return self.cards.get(card_id)

    def load_from_exe_and_wa(self, exe_bytes: bytes, wa_bytes: bytes) -> int:
        """Loads all 722 cards from SLUS_014.11 and WA_MRG.MRG."""
        self.cards.clear()

        # 1. Extract card names from SLUS_014.11
        names = self._extract_names(exe_bytes)

        # 2. Extract stats from SLUS_014.11 (0x1C4A44)
        stats_data = exe_bytes[SLUS_STATS_OFFSET : SLUS_STATS_OFFSET + TOTAL_CARDS * 4]

        # 3. Extract costs and passwords from WA_MRG.MRG (0x0FB9808)
        pass_data = wa_bytes[WA_PASSWORDS_OFFSET : WA_PASSWORDS_OFFSET + TOTAL_CARDS * 8]

        # 4. Extract descriptions from SLUS_014.11 (0x1B0A02)
        has_desc_ptrs = len(exe_bytes) >= SLUS_DESCRIPTIONS_PTRS_OFFSET + TOTAL_CARDS * 2
        descriptions = []
        if has_desc_ptrs:
            for i in range(TOTAL_CARDS):
                ptr = struct.unpack_from("<H", exe_bytes, SLUS_DESCRIPTIONS_PTRS_OFFSET + i * 2)[0]
                desc = decode_description(exe_bytes, ptr, SLUS_DESCRIPTIONS_BASE)
                descriptions.append(desc)
        else:
            descriptions = [""] * TOTAL_CARDS

        for i in range(TOTAL_CARDS):
            card_id = i + 1
            name = names[i] if i < len(names) and names[i] else CARD_NAMES.get(card_id, f"Card #{card_id:03d}")

            # Stats
            raw_stat = struct.unpack_from("<I", stats_data, i * 4)[0]
            atk, def_, gs1, gs2, type_id = Card.unpack_stats(raw_stat)

            # Passwords & Cost
            pass_slice = pass_data[i * 8 : (i + 1) * 8]
            cost = struct.unpack_from("<I", pass_slice, 0)[0] if len(pass_slice) >= 4 else 0
            pwd = Card.unpack_password(pass_slice[4:8]) if len(pass_slice) >= 8 else "00000000"

            card = Card(
                card_id=card_id,
                name=name,
                atk=atk,
                def_=def_,
                type_id=type_id,
                gs1=gs1,
                gs2=gs2,
                password=pwd,
                star_cost=cost,
                description=descriptions[i]
            )
            self.cards[card_id] = card

        return len(self.cards)

    def save_to_exe_and_wa(self, exe_bytes: bytearray, wa_bytes: bytearray):
        """Serializes current in-memory card names, stats, costs, passwords, and descriptions back into the binaries."""
        for i in range(TOTAL_CARDS):
            card_id = i + 1
            card = self.cards.get(card_id)
            if not card:
                continue

            # 1. Update stats in SLUS
            packed_stat = card.pack_stats()
            struct.pack_into("<I", exe_bytes, SLUS_STATS_OFFSET + i * 4, packed_stat)

            # 2. Update star cost and password in WA_MRG
            pass_offset = WA_PASSWORDS_OFFSET + i * 8
            struct.pack_into("<I", wa_bytes, pass_offset, card.star_cost)
            pwd_bytes = card.pack_password()
            wa_bytes[pass_offset + 4 : pass_offset + 8] = pwd_bytes

        # 3. Update descriptions in SLUS_014.11
        if len(exe_bytes) >= SLUS_DESCRIPTIONS_MAX_OFFSET:
            cur_offset = SLUS_DESCRIPTIONS_FIRST_TEXT
            for i in range(TOTAL_CARDS):
                card_id = i + 1
                c = self.cards.get(card_id)
                desc_text = c.description if c else ""
                encoded = encode_description(desc_text)
                if cur_offset + len(encoded) >= SLUS_DESCRIPTIONS_MAX_OFFSET:
                    encoded = bytes([0xFF])
                ptr_val = cur_offset - SLUS_DESCRIPTIONS_BASE
                struct.pack_into("<H", exe_bytes, SLUS_DESCRIPTIONS_PTRS_OFFSET + i * 2, ptr_val)
                exe_bytes[cur_offset : cur_offset + len(encoded)] = encoded
                cur_offset += len(encoded)
            # Zero-pad remaining area up to the original padding boundary
            if cur_offset < 0x1BDD9E:
                exe_bytes[cur_offset : 0x1BDD9E] = b"\x00" * (0x1BDD9E - cur_offset)

        # 4. Update card names and pointer table in SLUS_014.11
        if len(exe_bytes) >= SLUS_NAMES_OFFSET:
            new_ptrs = list(self.raw_names_ptrs) if self.raw_names_ptrs else [0x6000] * 1024
            if len(new_ptrs) < 1024:
                new_ptrs.extend([0x6000] * (1024 - len(new_ptrs)))

            is_extended_layout = False
            if len(self.raw_names_ptrs) > 768:
                p768_off = SLUS_STRING_TABLE_BASE + self.raw_names_ptrs[768]
                if p768_off >= 0x1C9A00:
                    is_extended_layout = True

            if is_extended_layout:
                # Extended/Dream Mod layout:
                # Cards 1..721 in 0x1C6801..location_boundary (0x1C959A)
                # Locations (848..863) at 0x1C959A are preserved untouched
                # Card 722 is at 0x1C9A00
                # Types (768..791), Stars (792..801), Opponents (808..847) at 0x1C9A1B..0x1C9CF9 are preserved untouched
                names_buf = bytearray(b"\xFF")
                for cid in range(1, 722):
                    c = self.cards.get(cid)
                    cname = c.name if c and c.name else CARD_NAMES.get(cid, f"Card #{cid:03d}")
                    prefix = self.raw_name_prefixes.get(cid)
                    new_ptrs[cid] = (SLUS_NAMES_OFFSET + len(names_buf)) - SLUS_STRING_TABLE_BASE
                    names_buf.extend(encode_card_name(cname, font_prefix=prefix))

                loc_boundary = (SLUS_STRING_TABLE_BASE + self.raw_names_ptrs[848]) if len(self.raw_names_ptrs) > 848 else 0x1C959A
                if SLUS_NAMES_OFFSET + len(names_buf) <= loc_boundary:
                    exe_bytes[SLUS_NAMES_OFFSET : SLUS_NAMES_OFFSET + len(names_buf)] = names_buf
                    exe_bytes[SLUS_NAMES_OFFSET + len(names_buf) : loc_boundary] = b"\x00" * (loc_boundary - (SLUS_NAMES_OFFSET + len(names_buf)))

                # Write Card 722 at 0x1C9A00
                c722 = self.cards.get(722)
                c722_name = c722.name if c722 and c722.name else CARD_NAMES.get(722, "Card #722")
                c722_pfx = self.raw_name_prefixes.get(722)
                c722_bytes = encode_card_name(c722_name, font_prefix=c722_pfx)
                type_boundary = SLUS_STRING_TABLE_BASE + self.raw_names_ptrs[768]
                new_ptrs[722] = 0x1C9A00 - SLUS_STRING_TABLE_BASE
                if 0x1C9A00 + len(c722_bytes) <= type_boundary:
                    exe_bytes[0x1C9A00 : 0x1C9A00 + len(c722_bytes)] = c722_bytes
                    exe_bytes[0x1C9A00 + len(c722_bytes) : type_boundary] = b"\x00" * (type_boundary - (0x1C9A00 + len(c722_bytes)))

            else:
                # Standard Vanilla layout:
                # Cards 1..722 in 0x1C6801..0x1C92CD
                # Followed by tail strings (Types, Stars, Opponents, Locations)
                names_buf = bytearray(b"\xFF")
                for cid in range(1, TOTAL_CARDS + 1):
                    c = self.cards.get(cid)
                    cname = c.name if c and c.name else CARD_NAMES.get(cid, f"Card #{cid:03d}")
                    prefix = self.raw_name_prefixes.get(cid)
                    new_ptrs[cid] = (SLUS_NAMES_OFFSET + len(names_buf)) - SLUS_STRING_TABLE_BASE
                    names_buf.extend(encode_card_name(cname, font_prefix=prefix))

                orig_tail_start = (SLUS_STRING_TABLE_BASE + self.raw_names_ptrs[768]) if (len(self.raw_names_ptrs) > 768 and self.raw_names_ptrs[768] not in (0, 0x6000)) else 0x1C92CE
                tail_data = self.tail_names_data if self.tail_names_data else bytes(exe_bytes[orig_tail_start : 0x1C96AC])
                new_tail_start = SLUS_NAMES_OFFSET + len(names_buf)
                delta = new_tail_start - orig_tail_start

                if new_tail_start + len(tail_data) <= SLUS_NAMES_MAX_OFFSET:
                    for i in range(TOTAL_CARDS + 1, len(new_ptrs)):
                        p = new_ptrs[i]
                        if p != 0x6000 and p != 0:
                            new_ptrs[i] = max(0, min(0xFFFF, p + delta))

                    exe_bytes[SLUS_NAMES_OFFSET : new_tail_start] = names_buf
                    exe_bytes[new_tail_start : new_tail_start + len(tail_data)] = tail_data
                    if new_tail_start + len(tail_data) < SLUS_NAMES_MAX_OFFSET:
                        exe_bytes[new_tail_start + len(tail_data) : SLUS_NAMES_MAX_OFFSET] = b"\x00" * (SLUS_NAMES_MAX_OFFSET - (new_tail_start + len(tail_data)))

            # Update pointer table at 0x1C6000
            if len(exe_bytes) >= SLUS_NAMES_PTRS_OFFSET + 2048:
                for i in range(1024):
                    struct.pack_into("<H", exe_bytes, SLUS_NAMES_PTRS_OFFSET + i * 2, new_ptrs[i])

    def import_cards_from_mod(self, mod_exe_bytes: bytes, mod_wa_bytes: bytes):
        """Copies all stats, passwords, costs, descriptions, and names from another mod's binaries into this database."""
        temp_db = CardDatabase()
        temp_db.load_from_exe_and_wa(mod_exe_bytes, mod_wa_bytes)
        for card_id, mod_card in temp_db.cards.items():
            if card_id in self.cards:
                self.cards[card_id].name = mod_card.name
                self.cards[card_id].atk = mod_card.atk
                self.cards[card_id].def_ = mod_card.def_
                self.cards[card_id].type_id = mod_card.type_id
                self.cards[card_id].gs1 = mod_card.gs1
                self.cards[card_id].gs2 = mod_card.gs2
                self.cards[card_id].password = mod_card.password
                self.cards[card_id].star_cost = mod_card.star_cost
                self.cards[card_id].description = mod_card.description
        self.raw_name_prefixes = dict(temp_db.raw_name_prefixes)
        if temp_db.tail_names_data:
            self.tail_names_data = temp_db.tail_names_data
        if hasattr(temp_db, "raw_names_ptrs") and temp_db.raw_names_ptrs:
            self.raw_names_ptrs = list(temp_db.raw_names_ptrs)
        if hasattr(temp_db, "orig_card_names_len"):
            self.orig_card_names_len = temp_db.orig_card_names_len

    def _extract_names(self, exe_bytes: bytes) -> List[str]:
        names = []
        self.raw_name_prefixes.clear()

        # Load original 1024-entry uint16 pointer table at 0x1C6000
        if len(exe_bytes) >= SLUS_NAMES_PTRS_OFFSET + 2048:
            self.raw_names_ptrs = list(struct.unpack("<1024H", exe_bytes[SLUS_NAMES_PTRS_OFFSET : SLUS_NAMES_PTRS_OFFSET + 2048]))
        else:
            self.raw_names_ptrs = []

        if not self.raw_names_ptrs:
            return [CARD_NAMES.get(i, f"Card #{i:03d}") for i in range(1, TOTAL_CARDS + 1)]

        for cid in range(1, TOTAL_CARDS + 1):
            p = self.raw_names_ptrs[cid]
            if p in (0, 0x6000):
                names.append(CARD_NAMES.get(cid, f"Card #{cid:03d}"))
                continue
            off = SLUS_STRING_TABLE_BASE + p
            raw = []
            while off < len(exe_bytes) and exe_bytes[off] != 0xFF:
                raw.append(exe_bytes[off])
                off += 1
            if len(raw) >= 3 and raw[0] == 0xF8:
                self.raw_name_prefixes[cid] = bytes(raw[:3])
                raw = raw[3:]
            name_str = "".join(TBL_BYTE_TO_CHAR.get(x, " ") for x in raw)
            names.append(name_str)

        orig_tail_start = (SLUS_STRING_TABLE_BASE + self.raw_names_ptrs[768]) if len(self.raw_names_ptrs) > 768 else 0x1C92CE
        if orig_tail_start < 0x1C9800:
            self.tail_names_data = exe_bytes[orig_tail_start : 0x1C96AC]
            self.orig_card_names_len = orig_tail_start - SLUS_NAMES_OFFSET
        else:
            self.tail_names_data = b""
            self.orig_card_names_len = 0x1C959A - SLUS_NAMES_OFFSET

        return names

