"""
Unit tests for CardCanvasRenderer and export_card_to_png.
"""

import os
from core.cards import Card
from core.card_renderer import get_card_theme, calculate_level_stars, export_card_to_png


def test_card_theme_and_stars():
    # Blue-Eyes (ATK 3000, DEF 2500, Type Dragon=0)
    be = Card(1, "Blue-Eyes White Dragon", atk=3000, def_=2500, type_id=0)
    theme = get_card_theme(be.type_id)
    assert theme["frame"] == "#C69248"  # Normal monster frame
    assert calculate_level_stars(be) == 8

    # Dark Hole (Magic=20)
    dh = Card(94, "Dark Hole", atk=0, def_=0, type_id=20)
    m_theme = get_card_theme(dh.type_id)
    assert m_theme["frame"] == "#198A62"  # Magic frame
    assert calculate_level_stars(dh) == 0

    # Widespread Ruin (Trap=21)
    wr = Card(686, "Widespread Ruin", atk=0, def_=0, type_id=21)
    t_theme = get_card_theme(wr.type_id)
    assert t_theme["frame"] == "#A9236F"  # Trap frame
    assert calculate_level_stars(wr) == 0


def test_export_card_png(tmp_path):
    out_png = str(tmp_path / "test_blue_eyes.png")
    be = Card(1, "Blue-Eyes White Dragon", atk=3000, def_=2500, type_id=0, password="89631139", star_cost=999999)
    ok = export_card_to_png(be, out_png)
    assert ok is True
    assert os.path.isfile(out_png)
    assert os.path.getsize(out_png) > 1000


def test_card_canvas_renderer():
    import tkinter as tk
    from core.card_renderer import CardCanvasRenderer
    from core.card_graphics import CardGraphicsDatabase

    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        return

    canvas = tk.Canvas(root, width=210, height=305)
    gdb = CardGraphicsDatabase()
    renderer = CardCanvasRenderer(canvas, graphics_db=gdb)

    be = Card(1, "Blue-Eyes White Dragon", atk=3000, def_=2500, type_id=0, gs1=1, gs2=2)
    renderer.render(be, width=210, height=305)
    items = canvas.find_all()
    assert len(items) > 5

    # Test Magic card
    dh = Card(94, "Dark Hole", atk=0, def_=0, type_id=20)
    renderer.render(dh, width=200, height=290)
    items_dh = canvas.find_all()
    assert len(items_dh) > 5

    root.destroy()
