"""
End-to-End Test for the 2-ISO Surgical Merger Pipeline.
"""

import hashlib
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.cdrom import encode_mode2_form1_sector, PS1DiscImage
from core.merger import YGOFMSurgicalMerger


def create_mock_ps1_disc(bin_path: str, exe_content: bytes, wa_content: bytes):
    """Generates a valid Mode 2 Form 1 PS1 disc image with SLUS_014.11 and WA_MRG.MRG."""
    with open(bin_path, "wb") as f:
        # 35 sectors
        for s in range(35):
            sec = bytearray(2352)
            sec[0:12] = bytes([0x00] + [0xFF]*10 + [0x00])

            # Sector 16: PVD
            if s == 16:
                pvd = bytearray(2048)
                pvd[0] = 0x01
                pvd[1:6] = b"CD001"
                pvd[6] = 0x01
                # Root dir record at 156
                root_rec = bytearray(34)
                root_rec[0] = 34
                struct.pack_into("<I", root_rec, 2, 18)   # Dir at LBA 18
                struct.pack_into("<I", root_rec, 10, 2048)
                root_rec[25] = 0x02
                pvd[156 : 156 + 34] = root_rec
                sec[0x18 : 0x18 + 2048] = pvd

            # Sector 18: Directory with SLUS_014.11 and WA_MRG.MRG
            elif s == 18:
                dir_sec = bytearray(2048)
                offset = 0

                # 1. Entry for SLUS_014.11;1 at LBA 20
                name1 = b"SLUS_014.11;1"
                len1 = 33 + len(name1) + (1 if (33 + len(name1)) % 2 != 0 else 0)
                rec1 = bytearray(len1)
                rec1[0] = len1
                struct.pack_into("<I", rec1, 2, 20)
                struct.pack_into("<I", rec1, 10, len(exe_content))
                rec1[25] = 0
                rec1[32] = len(name1)
                rec1[33 : 33 + len(name1)] = name1
                dir_sec[offset : offset + len1] = rec1
                offset += len1

                # 2. Entry for WA_MRG.MRG;1 at LBA 30
                name2 = b"WA_MRG.MRG;1"
                len2 = 33 + len(name2) + (1 if (33 + len(name2)) % 2 != 0 else 0)
                rec2 = bytearray(len2)
                rec2[0] = len2
                struct.pack_into("<I", rec2, 2, 30)
                struct.pack_into("<I", rec2, 10, len(wa_content))
                rec2[25] = 0
                rec2[32] = len(name2)
                rec2[33 : 33 + len(name2)] = name2
                dir_sec[offset : offset + len2] = rec2
                sec[0x18 : 0x18 + 2048] = dir_sec

            # Sectors 20..: SLUS_014.11 content
            elif 20 <= s < 20 + ((len(exe_content) + 2047) // 2048):
                idx = (s - 20) * 2048
                chunk = exe_content[idx : idx + 2048]
                sec[0x18 : 0x18 + len(chunk)] = chunk

            # Sector 30: WA_MRG.MRG content
            elif s == 30:
                sec[0x18 : 0x18 + len(wa_content)] = wa_content

            encode_mode2_form1_sector(sec)
            f.write(sec)


class TestSurgicalMerger(unittest.TestCase):
    def test_2_iso_merge_workflow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            express_path = os.path.join(tmpdir, "vanilla_express.bin")
            target_path = os.path.join(tmpdir, "custom_mod13.bin")
            output_path = os.path.join(tmpdir, "mod13_drop100.bin")

            # Executable for Vanilla Express: contains drop engine up to 0x2274 with drop count 100 at 0x21c0
            express_exe = bytearray(0x2300)
            express_exe[0:8] = b"PS-X EXE"
            express_exe[0x21c0] = 100

            # Executable for Target Mod: contains original vanilla
            target_exe = bytearray(0x2300)
            target_exe[0:8] = b"PS-X EXE"
            target_exe[0x21c0] = 1

            # Target Mod WA_MRG.MRG contains unique custom mod data
            target_wa_mrg = b"TARGET_MOD_CUSTOM_CARDS_DECKS_DROPS_" + b"Z" * 150
            express_wa_mrg = b"VANILLA_EXPRESS_STANDARD_DATA_______" + b"X" * 150

            # Generate both mock discs
            create_mock_ps1_disc(express_path, bytes(express_exe), express_wa_mrg)
            create_mock_ps1_disc(target_path, bytes(target_exe), target_wa_mrg)

            # Run merger with Drop x100
            result = YGOFMSurgicalMerger.merge(
                express_iso_path=express_path,
                target_mod_iso_path=target_path,
                output_iso_path=output_path,
                drop_multiplier=100
            )

            self.assertTrue(result.success, f"Merge failed: {result.message}")
            self.assertTrue(os.path.exists(output_path))
            self.assertTrue(os.path.exists(result.output_cue))

            # Inspect the generated output disc
            out_iso = PS1DiscImage(output_path)

            # 1. Verify executable has the Drop x100 patch at 0x21c0
            patched_exe = out_iso.extract_file("SLUS_014.11")
            self.assertEqual(patched_exe[0x21c0], 100, "Drop x100 was not properly set at 0x21c0!")

            # 2. Verify Target Mod's WA_MRG.MRG is preserved
            out_wa_mrg = out_iso.extract_file("WA_MRG.MRG")
            self.assertEqual(out_wa_mrg, target_wa_mrg, "Target Mod's WA_MRG.MRG was corrupted or replaced!")
            self.assertNotEqual(out_wa_mrg, express_wa_mrg)


if __name__ == "__main__":
    unittest.main()
