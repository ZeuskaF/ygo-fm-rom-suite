"""
Tests for core/field_spells.py (Duel Arenas & Field Spells Database).
"""

import os
import tempfile
import pytest
from core.field_spells import (
    FieldSpellDatabase,
    FieldSpellData,
    DEFAULT_FIELD_COLORS,
    FIELD_PRESETS,
    FIELD_METADATA,
    ARENA_WA_OFFSETS,
)


def test_field_spells_initialization():
    db = FieldSpellDatabase()
    assert len(db.fields) == 7
    for fid in range(7):
        assert fid in db.fields
        f = db.get_field(fid)
        assert f.field_id == fid
        assert f.wa_offset == ARENA_WA_OFFSETS[fid]
        assert "ground" in f.colors
        assert "grid" in f.colors


def test_field_spells_card_lookup():
    db = FieldSpellDatabase()
    forest = db.get_field_by_card_id(301)
    assert forest is not None
    assert forest.field_id == 1
    assert "Insect" in forest.boosted_types

    yami = db.get_field_by_card_id(306)
    assert yami is not None
    assert yami.field_id == 6
    assert "Spellcaster" in yami.boosted_types
    assert "Fairy" in yami.weakened_types

    assert db.get_field_by_card_id(999) is None
    assert db.get_field_by_card_id(0) is None


def test_field_spells_stat_modifiers():
    db = FieldSpellDatabase()
    # Forest boosts Insect, Beast, Plant, Beast-Warrior
    assert db.calculate_stat_modifier(1, "Insect") == (500, 500)
    assert db.calculate_stat_modifier(1, "Dragon") == (0, 0)

    # Umi weakens Pyro
    assert db.calculate_stat_modifier(5, "Fish") == (500, 500)
    assert db.calculate_stat_modifier(5, "Pyro") == (-500, -500)
    assert db.calculate_stat_modifier(5, "Warrior") == (0, 0)

    # Normal field: neutral to all
    assert db.calculate_stat_modifier(0, "Dragon") == (0, 0)
    assert db.calculate_stat_modifier(0, "Spellcaster") == (0, 0)


def test_field_spells_color_customization():
    db = FieldSpellDatabase()
    db.set_field_color(1, "ground", "#123456")
    assert db.get_field(1).colors["ground"] == "#123456"

    # Reset
    db.reset_to_defaults()
    assert db.get_field(1).colors["ground"] == DEFAULT_FIELD_COLORS[1]["ground"]


def test_field_spells_preset_application():
    db = FieldSpellDatabase()
    assert db.apply_preset("Cyber Neón 3D / Tron")
    cyber_ground = db.get_field(0).colors["ground"]
    assert cyber_ground == "#14141A"

    assert not db.apply_preset("NonExistentPreset")


def test_field_spells_export_import_json():
    db = FieldSpellDatabase()
    db.set_field_color(3, "ground", "#AABBCC")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        assert db.save_to_json_file(tmp_path)
        new_db = FieldSpellDatabase()
        updated_count = new_db.load_from_json_file(tmp_path)
        assert updated_count == 7
        assert new_db.get_field(3).colors["ground"] == "#AABBCC"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
