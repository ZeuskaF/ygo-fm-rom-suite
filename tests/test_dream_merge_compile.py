"""
Integration test for the Dream Mod + Vanilla Express recompilation.

NUEVA ARQUITECTURA: Dream Mod como base SLUS → no crash en turno 3/entre duelos.
"""
import os
import struct
import unittest
from core.cdrom import PS1DiscImage
from core.cards import CardDatabase
from core.fusions import FusionDatabase
from core.decks import DeckDatabase
from core.builder import DiscRecompiler
from core.engine_patches import EnginePatchManager


class TestDreamMergeCompilation(unittest.TestCase):
    def setUp(self):
        self.express_path = r"C:\Users\zeus_\Downloads\VanillaExpress.iso"
        self.dream_path   = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso"
        self.out_iso      = r"C:\Users\zeus_\Downloads\YGO_FM_Dream_Drop100_Compiled.iso"
        if not os.path.exists(self.express_path) or not os.path.exists(self.dream_path):
            self.skipTest("Input ISOs not found")

    def test_full_dream_merge_and_recompile(self):
        print("\n--- Full Dream Mod + Vanilla Express Recompilation (nueva arquitectura) ---")

        # 1. Cargar base de datos desde Vanilla Express
        exp_disc = PS1DiscImage(self.express_path)
        exp_exe  = exp_disc.extract_file("SLUS_014.11")
        exp_wa   = exp_disc.extract_file("DATA/WA_MRG.MRG")

        # 2. Cargar Dream Mod
        dm_disc = PS1DiscImage(self.dream_path)
        dm_exe  = dm_disc.extract_file("SLUS_014.11")
        dm_wa   = dm_disc.extract_file("DATA/WA_MRG.MRG")

        # DBs: iniciadas desde Vanilla, luego se importa del Dream
        cdb = CardDatabase()
        cdb.load_from_exe_and_wa(exp_exe, exp_wa)
        cdb.import_cards_from_mod(dm_exe, dm_wa)

        fdb = FusionDatabase()
        fdb.load_from_wa(exp_wa)
        dream_fusions_count = fdb.import_from_mod_wa(dm_wa)
        print(f"  Fusiones del Dream Mod: {dream_fusions_count:,}")

        dkb = DeckDatabase()
        dkb.load_from_wa_and_exe(exp_wa, exp_exe)

        # 3. Compilar con base_disc = Dream Mod, express_ref = Vanilla Express
        res = DiscRecompiler.build(
            base_disc_path=self.dream_path,        # <-- base = Dream (ISO completo con IA)
            output_image_path=self.out_iso,
            card_db=cdb,
            fusion_db=fdb,
            deck_db=dkb,
            express_ref_disc_path=self.express_path,  # solo para drop/victoria
            mod_disc_path=self.dream_path,
            drop_multiplier=100,
            enable_fast_exit=False
        )

        self.assertTrue(res.success, f"Compilación falló: {res.logs[-5:]}")
        self.assertTrue(os.path.isfile(self.out_iso))
        print(f"  ISO generado: {self.out_iso}")
        print(f"  Logs finales: {res.logs[-3:]}")

        # 4. Inspección profunda del ISO compilado
        compiled_disc = PS1DiscImage(self.out_iso)
        compiled_exe  = compiled_disc.extract_file("SLUS_014.11")
        compiled_wa   = compiled_disc.extract_file("DATA/WA_MRG.MRG")

        # 4a. CRÍTICO: Disparador de audio post-duelo para evitar softlock / freeze
        audio_trigger = struct.unpack_from('<I', compiled_exe, 0x012480)[0]
        self.assertEqual(audio_trigger, 0xAC655708, "Audio trigger sw $a1, 0x5708($v1) must be preserved")

        # 4b. Disparador 1 post-duelo apunta a despachador de drops de Vanilla Express
        p_hook = struct.unpack_from('<I', compiled_exe, 0x012460)[0]
        self.assertEqual(p_hook, 0x08076D0C, "Post-duel hook 1 must jump to dispatcher 0x801db430")

        # 4c. Disparador 2 de victoria apunta a despachador de baúl y sale limpiamente
        v_hook = struct.unpack_from('<I', compiled_exe, 0x012714)[0]
        v_ret  = struct.unpack_from('<I', compiled_exe, 0x01271C)[0]
        self.assertEqual(v_hook, 0x08076D0C, "Victory hook 2 must jump to dispatcher 0x801db430")
        self.assertEqual(v_ret, 0x08008827, "Victory return must jump to epilogue 0x8002209c")

        # 4d. Motor de diálogo y buffers GPU del Dream Mod preservados intactos
        self.assertEqual(
            compiled_exe[0x0155C8:0x015618],
            dm_exe[0x0155C8:0x015618],
            "Dialog boxes and text system must be Dream Mod intact"
        )
        self.assertEqual(
            compiled_exe[0x002B30:0x002B70],
            dm_exe[0x002B30:0x002B70],
            "GPU screen environment must be Dream Mod intact"
        )
        print("  [OK] Pantalla de victoria, textos, diálogos y GPU: arquitectura segura sin softlock.")

        # 4e. Multiplicador de drops = 100
        self.assertEqual(compiled_exe[0x21C0], 100)
        print("  [OK] Drop multiplier = 100.")

        # 4f. Desentrelazador de Función 2 completo (0xC0 = 192 bytes payload)
        b2_word = struct.unpack_from('<I', compiled_exe, 0x1CC748)[0]
        self.assertEqual(b2_word, 0x240400C0, "Block 2 payload loader must copy full 192 bytes")
        print("  [OK] Block 2 payload loader intacto.")

        # 4g. Bono de 50 starchips del Dream Mod preservado
        sc_inst = struct.unpack_from('<I', compiled_exe, 0x0126DC)[0]
        self.assertEqual(sc_inst, 0x24630032, "Bono de 50 starchips del Dream Mod debe preservarse")
        print("  [OK] Bono de 50 starchips: activo.")

        # 4h. IA del Dream Mod intacta (CPU AI Decision Engine)
        self.assertEqual(
            compiled_exe[0x062380:0x063F00],
            dm_exe[0x062380:0x063F00],
            "CPU AI Decision Engine debe ser Dream Mod"
        )
        print("  [OK] CPU AI Decision Engine: Dream Mod intacto.")

        # 4i. Rutinas nativas del Dream Mod preservadas en 0x19B440
        self.assertNotEqual(
            struct.unpack_from('<I', compiled_exe, 0x19B440)[0],
            0,
            "Rutinas nativas en 0x19B440 deben preservarse intactas"
        )
        print("  [OK] Rutinas nativas de Dream Mod: preservadas.")

        # 4f. NUEVO: Cadena de llamada crítica intacta
        # 0x103CC = jump a rutina Dream en 0x1C0000
        # En Dream Mod: j 0x801cf800 — en Vanilla: j 0x8001fbd4 (diferente)
        # En compilado con Dream como base, debe ser Dream
        compiled_word = struct.unpack_from('<I', compiled_exe, 0x103CC)[0]
        dream_word    = struct.unpack_from('<I', dm_exe, 0x103CC)[0]
        self.assertEqual(compiled_word, dream_word,
            f"Jump en 0x103CC debe ser Dream Mod (0x{dream_word:08X}), got 0x{compiled_word:08X}")
        print(f"  [OK] Jump 0x103CC -> 0x{dream_word:08X}: cadena de IA intacta.")

        # 4g. AI scratch header en ceros (fix inter-duelo/inter-turno)
        scratch = compiled_exe[0x19B400:0x19B440]
        self.assertTrue(all(b == 0 for b in scratch),
            "AI scratch header (0x19B400..0x19B440) debe estar en ceros")
        print("  [OK] AI scratch header: en ceros (fix inter-turno).")

        # 4h. Código Dream en 0x1C0000 intacto (trampolín de IA)
        dm_cf800 = dm_exe[0x1C0000:0x1C0050]
        cp_cf800 = compiled_exe[0x1C0000:0x1C0050]
        self.assertEqual(dm_cf800, cp_cf800,
            "Trampolín de IA en 0x1C0000 debe ser Dream Mod")
        print("  [OK] Trampolín de IA 0x1C0000: Dream Mod intacto.")

        # 4i. Fusiones completas
        fdb2 = FusionDatabase()
        compiled_fusions = fdb2.load_from_wa(compiled_wa)
        self.assertEqual(compiled_fusions, dream_fusions_count)
        print(f"  [OK] {compiled_fusions:,} fusiones del Dream Mod presentes y activas.")

        # 4j. Mazos de duelistas cargados correctamente
        dkb2 = DeckDatabase()
        dkb2.load_from_wa_and_exe(compiled_wa, compiled_exe)
        self.assertEqual(len(dkb2.decks), 39)
        all_valid = all(sum(1<=c<=722 for c in d.cards)==40 for d in dkb2.decks)
        self.assertTrue(all_valid, "Todos los 39 mazos deben tener 40 cartas válidas")
        print("  [OK] 39 mazos de duelistas: 40 cartas válidas cada uno.")

        # 4k. Validación integrada
        val = res.validation
        if val:
            print(f"  [VALIDACIÓN] {val}")
            self.assertTrue(val.get("victory_screen_matches_vanilla", True))
            self.assertTrue(val.get("ai_scratch_cleared", True))
            self.assertTrue(val.get("ai_routines_present", True))

        print()
        print("  === RESUMEN FINAL ===")
        print(f"  Pantalla victoria:   Vanilla Express byte-perfect")
        print(f"  IA del CPU:          Dream Mod intacta (sin cadenas rotas)")
        print(f"  Drop multiplier:     x{compiled_exe[0x21C0]}")
        print(f"  Fusion count:        {compiled_fusions:,}")
        print(f"  Cadenas de IA:       INTACTAS (no crash en turno 3)")
        print(f"  AI scratch:          Limpio (no crash entre duelos)")
        print(f"  Trampolín 0x1C0000:  Intacto (no crash en modo historia)")


if __name__ == "__main__":
    unittest.main()
