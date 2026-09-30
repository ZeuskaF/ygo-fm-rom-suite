# Yu-Gi-Oh! Forbidden Memories ROM Suite & ISO Recompiler 🎮⚔️

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests Status](https://img.shields.io/badge/tests-53%20passed-brightgreen.svg)](tests/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![PS1 Disc](https://img.shields.io/badge/formats-ISO%20%7C%20BIN%20%7C%20CUE-red.svg)]()

> **Languages:** [🇬🇧 English](README.md) | [🇪🇸 Español](README_ES.md)

A professional, standalone reverse-engineering toolkit and disc recompiler for **Yu-Gi-Oh! Forbidden Memories** (PlayStation 1, `SLUS-01411` / `SLES-03951`). Inspect, modify, balance, and recompile every aspect of the game without requiring external disc utility tools.

---

## 🌟 Key Features

### 1. 🎴 Complete Visual Card Editor (Cards 001 to 722)
- **Live Attribute Editing:** Modify ATK, DEF, 24 official card types (including Magic, Trap, and Ritual), Primary and Secondary Guardian Stars, 8-digit BCD passwords, and Star Chip costs.
- **Card Name Customizer:** Edit card names with dynamic character encoding and full diacritic support.
- **Authentic Description Engine & Type Glyphs:** Native decoding and encoding of PS1 3-byte escape sequences (`0xF8 0x0B <type_id>`). Easily insert graphical type badges into card descriptions using human-readable tags like `[Beast]`, `[Warrior]`, `[Dragon]`, `[Spellcaster]`, or Spanish equivalents (`[Bestia]`, `[Guerrero]`, etc.).

### 2. 🎨 Card Graphics & Custom Artwork Ingestion
- **TIM Extraction:** Extract authentic 16-bit BGR555 TIM textures directly from `DATA/CARD_TEX.MRG`.
- **Custom Art Ingestion:** Import any standard PNG, JPEG, or WEBP image. The engine automatically handles aspect ratio fitting, downsampling, and color conversion into PS1 BGR555 texture format.
- **High-Definition Canvas Renderer:** Live visual preview featuring authentic card frames (Monster, Ritual, Spell, Trap), stars, levels, attribute badges, and text layouts. Export rendered cards as high-resolution PNG images.

### 3. ⚡ MIPS-Symmetric Fusion Engine
- **Hardware-Accurate MIPS Logic:** Replicates the PS1 MIPS R3000 CPU comparator (`0x80019a68`), ensuring fusion recipes are recognized seamlessly regardless of which card is selected first.
- **Sector-Safe 64 KB Packing:** Stores fusion tables at `DATA/WA_MRG.MRG` sector 5903 (`0x0B87800`) across all 7 battle arenas, strictly bounded to 65,536 bytes to prevent corruption of adjacent arena TIM textures in sector 34.
- **One-Click Dream Mod Importer:** Import over 31,500 advanced fusion recipes from popular mods (such as *Dream Mod 15x*) with a single click.

### 4. 🎲 Authentic 7-Pool Starter Deck Engine
- **True PS1 Name Entry Overlay:** Directly reads and writes to `DATA/WA_MRG.MRG` sector 7983 (`0x00F97800`), where the PS1 runtime generates the player's 40-card starter deck.
- **7 Independent Probability Pools:** Configure card pools with weights summing to 2,048:
  - **Pool 0:** Minor Monsters (16 draws)
  - **Pool 1:** Intermediate Monsters (16 draws)
  - **Pool 2:** Advanced Monsters (4 draws)
  - **Pool 3:** Key / Boss Monsters (1 draw)
  - **Pool 4:** Board Wipes (Raigeki / Dark Hole - 1 draw)
  - **Pool 5:** Field Spells (Forest, Wasteland, Mountain, Sogen, Umi, Yami - 1 draw)
  - **Pool 6:** Equip Spells (1 draw)
- **Mathematical Exactness:** Real-time Poisson/Bernoulli multi-draw probability calculations ($P(\ge 1) = 1 - \prod_{p=0}^6 (1 - w_p / 2048)^{\text{draws}_p}$).
- **Quick Presets:** Instant weight assignment for 25%, 50%, and **100% Guaranteed** starting cards.

### 5. 🌌 Field Spells & Duel Board Customizer
- **Field Spell Parameters:** Customize stat boosts and reductions for all 6 field spells (Forest, Wasteland, Mountain, Sogen, Umi, Yami).
- **3D Duel Arena Customization:** Adjust battle arena RGB color tints and ambient lighting.
- **Interactive 3D Board Visualizer:** Real-time visual representation of the dueling grid with monster placements, field backgrounds, and atmospheric effects.
- **Preset Management:** Export and import custom field configurations via JSON.

### 6. ⚔️ Duelist Decks & AI Difficulty (39 Opponents)
- **Deck Customization:** Edit the complete 40-card decks for all 39 campaign and free duel opponents (from Simon Muran and Jono to Heishin, Seto 3rd, and Nitemare).
- **AI Aggression Slider:** Configure the AI's fusion probability and tactical aggression from 0% to 100%.

### 7. 🏆 Drop Tables & Reverse Search Engine
- **Rank Inspection:** View and modify drop pools across all 4 official rank brackets: **SA-POW**, **BCD-POW**, **SA-TEC**, and **BCD-TEC**.
- **Konami PRNG Auto-Normalization:** Maintains strict 2,048 weight sums required by the game's internal RNG table.
- **Reverse Drop Search ("Who Drops This Card?"):** Search any card in the database to instantly identify which duelists drop it, in what rank bracket, and with what exact probability.
- **Rank Calculation Guide:** Detailed in-app guide detailing how the game scores turns, fusions, card consumption, and trap activations to award letter ranks.

### 8. 🎁 Universal Rewards Engine (Drop x1 to Drop x100)
- **Crash-Free Post-Duel Rewards:** Replaces fragile assembly hooks with direct trunk memory injection (`0x801db430`) and clean frame epilogue returns (`0x8002209c`).
- **Anti-Softlock Audio Trigger:** Automatically clears the post-duel sound fadeout flag to eliminate black screens and freezes across all game variants (Vanilla, Dream Mod, Mod 11, etc.).
- **Configurable Multiplier:** Adjust card drop yield from 1 to 100 cards per duel.

### 9. 💿 Standalone & Surgical Disc Recompiler
- **Mode 2 Form 1 CD-ROM Rebuilding:** Full low-level sector reconstruction with hardware-accurate **EDC (CRC32)** and **Reed-Solomon L-EC (P/Q parity)** generation.
- **Standalone Disc Compilation:** Built-in vanilla database fallback allows generating playable discs without needing an original ISO file.
- **Surgical Mod Merger:** Selectively extract and merge specific subsystems (e.g. only fusions, only drops, or only graphics) from modded discs into clean targets.
- **Emulator & Hardware Ready:** Outputs matching `.iso`, `.bin`, and `.cue` files tested and compatible with DuckStation, ePSXe, RetroArch (Beetle PSX / SwanStation), and real PS1 consoles with optical drive emulators (xStation, PSIO).

---

## 📂 Project Architecture

```
ygo_fm_rom_suite/
├── Iniciar_Suite.bat          # Spanish Windows launcher
├── Launch_Suite.bat           # English Windows launcher
├── launch_suite.sh            # Linux / macOS shell launcher
├── main.py                    # Main entry point (CLI/GUI router)
├── requirements.txt           # Python dependencies (Pillow, pytest)
├── LICENSE                    # MIT License
├── README.md                  # English documentation
├── README_ES.md               # Spanish documentation
├── docs/                      # Deep-dive technical specifications
│   ├── ARCHITECTURE.md        # Technical architecture & PS1 disc layout (EN)
│   └── ARQUITECTURA_ES.md     # Technical architecture & PS1 disc layout (ES)
├── core/                      # ROM hacking & recompilation core engine
│   ├── cards.py               # 722-card serializer & description encoder
│   ├── card_data.py           # Canonical types, stars, and constants
│   ├── canonical_card_names.py# Official localized card names dictionary
│   ├── card_graphics.py       # TIM BGR555 texture extractor & injector
│   ├── card_renderer.py       # High-definition visual card canvas engine
│   ├── cdrom.py               # ISO-9660 Mode 2 Form 1 CD-ROM sector engine
│   ├── builder.py             # Disc recompiler & EDC/ECC parity generator
│   ├── fusions.py             # Fusion database & 7-arena synchronized writer
│   ├── decks.py               # Duelist decks & AI difficulty engine
│   ├── drops.py               # Drop tables, reverse search & auto-normalizer
│   ├── starter_deck.py        # 7-Pool starter deck probability engine
│   ├── starter_deck_data.py   # Base64 vanilla pool assets & fallback ROM data
│   ├── field_spells.py        # Field spell stat modifiers & color palettes
│   ├── duel_board_renderer.py # 3D duel arena visualizer
│   ├── engine_patches.py      # Drop x100, trunk hooks & audio fix patches
│   ├── mips_engine.py         # MIPS R3000A disassembler & AOB pattern scanner
│   └── merger.py              # Surgical 2-ISO feature merger
├── ui/                        # User interface modules
│   ├── gui.py                 # Modern Tkinter dark-theme GUI (full suite)
│   └── cli.py                 # Command-line interface for automation
└── tests/                     # Automated test suite (53 tests)
    ├── test_cards.py          # Card serialization & glyph decoding tests
    ├── test_card_graphics.py  # BGR555 conversion & art ingestion tests
    ├── test_card_renderer.py  # Visual card rendering tests
    ├── test_fusions.py        # MIPS symmetry & fusion boundary tests
    ├── test_starter_deck.py   # 7-pool probabilities & WA_MRG injection tests
    ├── test_field_spells.py   # Field spell calculations & preset tests
    ├── test_drops.py          # Drop normalization & reverse search tests
    ├── test_drop_multipliers.py # MIPS multiplier clamping tests
    ├── test_drop_recompile.py # End-to-end drop recompilation tests
    ├── test_builder.py        # Disc builder & sector injection tests
    ├── test_standalone_builder.py # Disc compilation without source ISO
    ├── test_dream_merge_compile.py # 2-ISO surgical merge integration tests
    ├── test_cdrom.py          # EDC CRC32 & Reed-Solomon parity tests
    ├── test_mips_engine.py    # Disassembler & AOB scanner tests
    └── test_gui_smoke.py      # Tkinter GUI initialization smoke tests
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10** or higher.
- Operating System: Windows 10/11, Linux (Ubuntu, Debian, Fedora, Arch), or macOS.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/ygo-fm-rom-suite.git
   cd ygo-fm-rom-suite
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 💻 Usage

### Graphical Interface (Recommended)

- **On Windows:** Double-click `Launch_Suite.bat` (or `Iniciar_Suite.bat`).
- **On Linux / macOS:** Run:
  ```bash
  chmod +x launch_suite.sh
  ./launch_suite.sh
  ```
- **Via Terminal:**
  ```bash
  python main.py
  ```

#### Basic Workflow:
1. Click **`📂 Load ISO / BIN`** and select your PS1 disc image (e.g. `SLUS_014.11` vanilla game or a mod).
2. *(Optional)* Click **`📥 Import Mod`** to import fusion tables or card stats from other disc images.
3. Customize cards, fusion recipes, drop rates, starter deck pools, or field spells.
4. Set your desired drop multiplier in **⚙️ Engine & Rewards** (e.g. Drop x5, Drop x15, Drop x100).
5. Click **`⚡ GENERATE NEW COMPILED ROM / ISO ⚡`** to export a ready-to-play `.iso` / `.bin` / `.cue` disc image!

---

### Command-Line Interface (CLI)

The suite provides automated command-line commands for headless environments, CI/CD, and batch patch operations:

```bash
# Display general help
python main.py --help

# Recompile an ISO with custom Drop multiplier and auto-patches
python main.py compile --source "VanillaExpress.iso" --output "ModifiedGame.iso" --drops 15

# Export card database to JSON
python main.py export-cards --source "VanillaExpress.iso" --output "cards.json"

# Import modded fusions into a clean ISO
python main.py merge-fusions --source "VanillaExpress.iso" --mod "DreamMod.iso" --output "Merged.iso"
```

---

## 🧪 Testing & Validation

The test suite covers unit and integration tests across all modules, including mathematical correctness of EDC/ECC parity, MIPS disassembly, and bit-level disc manipulation:

```bash
python -m pytest -v
```

```text
============================= 53 passed in 33.03s =============================
```

All 53 tests run without external dependencies (using pure Python and Pillow).

---

## 📖 Deep-Dive Technical Documentation

For in-depth explanations of PS1 disc sectors, memory offsets, MIPS disassembly routines, and mathematical formulas, please refer to:
- [Architecture Guide (English)](docs/ARCHITECTURE.md)
- [Guía de Arquitectura (Español)](docs/ARQUITECTURA_ES.md)

---

## 🤝 Contributing

Contributions, bug reports, and pull requests are warmly welcomed! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on code style, testing requirements, and submission processes.

---

## ⚖️ License & Disclaimer

This project is released under the **[MIT License](LICENSE)**.

**Disclaimer:** *Yu-Gi-Oh!* and *Yu-Gi-Oh! Forbidden Memories* are registered trademarks of Konami Digital Entertainment and Kazuki Takahashi. This project is an independent research and educational endeavor created under fair use principles for game preservation and modding. No copyrighted commercial game assets or ROMs are distributed within this repository.
