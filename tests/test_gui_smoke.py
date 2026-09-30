import pytest
from ui.gui import ROMSuiteGUI, UI_THEME_PRESETS
from core.card_renderer import FRAME_THEMES, apply_frame_preset

def test_gui_initialization():
    app = ROMSuiteGUI()
    tab_names = [app.notebook.tab(i, "text").strip() for i in range(app.notebook.index("end"))]
    assert any("Mazo Inicial" in t for t in tab_names)
    assert any("Oponentes" in t for t in tab_names)
    assert any("Drops" in t for t in tab_names)
    assert any("Colores" in t for t in tab_names)
    assert any("Campos" in t for t in tab_names)
    assert len(app.starter_deck_db.slots) == 1024

    # Test Opponent Fusions population (Fix verification)
    app._populate_opponents_tree()
    if not app.deck_db.get(1):
        from core.decks import DuelistDeck
        deck = DuelistDeck(duelist_id=1)
        deck.cards[:5] = [1, 2, 3, 4, 5]
        app.deck_db.decks.append(deck)
    app.active_deck = app.deck_db.get(1)
    if not app.fusion_db.fusions:
        app.fusion_db.fusions[(1, 2)] = 3

    app._refresh_opponent_fusions_view()
    fusion_items = app.opp_fusions_tree.get_children()
    assert len(fusion_items) > 0, "CPU fusions tree should contain fusions for Simon Muran!"

    # Test Card Description and Name field editing
    app.active_card = app.get_card_object(1)
    app.curr_name_var.set("Blue-Eyes Ultimate Shin")
    app.curr_desc_text.delete("1.0", "end")
    app.curr_desc_text.insert("1.0", "Dragón Blanco Legendario")
    app._render_current_card_from_ui()
    app._on_save_card_changes()
    assert app.active_card.name == "Blue-Eyes Ultimate Shin"
    assert app.active_card.description == "Dragón Blanco Legendario"

    # Test Quick Add Card to Starter Deck
    app.quick_add_starter_var.set("722")
    app._on_quick_add_starter_card()
    assert app.starter_deck_db.get_weight(722) >= 10

    # Test direct card probability prompt dialog (focused dialog, not search catalog)
    app.active_card = app.get_card_object(35)
    app._on_prompt_add_card_to_starter(card_id=35)
    import tkinter as tk
    top_dlgs = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(top_dlgs) > 0
    prob_dlg = top_dlgs[-1]
    assert "Mazo Inicial" in prob_dlg.title()
    assert "035" in prob_dlg.title()
    prob_dlg.destroy()

    # Test Duel Fields Tab switching, test monster stats, and presets
    app.field_selector_var.set("3: ⛰️ Montaña (Mountain #303 - Dragón, Bestia Alada, Trueno)")
    app._on_field_selected()
    assert app.selected_field_id == 3
    assert "BONIFICACIÓN" in app.field_boost_info_var.get()

    app.field_preset_var.set("Cyber Neón 3D / Tron")
    app._on_apply_field_preset()
    assert app.field_spells_db.get_field(3).colors["grid"] == "#33CCFF"

    # Test Color Studio & Theme changes
    app._apply_ui_theme(UI_THEME_PRESETS["Oro Faraónico / Rompecabezas"])
    apply_frame_preset("Anime Clásico Duel Monsters")
    app._render_color_preview_card()

    app.destroy()

