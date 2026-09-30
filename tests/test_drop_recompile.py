"""
Integration test for Drop Database modification, auto-normalization, and ISO recompilation.
"""

import os
import struct
import pytest

from core.cdrom import PS1DiscImage
from core.cards import CardDatabase
from core.fusions import FusionDatabase
from core.decks import DeckDatabase
from core.drops import DropDatabase, POOL_TARGET_SUM
from core.builder import DiscRecompiler

DREAM_ISO   = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso"
VANILLA_ISO = r"C:\Users\zeus_\Downloads\VanillaExpress.iso"


@pytest.mark.skipif(not (os.path.isfile(DREAM_ISO) and os.path.isfile(VANILLA_ISO)),
                    reason="Reference ISOs not available")
def test_drop_modification_and_recompile(tmp_path):
    out_iso = str(tmp_path / "test_drops_out.iso")

    disc_d = PS1DiscImage(DREAM_ISO)
    wa_d = disc_d.extract_file("DATA/WA_MRG.MRG")
    exe_d = disc_d.extract_file("SLUS_014.11")

    card_db = CardDatabase()
    card_db.load_from_exe_and_wa(exe_d, wa_d)

    fusion_db = FusionDatabase()
    fusion_db.load_from_wa(wa_d)

    deck_db = DeckDatabase()
    deck_db.load_from_wa_and_exe(wa_d, exe_d)

    drop_db = DropDatabase()
    drop_db.load_from_wa(wa_d, exe_d)

    # Let's modify Simon Muran (Duelist 1) SA-POW:
    # Set Meteor B. Dragon (Card 397) drop weight to 100
    simon = drop_db.get_duelist(1)
    assert simon is not None
    simon.set_card_weight("SA-POW", 397, 100)
    # Auto-normalize so sum is 2048
    ok = simon.normalize_pool("SA-POW")
    assert ok is True
    assert simon.get_pool_sum("SA-POW") == 2048
    actual_weight = simon.get_card_weight("SA-POW", 397)
    assert actual_weight > 0

    # Build the recompiled ISO
    res = DiscRecompiler.build(
        base_disc_path=DREAM_ISO,
        output_image_path=out_iso,
        card_db=card_db,
        fusion_db=fusion_db,
        deck_db=deck_db,
        drop_db=drop_db,
        express_ref_disc_path=VANILLA_ISO,
        drop_multiplier=100
    )

    assert res.success is True
    assert res.drops_synchronized == 39
    assert res.validation.get("duelist_drop_pools_valid") is True
    assert res.validation.get("valid_drop_duelists_count") == 39
    assert res.validation.get("audio_queue_trigger_ok") is True

    # Verify the compiled image contains our custom drop
    out_disc = PS1DiscImage(out_iso)
    new_wa = out_disc.extract_file("DATA/WA_MRG.MRG")
    new_drop_db = DropDatabase()
    new_drop_db.load_from_wa(new_wa)

    simon_new = new_drop_db.get_duelist(1)
    assert simon_new.get_card_weight("SA-POW", 397) == actual_weight
    assert simon_new.get_pool_sum("SA-POW") == 2048
