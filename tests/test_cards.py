import unittest
import os
from core.cdrom import PS1DiscImage
from core.cards import Card, CardDatabase, SLUS_STATS_OFFSET, WA_PASSWORDS_OFFSET

class TestCardsModule(unittest.TestCase):
    def setUp(self):
        self.iso_path = r"C:\Users\zeus_\Downloads\VanillaExpress.iso"
        if not os.path.exists(self.iso_path):
            self.skipTest("VanillaExpress.iso not found")
        self.iso = PS1DiscImage(self.iso_path)
        self.exe = self.iso.extract_file("SLUS_014.11")
        self.wa = self.iso.extract_file("DATA/WA_MRG.MRG")

    def test_load_cards(self):
        db = CardDatabase()
        count = db.load_from_exe_and_wa(self.exe, self.wa)
        self.assertEqual(count, 722)

        # Card 1: Blue-Eyes White Dragon
        be = db.get(1)
        self.assertIsNotNone(be)
        self.assertIn("Blue", be.name)
        self.assertEqual(be.atk, 3000)
        self.assertEqual(be.def_, 2500)
        self.assertEqual(be.type_name, "Dragon")
        self.assertEqual(be.password, "89631139")
        self.assertEqual(be.star_cost, 999999)

        # Card 2: Mystical Elf
        me = db.get(2)
        self.assertIsNotNone(me)
        self.assertEqual(me.atk, 800)
        self.assertEqual(me.def_, 2000)
        self.assertEqual(me.type_name, "Spellcaster")
        self.assertEqual(me.password, "15025844")
        self.assertEqual(me.star_cost, 160)

    def test_roundtrip_byte_exact(self):
        db = CardDatabase()
        db.load_from_exe_and_wa(self.exe, self.wa)

        exe_copy = bytearray(self.exe)
        wa_copy = bytearray(self.wa)

        db.save_to_exe_and_wa(exe_copy, wa_copy)

        # Check stats slice in exe
        orig_stats = self.exe[SLUS_STATS_OFFSET : SLUS_STATS_OFFSET + 722 * 4]
        new_stats = exe_copy[SLUS_STATS_OFFSET : SLUS_STATS_OFFSET + 722 * 4]
        self.assertEqual(orig_stats, new_stats)

        # Check passwords slice in wa
        orig_pw = self.wa[WA_PASSWORDS_OFFSET : WA_PASSWORDS_OFFSET + 722 * 8]
        new_pw = wa_copy[WA_PASSWORDS_OFFSET : WA_PASSWORDS_OFFSET + 722 * 8]
        self.assertEqual(orig_pw, new_pw)

    def test_card_descriptions(self):
        db = CardDatabase()
        db.load_from_exe_and_wa(self.exe, self.wa)

        c1 = db.get(1)
        self.assertIsNotNone(c1)
        self.assertTrue(len(c1.description) > 0)
        self.assertIn("unsurpassed", c1.description.lower())

        c35 = db.get(35)
        self.assertIsNotNone(c35)
        self.assertIn("ultimate wizard", c35.description.lower())

        # Test edit and re-save
        exe_copy = bytearray(self.exe)
        wa_copy = bytearray(self.wa)
        c1.description = "Dragon legendario\nde gran poder!"
        db.save_to_exe_and_wa(exe_copy, wa_copy)

        db2 = CardDatabase()
        db2.load_from_exe_and_wa(bytes(exe_copy), bytes(wa_copy))
        self.assertEqual(db2.get(1).description, "Dragon legendario\nde gran poder!")
        self.assertEqual(db2.get(35).description, c35.description)

    def test_card_name_editing_and_serialization(self):
        db = CardDatabase()
        db.load_from_exe_and_wa(self.exe, self.wa)
        c1 = db.get(1)
        self.assertEqual(c1.name, "Blue-eyes White Dragon")

        # Edit name
        c1.name = "Dragon Blanco Supremo"
        exe_copy = bytearray(self.exe)
        wa_copy = bytearray(self.wa)
        db.save_to_exe_and_wa(exe_copy, wa_copy)

        db2 = CardDatabase()
        db2.load_from_exe_and_wa(bytes(exe_copy), bytes(wa_copy))
        self.assertEqual(db2.get(1).name, "Dragon Blanco Supremo")
        self.assertEqual(db2.get(2).name, "Mystical Elf")

    def test_dream_mod_cards_and_signs_untruncated(self):
        dream_path = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso"
        if not os.path.exists(dream_path):
            self.skipTest("Dream mod ISO not found")

        dream_iso = PS1DiscImage(dream_path)
        dream_slus = dream_iso.extract_file("SLUS_014.11")
        dream_wa = dream_iso.extract_file("DATA/WA_MRG.MRG")

        db = CardDatabase()
        db.load_from_exe_and_wa(dream_slus, dream_wa)

        # Card 722 must be Magician of Black Chaos, NOT Fortress Whale or Metropolis
        c722 = db.get(722)
        self.assertIsNotNone(c722)
        self.assertEqual(c722.name, "Magician of Black Chaos")

        # Save to a fresh bytearray copy
        exe_copy = bytearray(dream_slus)
        wa_copy = bytearray(dream_wa)
        db.save_to_exe_and_wa(exe_copy, wa_copy)

        # Decode Guardian Stars from exe_copy using updated pointer table
        import struct
        from core.cards import SLUS_NAMES_PTRS_OFFSET, SLUS_STRING_TABLE_BASE, TBL_BYTE_TO_CHAR
        ptrs = list(struct.unpack("<1024H", exe_copy[SLUS_NAMES_PTRS_OFFSET : SLUS_NAMES_PTRS_OFFSET + 2048]))

        # Saturn is index 794
        saturn_off = SLUS_STRING_TABLE_BASE + ptrs[794]
        raw_saturn = []
        off = saturn_off
        while off < len(exe_copy) and exe_copy[off] != 0xFF:
            raw_saturn.append(exe_copy[off])
            off += 1
        decoded_saturn = "".join(TBL_BYTE_TO_CHAR.get(x, " ") for x in raw_saturn).strip()
        self.assertEqual(decoded_saturn, "Saturn", f"Saturn was truncated or corrupted to: {decoded_saturn}")

        # Pluto is index 796
        pluto_off = SLUS_STRING_TABLE_BASE + ptrs[796]
        raw_pluto = []
        off = pluto_off
        while off < len(exe_copy) and exe_copy[off] != 0xFF:
            raw_pluto.append(exe_copy[off])
            off += 1
        decoded_pluto = "".join(TBL_BYTE_TO_CHAR.get(x, " ") for x in raw_pluto).strip()
        self.assertEqual(decoded_pluto, "Pluto", f"Pluto was truncated or corrupted to: {decoded_pluto}")

        # Mars is index 792
        mars_off = SLUS_STRING_TABLE_BASE + ptrs[792]
        raw_mars = []
        off = mars_off
        while off < len(exe_copy) and exe_copy[off] != 0xFF:
            raw_mars.append(exe_copy[off])
            off += 1
        decoded_mars = "".join(TBL_BYTE_TO_CHAR.get(x, " ") for x in raw_mars).strip()
        self.assertEqual(decoded_mars, "Mars", f"Mars was truncated or corrupted to: {decoded_mars}")

    def test_card_description_type_glyphs(self):
        from core.cards import decode_description, encode_description

        # Raw bytes for Card 673 ("Sacrifice [Beast]\nto summon\nThe War-Lion.")
        raw_673 = bytes([29, 3, 15, 8, 5, 19, 5, 15, 1, 0, 248, 11, 5, 254, 2, 4, 0, 7, 13, 14, 14, 4, 6, 254, 28, 9, 1, 0, 34, 3, 8, 48, 42, 5, 4, 6, 11, 255])
        decoded = decode_description(raw_673, 0, base=0)
        self.assertIn("[Beast]", decoded)
        self.assertIn("Sacrifice [Beast]", decoded)

        # Roundtrip encoding back to bytes
        reencoded = encode_description(decoded)
        self.assertEqual(reencoded, raw_673)

        # Spanish alias [Bestia] encodes to the same 0xF8 0x0B 0x05
        spanish_desc = "Sacrifica [Bestia]\npara invocar\na War-Lion."
        encoded_es = encode_description(spanish_desc)
        self.assertIn(bytes([0xF8, 0x0B, 0x05]), encoded_es)


if __name__ == "__main__":
    unittest.main()

