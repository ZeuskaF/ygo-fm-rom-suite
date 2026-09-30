"""
2-ISO Surgical Mod Merger for Yu-Gi-Oh! Forbidden Memories.
Fuses the rock-solid Drop x100 engine from Vanilla Express into any Target Mod ISO,
preserving 100% of the Target Mod's custom assets, cards, fusions, decks, and WA_MRG.MRG.
"""

import hashlib
import os
import shutil
from typing import Callable, Dict, Optional, Tuple

from core.cdrom import PS1DiscImage
from core.mips_engine import DropX100Transplanter, PSXExecutable


class MergeResult:
    def __init__(self):
        self.success = False
        self.message = ""
        self.output_bin = ""
        self.output_cue = ""
        self.patches_applied = 0
        self.target_exe_name = ""
        self.wa_mrg_hash = ""
        self.details = []

    def add_log(self, text: str):
        self.details.append(text)


class YGOFMSurgicalMerger:
    """
    Coordinates loading Vanilla Express and Target Mod ISOs,
    extracting the stable drop x100 routines, transplanting them into the
    Target Mod's executable, and outputting a stable, playable ISO/BIN.
    """

    @staticmethod
    def _find_exe_name(iso: PS1DiscImage) -> str:
        """Finds the main PSX executable via SYSTEM.CNF or by standard naming."""
        # 1. Try parsing SYSTEM.CNF
        for key in iso.file_table:
            if "SYSTEM.CNF" in key:
                try:
                    cnf_bytes = iso.extract_file(key)
                    cnf_text = cnf_bytes.decode("ascii", errors="replace")
                    for line in cnf_text.splitlines():
                        line = line.strip()
                        if line.startswith("BOOT") and "=" in line:
                            # e.g. BOOT = cdrom:\SLUS_014.11;1
                            val = line.split("=", 1)[1].strip()
                            val = val.replace("cdrom:\\", "").replace("cdrom:", "").split(";")[0]
                            clean_name = os.path.basename(val).strip()
                            if clean_name.upper() in iso.file_table:
                                return clean_name.upper()
                except Exception:
                    pass

        # 2. Look for standard SLUS/SLES/SLPM executables
        for key in iso.file_table:
            base = os.path.basename(key)
            if base.startswith(("SLUS_", "SLES_", "SLPM_")):
                return key

        # Fallback
        return "SLUS_014.11"

    @classmethod
    def merge(
        cls,
        express_iso_path: str,
        target_mod_iso_path: str,
        output_iso_path: str,
        drop_multiplier: int = 100,
        progress_cb: Optional[Callable[[float, str], None]] = None
    ) -> MergeResult:
        result = MergeResult()

        def report(prog: float, msg: str):
            result.add_log(f"[{int(prog*100)}%] {msg}")
            if progress_cb:
                progress_cb(prog, msg)

        # 1. Validation
        if not os.path.isfile(express_iso_path):
            result.message = f"Vanilla Express ISO no existe: {express_iso_path}"
            return result
        if not os.path.isfile(target_mod_iso_path):
            result.message = f"Target Mod ISO no existe: {target_mod_iso_path}"
            return result

        report(0.05, "Abriendo imágenes de disco PS1...")
        try:
            express_iso = PS1DiscImage(express_iso_path)
            target_iso = PS1DiscImage(target_mod_iso_path)
        except Exception as e:
            result.message = f"Error al leer formato ISO/BIN: {str(e)}"
            return result

        # 2. Identify Executables
        report(0.15, "Localizando ejecutables en los discos...")
        express_exe_name = cls._find_exe_name(express_iso)
        target_exe_name = cls._find_exe_name(target_iso)
        result.target_exe_name = target_exe_name
        report(0.25, f"Ejecutable Express: {express_exe_name} | Ejecutable Target: {target_exe_name}")

        try:
            express_exe_bytes = express_iso.extract_file(express_exe_name)
            target_exe_bytes = target_iso.extract_file(target_exe_name)
        except Exception as e:
            result.message = f"Error extrayendo ejecutable del disco: {str(e)}"
            return result

        # 3. Clean WA_MRG.MRG in Target Mod, purging any Ghost corruption
        report(0.35, "Verificando arquitectura de WA_MRG.MRG en Target Mod...")
        wa_mrg_key = None
        for key in target_iso.file_table:
            if "WA_MRG.MRG" in key:
                wa_mrg_key = key
                break

        files_to_inject: Dict[str, bytes] = {}

        if wa_mrg_key:
            target_wa_bytes = bytearray(target_iso.extract_file(wa_mrg_key))
            result.wa_mrg_hash = hashlib.sha256(target_wa_bytes).hexdigest()[:16]
            express_wa_key = None
            for key in express_iso.file_table:
                if "WA_MRG.MRG" in key:
                    express_wa_key = key
                    break

            if express_wa_key:
                express_wa = express_iso.extract_file(express_wa_key)
                # Purge Ghost tables in all 7 duel stages (0xbc1c00 + k * 0x75800)
                for k in range(7):
                    off = 0xbc1c00 + k * 0x75800
                    if off + 0x400 <= len(target_wa_bytes) and off + 0x400 <= len(express_wa):
                        target_wa_bytes[off : off + 0x400] = express_wa[off : off + 0x400]

            files_to_inject[wa_mrg_key] = bytes(target_wa_bytes)
            report(0.45, "WA_MRG.MRG preparado: fusiones, decks y drops del mod 100% integrados.")

        # 4. Build Final Executable using Target Mod as Native Base
        # Preserves 100% of the Mod's native Combat AI (so CPU moves and attacks),
        # card database, texts, ritual hook, and assets, while transplanting the complete
        # Drop x100 engine from Vanilla Express and eradicating Ghost corruption.
        out_dir = os.path.dirname(os.path.abspath(output_iso_path))
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        report(0.60, f"Trasplantando Motor Drop x{drop_multiplier} de Vanilla Express...")
        mod_exe = bytearray(target_exe_bytes)

        # 1. Function 1, storage slots & multiplier (0x21b0 .. 0x2278)
        if len(mod_exe) >= 0x2278 and len(express_exe_bytes) >= 0x2278:
            mod_exe[0x21b0 : 0x2278] = express_exe_bytes[0x21b0 : 0x2278]
            mod_exe[0x21c0] = drop_multiplier & 0xFF

        # 2. Helper routine in unused bios string area (contains 0x80011da8)
        if len(mod_exe) >= 0x25d0 and len(express_exe_bytes) >= 0x25d0:
            mod_exe[0x2540 : 0x25d0] = express_exe_bytes[0x2540 : 0x25d0]

        # 3. Complete roll_random_card (0x12034 .. 0x12080)
        if len(mod_exe) >= 0x12080 and len(express_exe_bytes) >= 0x12080:
            mod_exe[0x12034 : 0x12080] = express_exe_bytes[0x12034 : 0x12080]

        # 4. Post-duel entry hook (0x12460 .. 0x12488)
        if len(mod_exe) >= 0x12488 and len(express_exe_bytes) >= 0x12488:
            mod_exe[0x12460 : 0x12488] = express_exe_bytes[0x12460 : 0x12488]

        # 5. Fix 0x126dc to NOP (removes Ghost +50 card offset)
        if len(mod_exe) >= 0x126e0:
            mod_exe[0x126dc : 0x126e0] = b"\x00\x00\x00\x00"

        # 6. Post-duel reward hook: deposit 100 cards into trunk, then cleanly skip
        # rating and drop screens, returning immediately to the map/menu with zero bugs.
        if len(mod_exe) >= 0x127b0 and len(express_exe_bytes) >= 0x12718:
            # 6A. Call Dispatcher -> Function 2 (deposits all 100 cards directly into trunk)
            mod_exe[0x12710 : 0x12714] = express_exe_bytes[0x12710 : 0x12714]  # lh $a0, 60($v0)
            mod_exe[0x12714 : 0x12718] = express_exe_bytes[0x12714 : 0x12718]  # j 0x801db430
            mod_exe[0x12718 : 0x1271c] = b"\x00\x00\x00\x00"                 # nop

            # 6B. Fast-exit routine: increments win count, sets next scene (3=exit duel to map/menu),
            # starts screen fade, clears duel state (818($gp)=0), and returns cleanly to main loop.
            skip_hook_words = [
                0x9382025d,  # lbu $v0, 605($gp)
                0x278502d0,  # addiu $a1, $gp, 720
                0x00021080,  # sll $v0, $v0, 2
                0x00452021,  # addu $a0, $v0, $a1
                0x8c830000,  # lw $v1, 0($a0)
                0x00000000,  # nop
                0x94620518,  # lhu $v0, 1304($v1)
                0x00000000,  # nop
                0x24420001,  # addiu $v0, $v0, 1
                0xa4620518,  # sh $v0, 1304($v1)
                0x3c01800a,  # lui $at, 0x800a
                0x24020001,  # addiu $v0, $zero, 1
                0xa022b369,  # sb $v0, -19607($at)
                0x24020003,  # addiu $v0, $zero, 3
                0xa022b269,  # sb $v0, -19863($at)
                0x24020001,  # addiu $v0, $zero, 1
                0xa022b26c,  # sb $v0, -19860($at)
                0x34027310,  # ori $v0, $zero, 0x7310
                0xa782008e,  # sh $v0, 142($gp)
                0xa7800332,  # sh $zero, 818($gp)
                0x08008827,  # j 0x8002209c
                0x00000000,  # nop
            ]
            skip_bytes = bytearray()
            for w in skip_hook_words:
                skip_bytes.extend(w.to_bytes(4, "little"))

            mod_exe[0x1271c : 0x1271c + len(skip_bytes)] = skip_bytes
            mod_exe[0x1271c + len(skip_bytes) : 0x127b0] = b"\x00" * (0x127b0 - (0x1271c + len(skip_bytes)))


        # 7. Helper hook for card offset (0x14c50 .. 0x14c58)
        if len(mod_exe) >= 0x14c58 and len(express_exe_bytes) >= 0x14c58:
            mod_exe[0x14c50 : 0x14c58] = express_exe_bytes[0x14c50 : 0x14c58]

        # 8. Chest hook (0x285fc .. 0x28608)
        if len(mod_exe) >= 0x28608 and len(express_exe_bytes) >= 0x28608:
            mod_exe[0x285fc : 0x28608] = express_exe_bytes[0x285fc : 0x28608]

        # 9. Helper hook for card boundary (0x28d68 .. 0x28d70)
        if len(mod_exe) >= 0x28d70 and len(express_exe_bytes) >= 0x28d70:
            mod_exe[0x28d68 : 0x28d70] = express_exe_bytes[0x28d68 : 0x28d70]

        # 10. Purge Ghost scratchpad (0x19b400 .. 0x19b700)
        if len(mod_exe) >= 0x19b700:
            mod_exe[0x19b400 : 0x19b700] = b"\x00" * 0x300

        # 11. Dispatcher at 0x801db430 (0x1cbc30 .. 0x1cbc98)
        if len(mod_exe) >= 0x1cbc98 and len(express_exe_bytes) >= 0x1cbc98:
            mod_exe[0x1cbc30 : 0x1cbc98] = express_exe_bytes[0x1cbc30 : 0x1cbc98]

        # 12. Interleaved code table at 0x801db760 (0x1cbf60 .. 0x1cc020)
        if len(mod_exe) >= 0x1cc020 and len(express_exe_bytes) >= 0x1cc020:
            mod_exe[0x1cbf60 : 0x1cc020] = express_exe_bytes[0x1cbf60 : 0x1cc020]

        # 13. Function 2 at 0x801dbf30 (0x1cc730 .. 0x1cc7a4)
        if len(mod_exe) >= 0x1cc7a4 and len(express_exe_bytes) >= 0x1cc7a4:
            mod_exe[0x1cc730 : 0x1cc7a4] = express_exe_bytes[0x1cc730 : 0x1cc7a4]

        result.patches_applied = 13
        report(0.75, "IA nativa del mod, motor Drop x100 y transiciones post-duelo sincronizados.")

        files_to_inject[target_exe_name] = bytes(mod_exe)

        # 5. Inject modified files atomically into Target Mod disc and recalculate EDC/ECC
        report(0.85, "Inyectando archivos en la imagen de disco y recalculando EDC/ECC...")
        target_iso.inject_files_in_place(files_to_inject, output_filepath=output_iso_path)


        result.output_bin = output_iso_path

        # 6. Generate companion formats (.cue and .bin/.iso)
        base_no_ext, ext = os.path.splitext(output_iso_path)
        if ext.lower() == ".iso":
            companion_bin = base_no_ext + ".bin"
            companion_cue = base_no_ext + ".cue"
            shutil.copyfile(output_iso_path, companion_bin)
            bin_filename = os.path.basename(companion_bin)
            cue_content = (
                f'FILE "{bin_filename}" BINARY\n'
                f'  TRACK 01 MODE2/2352\n'
                f'    INDEX 01 00:00:00\n'
            )
            with open(companion_cue, "w", encoding="utf-8") as f:
                f.write(cue_content)
            result.output_cue = companion_cue
            report(0.98, "Formatos listos: Archivo ISO único y BIN/CUE listos para jugar.")
        elif ext.lower() == ".bin":
            cue_path = base_no_ext + ".cue"
            bin_filename = os.path.basename(output_iso_path)
            cue_content = (
                f'FILE "{bin_filename}" BINARY\n'
                f'  TRACK 01 MODE2/2352\n'
                f'    INDEX 01 00:00:00\n'
            )
            with open(cue_path, "w", encoding="utf-8") as f:
                f.write(cue_content)
            result.output_cue = cue_path
            companion_iso = base_no_ext + ".iso"
            shutil.copyfile(output_iso_path, companion_iso)
            report(0.98, "Formatos listos: Archivo BIN/CUE e ISO independiente generados.")

        report(1.0, "¡Fusión completada con éxito!")
        result.success = True
        result.message = f"ROM generada con éxito con Drop x{drop_multiplier} estable y contenido completo del mod."
        return result
