"""
Test proving that DiscRecompiler can compile a full Drop x100 ROM
WITHOUT requiring VanillaExpress.iso (100% standalone mode).
"""

import os
import pytest

from core.cdrom import PS1DiscImage
from core.cards import CardDatabase
from core.fusions import FusionDatabase
from core.decks import DeckDatabase
from core.drops import DropDatabase
from core.builder import DiscRecompiler

DREAM_ISO = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso"


@pytest.mark.skipif(not os.path.isfile(DREAM_ISO), reason="Dream Mod ISO not found")
def test_recompile_without_vanilla_iso(tmp_path):
    out_iso = str(tmp_path / "standalone_drop100.iso")

    disc = PS1DiscImage(DREAM_ISO)
    exe = disc.extract_file("SLUS_014.11")
    wa  = disc.extract_file("DATA/WA_MRG.MRG")

    card_db = CardDatabase()
    card_db.load_from_exe_and_wa(exe, wa)

    fusion_db = FusionDatabase()
    fusion_db.load_from_wa(wa)

    deck_db = DeckDatabase()
    deck_db.load_from_wa_and_exe(wa, exe)

    drop_db = DropDatabase()
    drop_db.load_from_wa(wa, exe)

    # Note: express_ref_disc_path=None! NO VANILLA ISO NEEDED!
    res = DiscRecompiler.build(
        base_disc_path=DREAM_ISO,
        output_image_path=out_iso,
        card_db=card_db,
        fusion_db=fusion_db,
        deck_db=deck_db,
        drop_db=drop_db,
        express_ref_disc_path=None,
        drop_multiplier=100
    )

    assert res.success is True
    assert res.patches_applied >= 6
    assert res.validation.get("audio_queue_trigger_ok") is True
    assert res.validation.get("post_duel_hook_ok") is True
    assert res.validation.get("victory_hook_ok") is True
    assert res.validation.get("victory_return_ok") is True
    assert res.validation.get("dispatcher_present") is True
    assert res.validation.get("block2_payload_loader_ok") is True
    assert res.validation.get("duelist_drop_pools_valid") is True
    assert os.path.isfile(out_iso)
