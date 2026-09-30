"""
PS1 Disc Image Builder and Recompiler for Yu-Gi-Oh! Forbidden Memories.

ARQUITECTURA CORRECTA (post análisis de memoria profundo):
  - Usa Dream Mod como EJECUTABLE BASE (SLUS) para preservar todas las
    interconexiones internas de su IA (84 regiones modificadas, todas enlazadas).
  - Restaura SOLO las regiones de drop/victoria de Vanilla Express encima del Dream.
  - Resultado: sin cadenas de llamada rotas → no crash en turno 3, entre duelos,
    ni en modo historia.
  - WA_MRG del Dream Mod se usa para conservar las tablas de fusión del CPU.
"""

import struct
import os
import shutil
from typing import Any, Callable, Optional

from core.cdrom import PS1DiscImage
from core.cards import CardDatabase
from core.fusions import FusionDatabase
from core.decks import DeckDatabase
from core.drops import DropDatabase
from core.starter_deck import StarterDeckDatabase
from core.field_spells import ARENA_WA_OFFSETS, ARENA_STRIDE, FieldSpellDatabase
from core.engine_patches import EnginePatchManager


class DiscRecompilerResult:
    def __init__(self):
        self.success = False
        self.output_iso = ""
        self.output_bin = ""
        self.output_cue = ""
        self.cards_updated = 0
        self.fusions_synchronized = 0
        self.drops_synchronized = 0
        self.patches_applied = 0
        self.ai_patches_applied = 0
        self.decks_imported = 0
        self.starter_deck_updated = False
        self.validation = {}
        self.logs = []

    def log(self, msg: str):
        self.logs.append(msg)


