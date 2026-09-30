import pytest
import struct
from core.starter_deck import (
    StarterDeckDatabase,
    STARTER_DECK_OFFSET,
    STARTER_DECK_SLOTS,
    STARTER_DECK_BYTES
)

def test_starter_deck_init_vanilla():
    db = StarterDeckDatabase()
    assert len(db.slots) == STARTER_DECK_SLOTS
    assert all(1 <= cid <= 722 for cid in db.slots)
    counts = db.get_counts()
    assert sum(counts.values()) == STARTER_DECK_SLOTS
    # In vanilla, Dark Hole (#336) and Raigeki (#337) have weight 2
    assert db.get_weight(336) == 2
    assert db.get_weight(337) == 2
    assert round(db.get_card_percentage(336), 3) == round(2 / 1024 * 100, 3)

def test_starter_deck_load_save_roundtrip():
    db = StarterDeckDatabase()
    exe = bytearray(0x100000)  # 1MB buffer
    written = db.save_to_exe(exe)
    assert written == STARTER_DECK_BYTES

    db2 = StarterDeckDatabase()
    db2.slots = [0] * STARTER_DECK_SLOTS
    loaded = db2.load_from_exe(bytes(exe))
    assert loaded == STARTER_DECK_SLOTS
    assert db2.slots == db.slots

def test_starter_deck_probabilities():
    db = StarterDeckDatabase()
    # If card has weight 0
    assert db.get_card_probability_in_deck(999) == 0.0
    assert db.get_expected_copies(999) == 0.0

    # Weight 2 out of 1024 in 40 draws: P = 1 - (1 - 2/1024)^40
    p = db.get_card_probability_in_deck(336, 40)
    expected_p = (1.0 - (1.0 - 2/1024)**40) * 100.0
    assert abs(p - expected_p) < 1e-4

    # Guaranteed card: weight 256
    db.set_card_weight(35, 256)
    p_dm = db.get_card_probability_in_deck(35, 40)
    assert p_dm > 99.99
    assert len(db.slots) == STARTER_DECK_SLOTS
    assert sum(db.get_counts().values()) == STARTER_DECK_SLOTS
    assert db.get_weight(35) == 256

def test_starter_deck_add_remove():
    db = StarterDeckDatabase()
    # Add Blue-Eyes White Dragon (#1)
    orig_w = db.get_weight(1)
    db.add_card(1, weight=10)
    assert db.get_weight(1) == orig_w + 10
    assert len(db.slots) == STARTER_DECK_SLOTS

    # Remove completely
    db.remove_card(1)
    assert db.get_weight(1) == 0
    assert len(db.slots) == STARTER_DECK_SLOTS

def test_starter_deck_import_from_mod():
    db = StarterDeckDatabase()
    mod_exe = bytearray(0x100000)
    # Fill mod starter deck with Dark Magician (#35) and Celtic Guardian (#41)
    mod_slots = [35] * 512 + [41] * 512
    struct.pack_into(f"<{STARTER_DECK_SLOTS}H", mod_exe, STARTER_DECK_OFFSET, *mod_slots)

    imported = db.import_from_mod(bytes(mod_exe))
    assert imported == STARTER_DECK_SLOTS
    assert db.get_weight(35) == 512
    assert db.get_weight(41) == 512
    assert db.get_weight(1) == 0

def test_starter_deck_active_cards_list():
    db = StarterDeckDatabase()
    active = db.get_active_cards()
    assert len(active) > 0
    # Should be sorted descending by weight
    weights = [item["weight"] for item in active]
    assert weights == sorted(weights, reverse=True)


import os
from core.cdrom import PS1DiscImage
from core.cards import CardDatabase
from core.fusions import FusionDatabase
from core.decks import DeckDatabase
from core.drops import DropDatabase
from core.builder import DiscRecompiler

DREAM_ISO = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso"

