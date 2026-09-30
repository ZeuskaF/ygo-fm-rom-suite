"""
Tests for PS1 CD-ROM engine (EDC/ECC and ISO 9660 handling).
"""

import os
import sys
import unittest
import struct

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.cdrom import (
    compute_edc,
    generate_ecc,
    encode_mode2_form1_sector,
    PS1DiscImage
)

class TestCDROM(unittest.TestCase):
    def test_edc_calculation(self):
        # Known EDC test: empty 2056 bytes
        empty_data = bytes(0x808)
        edc = compute_edc(empty_data, len(empty_data))
        self.assertIsInstance(edc, int)
        self.assertTrue(0 <= edc <= 0xFFFFFFFF)

    def test_ecc_mode2_form1_encoding(self):
        # Create a blank Mode 2 Form 1 sector (2352 bytes)
        sector = bytearray(2352)
        # Sync pattern
        sector[0:12] = bytes([0x00] + [0xFF]*10 + [0x00])
        # Header (00:02:00, Mode 2)
        sector[12:16] = bytes([0x00, 0x02, 0x00, 0x02])
        # Subheader
        sector[16:24] = bytes([0x00, 0x00, 0x08, 0x00] * 2)
        # Fill user data with a known pattern
        for i in range(2048):
            sector[0x18 + i] = (i & 0xFF)

        # Encode sector
        encode_mode2_form1_sector(sector)

        # Verify EDC at 0x818 is non-zero
        edc_val = struct.unpack_from("<I", sector, 0x818)[0]
        self.assertNotEqual(edc_val, 0)

        # Verify P-parity (0x81C..0x8C7) and Q-parity (0x8C8..0x92F) are non-zero
        p_parity = sector[0x81C : 0x8C8]
        q_parity = sector[0x8C8 : 0x930]
        self.assertTrue(any(b != 0 for b in p_parity))
        self.assertTrue(any(b != 0 for b in q_parity))

    def test_mock_iso_extraction_and_injection(self):
        import tempfile
        # Create a mock 2352-byte PS1 ISO with 20 sectors
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp_path = tmp.name
            # Write 20 dummy sectors
            for s in range(25):
                sec = bytearray(2352)
                sec[0:12] = bytes([0x00] + [0xFF]*10 + [0x00])
                # Sector 16: PVD
                if s == 16:
                    pvd = bytearray(2048)
                    pvd[0] = 0x01
                    pvd[1:6] = b"CD001"
                    pvd[6] = 0x01
                    # Root dir record at offset 156
                    root_rec = bytearray(34)
                    root_rec[0] = 34  # length
                    struct.pack_into("<I", root_rec, 2, 18)   # Root dir at LBA 18
                    struct.pack_into("<I", root_rec, 10, 2048) # 1 sector dir
                    root_rec[25] = 0x02 # directory flag
                    pvd[156 : 156 + 34] = root_rec
                    sec[0x18 : 0x18 + 2048] = pvd
                elif s == 18:
                    # Root directory sector containing entry for SLUS_014.11
                    dir_sec = bytearray(2048)
                    # File record for SLUS_014.11;1
                    name = b"SLUS_014.11;1"
                    rec_len = 33 + len(name)
                    if rec_len % 2 != 0:
                        rec_len += 1
                    file_rec = bytearray(rec_len)
                    file_rec[0] = rec_len
                    struct.pack_into("<I", file_rec, 2, 20) # file at LBA 20
                    struct.pack_into("<I", file_rec, 10, 100) # size 100 bytes
                    file_rec[25] = 0 # regular file
                    file_rec[32] = len(name)
                    file_rec[33 : 33 + len(name)] = name
                    dir_sec[0 : rec_len] = file_rec
                    sec[0x18 : 0x18 + 2048] = dir_sec
                elif s == 20:
                    # File content sector (exactly 100 bytes)
                    sec[0x18 : 0x18 + 100] = b"ORIGINAL_EXE_CONTENT_" + b"A" * 79

                encode_mode2_form1_sector(sec)
                tmp.write(sec)

        try:
            iso = PS1DiscImage(tmp_path)
            self.assertIn("SLUS_014.11", iso.file_table)
            content = iso.extract_file("SLUS_014.11")
            self.assertTrue(content.startswith(b"ORIGINAL_EXE_CONTENT_"))

            # Test injection (exactly 100 bytes)
            new_content = b"MODIFIED_EXE_CONTENT_" + b"B" * 79
            iso.inject_file_in_place("SLUS_014.11", new_content)

            # Re-read and check
            iso2 = PS1DiscImage(tmp_path)
            updated = iso2.extract_file("SLUS_014.11")
            self.assertEqual(updated, new_content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == "__main__":
    unittest.main()