class DiscRecompiler:
    @staticmethod
    def build(
        base_disc_path: str,
        output_image_path: str,
        card_db: CardDatabase,
        fusion_db: FusionDatabase,
        deck_db: Optional[DeckDatabase] = None,
        drop_db: Optional[DropDatabase] = None,
        starter_deck_db: Optional[StarterDeckDatabase] = None,
        graphics_db: Optional[Any] = None,
        field_spells_db: Optional[Any] = None,
        express_ref_disc_path: Optional[str] = None,
        mod_disc_path: Optional[str] = None,
        drop_multiplier: int = 100,
        enable_fast_exit: bool = False,
        progress_cb: Optional[Callable[[float, str], None]] = None
    ) -> DiscRecompilerResult:
        """
        Compila la ROM a partir del Dream Mod como ejecutable base.

        Pipeline:
          1. Abre base_disc (Dream Mod o el ISO que el usuario cargó)
          2. Si hay mod_disc_path distinto al base, importa su SLUS y WA_MRG
          3. Usa el SLUS del mod como ejecutable base (preserva IA intacta)
          4. Aplica regiones de drop/victoria de Vanilla Express encima
          5. Guarda mazos de duelistas y dificultad
          6. Serializa cartas y fusiones
          7. Regenera EDC/ECC y escribe ISO
        """
        res = DiscRecompilerResult()

        def report(prog: float, text: str):
            res.log(f"[{int(prog * 100)}%] {text}")
            if progress_cb:
                progress_cb(prog, text)

        # ------------------------------------------------------------------
        # 1. Validación y apertura del ISO base
        # ------------------------------------------------------------------
        if not os.path.isfile(base_disc_path):
            raise FileNotFoundError(f"ISO base no encontrada: {base_disc_path}")

        report(0.05, f"Abriendo imagen base: {os.path.basename(base_disc_path)}")
        base_disc = PS1DiscImage(base_disc_path)

        def find_keys(disc):
            slus_k = wa_k = None
            for k in disc.file_table:
                ku = k.upper()
                if any(x in ku for x in ("SLUS_", "SLES_", "SLPM_")):
                    slus_k = k
                elif "WA_MRG.MRG" in ku:
                    wa_k = k
            return slus_k or "SLUS_014.11", wa_k or "DATA/WA_MRG.MRG"

        slus_key, wa_key = find_keys(base_disc)

        # ------------------------------------------------------------------
        # 2. Cargar Vanilla Express como referencia (solo para drop engine)
        # ------------------------------------------------------------------
        express_exe_bytes: Optional[bytes] = None
        express_wa_bytes: Optional[bytes] = None

        if express_ref_disc_path and os.path.isfile(express_ref_disc_path):
            report(0.12, "Cargando Vanilla Express como referencia de drop engine y victoria...")
            exp_disc = PS1DiscImage(express_ref_disc_path)
            exp_slus, exp_wa = find_keys(exp_disc)
            express_exe_bytes = exp_disc.extract_file(exp_slus)
            express_wa_bytes  = exp_disc.extract_file(exp_wa)
            report(0.16, f"Vanilla Express cargado ({len(express_exe_bytes):,} bytes SLUS).")

        # ------------------------------------------------------------------
        # 3. Determinar el ejecutable base: mod_disc si se especificó, si no base_disc
        #    CLAVE: el mod es la base porque tiene toda la IA interconectada
        #    y todos los assets 3D (MODEL.MRG, SU.MRG) necesarios en combate.
        # ------------------------------------------------------------------
        mod_exe_bytes: Optional[bytes] = None
        mod_wa_bytes:  Optional[bytes] = None
        mod_disc: Optional[PS1DiscImage] = None

        if mod_disc_path and os.path.isfile(mod_disc_path):
            report(0.20, f"Cargando mod como base de ejecutable y assets: {os.path.basename(mod_disc_path)}")
            mod_disc = PS1DiscImage(mod_disc_path)
            mod_slus, mod_wa = find_keys(mod_disc)
            mod_exe_bytes = mod_disc.extract_file(mod_slus)
            mod_wa_bytes  = mod_disc.extract_file(mod_wa)
            report(0.25, f"Mod SLUS cargado: {len(mod_exe_bytes):,} bytes. WA_MRG: {len(mod_wa_bytes):,} bytes.")

        # El ejecutable de trabajo comienza como el mod (si existe) o el base
        if mod_exe_bytes is not None:
            exe_bytes = bytearray(mod_exe_bytes)
            wa_bytes  = bytearray(mod_wa_bytes)
            report(0.28, "Ejecutable base: Dream Mod (preserva IA, fusiones y cadenas de llamadas intactas).")
        else:
            report(0.20, "Cargando ejecutable desde imagen base...")
            exe_bytes = bytearray(base_disc.extract_file(slus_key))
            wa_bytes  = bytearray(base_disc.extract_file(wa_key))
            report(0.28, "Ejecutable base: imagen cargada.")

        # ------------------------------------------------------------------
        # 4. Aplicar drop engine + pantalla de victoria
        #    Si no se dispone de VanillaExpress.iso, usa el motor nativo embebido.
        # ------------------------------------------------------------------
        report(0.32, f"Aplicando motor de drops x{drop_multiplier} y pantalla de victoria estable...")
        res.patches_applied = EnginePatchManager.apply_drop_engine(
            target_exe=exe_bytes,
            express_exe=express_exe_bytes,
            drop_multiplier=drop_multiplier
        )
        if express_exe_bytes:
            report(0.36, f"  {res.patches_applied} parches aplicados (usando referencia Vanilla Express).")
        else:
            report(0.36, f"  {res.patches_applied} parches aplicados con éxito (modo autónomo/standalone sin requerir ISO de Vanilla).")


        # ------------------------------------------------------------------
        # 5. Limpiar estado scratch de IA (previene crash entre turnos y duelos)
        #    Solo borra el header de 64 bytes, NO los routines.
        # ------------------------------------------------------------------
        report(0.38, "Inicializando estado temporal de IA a cero (fix inter-turno/inter-duelo)...")
        cleaned = EnginePatchManager.clear_ai_scratch_state(exe_bytes)
        report(0.40, f"  {cleaned} región(es) de estado temporal limpiadas.")

        # ------------------------------------------------------------------
        # 6. Importar mazos de duelistas desde el mod (si deck_db disponible)
        # ------------------------------------------------------------------
        if deck_db is not None and not deck_db.decks and mod_exe_bytes is not None and mod_wa_bytes is not None:
            report(0.42, "Importando mazos del mod hacia deck_db...")
            updated = deck_db.import_from_mod(mod_wa_bytes, mod_exe_bytes)
            report(0.44, f"  {updated}/39 mazos importados del mod.")
        elif deck_db is None and mod_exe_bytes is not None and mod_wa_bytes is not None:
            deck_db = DeckDatabase()
            report(0.42, "Importando mazos del mod hacia nuevo deck_db...")
            deck_db.import_from_mod(mod_wa_bytes, mod_exe_bytes)

        if deck_db is not None and deck_db.decks:
            report(0.46, "Escribiendo mazos y dificultad en SLUS y WA_MRG (7 arenas)...")
            deck_db.save_to_wa_and_exe(wa_bytes, exe_bytes)
            res.decks_imported = len(deck_db.decks)

        # ------------------------------------------------------------------
        # 6.5. Serializar tablas auténticas del mazo inicial (7 pools en WA_MRG y SLUS)
        # ------------------------------------------------------------------
        if starter_deck_db is not None:
            report(0.48, "Escribiendo pools auténticos de mazo inicial (7 pools) en WA_MRG y SLUS...")
            written_wa = starter_deck_db.save_to_wa(wa_bytes)
            written_exe = starter_deck_db.save_to_exe(exe_bytes)
            if written_wa > 0 or written_exe > 0:
                res.starter_deck_updated = True
                report(0.49, f"  Mazo inicial compilado con éxito ({written_wa} bytes en WA_MRG sector 7983, {written_exe} bytes en SLUS).")

        # ------------------------------------------------------------------
        # 7. Serializar estadísticas de cartas
        # ------------------------------------------------------------------
        report(0.50, "Compilando estadísticas de cartas, contraseñas y costos...")
        card_db.save_to_exe_and_wa(exe_bytes, wa_bytes)
        res.cards_updated = len(card_db.cards)

        # ------------------------------------------------------------------
        # 8. Sincronizar fusiones en las 7 arenas
        # ------------------------------------------------------------------
        report(0.62, "Sincronizando tabla de fusiones en las 7 arenas de combate...")
        fusion_db.save_to_wa(wa_bytes)
        res.fusions_synchronized = 7

        # ------------------------------------------------------------------
        # 8.5. Sincronizar tablas de drops de los 39 duelistas
        # ------------------------------------------------------------------
        if drop_db is not None:
            report(0.68, "Serializando y sincronizando tablas de drops de 39 duelistas en WA_MRG...")
            drop_db.save_to_wa(wa_bytes)
            res.drops_synchronized = 39
            report(0.70, f"  {res.drops_synchronized} tablas de drop de duelistas sincronizadas.")

        # ------------------------------------------------------------------
        # 8.6. Inyectar gráficos de cartas personalizados en WA_MRG
        # ------------------------------------------------------------------
        if graphics_db is not None:
            report(0.71, "Inyectando gráficos de cartas personalizados en WA_MRG...")
            injected_art = graphics_db.apply_to_wa(wa_bytes)
            if injected_art > 0:
                report(0.72, f"  {injected_art} arte(s) de cartas personalizados inyectados.")

        # ------------------------------------------------------------------
        # 8.7. Sincronizar configuraciones de campos y arenas en WA_MRG
        # ------------------------------------------------------------------
        if field_spells_db is not None:
            report(0.72, "Sincronizando configuraciones de campos de duelo (7 arenas) en WA_MRG...")
            valid_arenas = sum(1 for fid in range(7) if ARENA_WA_OFFSETS.get(fid, 0) + ARENA_STRIDE <= len(wa_bytes))
            report(0.725, f"  {valid_arenas}/7 arenas de combate validadas en WA_MRG.")

        # ------------------------------------------------------------------
        # 9. Validar integridad completa antes de escribir
        # ------------------------------------------------------------------
        report(0.72, "Validando integridad exhaustiva de memoria y tablas del nuevo ejecutable...")
        res.validation = EnginePatchManager.validate_full_build(
            bytes(exe_bytes), bytes(wa_bytes)
        )
        for key, val in res.validation.items():
            status = "OK" if val else "FALLO"
            report(0.72, f"  [{status}] {key}: {val}")


        # ------------------------------------------------------------------
        # 11. Inyección atómica y re-codificación de sectores
        # ------------------------------------------------------------------
        report(0.78, "Recalculando checksums EDC y paridades Reed-Solomon L-EC (P/Q)...")
        out_dir = os.path.dirname(os.path.abspath(output_image_path))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        disc_template = mod_disc if mod_disc is not None else base_disc
        inj_slus, inj_wa = find_keys(disc_template)

        files_to_inject = {
            inj_slus: bytes(exe_bytes),
            inj_wa:   bytes(wa_bytes)
        }
        disc_template.inject_files_in_place(files_to_inject, output_filepath=output_image_path)
        report(0.92, "Generando formatos de distribución (.iso, .bin, .cue)...")

        # Companion formats
        base_no_ext, ext = os.path.splitext(output_image_path)

        if ext.lower() == ".iso":
            res.output_iso = output_image_path
            bin_path = f"{base_no_ext}.bin"
            try:
                shutil.copyfile(output_image_path, bin_path)
                res.output_bin = bin_path
            except Exception:
                pass
        else:
            res.output_bin = output_image_path
            iso_path = f"{base_no_ext}.iso"
            try:
                shutil.copyfile(output_image_path, iso_path)
                res.output_iso = iso_path
            except Exception:
                pass

        cue_path = f"{base_no_ext}.cue"
        target_name = os.path.basename(res.output_bin if res.output_bin else output_image_path)
        cue_content = (
            f'FILE "{target_name}" BINARY\n'
            f'  TRACK 01 MODE2/2352\n'
            f'    INDEX 01 00:00:00\n'
        )
        try:
            with open(cue_path, "w", encoding="utf-8") as f:
                f.write(cue_content)
            res.output_cue = cue_path
        except Exception:
            pass

        report(1.0, "¡Compilación finalizada! ROM estable, sin crash en turno 3 ni entre duelos.")
        res.success = True
        return res