@pytest.mark.skipif(not os.path.isfile(DREAM_ISO), reason="Dream Mod ISO not found")
def test_recompile_with_custom_starter_deck(tmp_path):
    out_iso = str(tmp_path / "custom_starter.iso")

    disc = PS1DiscImage(DREAM_ISO)
    exe = disc.extract_file("SLUS_014.11")
    wa = disc.extract_file("DATA/WA_MRG.MRG")

    card_db = CardDatabase()
    card_db.load_from_exe_and_wa(exe, wa)

    fusion_db = FusionDatabase()
    fusion_db.load_from_wa(wa)

    deck_db = DeckDatabase()
    deck_db.load_from_wa_and_exe(wa, exe)

    drop_db = DropDatabase()
    drop_db.load_from_wa(wa, exe)

    starter_db = StarterDeckDatabase()
    # Guarantee Dark Magician (#35) with weight 300
    starter_db.set_card_weight(35, 300)
    assert starter_db.get_weight(35) == 300

    res = DiscRecompiler.build(
        base_disc_path=DREAM_ISO,
        output_image_path=out_iso,
        card_db=card_db,
        fusion_db=fusion_db,
        deck_db=deck_db,
        drop_db=drop_db,
        starter_deck_db=starter_db,
        drop_multiplier=100
    )

    assert res.success is True
    assert res.starter_deck_updated is True
    assert os.path.isfile(out_iso)

    # Read back compiled ISO and verify starter deck in both SLUS and WA_MRG
    compiled_disc = PS1DiscImage(out_iso)
    compiled_exe = compiled_disc.extract_file("SLUS_014.11")
    compiled_wa = compiled_disc.extract_file("DATA/WA_MRG.MRG")

    reloaded_starter = StarterDeckDatabase()
    loaded_slots = reloaded_starter.load_from_exe(compiled_exe)
    assert loaded_slots == STARTER_DECK_SLOTS
    assert reloaded_starter.get_weight(35) == 300

    # Reload from compiled WA_MRG: verify authentic 7 pools are saved in DATA/WA_MRG.MRG
    pools_loaded = reloaded_starter.load_from_wa(compiled_wa)
    assert pools_loaded == 7
    # Card #35 was assigned to its routed pool (Pool 1)
    p_idx = starter_db.route_card_to_pool(35)
    dm_pool_w = reloaded_starter.get_pool_weight(35, p_idx)
    assert dm_pool_w > 0
    assert reloaded_starter.get_authentic_probability_in_deck(35) > 0.0


def test_starter_deck_wa_pools_load_save():
    """Verify authentic 7 pools load and save in WA_MRG format."""
    db = StarterDeckDatabase()
    assert len(db.pools) == 7
    # In vanilla, Raigeki (#337) and Dark Hole (#336) are in Pool 4 with weight 1024 / 2048 (50% each)
    assert db.get_pool_weight(336, 4) == 1024
    assert db.get_pool_weight(337, 4) == 1024
    assert db.get_authentic_probability_in_deck(336) == 50.0
    assert db.get_authentic_probability_in_deck(337) == 50.0

    # Guaranteed Blue-Eyes White Dragon (#1) in Pool 3
    db.set_pool_card_weight(3, 1, 2048)
    assert db.get_pool_weight(1, 3) == 2048
    assert db.get_authentic_probability_in_deck(1) == 100.0

    # Mock WA buffer and save
    mock_wa = bytearray(0x1000000)  # 16 MB
    written = db.save_to_wa(mock_wa)
    assert written == 7 * 1446

    # Reload from mock WA buffer
    db2 = StarterDeckDatabase()
    db2.reset_to_vanilla()
    assert db2.get_pool_weight(1, 3) == 0

    loaded = db2.load_from_wa(bytes(mock_wa))
    assert loaded == 7
    assert db2.get_pool_weight(1, 3) == 2048
    assert db2.get_authentic_probability_in_deck(1) == 100.0


