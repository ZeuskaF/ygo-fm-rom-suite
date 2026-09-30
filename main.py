"""
Entry point for Yu-Gi-Oh! Forbidden Memories 2-ISO Surgical Mod Merger.
Launches the GUI by default, or the CLI if command-line arguments are provided.
"""

import sys

def main():
    # If command line arguments provided (other than just script name), run CLI
    if len(sys.argv) > 1 and sys.argv[1] not in ("--gui", "-g"):
        from ui.cli import run_cli
        sys.exit(run_cli())
    else:
        from ui.gui import run_gui
        run_gui()

if __name__ == "__main__":
    main()
