"""
Tests for MIPS analysis and transplant engine.
"""

import os
import sys
import unittest
import struct

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.mips_engine import (
    MIPSInstruction,
    AOBPattern,
    PSXExecutable,
    DropX100Transplanter
)

class TestMIPSEngine(unittest.TestCase):
    def test_mips_instruction_disassembly(self):
        # 0x24020064 -> addiu $v0, $zero, 100
        inst = MIPSInstruction(0x24020064, 0x80010000)
        self.assertEqual(inst.disasm(), "addiu $v0, $zero, 100")

        # NOP (0x00000000)
        nop = MIPSInstruction(0x00000000, 0x80010004)
        self.assertEqual(nop.disasm(), "nop")

        # jr $ra (0x03E00008)
        jr = MIPSInstruction(0x03E00008, 0x80010008)
        self.assertEqual(jr.disasm(), "jr $ra")

    def test_aob_pattern_search(self):
        data = bytes([0x12, 0x34, 0x24, 0x02, 0x00, 0x64, 0xAB, 0xCD, 0x24, 0x02, 0x00, 0x64])
        # Search with wildcards
        pattern = AOBPattern("24 02 ?? 64")
        matches = pattern.search(data)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0], 2)
        self.assertEqual(matches[1], 8)

    def test_psx_executable_parsing(self):
        raw = bytearray(0x1000)
        raw[0:8] = b"PS-X EXE"
        struct.pack_into("<I", raw, 0x18, 0x80010000) # Load address
        struct.pack_into("<I", raw, 0x1C, 0x800)        # Text size
        # Add a test instruction at offset 0x800
        struct.pack_into("<I", raw, 0x800, 0x24020064)

        exe = PSXExecutable(bytes(raw))
        self.assertTrue(exe.has_header)
        self.assertEqual(exe.load_address, 0x80010000)
        self.assertEqual(exe.ram_to_offset(0x80010000), 0x800)
        self.assertEqual(exe.offset_to_ram(0x800), 0x80010000)
        self.assertEqual(exe.read_word(0x800), 0x24020064)

    def test_drop_customization(self):
        target = bytearray([0x64, 0x00, 0x02, 0x24]) # addiu $v0, $zero, 100
        modified = DropX100Transplanter.customize_drop_count(target, count=50)
        self.assertEqual(modified, 1)
        # Should now be addiu $v0, $zero, 50
        inst = MIPSInstruction(struct.unpack_from("<I", target, 0)[0])
        self.assertEqual(inst.disasm(), "addiu $v0, $zero, 50")

if __name__ == "__main__":
    unittest.main()
