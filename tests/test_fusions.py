import unittest
import os
from core.cdrom import PS1DiscImage
from core.fusions import FusionDatabase, WA_FUSION_ARENA_BASE, WA_ARENA_STEP, FUSION_TABLE_SIZE, NUM_ARENAS

class TestFusionsModule(unittest.TestCase):
    def setUp(self):
        self.express_path = r"C:\Users\zeus_\Downloads\VanillaExpress.iso"
        self.dream_path = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso"
        if not os.path.exists(self.express_path):
            self.skipTest("VanillaExpress.iso not found")
        self.iso = PS1DiscImage(self.express_path)
        self.wa = self.iso.extract_file("DATA/WA_MRG.MRG")

    def test_load_fusions(self):
        fdb = FusionDatabase()
        count = fdb.load_from_wa(self.wa)
        self.assertGreater(count, 1000)

        # Check Baby Dragon fusions
        baby_fusions = fdb.get_fusions_for_card(4)
        self.assertGreater(len(baby_fusions), 0)

    def test_save_all_7_arenas_synchronized(self):
        fdb = FusionDatabase()
        fdb.load_from_wa(self.wa)

        wa_copy = bytearray(self.wa)
        fdb.save_to_wa(wa_copy)

        # Verify all 7 arenas have identical bytes to arena 0
        arena0 = wa_copy[WA_FUSION_ARENA_BASE : WA_FUSION_ARENA_BASE + FUSION_TABLE_SIZE]
        for a in range(1, NUM_ARENAS):
            off = WA_FUSION_ARENA_BASE + a * WA_ARENA_STEP
            arena_k = wa_copy[off : off + FUSION_TABLE_SIZE]
            self.assertEqual(arena0, arena_k, f"Arena {a} does not match Arena 0")

    def test_import_from_dream_mod(self):
        if not os.path.exists(self.dream_path):
            self.skipTest("Dream mod ISO not found")

        dream_iso = PS1DiscImage(self.dream_path)
        dream_wa = dream_iso.extract_file("DATA/WA_MRG.MRG")

        fdb = FusionDatabase()
        orig_count = fdb.load_from_wa(self.wa)
        dream_count = fdb.import_from_mod_wa(dream_wa)

        self.assertGreater(dream_count, 1000)
        # Check that Dream Mod fusions are distinct or loaded properly
        self.assertEqual(len(fdb.raw_table), FUSION_TABLE_SIZE)

    def test_modify_fusion(self):
        fdb = FusionDatabase()
        fdb.load_from_wa(self.wa)
        pair = list(fdb.fusions.keys())[0]
        fdb.modify_fusion(pair[0], pair[1], 722)
        fdb._parse_fusions()
        self.assertEqual(fdb.fusions.get(pair), 722)

    def test_add_fusion_odd_card(self):
        fdb = FusionDatabase()
        fdb.load_from_wa(self.wa)
        # Card 1 has odd fusion count in Vanilla
        fdb.delete_fusion(1, 700)
        ok = fdb.add_fusion(1, 700, 713)
        self.assertTrue(ok)
        fdb._parse_fusions()
        self.assertEqual(fdb.fusions.get((1, 700)), 713)

    def test_add_fusion_even_card_gap_relocation(self):
        fdb = FusionDatabase()
        fdb.load_from_wa(self.wa)
        # Card 3 has 10 fusions (even count) in Vanilla and relocates safely into table gap
        ok = fdb.add_fusion(3, 701, 714)
        self.assertTrue(ok)
        fdb._parse_fusions()
        self.assertEqual(fdb.fusions.get((3, 701)), 714)

    def test_delete_and_reuse_slot(self):
        fdb = FusionDatabase()
        fdb.load_from_wa(self.wa)
        # Delete existing fusion (Card 2 + Card 8 -> 638)
        self.assertIn((2, 8), fdb.fusions)
        ok_del = fdb.delete_fusion(2, 8)
        self.assertTrue(ok_del)
        fdb._parse_fusions()
        self.assertNotIn((2, 8), fdb.fusions)

        # Reuse the deleted slot without needing extra gap allocation
        ok = fdb.add_fusion(2, 701, 715)
        self.assertTrue(ok)
        fdb._parse_fusions()
        self.assertEqual(fdb.fusions.get((2, 701)), 715)

    def test_bidirectional_fusion_registration(self):
        fdb = FusionDatabase()
        fdb.load_from_wa(self.wa)

        # Add a new fusion between Card 1 (Blue-Eyes) and Card 2 (Mystical Elf) -> 722
        ok = fdb.add_fusion(1, 2, 722)
        self.assertTrue(ok)

        # Database cache supports querying both orders
        self.assertEqual(fdb.get_result(1, 2), 722)
        self.assertEqual(fdb.get_result(2, 1), 722)

        # Inspect host Card 1 (min(1, 2)) in raw_table directly
        import struct
        def get_host_partners(host):
            p = struct.unpack_from('<H', fdb.raw_table, host * 2)[0]
            if p == 0:
                return {}
            h = fdb.raw_table[p]
            cnt = (511 - fdb.raw_table[p+1]) if h == 0 else h
            pos = p + (2 if h == 0 else 1)
            res = {}
            while cnt > 0 and pos + 5 <= len(fdb.raw_table):
                b0, b1, b2, b3, b4 = fdb.raw_table[pos : pos + 5]
                p1 = ((b0 & 0x03) << 8) | b1
                r1 = (((b0 >> 2) & 0x03) << 8) | b2
                if p1 != 0:
                    res[p1] = r1
                cnt -= 1
                if cnt > 0:
                    p2 = (((b0 >> 4) & 0x03) << 8) | b3
                    r2 = (((b0 >> 6) & 0x03) << 8) | b4
                    if p2 != 0:
                        res[p2] = r2
                    cnt -= 1
                pos += 5
            return res

        card1_partners = get_host_partners(1)
        self.assertIn(2, card1_partners, "Card 1's list does not contain partner 2")
        self.assertEqual(card1_partners[2], 722)

        # MIPS CPU in-game engine simulation (SLUS_014.11 at 0x80019a60)
        # Guarantees that whether played as Card 1 first or Card 2 first, the result is 722
        def mips_lookup(table, c1, c2):
            a0 = min(c1, c2)
            a1 = max(c1, c2)
            ptr = struct.unpack_from('<H', table, a0 * 2)[0]
            if ptr == 0 or ptr >= len(table):
                return 0
            pos = ptr
            t0 = table[pos]
            pos += 1
            if t0 == 0:
                if pos >= len(table):
                    return 0
                t0 = 511 - table[pos]
                pos += 1
            a3 = pos + 3
            while True:
                if pos + 5 > len(table):
                    return 0
                a2 = table[pos]
                v1 = table[a3 - 2]
                v0 = ((a2 & 0x03) << 8) | v1
                if v0 == a1:
                    return (((a2 >> 2) & 0x03) << 8) | table[pos + 2]
                v1 = table[a3]
                v0 = (((a2 >> 4) & 0x03) << 8) | v1
                if v0 == a1:
                    return (((a2 >> 6) & 0x03) << 8) | table[pos + 4]
                a3 += 5
                t0 -= 2
                if t0 <= 0:
                    return 0
                pos += 5

        self.assertEqual(mips_lookup(fdb.raw_table, 1, 2), 722)
        self.assertEqual(mips_lookup(fdb.raw_table, 2, 1), 722)
        # Check classic fusions still work
        self.assertEqual(mips_lookup(fdb.raw_table, 4, 6), 31)
        self.assertEqual(mips_lookup(fdb.raw_table, 6, 4), 31)


if __name__ == "__main__":
    unittest.main()


