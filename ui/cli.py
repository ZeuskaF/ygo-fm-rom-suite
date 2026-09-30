"""
Command-Line Interface (CLI) for Yu-Gi-Oh! Forbidden Memories 2-ISO Surgical Mod Merger.
"""

import argparse
import os
import sys
from typing import Optional

from core.merger import YGOFMSurgicalMerger


def run_cli(args: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Yu-Gi-Oh! Forbidden Memories 2-ISO Surgical Mod Merger (Drop x100 Estable)",
        epilog="Ejemplo: python main.py --express \"VanillaExpress.bin\" --mod \"Mod13.bin\" --output \"Mod13_x100.bin\""
    )

    parser.add_argument(
        "-e", "--express",
        dest="express_path",
        required=True,
        help="Ruta a la imagen ISO/BIN de Vanilla Express (donante de la rutina Drop x100)"
    )

    parser.add_argument(
        "-m", "--mod",
        dest="mod_path",
        required=True,
        help="Ruta a la imagen ISO/BIN del Mod a modificar (conservará todos sus datos y cartas)"
    )

    parser.add_argument(
        "-o", "--output",
        dest="output_path",
        required=False,
        default=None,
        help="Ruta del archivo de salida .bin o .iso (por defecto: <nombre_mod>_drop_x100.bin)"
    )

    parser.add_argument(
        "-d", "--drop",
        dest="drop_multiplier",
        type=int,
        default=100,
        help="Multiplicador de cartas por duelo (1-255, por defecto 100)"
    )

    parsed = parser.parse_args(args)

    if not parsed.output_path:
        base_name, ext = os.path.splitext(parsed.mod_path)
        parsed.output_path = f"{base_name}_drop_x{parsed.drop_multiplier}.iso"

    print("=" * 70)
    print("   Yu-Gi-Oh! Forbidden Memories - Fusionador Quirúrgico de Mods")
    print(f"   Motor de Drop Estable: x{parsed.drop_multiplier}")
    print("=" * 70)
    print(f"[*] ISO Vanilla Express: {parsed.express_path}")
    print(f"[*] ISO Mod Destino:     {parsed.mod_path}")
    print(f"[*] Archivo de Salida:   {parsed.output_path}")
    print("-" * 70)

    def print_progress(prog: float, msg: str):
        pct = int(prog * 100)
        bar_len = 30
        filled = int(bar_len * prog)
        bar = "#" * filled + "-" * (bar_len - filled)
        try:
            sys.stdout.write(f"\r[{bar}] {pct:3d}% - {msg:<40}")
            sys.stdout.flush()
        except UnicodeEncodeError:
            clean_msg = msg.encode("ascii", errors="replace").decode("ascii")
            sys.stdout.write(f"\r[{bar}] {pct:3d}% - {clean_msg:<40}")
            sys.stdout.flush()

    print()
    result = YGOFMSurgicalMerger.merge(
        express_iso_path=parsed.express_path,
        target_mod_iso_path=parsed.mod_path,
        output_iso_path=parsed.output_path,
        drop_multiplier=parsed.drop_multiplier,
        progress_cb=print_progress
    )
    print("\n" + "-" * 70)

    if result.success:
        print(f"[OK] {result.message}")
        print(f"[OK] Imagen generada: {result.output_bin}")
        if result.output_cue:
            print(f"[OK] Archivo CUE:    {result.output_cue}")
        print(f"[OK] Parches inyectados: {result.patches_applied}")
        if result.wa_mrg_hash:
            print(f"[OK] WA_MRG.MRG preservado intacto (Hash: {result.wa_mrg_hash}...)")
        print("\nListo para cargar en tu emulador favorito (DuckStation, ePSXe, etc.)!")
        return 0
    else:
        print(f"[ERROR] {result.message}")
        return 1


if __name__ == "__main__":
    sys.exit(run_cli())
