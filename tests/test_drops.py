"""
Unit tests for the DropDatabase and probability engine.
"""

import os
import pytest
from core.drops import DropDatabase, DuelistDrops, POOL_TARGET_SUM, POOL_NAMES
from core.cdrom import PS1DiscImage

VANILLA_ISO = r"C:\Users\zeus_\Downloads\VanillaExpress.iso"
DREAM_ISO   = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso"


def test_duelist_drops_basic():
    d = DuelistDrops(1)
    assert d.duelist_id == 1
    assert d.name == "Simon Muran"
    assert d.get_pool_sum("SA-POW") == 0
    assert d.get_card_weight("SA-POW", 1) == 0
    assert d.get_card_percentage("SA-POW", 1) == 0.0

    d.set_card_weight("SA-POW", 1, 100)
    assert d.get_card_weight("SA-POW", 1) == 100
    assert abs(d.get_card_percentage("SA-POW", 1) - (100 / 2048.0 * 100.0)) < 1e-4

    d.set_card_weight("SA-POW", 2, 300)
    assert d.get_pool_sum("SA-POW") == 400

    # Test normalization
    ok = d.normalize_pool("SA-POW")
    assert ok is True
    assert d.get_pool_sum("SA-POW") == POOL_TARGET_SUM


@pytest.mark.skipif(not os.path.isfile(VANILLA_ISO), reason="VanillaExpress.iso not found")
def test_load_vanilla_express_drops():
    disc = PS1DiscImage(VANILLA_ISO)
    wa = disc.extract_file("DATA/WA_MRG.MRG")
    slus = disc.extract_file("SLUS_014.11")

    db = DropDatabase()
    loaded = db.load_from_wa(wa, slus)
    assert loaded == 39
    assert db.is_16bit is False

    # Check Simon Muran
    simon = db.get_duelist(1)
    assert simon is not None
    assert simon.name == "Simon Muran"
    assert simon.get_pool_sum("SA-POW") == 2048
    assert simon.get_pool_sum("BCD-POW") == 2048
    assert simon.get_pool_sum("SA-TEC") == 2048
    assert simon.get_pool_sum("BCD-TEC") == 2048

    # Search for card drops
    # Card 9 is dropped by Simon Muran in SA-POW (weight 72)
    results = db.search_card_drops(9)
    assert len(results) > 0
    simon_drops = [r for r in results if r["duelist_id"] == 1 and r["pool_name"] == "SA-POW"]
    assert len(simon_drops) == 1
    assert simon_drops[0]["weight"] == 72
    assert abs(simon_drops[0]["percentage"] - (72 / 2048.0 * 100.0)) < 1e-4


@pytest.mark.skipif(not os.path.isfile(DREAM_ISO), reason="Dream Mod ISO not found")
def test_load_dream_mod_drops():
    disc = PS1DiscImage(DREAM_ISO)
    wa = disc.extract_file("DATA/WA_MRG.MRG")
    slus = disc.extract_file("SLUS_014.11")

    db = DropDatabase()
    loaded = db.load_from_wa(wa, slus)
    assert loaded == 39
    assert db.is_16bit is True

    for d in db.duelists:
        for p in POOL_NAMES:
            assert d.get_pool_sum(p) == 2048, f"Duelist {d.name} {p} does not sum to 2048!"

    # Search for Meteor B. Dragon (Card 397)
    mbd_drops = db.search_card_drops(397)
    assert len(mbd_drops) > 0
    # Every drop should have valid percentage
    for r in mbd_drops:
        assert r["weight"] > 0
        assert r["percentage"] > 0.0
