"""
MIPS R3000A Analysis and Signature Engine for Yu-Gi-Oh! Forbidden Memories.
Handles PS-X EXE disassembly, Array-of-Bytes (AOB) pattern scanning with wildcards,
diff extraction between Vanilla Express and target executables,
and surgical injection of the stable drop x100 routine.
"""

import re
import struct
from typing import Dict, List, Optional, Tuple

# MIPS R3000 Register Names
MIPS_REGS = [
    "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
    "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
    "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
    "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra"
]

class MIPSInstruction:
    def __init__(self, raw: int, address: int = 0):
        self.raw = raw & 0xFFFFFFFF
        self.address = address
        self.opcode = (self.raw >> 26) & 0x3F
        self.rs = (self.raw >> 21) & 0x1F
        self.rt = (self.raw >> 16) & 0x1F
        self.rd = (self.raw >> 11) & 0x1F
        self.shamt = (self.raw >> 6) & 0x1F
        self.funct = self.raw & 0x3F
        self.imm = self.raw & 0xFFFF
        self.simm = self.imm if self.imm < 0x8000 else self.imm - 0x10000
        self.target = (self.raw & 0x03FFFFFF) << 2

    def __repr__(self) -> str:
        return f"{hex(self.address)}: {hex(self.raw)} {self.disasm()}"

    def disasm(self) -> str:
        # Common instructions in drop loops
        op = self.opcode
        rs_name = MIPS_REGS[self.rs]
        rt_name = MIPS_REGS[self.rt]
        rd_name = MIPS_REGS[self.rd]

        if op == 0x00: # SPECIAL
            if self.funct == 0x00:
                if self.raw == 0:
                    return "nop"
                return f"sll {rd_name}, {rt_name}, {self.shamt}"
            elif self.funct == 0x08:
                return f"jr {rs_name}"
            elif self.funct == 0x09:
                return f"jalr {rd_name}, {rs_name}"
            elif self.funct == 0x20:
                return f"add {rd_name}, {rs_name}, {rt_name}"
            elif self.funct == 0x21:
                return f"addu {rd_name}, {rs_name}, {rt_name}"
            elif self.funct == 0x23:
                return f"subu {rd_name}, {rs_name}, {rt_name}"
            elif self.funct == 0x24:
                return f"and {rd_name}, {rs_name}, {rt_name}"
            elif self.funct == 0x25:
                return f"or {rd_name}, {rs_name}, {rt_name}"
            elif self.funct == 0x2A:
                return f"slt {rd_name}, {rs_name}, {rt_name}"
            elif self.funct == 0x2B:
                return f"sltu {rd_name}, {rs_name}, {rt_name}"
            return f"special funct={hex(self.funct)}"
        elif op == 0x02:
            return f"j {hex((self.address & 0xF0000000) | self.target)}"
        elif op == 0x03:
            return f"jal {hex((self.address & 0xF0000000) | self.target)}"
        elif op == 0x04:
            return f"beq {rs_name}, {rt_name}, {hex(self.address + 4 + (self.simm << 2))}"
        elif op == 0x05:
            return f"bne {rs_name}, {rt_name}, {hex(self.address + 4 + (self.simm << 2))}"
        elif op == 0x08:
            return f"addi {rt_name}, {rs_name}, {self.simm}"
        elif op == 0x09:
            return f"addiu {rt_name}, {rs_name}, {self.simm}"
        elif op == 0x0A:
            return f"slti {rt_name}, {rs_name}, {self.simm}"
        elif op == 0x0B:
            return f"sltiu {rt_name}, {rs_name}, {self.simm}"
        elif op == 0x0C:
            return f"andi {rt_name}, {rs_name}, {hex(self.imm)}"
        elif op == 0x0D:
            return f"ori {rt_name}, {rs_name}, {hex(self.imm)}"
        elif op == 0x0F:
            return f"lui {rt_name}, {hex(self.imm)}"
        elif op == 0x20:
            return f"lb {rt_name}, {self.simm}({rs_name})"
        elif op == 0x21:
            return f"lh {rt_name}, {self.simm}({rs_name})"
        elif op == 0x23:
            return f"lw {rt_name}, {self.simm}({rs_name})"
        elif op == 0x24:
            return f"lbu {rt_name}, {self.simm}({rs_name})"
        elif op == 0x25:
            return f"lhu {rt_name}, {self.simm}({rs_name})"
        elif op == 0x28:
            return f"sb {rt_name}, {self.simm}({rs_name})"
        elif op == 0x29:
            return f"sh {rt_name}, {self.simm}({rs_name})"
        elif op == 0x2B:
            return f"sw {rt_name}, {self.simm}({rs_name})"

        return f"op_{hex(op)} {rt_name}, {rs_name}, {hex(self.imm)}"


