# Changelog 📋

All notable changes to the **Yu-Gi-Oh! Forbidden Memories ROM Suite** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-09-30 - Official Release 🎉

### Added
- **Visual Card Editor (001–722):** Complete attribute editing (ATK, DEF, Types, Guardian Stars, BCD Passwords, Star Chip costs).
- **Custom Card Art Ingestion:** Extraction of 16-bit BGR555 TIM textures from `DATA/CARD_TEX.MRG` and ingestion of PNG/JPG/WEBP custom artwork.
- **High-Definition Card Canvas Renderer:** Visual card generator with authentic frames, star ranks, type badges, and PNG export.
- **Authentic Description Engine:** Native decoding and encoding of PS1 3-byte escape sequences (`0xF8 0x0B <type_id>`) with support for type badges (`[Beast]`, `[Warrior]`, `[Dragon]`, `[Bestia]`, `[Guerrero]`, etc.).
- **MIPS-Symmetric Fusion Engine:** Reverse-engineered CPU comparator (`0x80019a68`), 64 KB memory bounds safety, and 7-arena synchronization in `DATA/WA_MRG.MRG`.
- **1-Click Dream Mod Fusion Importer:** Seamless import of over 31,500 advanced fusion recipes.
- **Authentic 7-Pool Starter Deck System:** Reverse-engineered Name Entry overlay in `DATA/WA_MRG.MRG` sector 7983 with exact multi-draw Poisson probabilities and 100% guaranteed card presets.
- **Field Spells & 3D Arena Customizer:** Custom stat boost/penalty editing for the 6 field spells, 3D battle arena RGB tints, and interactive visual duel grid.
- **Duelist Decks & AI Difficulty:** 40-card deck editor and aggression slider for all 39 campaign opponents.
- **Drop Tables & Reverse Search Engine:** Full SA-POW, BCD-POW, SA-TEC, BCD-TEC drop rate editing, 2,048 auto-normalization, and "Who Drops This Card?" reverse lookup.
- **Universal Rewards Engine:** Configurable drops from Drop x1 to Drop x100, direct memory trunk injection (`0x801db430`), and audio fadeout flag clearing to prevent softlocks.
- **Mode 2 Form 1 CD-ROM Recompiler:** Hardware-accurate EDC (CRC32) and Reed-Solomon L-EC (P/Q parity) regeneration across all sectors.
- **Dual Interface:** Full-featured modern Tkinter dark theme GUI + headless CLI for automation.
- **Comprehensive Test Suite:** 53 unit and integration tests passing with 100% coverage of core subsystems.
