"""
Unit tests for authentic card graphics extraction and injection from WA_MRG.
"""

import os
import pytest
from PIL import Image

from core.cdrom import PS1DiscImage
from core.card_graphics import (
    CardGraphicsDatabase,
    bgr555_to_rgb,
    rgb_to_bgr555,
    LARGE_WIDTH,
    LARGE_HEIGHT
)

DREAM_ISO = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso"


def test_bgr555_conversion():
    # Test pure white
    assert bgr555_to_rgb(0x7FFF) == (248, 248, 248)
    assert rgb_to_bgr555(248, 248, 248) == 0x7FFF

    # Test pure black
    assert bgr555_to_rgb(0x0000) == (0, 0, 0)
    assert rgb_to_bgr555(0, 0, 0) == 0x0000

    # Test pure red, green, blue roundtrip
    r_val = rgb_to_bgr555(248, 0, 0)
    assert bgr555_to_rgb(r_val) == (248, 0, 0)

    g_val = rgb_to_bgr555(0, 248, 0)
    assert bgr555_to_rgb(g_val) == (0, 248, 0)

    b_val = rgb_to_bgr555(0, 0, 248)
    assert bgr555_to_rgb(b_val) == (0, 0, 248)


@pytest.mark.skipif(not os.path.isfile(DREAM_ISO), reason="Dream Mod ISO not found")
def test_extract_authentic_card_art():
    disc = PS1DiscImage(DREAM_ISO)
    wa = disc.extract_file("DATA/WA_MRG.MRG")

    gfx_db = CardGraphicsDatabase()
    gfx_db.set_wa_data(wa)

    assert gfx_db.has_data() is True

    # Card 1: Blue-Eyes White Dragon
    art1 = gfx_db.get_card_art(1)
    assert art1 is not None
    assert art1.size == (LARGE_WIDTH, LARGE_HEIGHT)

    # Card 35: Dark Magician
    art35 = gfx_db.get_card_art(35)
    assert art35 is not None
    assert art35.size == (LARGE_WIDTH, LARGE_HEIGHT)

    # Card 722: Dark Magic Ritual
    art722 = gfx_db.get_card_art(722)
    assert art722 is not None
    assert art722.size == (LARGE_WIDTH, LARGE_HEIGHT)


@pytest.mark.skipif(not os.path.isfile(DREAM_ISO), reason="Dream Mod ISO not found")
def test_custom_art_injection():
    disc = PS1DiscImage(DREAM_ISO)
    wa = bytearray(disc.extract_file("DATA/WA_MRG.MRG"))

    gfx_db = CardGraphicsDatabase()
    gfx_db.set_wa_data(bytes(wa))

    # Create a custom test image (e.g. golden yellow square)
    custom_img = Image.new("RGB", (LARGE_WIDTH, LARGE_HEIGHT), (255, 215, 0))
    gfx_db.set_custom_art(1, custom_img)

    # Injected into WA_MRG
    injected_count = gfx_db.apply_to_wa(wa)
    assert injected_count == 1

    # Reload from the modified WA_MRG
    gfx_db2 = CardGraphicsDatabase()
    gfx_db2.set_wa_data(bytes(wa))
    extracted = gfx_db2.get_card_art(1)

    assert extracted is not None
    assert extracted.size == (LARGE_WIDTH, LARGE_HEIGHT)
    # Check that center pixel is golden yellow (quantized to BGR555)
    center_color = extracted.getpixel((50, 48))
    assert center_color[0] >= 240
    assert center_color[1] >= 200