class AOBPattern:
    """
    Pattern scanner supporting byte arrays with wildcards (e.g. '24 02 00 64 ?? ?? ?? ??').
    """
    def __init__(self, pattern_str: str):
        self.pattern_str = pattern_str.strip()
        tokens = self.pattern_str.split()
        regex_parts = []
        for t in tokens:
            if t in ("?", "??", "*"):
                regex_parts.append(b".")
            else:
                regex_parts.append(re.escape(bytes([int(t, 16)])))
        self.regex = re.compile(b"".join(regex_parts), re.DOTALL)

    def search(self, data: bytes) -> List[int]:
        """Returns all matching byte offsets in data."""
        return [match.start() for match in self.regex.finditer(data)]


class PSXExecutable:
    """
    Parser for PS-X EXE files (e.g. SLUS_014.11).
    Header is 2048 bytes; code/data begins at offset 0x800.
    """
    MAGIC = b"PS-X EXE"

    def __init__(self, raw_bytes: bytes):
        self.raw_data = bytearray(raw_bytes)
        if not self.raw_data.startswith(self.MAGIC):
            # Some versions might lack standard header if extracted raw, but standard SLUS always has it
            self.has_header = False
            self.load_address = 0x80010000
            self.text_offset = 0
            self.text_size = len(self.raw_data)
        else:
            self.has_header = True
            self.initial_pc = struct.unpack_from("<I", self.raw_data, 0x10)[0]
            self.initial_gp = struct.unpack_from("<I", self.raw_data, 0x14)[0]
            self.load_address = struct.unpack_from("<I", self.raw_data, 0x18)[0]
            self.text_size = struct.unpack_from("<I", self.raw_data, 0x1C)[0]
            self.text_offset = 0x800

    def ram_to_offset(self, ram_addr: int) -> int:
        return (ram_addr - self.load_address) + self.text_offset

    def offset_to_ram(self, offset: int) -> int:
        return (offset - self.text_offset) + self.load_address

    def read_word(self, offset: int) -> int:
        return struct.unpack_from("<I", self.raw_data, offset)[0]

    def write_word(self, offset: int, value: int):
        struct.pack_into("<I", self.raw_data, offset, value & 0xFFFFFFFF)

    def to_bytes(self) -> bytes:
        return bytes(self.raw_data)


class DropX100Transplanter:
    """
    Extracts the stable drop x100 routines from Vanilla Express
    and transplants them safely into a target mod's executable.
    """

    # Signature for Yu-Gi-Oh! Forbidden Memories duel drop loop:
    # Look for loop counter initialization, chest reward invocation, and trunk array stores.
    # In MIPS: addiu $reg, $zero, count or slti $reg, limit
    DROP_LOOP_SIGNATURES = [
        # Pattern 1: Reward loop check with addiu / slti
        "24 02 00 64",  # li $v0, 100 (0x64) in Vanilla Express
        "24 04 00 64",  # li $a0, 100
        "24 05 00 64",  # li $a1, 100
        "24 10 00 64",  # li $s0, 100
        "24 11 00 64",  # li $s1, 100
    ]

    @staticmethod
    def extract_diff_regions(base_exe: bytes, express_exe: bytes) -> List[Tuple[int, bytes, bytes]]:
        """
        Finds all contiguous differing byte ranges between base and Vanilla Express.
        Returns list of (offset, base_bytes, express_bytes).
        """
        min_len = min(len(base_exe), len(express_exe))
        diffs = []
        in_diff = False
        start = 0

        for i in range(min_len):
            different = (base_exe[i] != express_exe[i])
            if different and not in_diff:
                in_diff = True
                start = i
            elif not different and in_diff:
                in_diff = False
                diffs.append((start, base_exe[start:i], express_exe[start:i]))

        if in_diff:
            diffs.append((start, base_exe[start:min_len], express_exe[start:min_len]))

        return diffs

    @staticmethod
    def apply_diff_patches(target_exe: bytearray, diffs: List[Tuple[int, bytes, bytes]]) -> int:
        """
        Applies verified diff blocks to target executable.
        Returns number of patches applied.
        """
        applied = 0
        for offset, base_bytes, express_bytes in diffs:
            if offset + len(express_bytes) <= len(target_exe):
                target_exe[offset : offset + len(express_bytes)] = express_bytes
                applied += 1
        return applied

    @staticmethod
    def customize_drop_count(target_exe: bytearray, count: int = 100) -> int:
        """
        Scans target executable for the drop count immediate (0x64 = 100)
        in reward loop instructions and adjusts it to requested count (e.g. 5, 15, 50, 100).
        """
        if count <= 0 or count > 255:
            raise ValueError(f"Drop count must be between 1 and 255 (got {count}).")

        modified = 0
        val_bytes = bytes([count, 0x00]) # Little endian immediate 16-bit
        # Look for addiu $reg, $zero, 0x0064 -> [0x64, 0x00, 0x??, 0x24]
        for i in range(0, len(target_exe) - 3, 4):
            word = struct.unpack_from("<I", target_exe, i)[0]
            opcode = (word >> 26) & 0x3F
            imm = word & 0xFFFF
            # If addiu/ori with immediate 0x64 (100)
            if opcode in (0x09, 0x0D, 0x08) and imm == 0x0064:
                new_word = (word & 0xFFFF0000) | count
                struct.pack_into("<I", target_exe, i, new_word)
                modified += 1

        return modified
