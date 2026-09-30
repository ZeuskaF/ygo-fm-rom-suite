import unittest
import os
import tempfile
import struct
from core.cdrom import PS1DiscImage
from core.cards import CardDatabase
from core.fusions import FusionDatabase
from core.decks import DeckDatabase, DECK_TABLE_BASE, ARENA_STRIDE, DECK_ENTRY_SIZE, NUM_ARENAS
from core.builder import DiscRecompiler

class TestBuilderModule(unittest.TestCase):
    def setUp(self):
        self.express_path = r"C:\Users\zeus_\Downloads\VanillaExpress.iso"
        if not os.path.exists(self.express_path):
            self.skipTest("VanillaExpress.iso not found")

    def test_recompile_cycle(self):
        temp_dir = tempfile.mkdtemp()
        output_iso = os.path.join(temp_dir, "CompiledTest.iso")

        # 1. Load base databases
        iso = PS1DiscImage(self.express_path)
        exe = iso.extract_file("SLUS_014.11")
        wa = iso.extract_file("DATA/WA_MRG.MRG")

        cdb = CardDatabase()
        cdb.load_from_exe_and_wa(exe, wa)

        fdb = FusionDatabase()
        fdb.load_from_wa(wa)

        # 2. Modify one card stat (e.g. Card 1 Blue-Eyes ATK = 3500)
        be = cdb.get(1)
        be.atk = 3500

        # 3. Build new ISO
        res = DiscRecompiler.build(
            base_disc_path=self.express_path,
            output_image_path=output_iso,
            card_db=cdb,
            fusion_db=fdb,
            drop_multiplier=100,
            enable_fast_exit=True
        )

        self.assertTrue(res.success)
        self.assertTrue(os.path.exists(output_iso))
        self.assertTrue(os.path.exists(res.output_cue))

        # 4. Verify rebuilt ISO
        new_disc = PS1DiscImage(output_iso)
        new_exe = new_disc.extract_file("SLUS_014.11")
        new_wa = new_disc.extract_file("DATA/WA_MRG.MRG")

        new_cdb = CardDatabase()
        new_cdb.load_from_exe_and_wa(new_exe, new_wa)

        reloaded_be = new_cdb.get(1)
        self.assertEqual(reloaded_be.atk, 3500)

        # Cleanup
        try:
            if os.path.exists(output_iso):
                os.remove(output_iso)
            if res.output_bin and os.path.exists(res.output_bin):
                os.remove(res.output_bin)
            if res.output_cue and os.path.exists(res.output_cue):
                os.remove(res.output_cue)
            os.rmdir(temp_dir)
        except Exception:
            pass

    def test_deck_and_difficulty_preservation(self):
        temp_dir = tempfile.mkdtemp()
        output_iso = os.path.join(temp_dir, "CompiledDecksTest.iso")

        iso = PS1DiscImage(self.express_path)
        exe = iso.extract_file("SLUS_014.11")
        wa = iso.extract_file("DATA/WA_MRG.MRG")

        cdb = CardDatabase()
        cdb.load_from_exe_and_wa(exe, wa)

        fdb = FusionDatabase()
        fdb.load_from_wa(wa)

        deck_db = DeckDatabase()
        deck_db.load_from_wa_and_exe(wa, exe)

        # Modify Simon Muran (Duelist 1): card 0 = 722, difficulty = 85
        simon = deck_db.get(1)
        self.assertIsNotNone(simon)
        simon.cards[0] = 722
        simon.difficulty = 85

        # Modify Nitemare (Duelist 39): card 39 = 1, difficulty = 99
        nitemare = deck_db.get(39)
        self.assertIsNotNone(nitemare)
        nitemare.cards[39] = 1
        nitemare.difficulty = 99

        # Build ISO
        res = DiscRecompiler.build(
            base_disc_path=self.express_path,
            output_image_path=output_iso,
            card_db=cdb,
            fusion_db=fdb,
            deck_db=deck_db,
            drop_multiplier=100
        )

        self.assertTrue(res.success)

        # Verify rebuilt ISO
        new_disc = PS1DiscImage(output_iso)
        new_exe = new_disc.extract_file("SLUS_014.11")
        new_wa = new_disc.extract_file("DATA/WA_MRG.MRG")

        reloaded_decks = DeckDatabase()
        reloaded_decks.load_from_wa_and_exe(new_wa, new_exe)

        reloaded_simon = reloaded_decks.get(1)
        self.assertEqual(reloaded_simon.cards[0], 722)
        self.assertEqual(reloaded_simon.difficulty, 85)

        reloaded_nitemare = reloaded_decks.get(39)
        self.assertEqual(reloaded_nitemare.cards[39], 1)
        self.assertEqual(reloaded_nitemare.difficulty, 99)

        # Verify all 7 arenas in WA_MRG have the exact same deck
        for arena in range(NUM_ARENAS):
            arena_base = DECK_TABLE_BASE + arena * ARENA_STRIDE
            card_0_simon = struct.unpack_from('<H', new_wa, arena_base)[0]
            self.assertEqual(card_0_simon, 722, f"Arena {arena} duelist 1 card 0 mismatch")
            card_39_nitemare = struct.unpack_from('<H', new_wa, arena_base + 38 * DECK_ENTRY_SIZE + 39 * 2)[0]
            self.assertEqual(card_39_nitemare, 1, f"Arena {arena} duelist 39 card 39 mismatch")

        # Cleanup
        try:
            if os.path.exists(output_iso):
                os.remove(output_iso)
            if res.output_bin and os.path.exists(res.output_bin):
                os.remove(res.output_bin)
            if res.output_cue and os.path.exists(res.output_cue):
                os.remove(res.output_cue)
            os.rmdir(temp_dir)
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()
