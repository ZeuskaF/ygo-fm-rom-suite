"""
Graphical User Interface (GUI) for Yu-Gi-Oh! Forbidden Memories ROM Suite & ISO Recompiler.
Modern multi-tab visual editor for Cards, Fusions, and Engine Options,
with real-time filtering, 1-click mod asset import, and verified Mode 2 Form 1 ISO recompilation.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser, simpledialog
from typing import Optional

from core.cdrom import PS1DiscImage
from core.cards import Card, CardDatabase
from core.fusions import FusionDatabase
from core.decks import DeckDatabase, DuelistDeck
from core.drops import DropDatabase, POOL_NAMES, POOL_TARGET_SUM, RANK_INFO, DuelistDrops
from core.starter_deck import StarterDeckDatabase, STARTER_DECK_SLOTS
from core.card_graphics import CardGraphicsDatabase
from core.card_renderer import (
    CardCanvasRenderer, export_card_to_png,
    FRAME_THEMES, DEFAULT_FRAME_THEMES, FRAME_COLOR_PRESETS,
    GUARDIAN_STAR_DATA, DEFAULT_GUARDIAN_STAR_DATA,
    apply_frame_preset, reset_frame_colors
)
from core.builder import DiscRecompiler
from core.card_data import CARD_TYPES, GUARDIAN_STARS, CARD_NAMES, OPPONENT_NAMES, get_card_name
from core.field_spells import (
    FieldSpellDatabase, FieldSpellData, DEFAULT_FIELD_COLORS,
    FIELD_PRESETS, FIELD_METADATA, ARENA_WA_OFFSETS, ARENA_STRIDE
)
from core.duel_board_renderer import DuelBoardRenderer


UI_THEME_PRESETS = {
    "Dark Cyber Cyan (Por Defecto)": {
        "bg": "#1E1E24",
        "panel_bg": "#282830",
        "accent": "#00D2FF",
        "btn_primary": "#007ACC",
        "fg": "#EDEDED",
        "tab_bg": "#2C2C34"
    },
    "Oro Faraónico / Rompecabezas": {
        "bg": "#1A1710",
        "panel_bg": "#2A2518",
        "accent": "#FFD700",
        "btn_primary": "#C69214",
        "fg": "#FFF8E7",
        "tab_bg": "#332D1E"
    },
    "Mago Oscuro / Púrpura Arcano": {
        "bg": "#181024",
        "panel_bg": "#261A38",
        "accent": "#C77DFF",
        "btn_primary": "#7B2CBF",
        "fg": "#F8F0FC",
        "tab_bg": "#33224C"
    },
    "KaibaCorp Blue / Ojos Azules": {
        "bg": "#0D1826",
        "panel_bg": "#16283D",
        "accent": "#48CAE4",
        "btn_primary": "#0077B6",
        "fg": "#EDF6F9",
        "tab_bg": "#1E3550"
    },
    "Retro PlayStation 1999 (Gris)": {
        "bg": "#262626",
        "panel_bg": "#363636",
        "accent": "#E0E0E0",
        "btn_primary": "#4A4A4A",
        "fg": "#FFFFFF",
        "tab_bg": "#404040"
    },
    "Dragón Negro de Ojos Rojos (Carmesí)": {
        "bg": "#221010",
        "panel_bg": "#361A1A",
        "accent": "#FF4D4D",
        "btn_primary": "#B71C1C",
        "fg": "#FFF0F0",
        "tab_bg": "#4A2020"
    }
}


class ToolTip:
    """Floating hover tooltip for compact UI elements."""
    def __init__(self, widget, text_provider):
        self.widget = widget
        self.text_provider = text_provider
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window:
            return
        txt = self.text_provider() if callable(self.text_provider) else str(self.text_provider)
        if not txt:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tw, text=txt, justify=tk.LEFT, background="#14141A", foreground="#00D2FF",
            relief=tk.SOLID, borderwidth=1, font=("Segoe UI", 9), padx=8, pady=4
        )
        lbl.pack()

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class ROMSuiteGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Yu-Gi-Oh! Forbidden Memories - ROM Suite & ISO Recompiler")
        self.geometry("1120x760")
        self.minsize(980, 660)

        # In-memory databases
        self.card_db = CardDatabase()
        self.fusion_db = FusionDatabase()
        self.deck_db = DeckDatabase()
        self.drop_db = DropDatabase()
        self.starter_deck_db = StarterDeckDatabase()
        self.graphics_db = CardGraphicsDatabase()
        self.base_iso_path = ""
        self.ref_express_path = r"C:\Users\zeus_\Downloads\VanillaExpress.iso"
        if not os.path.isfile(self.ref_express_path):
            self.ref_express_path = ""

        # UI State variables
        self.base_path_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Esperando selección de imagen ISO/BIN...")
        self.cards_count_var = tk.StringVar(value="Cartas: 0 / 722")
        self.fusions_count_var = tk.StringVar(value="Fusiones: 0")
        self.search_card_var = tk.StringVar(value="")
        self.filter_type_var = tk.StringVar(value="Todos")
        self.search_fusion_var = tk.StringVar(value="")

        # Starter Deck UI state (Authentic 7 PS1 Pools)
        self.starter_search_var = tk.StringVar(value="")
        self.starter_pool_filter_var = tk.StringVar(value="Todos los Pools (Global)")
        self.starter_slots_sum_var = tk.StringVar(value="7 Pools Activos (Total: 40 cartas en mazo)")
        self.starter_count_var = tk.StringVar(value="Cartas distintas en pool: 0")
        self.selected_starter_card_id = 0
        self.edit_starter_card_name_var = tk.StringVar(value="—")
        self.edit_starter_pool_var = tk.StringVar(value="Pool 0: Monstruos Menores (16 cartas)")
        self.edit_starter_weight_var = tk.StringVar(value="0")
        self.edit_starter_pool_pct_var = tk.StringVar(value="0.00 %")
        self.edit_starter_deck_prob_var = tk.StringVar(value="0.00 %")
        self.edit_starter_expected_var = tk.StringVar(value="0.00 copias")
        self.quick_add_starter_var = tk.StringVar(value="")

        # Duel Fields / Field Spells state
        self.field_spells_db = FieldSpellDatabase()
        self.selected_field_id = 0
        self.field_selector_var = tk.StringVar(value="0: 🏛️ Normal (Coliseo Egipcio)")
        self.field_preset_var = tk.StringVar(value="Forbidden Memories Clásico (PS1)")
        self.field_test_monster_var = tk.StringVar(value="001: Blue-Eyes White Dragon [Dragon - 3000/2500]")
        self.field_test_slot_var = tk.StringVar(value="M3 (Centro)")
        self.field_boost_info_var = tk.StringVar(value="Terreno Neutral. Sin bonificaciones ni penalizaciones.")
        self.field_image_path_var = tk.StringVar(value="Sin textura personalizada (Procedural)")
        self._field_swatch_widgets = {}

        # Opponent Pool and Fusions view state
        self.opp_pool_rank_var = tk.StringVar(value="SA-POW")
        self.opp_pool_search_var = tk.StringVar(value="")
        self.opp_pool_sum_var = tk.StringVar(value="Suma Pool: 2048 / 2048 (100.0%)")
        self.opp_fus_filter_mode_var = tk.StringVar(value="Ambos materiales en Mazo (Invocables)")
        self.opp_fus_search_var = tk.StringVar(value="")
        self.opp_fus_count_var = tk.StringVar(value="0 fusiones")

        # Color Studio & Theme state
        self.theme_preset_var = tk.StringVar(value="Dark Cyber Cyan (Por Defecto)")
        self.frame_preset_var = tk.StringVar(value="Clásico FM (PS1)")
        self.color_preview_card_var = tk.StringVar(value="Monstruo Normal (Blue-Eyes White Dragon #001)")

        # Drop tables UI state
        self.selected_drop_duelist_id = 1
        self.selected_drop_pool = "SA-POW"
        self.selected_drop_card_id = 0
        self.drop_pool_sum_var = tk.StringVar(value="Suma del Pool: 2048 / 2048 (100.0%)")
        self.drop_count_var = tk.StringVar(value="Cartas en Pool: 0")
        self.drop_search_var = tk.StringVar(value="")
        self.drop_only_active_var = tk.BooleanVar(value=True)
        self.edit_drop_card_name_var = tk.StringVar(value="—")
        self.edit_drop_weight_var = tk.StringVar(value="0")
        self.edit_drop_pct_var = tk.StringVar(value="0.00 %")
        self.reverse_search_var = tk.StringVar(value="")
        self.reverse_rank_filter_var = tk.StringVar(value="Todos los rangos")
        self.reverse_results_count_var = tk.StringVar(value="Coincidencias: 0")

        # Engine settings
        self.drop_multiplier_var = tk.StringVar(value="100")
        self.fast_exit_var = tk.BooleanVar(value=False)
        self.trunk_deposit_var = tk.BooleanVar(value=True)
        self.preserve_ai_var = tk.BooleanVar(value=True)
        self.import_cpu_ai_var = tk.BooleanVar(value=True)
        self.imported_mod_path = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso" if os.path.isfile(r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso") else ""

        # Card inspector variables
        self.curr_card_id_var = tk.StringVar(value="#---")
        self.curr_name_var = tk.StringVar(value="---")
        self.curr_atk_var = tk.StringVar(value="0")
        self.curr_def_var = tk.StringVar(value="0")
        self.curr_type_var = tk.StringVar(value="Dragon")
        self.curr_gs1_var = tk.StringVar(value="None")
        self.curr_gs2_var = tk.StringVar(value="None")
        self.curr_password_var = tk.StringVar(value="00000000")
        self.curr_cost_var = tk.StringVar(value="0")
        self.active_card: Optional[Card] = None

        # Build style and layout
        self._setup_styles()
        self._build_ui()

        # Auto-cargar Dream Mod como base por defecto (contiene IA completa)
        # Vanilla Express se usa solo como referencia para drop/victoria.
        dream_default = r"C:\Users\zeus_\Downloads\Yu-Gi-Oh FM  Dream Vanilla 15x.iso"
        vanilla_default = r"C:\Users\zeus_\Downloads\VanillaExpress.iso"

        if os.path.isfile(dream_default):
            self.base_path_var.set(dream_default)
            self.iso_badge_var.set(f"📁 [ROM]: {os.path.basename(dream_default)}")
            self._async_load_base_iso(dream_default)
        elif os.path.isfile(vanilla_default):
            self.base_path_var.set(vanilla_default)
            self.iso_badge_var.set(f"📁 [ROM]: {os.path.basename(vanilla_default)}")
            self._async_load_base_iso(vanilla_default)

    def _setup_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.configure(bg="#1E1E24")
        self.style.configure("TFrame", background="#1E1E24")
        self.style.configure("TLabelframe", background="#1E1E24", foreground="#E0E0E0")
        self.style.configure("TLabelframe.Label", background="#1E1E24", foreground="#00D2FF", font=("Segoe UI", 10, "bold"))
        self.style.configure("TLabel", background="#1E1E24", foreground="#EDEDED", font=("Segoe UI", 9))
        self.style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=5)
        self.style.configure("Action.TButton", font=("Segoe UI", 11, "bold"), padding=8, background="#007ACC", foreground="#FFFFFF")
        self.style.configure("Green.TButton", font=("Segoe UI", 11, "bold"), padding=8, background="#2E7D32", foreground="#FFFFFF")
        self.style.configure("Purple.TButton", font=("Segoe UI", 9, "bold"), padding=6, background="#6A1B9A", foreground="#FFFFFF")
        self.style.configure("TNotebook", background="#1E1E24", borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#2C2C34", foreground="#C0C0C0", padding=[12, 6], font=("Segoe UI", 9, "bold"))
        self.style.map("TNotebook.Tab", background=[("selected", "#007ACC")], foreground=[("selected", "#FFFFFF")])
        self.style.configure("Treeview", background="#282830", foreground="#FFFFFF", fieldbackground="#282830", font=("Segoe UI", 9), rowheight=24)
        self.style.configure("Treeview.Heading", background="#1E1E24", foreground="#00D2FF", font=("Segoe UI", 9, "bold"))
        self.style.map("Treeview", background=[("selected", "#005A9E")])

    def get_card_display_name(self, cid: int) -> str:
        """Returns the actual card name prioritizing loaded in-memory card stats."""
        c = self.card_db.get(cid)
        if c and c.name:
            return c.name
        return CARD_NAMES.get(cid, f"Carta #{cid:03d}")

    def get_card_object(self, cid: int) -> Card:
        """Returns the full Card object if loaded, or a valid populated fallback."""
        c = self.card_db.get(cid)
        if c:
            return c
        name = CARD_NAMES.get(cid, f"Carta #{cid:03d}")
        return Card(card_id=cid, name=name)

    def _build_ui(self):
        # 1. Top Header & Unified Controls Bar
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=14, pady=(8, 4))

        top_row = ttk.Frame(top_frame)
        top_row.pack(fill=tk.X)

        title_lbl = tk.Label(
            top_row,
            text="Yu-Gi-Oh! Forbidden Memories - ROM Suite",
            font=("Segoe UI", 12, "bold"),
            fg="#00D2FF",
            bg="#1E1E24"
        )
        title_lbl.pack(side=tk.LEFT)

        # Path Badge (Compact indicator with tooltip showing full path)
        self.iso_badge_var = tk.StringVar(value="📁 [ROM Base]: Sin archivo cargado")
        self.iso_badge = tk.Label(
            top_row,
            textvariable=self.iso_badge_var,
            font=("Segoe UI", 9, "bold"),
            fg="#E0E0E0",
            bg="#2A2A36",
            padx=8, pady=3,
            cursor="hand2",
            relief=tk.RIDGE
        )
        self.iso_badge.pack(side=tk.LEFT, padx=10)
        self.iso_tooltip = ToolTip(self.iso_badge, lambda: f"Ruta completa de la ROM base cargada:\n{self.base_path_var.get() or 'Ninguna'}")

        # Unified Open Button
        open_btn = ttk.Button(top_row, text="📂 Cargar ROM / Mod", command=self._on_browse_base_iso)
        open_btn.pack(side=tk.LEFT, padx=3)

        # Rank Guide Button
        guide_btn = ttk.Button(top_row, text="📖 Guía Ranks", command=self._show_rank_guide_dialog)
        guide_btn.pack(side=tk.LEFT, padx=3)

        # Prominent Compile Button permanently visible at top!
        self.compile_btn = ttk.Button(
            top_row,
            text="⚡ GENERAR NUEVA ROM",
            style="Green.TButton",
            command=self._on_compile_rom
        )
        self.compile_btn.pack(side=tk.RIGHT, padx=4)

        # 2. Main Tabs Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        self._build_cards_tab()
        self._build_fusions_tab()
        self._build_opponents_tab()
        self._build_drops_tab()
        self._build_starter_deck_tab()
        self._build_fields_tab()
        self._build_colors_tab()
        self._build_engine_tab()
        self._build_logs_tab()

        # 3. Bottom Recompile & Status Bar
        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill=tk.X, padx=14, pady=(2, 6))

        self.progress_bar = ttk.Progressbar(bottom_frame, mode="determinate", length=220)
        self.progress_bar.pack(side=tk.RIGHT, padx=(8, 0))

        self.status_lbl = tk.Label(
            bottom_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 9, "italic"),
            fg="#A0A0A0",
            bg="#1E1E24"
        )
        self.status_lbl.pack(side=tk.LEFT, anchor="w", fill=tk.X, expand=True)

    def _build_cards_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" 🃏 Cartas (001-722) ")

        # Search and Filter Bar
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(bar, text="Buscar:").pack(side=tk.LEFT, padx=(0, 4))
        search_ent = ttk.Entry(bar, textvariable=self.search_card_var, width=22)
        search_ent.pack(side=tk.LEFT, padx=4)
        search_ent.bind("<KeyRelease>", lambda e: self._filter_cards_tree())

        ttk.Label(bar, text="Tipo:").pack(side=tk.LEFT, padx=(12, 4))
        type_combo = ttk.Combobox(bar, textvariable=self.filter_type_var, values=["Todos"] + CARD_TYPES, state="readonly", width=14)
        type_combo.pack(side=tk.LEFT, padx=4)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._filter_cards_tree())

        ttk.Label(bar, textvariable=self.cards_count_var, foreground="#00D2FF").pack(side=tk.RIGHT, padx=8)

        # Main splitter (Tree on left, Editor on right)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Left: Cards Treeview
        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=3)

        cols = ("id", "name", "atk", "def", "type", "gs1", "gs2", "cost")
        self.cards_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.cards_tree.heading("id", text="ID")
        self.cards_tree.heading("name", text="Nombre de Carta")
        self.cards_tree.heading("atk", text="ATK")
        self.cards_tree.heading("def", text="DEF")
        self.cards_tree.heading("type", text="Tipo")
        self.cards_tree.heading("gs1", text="Estrella 1")
        self.cards_tree.heading("gs2", text="Estrella 2")
        self.cards_tree.heading("cost", text="Coste")

        self.cards_tree.column("id", width=48, anchor="center")
        self.cards_tree.column("name", width=180, anchor="w")
        self.cards_tree.column("atk", width=60, anchor="center")
        self.cards_tree.column("def", width=60, anchor="center")
        self.cards_tree.column("type", width=100, anchor="center")
        self.cards_tree.column("gs1", width=75, anchor="center")
        self.cards_tree.column("gs2", width=75, anchor="center")
        self.cards_tree.column("cost", width=75, anchor="center")

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.cards_tree.yview)
        self.cards_tree.configure(yscrollcommand=tree_scroll.set)
        self.cards_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.cards_tree.bind("<<TreeviewSelect>>", self._on_card_selected)

        # Right: Card Inspector & Visual Card Representation
        edit_frame = ttk.LabelFrame(paned, text=" Inspector, Editor y Representación Gráfica ")
        paned.add(edit_frame, weight=3)

        split_box = ttk.Frame(edit_frame)
        split_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left Column: Form Fields
        fields = ttk.Frame(split_box)
        fields.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 10))

        # Header Info
        header_box = ttk.Frame(fields)
        header_box.pack(fill=tk.X, pady=(0, 4))
        tk.Label(header_box, textvariable=self.curr_card_id_var, font=("Segoe UI", 12, "bold"), fg="#00D2FF", bg="#1E1E24").pack(side=tk.LEFT)

        # Card Name Editable Row
        name_row = ttk.Frame(fields)
        name_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(name_row, text="Nombre:").pack(side=tk.LEFT, padx=(0, 4))
        self.card_name_entry = ttk.Entry(name_row, textvariable=self.curr_name_var, font=("Segoe UI", 9, "bold"), width=24)
        self.card_name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        self.card_name_entry.bind("<KeyRelease>", lambda e: self._render_current_card_from_ui())

        # ATK / DEF Row
        stat_row = ttk.Frame(fields)
        stat_row.pack(fill=tk.X, pady=4)
        ttk.Label(stat_row, text="ATK:").pack(side=tk.LEFT)
        e_atk = ttk.Entry(stat_row, textvariable=self.curr_atk_var, width=7)
        e_atk.pack(side=tk.LEFT, padx=(4, 14))
        e_atk.bind("<KeyRelease>", lambda e: self._render_current_card_from_ui())

        ttk.Label(stat_row, text="DEF:").pack(side=tk.LEFT)
        e_def = ttk.Entry(stat_row, textvariable=self.curr_def_var, width=7)
        e_def.pack(side=tk.LEFT, padx=4)
        e_def.bind("<KeyRelease>", lambda e: self._render_current_card_from_ui())

        # Type Dropdown
        type_row = ttk.Frame(fields)
        type_row.pack(fill=tk.X, pady=5)
        ttk.Label(type_row, text="Tipo:").pack(side=tk.LEFT)
        cb_type = ttk.Combobox(type_row, textvariable=self.curr_type_var, values=CARD_TYPES, state="readonly", width=16)
        cb_type.pack(side=tk.LEFT, padx=6)
        cb_type.bind("<<ComboboxSelected>>", lambda e: self._render_current_card_from_ui())

        # Guardian Stars Row
        gs_row = ttk.Frame(fields)
        gs_row.pack(fill=tk.X, pady=5)
        ttk.Label(gs_row, text="Estrella 1:").pack(side=tk.LEFT)
        cb_gs1 = ttk.Combobox(gs_row, textvariable=self.curr_gs1_var, values=GUARDIAN_STARS, state="readonly", width=9)
        cb_gs1.pack(side=tk.LEFT, padx=(4, 10))
        cb_gs1.bind("<<ComboboxSelected>>", lambda e: self._render_current_card_from_ui())

        ttk.Label(gs_row, text="Estrella 2:").pack(side=tk.LEFT)
        cb_gs2 = ttk.Combobox(gs_row, textvariable=self.curr_gs2_var, values=GUARDIAN_STARS, state="readonly", width=9)
        cb_gs2.pack(side=tk.LEFT, padx=4)
        cb_gs2.bind("<<ComboboxSelected>>", lambda e: self._render_current_card_from_ui())

        # Password & Cost Row
        pass_row = ttk.Frame(fields)
        pass_row.pack(fill=tk.X, pady=5)
        ttk.Label(pass_row, text="Contraseña (8 dígitos):").pack(side=tk.LEFT)
        e_pwd = ttk.Entry(pass_row, textvariable=self.curr_password_var, width=11)
        e_pwd.pack(side=tk.LEFT, padx=(6, 0))
        e_pwd.bind("<KeyRelease>", lambda e: self._render_current_card_from_ui())

        cost_row = ttk.Frame(fields)
        cost_row.pack(fill=tk.X, pady=5)
        ttk.Label(cost_row, text="Coste en Estrellas:").pack(side=tk.LEFT)
        e_cost = ttk.Entry(cost_row, textvariable=self.curr_cost_var, width=11)
        e_cost.pack(side=tk.LEFT, padx=(6, 0))
        e_cost.bind("<KeyRelease>", lambda e: self._render_current_card_from_ui())

        # Description / Effect Box
        desc_lbl_row = ttk.Frame(fields)
        desc_lbl_row.pack(fill=tk.X, pady=(6, 2))
        ttk.Label(desc_lbl_row, text="📜 Descripción / Efecto (SLUS):").pack(side=tk.LEFT)
        gen_btn = ttk.Button(desc_lbl_row, text="⚡ Asistente de Efectos...", command=self._open_effect_generator_dialog)
        gen_btn.pack(side=tk.RIGHT)

        desc_box_frame = ttk.Frame(fields)
        desc_box_frame.pack(fill=tk.X, pady=(0, 4))
        self.curr_desc_text = tk.Text(desc_box_frame, height=4, width=30, wrap=tk.WORD,
                                      bg="#141419", fg="#EDEDED", insertbackground="#00D2FF",
                                      font=("Segoe UI", 9))
        self.curr_desc_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        desc_scroll = ttk.Scrollbar(desc_box_frame, orient=tk.VERTICAL, command=self.curr_desc_text.yview)
        self.curr_desc_text.configure(yscrollcommand=desc_scroll.set)
        desc_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.curr_desc_text.bind("<KeyRelease>", lambda e: self._on_desc_text_edited())

        # Save Button
        save_card_btn = ttk.Button(fields, text="💾 Guardar Cambios en Carta", style="Action.TButton", command=self._on_save_card_changes)
        save_card_btn.pack(fill=tk.X, pady=(10, 0))

        add_to_starter_btn = ttk.Button(fields, text="🎴 Añadir al Mazo Inicial", style="Purple.TButton", command=self._on_add_inspected_card_to_starter)
        add_to_starter_btn.pack(fill=tk.X, pady=(5, 0))

        # Right Column: Authentic Forbidden Memories Visual Card Canvas
        preview_box = ttk.LabelFrame(split_box, text=" Representación Gráfica (En Juego) ")
        preview_box.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(4, 4))

        self.card_canvas = tk.Canvas(preview_box, width=250, height=365, bg="#121214", highlightthickness=1, highlightbackground="#00D2FF")
        self.card_canvas.pack(padx=8, pady=6)

        self.card_renderer = CardCanvasRenderer(self.card_canvas, graphics_db=self.graphics_db)

        art_bar = ttk.Frame(preview_box)
        art_bar.pack(fill=tk.X, padx=8, pady=(0, 4))

        load_art_btn = ttk.Button(art_bar, text="🖼️ Cargar Ilustración...", command=self._on_load_card_artwork)
        load_art_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        clear_art_btn = ttk.Button(art_bar, text="✖", width=3, command=self._on_clear_card_artwork)
        clear_art_btn.pack(side=tk.LEFT, padx=2)

        export_png_btn = ttk.Button(preview_box, text="📸 Exportar como PNG", command=self._on_export_card_png)
        export_png_btn.pack(fill=tk.X, padx=8, pady=(0, 6))

    def _build_fusions_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" ⚗️ Fusiones ")

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=10, pady=(8, 4))

        ttk.Label(bar, text="Buscar Fusión:").pack(side=tk.LEFT, padx=(0, 4))
        f_search = ttk.Entry(bar, textvariable=self.search_fusion_var, width=24)
        f_search.pack(side=tk.LEFT, padx=4)
        f_search.bind("<KeyRelease>", lambda e: self._filter_fusions_tree())

        ttk.Label(bar, textvariable=self.fusions_count_var, foreground="#00D2FF").pack(side=tk.LEFT, padx=12)

        clone_btn = ttk.Button(bar, text="📥 Importar Fusiones de Mod", style="Purple.TButton", command=self._on_import_mod_dialog)
        clone_btn.pack(side=tk.RIGHT, padx=4)

        # Action Buttons row for modifying and adding fusions
        act_bar = ttk.Frame(tab)
        act_bar.pack(fill=tk.X, padx=10, pady=(0, 8))

        ttk.Button(act_bar, text="➕ Nueva Fusión...", command=self._on_add_fusion_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(act_bar, text="✏️ Cambiar Resultado...", command=self._on_edit_fusion_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(act_bar, text="🗑️ Eliminar Fusión", command=self._on_delete_fusion).pack(side=tk.LEFT, padx=3)

        # Main splitter (Treeview on left, Visual Preview on right)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Left: Treeview
        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=3)

        f_cols = ("mat_a", "mat_b", "arrow", "result")
        self.fusions_tree = ttk.Treeview(tree_frame, columns=f_cols, show="headings", selectmode="browse")
        self.fusions_tree.heading("mat_a", text="Material A")
        self.fusions_tree.heading("mat_b", text="Material B")
        self.fusions_tree.heading("arrow", text="➔")
        self.fusions_tree.heading("result", text="Carta Resultado")

        self.fusions_tree.column("mat_a", width=180, anchor="w")
        self.fusions_tree.column("mat_b", width=180, anchor="w")
        self.fusions_tree.column("arrow", width=36, anchor="center")
        self.fusions_tree.column("result", width=200, anchor="w")

        f_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.fusions_tree.yview)
        self.fusions_tree.configure(yscrollcommand=f_scroll.set)
        self.fusions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        f_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.fusions_tree.bind("<<TreeviewSelect>>", self._on_fusion_selected)

        # Right: Non-invasive Card Preview Pane
        f_preview_frame = ttk.LabelFrame(paned, text=" Vista Previa de Fusión ")
        paned.add(f_preview_frame, weight=1)

        f_ctrl = ttk.Frame(f_preview_frame)
        f_ctrl.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.fusion_preview_mode = tk.StringVar(value="result")
        self.f_btn_mat_a = ttk.Button(f_ctrl, text="Material A", command=lambda: self._set_fusion_preview_mode("mat_a"))
        self.f_btn_mat_a.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.f_btn_mat_b = ttk.Button(f_ctrl, text="Material B", command=lambda: self._set_fusion_preview_mode("mat_b"))
        self.f_btn_mat_b.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.f_btn_res = ttk.Button(f_ctrl, text="➔ Resultado", command=lambda: self._set_fusion_preview_mode("result"))
        self.f_btn_res.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.fusion_info_lbl = tk.Label(
            f_preview_frame, text="Selecciona una fusión de la lista",
            font=("Segoe UI", 9, "italic"), fg="#A0A0A0", bg="#1E1E24"
        )
        self.fusion_info_lbl.pack(pady=(2, 4))

        self.fusion_card_canvas = tk.Canvas(f_preview_frame, width=185, height=270, bg="#101014", highlightthickness=1, highlightbackground="#33333E")
        self.fusion_card_canvas.pack(anchor="center", padx=6, pady=(0, 6))
        self.fusion_card_renderer = CardCanvasRenderer(self.fusion_card_canvas, graphics_db=self.graphics_db)

        self._active_fusion_triple = (0, 0, 0)

    # ------------------------------------------------------------------
    # Opponents Tab
    # ------------------------------------------------------------------

    def _build_opponents_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" 🧟 Oponentes (39) ")

        # Active deck editor state
        self.active_deck: Optional[DuelistDeck] = None
        self.opp_diff_var   = tk.StringVar(value="0")
        self.opp_name_var   = tk.StringVar(value="—")
        self._deck_card_vars: list[tk.StringVar] = [tk.StringVar(value="0") for _ in range(40)]

        # Header bar
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=10, pady=8)
        ttk.Label(bar, text="Selecciona un oponente para ver y editar su mazo de 40 cartas y su dificultad de IA.",
                  foreground="#A0A0A0").pack(side=tk.LEFT)

        # Import from mod button
        import_opp_btn = ttk.Button(
            bar, text="📥 Importar Mazos del Mod",
            style="Purple.TButton", command=self._on_import_opponents_mod
        )
        import_opp_btn.pack(side=tk.RIGHT, padx=4)

        # Main horizontal panes
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # LEFT: Opponents list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Oponentes", foreground="#00D2FF",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))

        opp_cols = ("id", "name", "diff")
        self.opp_tree = ttk.Treeview(left_frame, columns=opp_cols, show="headings",
                                     selectmode="browse")
        self.opp_tree.heading("id",   text="#")
        self.opp_tree.heading("name", text="Oponente")
        self.opp_tree.heading("diff", text="Dif%")
        self.opp_tree.column("id",   width=32, anchor="center")
        self.opp_tree.column("name", width=160, anchor="w")
        self.opp_tree.column("diff", width=44, anchor="center")

        opp_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.opp_tree.yview)
        self.opp_tree.configure(yscrollcommand=opp_scroll.set)
        self.opp_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        opp_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.opp_tree.bind("<<TreeviewSelect>>", self._on_opponent_selected)

        # CENTER: Deck card editor + Invocation Pool + Fusions
        center_frame = ttk.Frame(paned)
        paned.add(center_frame, weight=3)

        # AI Behavior Explanation Banner
        ai_banner = tk.Label(
            center_frame,
            text="💡 ¿Por qué un CPU (ej. Simon Muran) usa cartas fuera de su mazo de 40 (como Mago Oscuro)?\n"
                 "La IA de Forbidden Memories roba cartas dinámicamente y da recompensas desde su 'Pool de Invocación / Drop' (2048 pts),\n"
                 "y realiza fusiones en mano según su nivel de dificultad. Revisa las sub-pestañas 'Pool de Invocación' y 'Fusiones'.",
            font=("Segoe UI", 8),
            fg="#00D2FF",
            bg="#252532",
            padx=8, pady=4,
            justify=tk.LEFT,
            relief=tk.RIDGE
        )
        ai_banner.pack(fill=tk.X, padx=2, pady=(0, 4))

        self.opp_subnotebook = ttk.Notebook(center_frame)
        self.opp_subnotebook.pack(fill=tk.BOTH, expand=True)

        # Subtab 1: Mazo Base Fijo (40 cartas)
        subtab_deck = ttk.Frame(self.opp_subnotebook)
        self.opp_subnotebook.add(subtab_deck, text=" 📋 Mazo Base (40 Cartas) ")

        deck_canvas = tk.Canvas(subtab_deck, bg="#1E1E24", highlightthickness=0)
        deck_scroll_y = ttk.Scrollbar(subtab_deck, orient=tk.VERTICAL, command=deck_canvas.yview)
        deck_canvas.configure(yscrollcommand=deck_scroll_y.set)
        deck_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        deck_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self._deck_inner = ttk.Frame(deck_canvas)
        deck_canvas.create_window((0, 0), window=self._deck_inner, anchor="nw")
        self._deck_inner.bind(
            "<Configure>",
            lambda e: deck_canvas.configure(scrollregion=deck_canvas.bbox("all"))
        )

        # Build 40 card-slot rows (label + ID entry + name label)
        self._deck_card_name_vars: list[tk.StringVar] = [tk.StringVar(value="—") for _ in range(40)]
        for slot in range(40):
            row = ttk.Frame(self._deck_inner)
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Label(row, text=f"{slot+1:02d}.", width=3,
                     font=("Segoe UI", 8), fg="#777", bg="#1E1E24").pack(side=tk.LEFT)
            var = self._deck_card_vars[slot]
            entry = ttk.Entry(row, textvariable=var, width=6, font=("Consolas", 9))
            entry.pack(side=tk.LEFT, padx=(2, 6))
            entry.bind("<FocusOut>", lambda e, s=slot: self._on_deck_card_changed(s))
            entry.bind("<Return>",   lambda e, s=slot: self._on_deck_card_changed(s))
            entry.bind("<FocusIn>",  lambda e, s=slot: self._preview_deck_slot(s))
            entry.bind("<Button-1>", lambda e, s=slot: self._preview_deck_slot(s))
            name_lbl = tk.Label(row, textvariable=self._deck_card_name_vars[slot],
                                font=("Segoe UI", 8), fg="#C0C0C0", bg="#1E1E24", anchor="w")
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            name_lbl.bind("<Button-1>", lambda e, s=slot: self._preview_deck_slot(s))
            row.bind("<Button-1>", lambda e, s=slot: self._preview_deck_slot(s))

        # Subtab 2: Pool de Invocación / Drops de IA (2048 pts)
        subtab_pool = ttk.Frame(self.opp_subnotebook)
        self.opp_subnotebook.add(subtab_pool, text=" 🎲 Pool Invocación / Drops (2048) ")

        pool_top_bar = ttk.Frame(subtab_pool)
        pool_top_bar.pack(fill=tk.X, padx=6, pady=4)

        ttk.Label(pool_top_bar, text="Rango:").pack(side=tk.LEFT, padx=(0, 4))
        pool_cb = ttk.Combobox(pool_top_bar, textvariable=self.opp_pool_rank_var, values=POOL_NAMES, state="readonly", width=10)
        pool_cb.pack(side=tk.LEFT, padx=4)
        pool_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_opponent_pool_view())

        ttk.Label(pool_top_bar, text="Buscar:").pack(side=tk.LEFT, padx=(8, 4))
        pool_search_entry = ttk.Entry(pool_top_bar, textvariable=self.opp_pool_search_var, width=14)
        pool_search_entry.pack(side=tk.LEFT, padx=4)
        pool_search_entry.bind("<KeyRelease>", lambda e: self._refresh_opponent_pool_view())

        pool_sum_lbl = tk.Label(pool_top_bar, textvariable=self.opp_pool_sum_var, font=("Segoe UI", 9, "bold"), fg="#00FF66", bg="#1E1E24")
        pool_sum_lbl.pack(side=tk.RIGHT, padx=4)

        pool_tree_frame = ttk.Frame(subtab_pool)
        pool_tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        pool_cols = ("id", "name", "weight", "pct")
        self.opp_pool_tree = ttk.Treeview(pool_tree_frame, columns=pool_cols, show="headings", selectmode="browse")
        self.opp_pool_tree.heading("id", text="#")
        self.opp_pool_tree.heading("name", text="Carta en Pool")
        self.opp_pool_tree.heading("weight", text="Slots (de 2048)")
        self.opp_pool_tree.heading("pct", text="Probabilidad %")

        self.opp_pool_tree.column("id", width=42, anchor="center")
        self.opp_pool_tree.column("name", width=180, anchor="w")
        self.opp_pool_tree.column("weight", width=85, anchor="center")
        self.opp_pool_tree.column("pct", width=85, anchor="center")

        pool_scroll = ttk.Scrollbar(pool_tree_frame, orient=tk.VERTICAL, command=self.opp_pool_tree.yview)
        self.opp_pool_tree.configure(yscrollcommand=pool_scroll.set)
        self.opp_pool_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pool_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.opp_pool_tree.bind("<<TreeviewSelect>>", self._on_opp_pool_card_selected)

        # Highlight note for Dark Magician / Boss cards
        self.opp_pool_note_var = tk.StringVar(value="")
        self.opp_pool_note_lbl = tk.Label(
            subtab_pool,
            textvariable=self.opp_pool_note_var,
            font=("Segoe UI", 8, "italic"),
            fg="#FFD700",
            bg="#1E1E24"
        )
        self.opp_pool_note_lbl.pack(fill=tk.X, padx=6, pady=(0, 4))

        # Subtab 3: Fusiones Potenciales del CPU
        subtab_fusions = ttk.Frame(self.opp_subnotebook)
        self.opp_subnotebook.add(subtab_fusions, text=" ⚡ Fusiones del CPU ")

        fus_filter_bar = ttk.Frame(subtab_fusions)
        fus_filter_bar.pack(fill=tk.X, padx=6, pady=(6, 2))

        ttk.Label(fus_filter_bar, text="Filtro:").pack(side=tk.LEFT, padx=(0, 2))
        fus_mode_combo = ttk.Combobox(
            fus_filter_bar,
            textvariable=self.opp_fus_filter_mode_var,
            values=[
                "Ambos materiales en Mazo (Invocables)",
                "Al menos un material en Mazo/Pool",
                "Monstruos Fuertes (ATK >= 1800)",
                "Todas las fusiones con sus cartas"
            ],
            state="readonly",
            width=28
        )
        fus_mode_combo.pack(side=tk.LEFT, padx=3)
        fus_mode_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_opponent_fusions_view())

        ttk.Label(fus_filter_bar, text="Buscar:").pack(side=tk.LEFT, padx=(6, 2))
        fus_search_ent = ttk.Entry(fus_filter_bar, textvariable=self.opp_fus_search_var, width=12)
        fus_search_ent.pack(side=tk.LEFT, padx=3)
        fus_search_ent.bind("<KeyRelease>", lambda e: self._refresh_opponent_fusions_view())

        fus_count_lbl = ttk.Label(fus_filter_bar, textvariable=self.opp_fus_count_var, foreground="#00D2FF")
        fus_count_lbl.pack(side=tk.RIGHT, padx=4)

        fus_tree_frame = ttk.Frame(subtab_fusions)
        fus_tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        fus_cols = ("mat_a", "mat_b", "arrow", "res", "atk")
        self.opp_fusions_tree = ttk.Treeview(fus_tree_frame, columns=fus_cols, show="headings", selectmode="browse")
        self.opp_fusions_tree.heading("mat_a", text="Material A")
        self.opp_fusions_tree.heading("mat_b", text="Material B")
        self.opp_fusions_tree.heading("arrow", text="")
        self.opp_fusions_tree.heading("res", text="Resultado Fusión")
        self.opp_fusions_tree.heading("atk", text="ATK")

        self.opp_fusions_tree.column("mat_a", width=120, anchor="w")
        self.opp_fusions_tree.column("mat_b", width=120, anchor="w")
        self.opp_fusions_tree.column("arrow", width=25, anchor="center")
        self.opp_fusions_tree.column("res", width=140, anchor="w")
        self.opp_fusions_tree.column("atk", width=55, anchor="center")

        fus_scroll = ttk.Scrollbar(fus_tree_frame, orient=tk.VERTICAL, command=self.opp_fusions_tree.yview)
        self.opp_fusions_tree.configure(yscrollcommand=fus_scroll.set)
        self.opp_fusions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        fus_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.opp_fusions_tree.bind("<<TreeviewSelect>>", self._on_opp_fusion_selected)

        # RIGHT: Difficulty + stats panel
        right_frame = ttk.LabelFrame(paned, text=" Estadísticas del Oponente ")
        paned.add(right_frame, weight=1)

        info_inner = ttk.Frame(right_frame)
        info_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(info_inner, textvariable=self.opp_name_var,
                 font=("Segoe UI", 11, "bold"), fg="#00D2FF", bg="#1E1E24").pack(anchor="w", pady=(0, 10))

        diff_row = ttk.Frame(info_inner)
        diff_row.pack(fill=tk.X, pady=6)
        ttk.Label(diff_row, text="Dificultad / Agresividad IA (0–100 %):").pack(anchor="w")
        diff_entry = ttk.Entry(diff_row, textvariable=self.opp_diff_var, width=6, font=("Segoe UI", 10))
        diff_entry.pack(anchor="w", pady=(4, 0))

        ttk.Label(info_inner, text="Valor mayor = más fusiones agresivas del CPU.\n"
                                   "Vanilla Express típico: 1–75%.\n"
                                   "Dream Mod: hasta 75% para bosses.",
                  foreground="#888888", wraplength=160).pack(anchor="w", pady=(6, 0))

        ttk.Separator(info_inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=12)

        save_deck_btn = ttk.Button(
            info_inner, text="💾 Guardar Cambios\nen este Duelista",
            style="Action.TButton", command=self._on_save_deck_changes
        )
        save_deck_btn.pack(fill=tk.X, pady=4)

        reset_btn = ttk.Button(
            info_inner, text="↩ Revertir",
            command=self._on_revert_deck
        )
        reset_btn.pack(fill=tk.X, pady=4)

        ttk.Separator(info_inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Label(info_inner, text="Vista Previa de Carta:", font=("Segoe UI", 9, "bold"), foreground="#00D2FF").pack(anchor="w", pady=(0, 4))
        self.opp_card_canvas = tk.Canvas(info_inner, width=185, height=270, bg="#101014", highlightthickness=1, highlightbackground="#33333E")
        self.opp_card_canvas.pack(anchor="center", pady=(0, 4))
        self.opp_card_renderer = CardCanvasRenderer(self.opp_card_canvas, graphics_db=self.graphics_db)

    def _populate_opponents_tree(self):
        """Refresh the opponents list from deck_db."""
        if not hasattr(self, 'opp_tree'):
            return
        for item in self.opp_tree.get_children():
            self.opp_tree.delete(item)
        for deck in self.deck_db.decks:
            self.opp_tree.insert(
                "", tk.END,
                iid=str(deck.duelist_id),
                values=(f"{deck.duelist_id:02d}", deck.name, f"{deck.difficulty}%")
            )

    def _on_opponent_selected(self, _event=None):
        """Load the selected duelist's deck into the editor."""
        sel = self.opp_tree.selection()
        if not sel:
            return
        did = int(sel[0])
        deck = self.deck_db.get(did)
        if not deck:
            return

        self.active_deck = deck
        self.opp_name_var.set(deck.name)
        self.opp_diff_var.set(str(deck.difficulty))

        for slot in range(40):
            cid = deck.cards[slot] if slot < len(deck.cards) else 0
            self._deck_card_vars[slot].set(str(cid))
            self._deck_card_name_vars[slot].set(self.get_card_display_name(cid) if cid else "—")

        # Automatically preview first card in deck
        for cid in deck.cards:
            if 1 <= cid <= 722:
                c = self.get_card_object(cid)
                if hasattr(self, 'opp_card_renderer'):
                    self.opp_card_renderer.render(c, width=185, height=270)
                break

        self._refresh_opponent_pool_view()
        self._refresh_opponent_fusions_view()

    def _preview_deck_slot(self, slot: int):
        """Previews the card currently in the given deck slot."""
        try:
            cid = int(self._deck_card_vars[slot].get().strip())
        except (ValueError, IndexError):
            return
        if 1 <= cid <= 722:
            card = self.get_card_object(cid)
            if hasattr(self, 'opp_card_renderer'):
                self.opp_card_renderer.render(card, width=185, height=270)

    def _on_deck_card_changed(self, slot: int):
        """Update the name label for a card slot when the ID entry changes."""
        try:
            cid = int(self._deck_card_vars[slot].get().strip())
            self._deck_card_name_vars[slot].set(self.get_card_display_name(cid) if 1 <= cid <= 722 else "—")
            self._preview_deck_slot(slot)
        except ValueError:
            self._deck_card_name_vars[slot].set("—")

    def _on_save_deck_changes(self):
        """Persist edits from the UI entries into the in-memory DuelistDeck."""
        if not self.active_deck:
            messagebox.showinfo("Atención", "Selecciona un oponente primero.")
            return
        try:
            new_diff = max(0, min(100, int(self.opp_diff_var.get().strip())))
        except ValueError:
            messagebox.showerror("Error", "La dificultad debe ser un número entre 0 y 100.")
            return

        errors = []
        new_cards = []
        for slot in range(40):
            try:
                cid = int(self._deck_card_vars[slot].get().strip())
                if not (1 <= cid <= 722):
                    errors.append(f"Ranura {slot+1}: ID {cid} fuera de rango (1-722)")
                    cid = self.active_deck.cards[slot]  # keep original
                new_cards.append(cid)
            except ValueError:
                errors.append(f"Ranura {slot+1}: valor no numérico")
                new_cards.append(self.active_deck.cards[slot])

        self.active_deck.difficulty = new_diff
        self.active_deck.cards = new_cards

        # Refresh tree row
        self.opp_tree.item(
            str(self.active_deck.duelist_id),
            values=(f"{self.active_deck.duelist_id:02d}", self.active_deck.name, f"{new_diff}%")
        )
        msg = f"Duelista #{self.active_deck.duelist_id} ({self.active_deck.name}) guardado."
        if errors:
            msg += f"\n⚠ {len(errors)} ranuras con errores corregidas automáticamente."
        self.status_var.set(msg)
        self.log(msg)
        if errors:
            messagebox.showwarning("Guardado con advertencias", "\n".join(errors[:5]))

    def _on_revert_deck(self):
        """Reload the current deck from deck_db (discard UI edits)."""
        self._on_opponent_selected()

    def _on_import_opponents_mod(self):
        """Import deck compositions and difficulty from a mod ISO."""
        path = filedialog.askopenfilename(
            title="Seleccionar Mod para Importar Mazos",
            filetypes=[("Imágenes de Disco PS1", "*.iso *.bin *.img"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        self.status_var.set(f"Importando mazos de {os.path.basename(path)}...")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(10)

        def task():
            try:
                mod_disc = PS1DiscImage(path)
                mod_slus_key = None
                mod_wa_key = None
                for k in mod_disc.file_table:
                    if "SLUS_" in k.upper() or "SLES_" in k.upper() or "SLPM_" in k.upper():
                        mod_slus_key = k
                    elif "WA_MRG.MRG" in k.upper():
                        mod_wa_key = k

                if not mod_slus_key or not mod_wa_key:
                    raise ValueError("No se encontraron SLUS o WA_MRG.MRG en el mod.")

                mod_exe = mod_disc.extract_file(mod_slus_key)
                mod_wa  = mod_disc.extract_file(mod_wa_key)
                updated = self.deck_db.import_from_mod(mod_wa, mod_exe)

                def on_done():
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate", value=100)
                    self.status_var.set(f"¡{updated}/39 mazos importados de {os.path.basename(path)}!")
                    self.log(f"Mazos importados: {updated}/39 de {os.path.basename(path)}")
                    self._populate_opponents_tree()
                    self._on_opponent_selected()
                    messagebox.showinfo("Importación Completada",
                                        f"Se importaron {updated}/39 mazos y\nniveles de dificultad del mod exitosamente.")
                self.after(0, on_done)

            except Exception as e:
                def on_error(err=e):
                    self.progress_bar.stop()
                    self.status_var.set("Error al importar mazos.")
                    self.log(f"ERROR: {err}")
                    messagebox.showerror("Error", f"No se pudo importar:\n{err}")
                self.after(0, on_error)

        threading.Thread(target=task, daemon=True).start()

    def _refresh_opponent_pool_view(self):
        """Refreshes the duelist's invocation/drop pool in Subtab 2."""
        if not hasattr(self, 'opp_pool_tree') or not self.active_deck:
            return

        did = self.active_deck.duelist_id
        duelist_drops = self.drop_db.get_duelist(did)
        if not duelist_drops:
            return

        rank = self.opp_pool_rank_var.get()
        query = self.opp_pool_search_var.get().strip().lower()

        for item in self.opp_pool_tree.get_children():
            self.opp_pool_tree.delete(item)

        active_drops = duelist_drops.get_active_drops(rank)
        pool_sum = duelist_drops.get_pool_sum(rank)
        self.opp_pool_sum_var.set(f"Suma: {pool_sum} / {POOL_TARGET_SUM}")

        for cid, name, weight, pct in active_drops:
            if query and (query not in name.lower() and query not in str(cid)):
                continue
            self.opp_pool_tree.insert(
                "", tk.END,
                iid=str(cid),
                values=(
                    f"#{cid:03d}",
                    name,
                    f"{weight} / {POOL_TARGET_SUM}",
                    f"{pct:.2f} %"
                )
            )

        # Highlight note for Simon Muran and key boss drops
        if did == 1 and rank == "SA-POW":
            dm_w = duelist_drops.get_card_weight("SA-POW", 35)
            if dm_w > 0:
                self.opp_pool_note_var.set(f"⭐ ¡Mago Oscuro (#035) presente en SA-POW con peso {dm_w}/2048 ({(dm_w/2048)*100:.2f}%)! La IA lo invoca activamente en duelo.")
            else:
                self.opp_pool_note_var.set("")
        else:
            self.opp_pool_note_var.set("")

    def _on_opp_pool_card_selected(self, _event=None):
        sel = self.opp_pool_tree.selection()
        if not sel:
            return
        try:
            cid = int(sel[0])
            card = self.get_card_object(cid)
            if hasattr(self, 'opp_card_renderer'):
                self.opp_card_renderer.render(card, width=185, height=270)
        except (ValueError, IndexError):
            pass

    def _refresh_opponent_fusions_view(self):
        """Populates Subtab 3 with key fusions this opponent can perform."""
        if not hasattr(self, 'opp_fusions_tree') or not self.active_deck:
            return

        for item in self.opp_fusions_tree.get_children():
            self.opp_fusions_tree.delete(item)

        deck_cids = set(self.active_deck.cards)
        pool_cids = set(deck_cids)
        # Add high-weight cards from drop pool
        duelist_drops = self.drop_db.get_duelist(self.active_deck.duelist_id)
        if duelist_drops:
            for p in POOL_NAMES:
                for cid, _, w, _ in duelist_drops.get_active_drops(p):
                    if w >= 8:
                        pool_cids.add(cid)

        filter_mode = getattr(self, 'opp_fus_filter_mode_var', None)
        mode_val = filter_mode.get() if filter_mode else "Ambos materiales en Mazo (Invocables)"
        search_query = getattr(self, 'opp_fus_search_var', None)
        query = search_query.get().strip().lower() if search_query else ""

        found_fusions = []
        for (ca, cb), cc in self.fusion_db.fusions.items():
            if mode_val.startswith("Ambos"):
                if ca not in deck_cids or cb not in deck_cids:
                    continue
            elif mode_val.startswith("Monstruos Fuertes"):
                if ca not in pool_cids and cb not in pool_cids:
                    continue
                res_card = self.card_db.get(cc)
                if not res_card or res_card.atk < 1800:
                    continue
            else:
                if ca not in pool_cids and cb not in pool_cids:
                    continue

            res_card = self.card_db.get(cc)
            atk = res_card.atk if res_card else 0
            found_fusions.append((ca, cb, cc, atk))

        found_fusions.sort(key=lambda x: x[3], reverse=True)

        count = 0
        for idx, (ca, cb, cc, atk) in enumerate(found_fusions):
            name_a = self.get_card_display_name(ca)
            name_b = self.get_card_display_name(cb)
            name_c = self.get_card_display_name(cc)
            if query:
                q_match = (
                    query in name_a.lower() or query in name_b.lower() or query in name_c.lower() or
                    query in str(ca) or query in str(cb) or query in str(cc)
                )
                if not q_match:
                    continue
            count += 1
            if count <= 250:
                self.opp_fusions_tree.insert(
                    "", tk.END,
                    iid=str(idx),
                    values=(
                        f"#{ca:03d} {name_a}",
                        f"#{cb:03d} {name_b}",
                        "➔",
                        f"#{cc:03d} {name_c}",
                        f"{atk}"
                    )
                )

        if hasattr(self, 'opp_fus_count_var'):
            self.opp_fus_count_var.set(f"{count} fusiones ({min(count, 250)} mostradas)")

    def _on_opp_fusion_selected(self, _event=None):
        sel = self.opp_fusions_tree.selection()
        if not sel:
            return
        vals = self.opp_fusions_tree.item(sel[0])["values"]
        if len(vals) < 4:
            return
        try:
            cid = int(str(vals[3]).split()[0].replace("#", ""))
            card = self.get_card_object(cid)
            if hasattr(self, 'opp_card_renderer'):
                self.opp_card_renderer.render(card, width=185, height=270)
        except (ValueError, IndexError):
            pass

    # ------------------------------------------------------------------
    # Drops & Calificaciones Tab
    # ------------------------------------------------------------------

    def _build_drops_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" 🎁 Drops y Calificaciones (39) ")

        # Sub-Notebook for two modes: 1) Drops by Duelist, 2) Reverse Card Search
        self.drop_subnotebook = ttk.Notebook(tab)
        self.drop_subnotebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # --------------------------------------------------------------
        # Sub-tab 1: Drops por Duelista (39 Oponentes)
        # --------------------------------------------------------------
        by_duelist_tab = ttk.Frame(self.drop_subnotebook)
        self.drop_subnotebook.add(by_duelist_tab, text=" 👥 Drops por Duelista ")

        paned = ttk.PanedWindow(by_duelist_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left pane: Opponents List (39 duelists)
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Oponentes (39)", foreground="#00D2FF", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        d_cols = ("id", "name")
        self.drop_opp_tree = ttk.Treeview(left_frame, columns=d_cols, show="headings", selectmode="browse")
        self.drop_opp_tree.heading("id", text="#")
        self.drop_opp_tree.heading("name", text="Oponente")
        self.drop_opp_tree.column("id", width=36, anchor="center")
        self.drop_opp_tree.column("name", width=150, anchor="w")

        d_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.drop_opp_tree.yview)
        self.drop_opp_tree.configure(yscrollcommand=d_scroll.set)
        self.drop_opp_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        d_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.drop_opp_tree.bind("<<TreeviewSelect>>", self._on_drop_duelist_selected)

        # Right pane: Active Opponent's Drop Pool Table + Editor
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)

        # Top rank selector bar
        r_bar = ttk.Frame(right_frame)
        r_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(r_bar, text="Calificación:").pack(side=tk.LEFT, padx=(0, 4))
        self.rank_btn_sa_pow = ttk.Button(r_bar, text="⚡ SA-POW", command=lambda: self._on_rank_pool_changed("SA-POW"))
        self.rank_btn_sa_pow.pack(side=tk.LEFT, padx=2)
        self.rank_btn_bcd_pow = ttk.Button(r_bar, text="🛡️ BCD-POW", command=lambda: self._on_rank_pool_changed("BCD-POW"))
        self.rank_btn_bcd_pow.pack(side=tk.LEFT, padx=2)
        self.rank_btn_sa_tec = ttk.Button(r_bar, text="🧠 SA-TEC", command=lambda: self._on_rank_pool_changed("SA-TEC"))
        self.rank_btn_sa_tec.pack(side=tk.LEFT, padx=2)
        self.rank_btn_bcd_tec = ttk.Button(r_bar, text="🧩 BCD-TEC", command=lambda: self._on_rank_pool_changed("BCD-TEC"))
        self.rank_btn_bcd_tec.pack(side=tk.LEFT, padx=2)

        self.drop_pool_sum_lbl = tk.Label(
            r_bar, textvariable=self.drop_pool_sum_var, font=("Segoe UI", 9, "bold"),
            fg="#00FF66", bg="#1E1E24"
        )
        self.drop_pool_sum_lbl.pack(side=tk.RIGHT, padx=8)

        # Filter and Options row
        opt_bar = ttk.Frame(right_frame)
        opt_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(opt_bar, text="Buscar carta:").pack(side=tk.LEFT, padx=(0, 4))
        drop_search_ent = ttk.Entry(opt_bar, textvariable=self.drop_search_var, width=18)
        drop_search_ent.pack(side=tk.LEFT, padx=4)
        drop_search_ent.bind("<KeyRelease>", lambda e: self._refresh_drops_table())

        cb_active = ttk.Checkbutton(
            opt_bar, text="Solo cartas que caen (>0%)",
            variable=self.drop_only_active_var, command=self._refresh_drops_table
        )
        cb_active.pack(side=tk.LEFT, padx=12)

        ttk.Label(opt_bar, textvariable=self.drop_count_var, foreground="#00D2FF").pack(side=tk.RIGHT, padx=8)

        # Drops Table
        table_frame = ttk.Frame(right_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)

        tbl_cols = ("id", "name", "type", "stats", "weight", "pct", "rank")
        self.duelist_drops_tree = ttk.Treeview(table_frame, columns=tbl_cols, show="headings", selectmode="browse")
        self.duelist_drops_tree.heading("id", text="ID")
        self.duelist_drops_tree.heading("name", text="Nombre de Carta")
        self.duelist_drops_tree.heading("type", text="Tipo")
        self.duelist_drops_tree.heading("stats", text="ATK / DEF")
        self.duelist_drops_tree.heading("weight", text="Peso (X/2048)")
        self.duelist_drops_tree.heading("pct", text="Probabilidad %")
        self.duelist_drops_tree.heading("rank", text="Rango")

        self.duelist_drops_tree.column("id", width=44, anchor="center")
        self.duelist_drops_tree.column("name", width=180, anchor="w")
        self.duelist_drops_tree.column("type", width=95, anchor="center")
        self.duelist_drops_tree.column("stats", width=95, anchor="center")
        self.duelist_drops_tree.column("weight", width=85, anchor="center")
        self.duelist_drops_tree.column("pct", width=85, anchor="center")
        self.duelist_drops_tree.column("rank", width=75, anchor="center")

        tbl_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.duelist_drops_tree.yview)
        self.duelist_drops_tree.configure(yscrollcommand=tbl_scroll.set)
        self.duelist_drops_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tbl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.duelist_drops_tree.bind("<<TreeviewSelect>>", self._on_drop_card_selected)

        # Bottom Inspector & Modifier
        drop_editor = ttk.LabelFrame(right_frame, text=" ✏️ Editor de Probabilidad de Drop ")
        drop_editor.pack(fill=tk.X, pady=(8, 0))

        e_inner = ttk.Frame(drop_editor)
        e_inner.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(e_inner, textvariable=self.edit_drop_card_name_var, font=("Segoe UI", 10, "bold"), fg="#00D2FF", bg="#1E1E24").pack(side=tk.LEFT)

        ttk.Label(e_inner, text="Peso (0–2048):").pack(side=tk.LEFT, padx=(16, 4))
        w_entry = ttk.Entry(e_inner, textvariable=self.edit_drop_weight_var, width=8, font=("Consolas", 10))
        w_entry.pack(side=tk.LEFT, padx=4)
        w_entry.bind("<KeyRelease>", self._on_drop_weight_typing)

        ttk.Label(e_inner, text="Probabilidad:").pack(side=tk.LEFT, padx=(12, 4))
        tk.Label(e_inner, textvariable=self.edit_drop_pct_var, font=("Segoe UI", 10, "bold"), fg="#00FF66", bg="#1E1E24").pack(side=tk.LEFT)

        save_drop_btn = ttk.Button(e_inner, text="💾 Guardar Drop", style="Action.TButton", command=self._on_save_drop_weight)
        save_drop_btn.pack(side=tk.LEFT, padx=12)

        norm_btn = ttk.Button(e_inner, text="⚖️ Auto-Normalizar a 2048", command=self._on_normalize_pool)
        norm_btn.pack(side=tk.LEFT, padx=4)

        add_btn = ttk.Button(e_inner, text="➕ Asignar otra Carta...", command=self._on_add_card_drop_dialog)
        add_btn.pack(side=tk.LEFT, padx=4)

        import_drops_btn = ttk.Button(e_inner, text="📥 Importar Drops de Mod", style="Purple.TButton", command=self._on_import_drops_mod)
        import_drops_btn.pack(side=tk.RIGHT, padx=4)

        # Right-most pane: Non-invasive Card Preview
        drop_preview_frame = ttk.LabelFrame(paned, text=" Vista Previa ")
        paned.add(drop_preview_frame, weight=1)

        self.drop_card_canvas = tk.Canvas(drop_preview_frame, width=185, height=270, bg="#101014", highlightthickness=1, highlightbackground="#33333E")
        self.drop_card_canvas.pack(anchor="center", padx=6, pady=8)
        self.drop_card_renderer = CardCanvasRenderer(self.drop_card_canvas, graphics_db=self.graphics_db)

        # --------------------------------------------------------------
        # Sub-tab 2: Buscador Inverso ("¿Quién da esta carta?")
        # --------------------------------------------------------------
        reverse_tab = ttk.Frame(self.drop_subnotebook)
        self.drop_subnotebook.add(reverse_tab, text=" 🔍 Buscador Inverso (\"¿Quién da esta carta?\") ")

        rev_top = ttk.Frame(reverse_tab)
        rev_top.pack(fill=tk.X, padx=12, pady=10)

        ttk.Label(rev_top, text="Buscar Carta (Nombre o ID):", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        rev_entry = ttk.Entry(rev_top, textvariable=self.reverse_search_var, width=28, font=("Segoe UI", 10))
        rev_entry.pack(side=tk.LEFT, padx=4)
        rev_entry.bind("<KeyRelease>", lambda e: self._on_reverse_search())

        ttk.Label(rev_top, text="Rango:").pack(side=tk.LEFT, padx=(14, 4))
        rev_rank_combo = ttk.Combobox(
            rev_top, textvariable=self.reverse_rank_filter_var,
            values=["Todos los rangos", "SA-POW", "BCD-POW", "SA-TEC", "BCD-TEC"],
            state="readonly", width=16
        )
        rev_rank_combo.pack(side=tk.LEFT, padx=4)
        rev_rank_combo.bind("<<ComboboxSelected>>", lambda e: self._on_reverse_search())

        rev_search_btn = ttk.Button(rev_top, text="🔍 Buscar", command=self._on_reverse_search)
        rev_search_btn.pack(side=tk.LEFT, padx=8)

        jump_btn = ttk.Button(rev_top, text="🎯 Ir a la Tabla de este Duelista", command=self._on_reverse_card_jump)
        jump_btn.pack(side=tk.RIGHT, padx=4)

        ttk.Label(rev_top, textvariable=self.reverse_results_count_var, foreground="#00D2FF", font=("Segoe UI", 9, "bold")).pack(side=tk.RIGHT, padx=12)

        # Reverse Search Main PanedWindow
        rev_paned = ttk.PanedWindow(reverse_tab, orient=tk.HORIZONTAL)
        rev_paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        # Reverse Search Table
        rev_table_frame = ttk.Frame(rev_paned)
        rev_paned.add(rev_table_frame, weight=3)

        rev_cols = ("did", "opponent", "rank", "weight", "pct", "card", "desc")
        self.reverse_search_tree = ttk.Treeview(rev_table_frame, columns=rev_cols, show="headings", selectmode="browse")
        self.reverse_search_tree.heading("did", text="#")
        self.reverse_search_tree.heading("opponent", text="Duelista / Enemigo")
        self.reverse_search_tree.heading("rank", text="Calificación")
        self.reverse_search_tree.heading("weight", text="Peso (X/2048)")
        self.reverse_search_tree.heading("pct", text="Probabilidad (%)")
        self.reverse_search_tree.heading("card", text="Carta")
        self.reverse_search_tree.heading("desc", text="Requisito de Victoria")

        self.reverse_search_tree.column("did", width=36, anchor="center")
        self.reverse_search_tree.column("opponent", width=160, anchor="w")
        self.reverse_search_tree.column("rank", width=80, anchor="center")
        self.reverse_search_tree.column("weight", width=85, anchor="center")
        self.reverse_search_tree.column("pct", width=95, anchor="center")
        self.reverse_search_tree.column("card", width=180, anchor="w")
        self.reverse_search_tree.column("desc", width=220, anchor="w")

        rev_scroll = ttk.Scrollbar(rev_table_frame, orient=tk.VERTICAL, command=self.reverse_search_tree.yview)
        self.reverse_search_tree.configure(yscrollcommand=rev_scroll.set)
        self.reverse_search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rev_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.reverse_search_tree.bind("<Double-1>", lambda e: self._on_reverse_card_jump())
        self.reverse_search_tree.bind("<<TreeviewSelect>>", self._on_reverse_card_selected)

        # Reverse Search Preview Pane
        rev_preview_frame = ttk.LabelFrame(rev_paned, text=" Vista Previa ")
        rev_paned.add(rev_preview_frame, weight=1)

        self.rev_card_canvas = tk.Canvas(rev_preview_frame, width=185, height=270, bg="#101014", highlightthickness=1, highlightbackground="#33333E")
        self.rev_card_canvas.pack(anchor="center", padx=6, pady=8)
        self.rev_card_renderer = CardCanvasRenderer(self.rev_card_canvas, graphics_db=self.graphics_db)

    # ------------------------------------------------------------------
    # Drops Tab Data Population & Interactions
    # ------------------------------------------------------------------

    def _populate_drop_duelists_tree(self):
        """Populate the 39 duelists in the left tree."""
        for item in self.drop_opp_tree.get_children():
            self.drop_opp_tree.delete(item)
        for d in self.drop_db.duelists:
            self.drop_opp_tree.insert("", tk.END, iid=str(d.duelist_id), values=(f"{d.duelist_id:02d}", d.name))
        # Select first duelist by default
        if self.drop_db.duelists:
            self.drop_opp_tree.selection_set("1")
            self.selected_drop_duelist_id = 1

    def _on_drop_duelist_selected(self, _event=None):
        sel = self.drop_opp_tree.selection()
        if not sel:
            return
        self.selected_drop_duelist_id = int(sel[0])
        self._refresh_drops_table()

    def _on_rank_pool_changed(self, pool_name: str):
        self.selected_drop_pool = pool_name
        self._refresh_drops_table()

    def _refresh_drops_table(self):
        duelist = self.drop_db.get_duelist(self.selected_drop_duelist_id)
        if not duelist:
            return

        pool_name = self.selected_drop_pool
        pool_sum = duelist.get_pool_sum(pool_name)
        pct_sum = (pool_sum / float(POOL_TARGET_SUM)) * 100.0

        # Update sum badge
        self.drop_pool_sum_var.set(f"Suma: {pool_sum} / {POOL_TARGET_SUM} ({pct_sum:.1f}%)")
        if pool_sum == POOL_TARGET_SUM:
            self.drop_pool_sum_lbl.configure(fg="#00FF66")
        else:
            self.drop_pool_sum_lbl.configure(fg="#FFAA00")

        # Clear tree
        for item in self.duelist_drops_tree.get_children():
            self.duelist_drops_tree.delete(item)

        query = self.drop_search_var.get().strip().lower()
        only_active = self.drop_only_active_var.get()

        active_count = 0
        items_to_insert = []
        for cid in range(1, 723):
            w = duelist.get_card_weight(pool_name, cid)
            if w > 0:
                active_count += 1
            if only_active and w == 0:
                continue

            card_obj = self.card_db.get(cid)
            name = card_obj.name if card_obj else CARD_NAMES.get(cid, f"Card #{cid}")
            if query and (query not in name.lower() and query not in str(cid)):
                continue

            c_type = card_obj.type_name if card_obj else "—"
            c_stats = f"{card_obj.atk}/{card_obj.def_}" if card_obj else "—"
            pct = (w / float(POOL_TARGET_SUM)) * 100.0

            items_to_insert.append((
                cid,
                (
                    f"#{cid:03d}",
                    name,
                    c_type,
                    c_stats,
                    f"{w} / {POOL_TARGET_SUM}",
                    f"{pct:.2f} %",
                    RANK_INFO[pool_name]["badge"]
                ),
                w
            ))

        # Sort: non-zero weights first (descending), then by ID
        items_to_insert.sort(key=lambda x: (x[2], -x[0]), reverse=True)

        for cid, vals, _w in items_to_insert:
            self.duelist_drops_tree.insert("", tk.END, iid=str(cid), values=vals)

        self.drop_count_var.set(f"Cartas en Pool: {active_count} / 722")

        first_items = self.duelist_drops_tree.get_children()
        if first_items:
            self.duelist_drops_tree.selection_set(first_items[0])
            self._on_drop_card_selected()

    def _on_drop_card_selected(self, _event=None):
        sel = self.duelist_drops_tree.selection()
        if not sel:
            return
        cid = int(sel[0])
        self.selected_drop_card_id = cid
        card_obj = self.get_card_object(cid)
        cname = card_obj.name
        self.edit_drop_card_name_var.set(f"Carta: #{cid:03d} {cname}")

        duelist = self.drop_db.get_duelist(self.selected_drop_duelist_id)
        if duelist:
            w = duelist.get_card_weight(self.selected_drop_pool, cid)
            self.edit_drop_weight_var.set(str(w))
            pct = (w / float(POOL_TARGET_SUM)) * 100.0
            self.edit_drop_pct_var.set(f"{pct:.2f} %")

        if hasattr(self, 'drop_card_renderer'):
            self.drop_card_renderer.render(card_obj, width=185, height=270)

    def _on_drop_weight_typing(self, _event=None):
        try:
            w = int(self.edit_drop_weight_var.get().strip())
            pct = (w / float(POOL_TARGET_SUM)) * 100.0
            self.edit_drop_pct_var.set(f"{pct:.2f} %")
        except ValueError:
            self.edit_drop_pct_var.set("— %")

    def _on_save_drop_weight(self):
        if not self.selected_drop_card_id:
            messagebox.showinfo("Atención", "Por favor selecciona una carta en la tabla primero.")
            return
        try:
            new_w = max(0, min(POOL_TARGET_SUM, int(self.edit_drop_weight_var.get().strip())))
        except ValueError:
            messagebox.showerror("Error", f"El peso debe ser un número entero entre 0 y {POOL_TARGET_SUM}.")
            return

        duelist = self.drop_db.get_duelist(self.selected_drop_duelist_id)
        if not duelist:
            return

        duelist.set_card_weight(self.selected_drop_pool, self.selected_drop_card_id, new_w)
        self._refresh_drops_table()
        # Reselect card
        if self.duelist_drops_tree.exists(str(self.selected_drop_card_id)):
            self.duelist_drops_tree.selection_set(str(self.selected_drop_card_id))
            self.duelist_drops_tree.see(str(self.selected_drop_card_id))

        cname = get_card_name(self.selected_drop_card_id)
        pct = (new_w / float(POOL_TARGET_SUM)) * 100.0
        msg = f"Drop actualizado: {duelist.name} [{self.selected_drop_pool}] -> #{self.selected_drop_card_id:03d} {cname} = {new_w}/2048 ({pct:.2f}%)"
        self.status_var.set(msg)
        self.log(msg)

    def _on_normalize_pool(self):
        duelist = self.drop_db.get_duelist(self.selected_drop_duelist_id)
        if not duelist:
            return
        pool_name = self.selected_drop_pool
        ok = duelist.normalize_pool(pool_name)
        if ok:
            self._refresh_drops_table()
            msg = f"Pool normalizado con éxito: {duelist.name} [{pool_name}] suma exactamente 2048."
            self.status_var.set(msg)
            self.log(msg)
            messagebox.showinfo("Auto-Normalización", f"El pool {pool_name} de {duelist.name} ha sido auto-balanceado.\n\nSuma total: 2048 / 2048 (100.0%).")
        else:
            messagebox.showwarning("Advertencia", "No se pudo normalizar: no hay cartas con peso mayor a 0 en este pool.")

    def _on_add_card_drop_dialog(self):
        """Allows assigning drop probability to any card that currently has weight 0."""
        duelist = self.drop_db.get_duelist(self.selected_drop_duelist_id)
        if not duelist:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Asignar Drop a otra Carta - {duelist.name}")
        dlg.geometry("420x260")
        dlg.configure(bg="#1E1E24")
        dlg.transient(self)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Asignar Drop a {duelist.name} [{self.selected_drop_pool}]", font=("Segoe UI", 10, "bold"), foreground="#00D2FF").pack(pady=10)

        card_var = tk.StringVar(value="")
        weight_var = tk.StringVar(value="50")

        f = ttk.Frame(dlg)
        f.pack(fill=tk.X, padx=20, pady=8)

        ttk.Label(f, text="Carta (ID 1-722 o Nombre):").pack(anchor="w")
        card_ent = ttk.Entry(f, textvariable=card_var, width=30)
        card_ent.pack(fill=tk.X, pady=4)

        ttk.Label(f, text="Peso a asignar (1-2048):").pack(anchor="w", pady=(8, 0))
        w_ent = ttk.Entry(f, textvariable=weight_var, width=12)
        w_ent.pack(anchor="w", pady=4)

        def do_assign():
            txt = card_var.get().strip()
            cid = None
            if txt.isdigit():
                val = int(txt)
                if 1 <= val <= 722:
                    cid = val
            if cid is None:
                # Search by name
                for i, name in CARD_NAMES.items():
                    if txt.lower() in name.lower():
                        cid = i
                        break
            if not cid:
                messagebox.showerror("Error", f"No se encontró ninguna carta con '{txt}'.", parent=dlg)
                return

            try:
                w = max(1, min(POOL_TARGET_SUM, int(weight_var.get().strip())))
            except ValueError:
                messagebox.showerror("Error", "El peso debe ser un número entero.", parent=dlg)
                return

            duelist.set_card_weight(self.selected_drop_pool, cid, w)
            dlg.destroy()
            self.selected_drop_card_id = cid
            self._refresh_drops_table()
            if self.duelist_drops_tree.exists(str(cid)):
                self.duelist_drops_tree.selection_set(str(cid))
                self.duelist_drops_tree.see(str(cid))
            self.status_var.set(f"Carta #{cid:03d} agregada al drop de {duelist.name} [{self.selected_drop_pool}] con peso {w}.")

        btn_row = ttk.Frame(dlg)
        btn_row.pack(fill=tk.X, padx=20, pady=16)
        ttk.Button(btn_row, text="Asignar y Cerrar", style="Green.TButton", command=do_assign).pack(side=tk.RIGHT)
        ttk.Button(btn_row, text="Cancelar", command=dlg.destroy).pack(side=tk.RIGHT, padx=8)

    def _on_import_drops_mod(self):
        """Imports drop tables from another mod ISO."""
        path = filedialog.askopenfilename(
            title="Seleccionar Mod para Importar Tablas de Drop",
            filetypes=[("Imágenes de Disco PS1", "*.iso *.bin *.img"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        self.status_var.set(f"Importando drops de {os.path.basename(path)}...")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(10)

        def task():
            try:
                mod_disc = PS1DiscImage(path)
                slus_k = wa_k = None
                for k in mod_disc.file_table:
                    if any(x in k.upper() for x in ("SLUS_", "SLES_", "SLPM_")):
                        slus_k = k
                    elif "WA_MRG.MRG" in k.upper():
                        wa_k = k

                if not wa_k:
                    raise ValueError("No se encontró DATA/WA_MRG.MRG en el mod.")

                mod_wa = mod_disc.extract_file(wa_k)
                mod_exe = mod_disc.extract_file(slus_k) if slus_k else None

                imported = self.drop_db.import_from_mod(mod_wa, mod_exe)

                def on_done():
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate", value=100)
                    self.status_var.set(f"¡Drops importados de {os.path.basename(path)} ({imported} duelistas)!")
                    self.log(f"Tablas de drop importadas con éxito de {os.path.basename(path)}.")
                    self._populate_drop_duelists_tree()
                    self._refresh_drops_table()
                    self._on_reverse_search()
                    messagebox.showinfo("Importación Exitosa", f"Se importaron las tablas de drop de {imported} duelistas de {os.path.basename(path)}.")

                self.after(0, on_done)
            except Exception as e:
                def on_error(err=e):
                    self.progress_bar.stop()
                    self.status_var.set("Error al importar drops.")
                    self.log(f"ERROR: {str(err)}")
                    messagebox.showerror("Error al importar drops", str(err))
                self.after(0, on_error)

        threading.Thread(target=task, daemon=True).start()

    # ------------------------------------------------------------------
    # Reverse Search Interactions
    # ------------------------------------------------------------------

    def _on_reverse_search(self, _event=None):
        query = self.reverse_search_var.get().strip().lower()
        rank_filter = self.reverse_rank_filter_var.get()

        for item in self.reverse_search_tree.get_children():
            self.reverse_search_tree.delete(item)

        if not query:
            self.reverse_results_count_var.set("Coincidencias: 0")
            return

        # Find matching cards
        matched_cids = []
        if query.isdigit():
            val = int(query)
            if 1 <= val <= 722:
                matched_cids.append(val)
        for cid, name in CARD_NAMES.items():
            if query in name.lower() and cid not in matched_cids:
                matched_cids.append(cid)
            if len(matched_cids) >= 15:
                break

        results = []
        for cid in matched_cids:
            drops = self.drop_db.search_card_drops(cid)
            for d in drops:
                if rank_filter != "Todos los rangos" and d["pool_name"] != rank_filter:
                    continue
                results.append(d)

        # Sort descending by percentage
        results.sort(key=lambda x: x["percentage"], reverse=True)

        for idx, r in enumerate(results[:200]):
            self.reverse_search_tree.insert(
                "", tk.END,
                iid=str(idx),
                values=(
                    f"{r['duelist_id']:02d}",
                    r["duelist_name"],
                    r["rank_badge"],
                    f"{r['weight']} / {POOL_TARGET_SUM}",
                    f"{r['percentage']:.2f} %",
                    f"#{r['card_id']:03d} {r['card_name']}",
                    RANK_INFO[r["pool_name"]]["title"]
                )
            )

        self.reverse_results_count_var.set(f"Coincidencias: {len(results)}")
        first_items = self.reverse_search_tree.get_children()
        if first_items:
            self.reverse_search_tree.selection_set(first_items[0])
            self._on_reverse_card_selected()

    def _on_reverse_card_selected(self, _event=None):
        sel = self.reverse_search_tree.selection()
        if not sel:
            return
        item = self.reverse_search_tree.item(sel[0])
        vals = item.get("values", [])
        if len(vals) < 6:
            return
        card_str = str(vals[5])  # "#001 Blue-Eyes..."
        try:
            cid = int(card_str.split()[0].replace("#", ""))
            card = self.get_card_object(cid)
            if hasattr(self, 'rev_card_renderer'):
                self.rev_card_renderer.render(card, width=185, height=270)
        except (ValueError, IndexError):
            pass

    def _on_reverse_card_jump(self):
        """Jumps to the Duelist Drops tab with the selected duelist and pool."""
        sel = self.reverse_search_tree.selection()
        if not sel:
            messagebox.showinfo("Atención", "Selecciona una fila en los resultados de búsqueda primero.")
            return

        vals = self.reverse_search_tree.item(sel[0])["values"]
        did = int(vals[0])
        rank_badge = vals[2]

        pool_map = {
            "S/A POW": "SA-POW",
            "B/C/D POW": "BCD-POW",
            "S/A TEC": "SA-TEC",
            "B/C/D TEC": "BCD-TEC"
        }
        pool_name = pool_map.get(rank_badge, "SA-POW")

        # Switch to sub-tab 0
        self.drop_subnotebook.select(0)
        self.selected_drop_duelist_id = did
        self.selected_drop_pool = pool_name

        if self.drop_opp_tree.exists(str(did)):
            self.drop_opp_tree.selection_set(str(did))
            self.drop_opp_tree.see(str(did))

        self._refresh_drops_table()

    # ------------------------------------------------------------------
    # Calificaciones Ranking Guide Dialog
    # ------------------------------------------------------------------

    def _show_rank_guide_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Guía del Sistema de Calificaciones y Drops de Yu-Gi-Oh! Forbidden Memories")
        dlg.geometry("760x640")
        dlg.minsize(680, 520)
        dlg.configure(bg="#1E1E24")
        dlg.transient(self)

        header = tk.Label(
            dlg,
            text="📖 Sistema de Calificaciones y Probabilidades de Drop",
            font=("Segoe UI", 14, "bold"),
            fg="#00D2FF",
            bg="#1E1E24"
        )
        header.pack(pady=(12, 6))

        text_frame = ttk.Frame(dlg)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        txt = tk.Text(text_frame, bg="#121214", fg="#E0E0E0", font=("Consolas", 10), wrap=tk.WORD, padx=12, pady=12)
        txt_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=txt.yview)
        txt.configure(yscrollcommand=txt_scroll.set)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        txt_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        guide_content = """================================================================================
CÓMO FUNCIONA EL SISTEMA DE CALIFICACIONES (POW vs TEC & RANGOS S/A/B/C/D)
================================================================================

1. ¿CÓMO DECIDE EL JUEGO ENTRE 'POW' (PODER) Y 'TEC' (TÉCNICA)?
Al finalizar cada duelo, el motor evalúa las acciones que realizaste:

  • NÚMERO DE TURNOS DEL DUELO:
    - 1 a 4 turnos  -> +2 puntos para POW (Victoria aplastante rápida)
    - 5 a 8 turnos  -> +1 punto para POW
    - 9 a 28 turnos -> Neutral
    - 29 a 32 turnos-> +1 punto para TEC
    - 33 o más turnos-> +2 puntos para TEC

  • CARTAS RESTANTES EN TU BARAJA:
    - 35 a 39 cartas restantes -> +2 puntos para POW
    - 0 a 4 cartas restantes   -> +4 puntos para TEC (Stall exhaustivo)

  • NÚMERO DE FUSIONES REALIZADAS:
    - 0 a 1 fusiones -> +2 puntos para POW (Ataque directo con monstruos fuertes)
    - 4 a 6 fusiones -> +2 puntos para TEC
    - 7 o más fusiones -> +4 puntos para TEC

  • CARTAS MÁGICAS Y TRAMPAS DEL ENEMIGO ACTIVADAS:
    - Activar trampas del oponente otorga puntos técnicos muy altos (+2 a +4 TEC).

  • VICTORIA POR AGOTAMIENTO DE MAZO (DECK OUT):
    - Si el rival se queda sin cartas en el mazo, la victoria es GARANTIZADA como TEC.

--------------------------------------------------------------------------------
2. CÁLCULO DE LA LETRA DE CALIFICACIÓN (S, A, B, C, D)
El juego calcula 'Puntos de Penalización' en base al daño recibido en tus LP,
número de cartas defensivas usadas, etc.:

  • Rango S: 0 a 4 puntos de penalización  (Dominio supremo)
  • Rango A: 5 a 9 puntos de penalización  (Superior)
  • Rango B: 10 a 19 puntos de penalización (Regular)
  • Rango C: 20 a 29 puntos de penalización (Apretado)
  • Rango D: 30 o más puntos de penalización (Crítico / Casi derrotado)

--------------------------------------------------------------------------------
3. ¿POR QUÉ EXISTEN 4 POOLS DE DROPS?
El código de Forbidden Memories agrupa las calificaciones en 4 tablas por duelista:

  1. ⚡ SA-POW: Compartida por Rango S y Rango A en victoria ofensiva.
     - Contiene los monstruos más fuertes (Dragones, Guerreros de alto ATK).
  2. 🛡️ BCD-POW: Compartida por Rangos B, C y D en victoria ofensiva.
     - Contiene monstruos regulares y piezas comunes.
  3. 🧠 SA-TEC: Compartida por Rango S y Rango A en victoria técnica.
     - Contiene las cartas mágicas y de equipo más codiciadas (Megamorph, Raigeki,
       Bright Castle, Widespread Ruin).
  4. 🧩 BCD-TEC: Compartida por Rangos B, C y D en victoria técnica.
     - Contiene trampas y magias menores.

--------------------------------------------------------------------------------
4. MATEMÁTICA DEL DROP ENGINE Y EL MULTIPLICADOR x100
  • Cada tabla de drop contiene exactamente 722 cartas.
  • La suma de todos los pesos en una tabla es SIEMPRE 2048.
  • Probabilidad (%) = (Peso / 2048) * 100%.
  • El multiplicador x100 ejecuta 100 tiradas pseudoaleatorias independientes
    sobre el pool que obtuviste en tu calificación y deposita automáticamente
    las cartas en tu baúl (mostrando las 4 primeras en pantalla de victoria).
================================================================================
"""
        txt.insert(tk.END, guide_content)
        txt.configure(state=tk.DISABLED)

        close_btn = ttk.Button(dlg, text="Entendido y Cerrar", style="Action.TButton", command=dlg.destroy)
        close_btn.pack(pady=10)

    # ------------------------------------------------------------------
    # Starter Deck (Mazo Inicial) Tab
    # ------------------------------------------------------------------

    def _build_starter_deck_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" 🎴 Mazo Inicial (Starter) ")

        # Header bar
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=14, pady=(8, 4))

        title_lbl = tk.Label(
            header_frame,
            text="🎴 Editor del Mazo Inicial y Baúl (Tabla de 1,024 Probabilidades)",
            font=("Segoe UI", 11, "bold"),
            fg="#00D2FF",
            bg="#1E1E24"
        )
        title_lbl.pack(anchor="w")

        info_lbl = tk.Label(
            header_frame,
            text="El motor original de PS1 genera el mazo de 40 cartas iniciales sorteando sobre 7 pools de probabilidad en DATA/WA_MRG.MRG (sector 7983).\n"
                 "Ajusta los pesos por pool (0-2048), fija cartas garantizadas (100% de aparición) o importa el mazo inicial de cualquier ISO/mod.",
            font=("Segoe UI", 8),
            fg="#A0A0A0",
            bg="#1E1E24",
            justify=tk.LEFT
        )
        info_lbl.pack(anchor="w", pady=(2, 6))

        # Control and Filter Bar
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=14, pady=4)

        ttk.Label(bar, text="Buscar carta:").pack(side=tk.LEFT, padx=(0, 4))
        search_ent = ttk.Entry(bar, textvariable=self.starter_search_var, width=16)
        search_ent.pack(side=tk.LEFT, padx=4)
        search_ent.bind("<KeyRelease>", lambda e: self._filter_starter_cards_tree())

        ttk.Label(bar, text="Pool:").pack(side=tk.LEFT, padx=(8, 2))
        self.starter_pool_filter_cb = ttk.Combobox(
            bar,
            textvariable=self.starter_pool_filter_var,
            values=[
                "Todos los Pools (Global)",
                "Pool 0: Monstruos Menores (16 cartas)",
                "Pool 1: Monstruos Medios (16 cartas)",
                "Pool 2: Monstruos Mayores (4 cartas)",
                "Pool 3: Monstruos Clave / Jefes (1 carta)",
                "Pool 4: Magias de Limpieza (1 carta)",
                "Pool 5: Magias de Campo (1 carta)",
                "Pool 6: Magias de Equipo (1 carta)"
            ],
            state="readonly",
            width=28
        )
        self.starter_pool_filter_cb.pack(side=tk.LEFT, padx=4)
        self.starter_pool_filter_cb.bind("<<ComboboxSelected>>", lambda e: self._filter_starter_cards_tree())

        lbl_sum = tk.Label(
            bar,
            textvariable=self.starter_slots_sum_var,
            font=("Segoe UI", 9, "bold"),
            fg="#00FF66",
            bg="#2A2A36",
            padx=8, pady=3,
            relief=tk.RIDGE
        )
        lbl_sum.pack(side=tk.LEFT, padx=6)

        lbl_cnt = tk.Label(
            bar,
            textvariable=self.starter_count_var,
            font=("Segoe UI", 9),
            fg="#00D2FF",
            bg="#2A2A36",
            padx=8, pady=3,
            relief=tk.RIDGE
        )
        lbl_cnt.pack(side=tk.LEFT, padx=4)

        # Action buttons
        ttk.Button(bar, text="➕ Catálogo (722 Cartas)", style="Action.TButton", command=self._on_add_starter_card_dialog).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bar, text="⚖️ Normalizar Pools", command=self._on_normalize_starter_deck).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bar, text="🔄 Reset Vanilla", command=self._on_reset_starter_deck).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bar, text="📥 Importar Mazo Inicial", style="Purple.TButton", command=self._on_import_starter_deck_dialog).pack(side=tk.RIGHT, padx=3)

        # Quick Add entry & button
        quick_f = ttk.Frame(bar)
        quick_f.pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Label(quick_f, text="Añadir Rápido:").pack(side=tk.LEFT, padx=(0, 2))
        q_ent = ttk.Entry(quick_f, textvariable=self.quick_add_starter_var, width=12)
        q_ent.pack(side=tk.LEFT, padx=2)
        q_ent.bind("<Return>", lambda e: self._on_quick_add_starter_card())
        ttk.Button(quick_f, text="⚡ +48 Peso", command=self._on_quick_add_starter_card).pack(side=tk.LEFT, padx=2)
        ttk.Button(quick_f, text="🎲 Probabilidad...", command=self._on_quick_add_with_prob_prompt).pack(side=tk.LEFT, padx=2)

        # Paned Window (Split into Pool Table and Inspector)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=14, pady=(4, 10))

        # LEFT PANE: Table of cards in pool
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=3)

        tree_cols = ("id", "name", "pool", "weight", "pool_pct", "deck_prob", "expected")
        self.starter_tree = ttk.Treeview(left_frame, columns=tree_cols, show="headings", selectmode="browse")
        self.starter_tree.heading("id", text="#")
        self.starter_tree.heading("name", text="Carta")
        self.starter_tree.heading("pool", text="Pool Asignado")
        self.starter_tree.heading("weight", text="Peso en Pool")
        self.starter_tree.heading("pool_pct", text="Prob. Tiro")
        self.starter_tree.heading("deck_prob", text="Prob. Mazo 40 Cartas")
        self.starter_tree.heading("expected", text="Copias Medias")

        self.starter_tree.column("id", width=42, anchor="center")
        self.starter_tree.column("name", width=160, anchor="w")
        self.starter_tree.column("pool", width=140, anchor="w")
        self.starter_tree.column("weight", width=85, anchor="center")
        self.starter_tree.column("pool_pct", width=80, anchor="center")
        self.starter_tree.column("deck_prob", width=125, anchor="center")
        self.starter_tree.column("expected", width=85, anchor="center")

        tree_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.starter_tree.yview)
        self.starter_tree.configure(yscrollcommand=tree_scroll.set)
        self.starter_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.starter_tree.bind("<<TreeviewSelect>>", self._on_starter_card_selected)

        # RIGHT PANE: Inspector & Artwork Preview
        right_frame = ttk.LabelFrame(paned, text=" Inspector y Probabilidad de Mazo Inicial ")
        paned.add(right_frame, weight=2)

        insp_inner = ttk.Frame(right_frame)
        insp_inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Card Title
        self.starter_insp_card_lbl = tk.Label(
            insp_inner,
            textvariable=self.edit_starter_card_name_var,
            font=("Segoe UI", 12, "bold"),
            fg="#00D2FF",
            bg="#1E1E24"
        )
        self.starter_insp_card_lbl.pack(anchor="w", pady=(0, 6))

        # Pool selector
        pool_sel_row = ttk.Frame(insp_inner)
        pool_sel_row.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(pool_sel_row, text="Pool de Asignación:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.starter_insp_pool_cb = ttk.Combobox(
            pool_sel_row,
            textvariable=self.edit_starter_pool_var,
            values=[
                "Pool 0: Monstruos Menores (16 cartas)",
                "Pool 1: Monstruos Medios (16 cartas)",
                "Pool 2: Monstruos Mayores (4 cartas)",
                "Pool 3: Monstruos Clave / Jefes (1 carta)",
                "Pool 4: Magias de Limpieza (1 carta)",
                "Pool 5: Magias de Campo (1 carta)",
                "Pool 6: Magias de Equipo (1 carta)"
            ],
            state="readonly",
            width=30
        )
        self.starter_insp_pool_cb.pack(side=tk.LEFT, padx=6)
        self.starter_insp_pool_cb.bind("<<ComboboxSelected>>", self._on_starter_pool_changed)

        # Weight Row (Spinbox / Entry)
        w_row = ttk.Frame(insp_inner)
        w_row.pack(fill=tk.X, pady=4)
        ttk.Label(w_row, text="Peso en Pool (0 a 2048):", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.starter_weight_spin = ttk.Spinbox(
            w_row, from_=0, to=2048, textvariable=self.edit_starter_weight_var, width=7, font=("Segoe UI", 9)
        )
        self.starter_weight_spin.pack(side=tk.LEFT, padx=(8, 4))
        self.starter_weight_spin.bind("<KeyRelease>", self._on_starter_weight_typed)
        self.starter_weight_spin.bind("<FocusOut>", self._on_starter_weight_typed)

        # Scale slider
        self.starter_slider = ttk.Scale(
            insp_inner, from_=0, to=2048, orient=tk.HORIZONTAL, command=self._on_starter_slider_moved
        )
        self.starter_slider.pack(fill=tk.X, pady=(2, 6))

        # Probability Statistics
        stats_frame = ttk.Frame(insp_inner)
        stats_frame.pack(fill=tk.X, pady=4)

        ttk.Label(stats_frame, text="Probabilidad por tiro en su pool:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(stats_frame, textvariable=self.edit_starter_pool_pct_var, font=("Segoe UI", 9, "bold"), fg="#00FF66", bg="#1E1E24").grid(row=0, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(stats_frame, text="Probabilidad final en Mazo (40 cartas):", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=2)
        tk.Label(stats_frame, textvariable=self.edit_starter_deck_prob_var, font=("Segoe UI", 9, "bold"), fg="#FFD700", bg="#1E1E24").grid(row=1, column=1, sticky="w", padx=6, pady=2)

        ttk.Label(stats_frame, text="Copias promedio esperadas en mazo:", font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=2)
        tk.Label(stats_frame, textvariable=self.edit_starter_expected_var, font=("Segoe UI", 9, "bold"), fg="#00D2FF", bg="#1E1E24").grid(row=2, column=1, sticky="w", padx=6, pady=2)

        # Quick Presets
        presets_box = ttk.LabelFrame(insp_inner, text=" Presets Rápidos ")
        presets_box.pack(fill=tk.X, pady=6)

        p_row1 = ttk.Frame(presets_box)
        p_row1.pack(fill=tk.X, padx=4, pady=3)
        ttk.Button(p_row1, text="⭐ Frecuente (120 peso)", command=lambda: self._on_quick_set_starter_weight(120)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(p_row1, text="🌟 Alta (512 peso)", command=lambda: self._on_quick_set_starter_weight(512)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        p_row2 = ttk.Frame(presets_box)
        p_row2.pack(fill=tk.X, padx=4, pady=3)
        ttk.Button(p_row2, text="🔥 Casi Segura (1024 peso)", command=lambda: self._on_quick_set_starter_weight(1024)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(p_row2, text="👑 Garantizada (2048 peso - 100%)", command=lambda: self._on_quick_set_starter_weight(2048)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        p_row3 = ttk.Frame(presets_box)
        p_row3.pack(fill=tk.X, padx=4, pady=3)
        ttk.Button(p_row3, text="❌ Quitar de este Pool (0 peso)", command=lambda: self._on_quick_set_starter_weight(0)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Buttons
        btn_row = ttk.Frame(insp_inner)
        btn_row.pack(fill=tk.X, pady=6)
        ttk.Button(btn_row, text="💾 Aplicar Peso", style="Action.TButton", command=self._on_save_starter_card_weight).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(btn_row, text="🗑️ Quitar Carta", command=self._on_remove_starter_card).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Authentic Card Artwork Preview
        ttk.Separator(insp_inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
        ttk.Label(insp_inner, text="Vista Previa Auténtica de Carta:", font=("Segoe UI", 9, "bold"), foreground="#00D2FF").pack(anchor="w", pady=(0, 2))
        self.starter_card_canvas = tk.Canvas(insp_inner, width=185, height=270, bg="#101014", highlightthickness=1, highlightbackground="#33333E")
        self.starter_card_canvas.pack(anchor="center", pady=(0, 4))
        self.starter_card_renderer = CardCanvasRenderer(self.starter_card_canvas, graphics_db=self.graphics_db)

    def _parse_selected_pool_filter(self) -> Optional[int]:
        txt = self.starter_pool_filter_var.get()
        if "Todos" in txt:
            return None
        for i in range(7):
            if f"Pool {i}" in txt:
                return i
        return None

    def _refresh_starter_deck_table(self):
        """Populates the starter deck tree with cards in pool."""
        if not hasattr(self, 'starter_tree'):
            return

        query = self.starter_search_var.get().strip().lower()
        pool_filter = self._parse_selected_pool_filter()
        active_cards = self.starter_deck_db.get_active_cards(pool_filter=pool_filter)

        for item in self.starter_tree.get_children():
            self.starter_tree.delete(item)

        matched_count = 0
        for item in active_cards:
            cid = item["card_id"]
            name = self.get_card_display_name(cid)
            if query and (query not in name.lower() and query not in str(cid)):
                continue

            self.starter_tree.insert(
                "", tk.END,
                iid=str(cid),
                values=(
                    f"#{cid:03d}",
                    name,
                    item.get("pool_name", f"Pool {item.get('pool_index', 0)}"),
                    f"{item['weight']} / 2048",
                    f"{item['pool_pct']:.3f} %",
                    f"{item['deck_prob_pct']:.2f} %",
                    f"{item['expected_copies']:.2f}"
                )
            )
            matched_count += 1

        if pool_filter is not None and pool_filter < len(self.starter_deck_db.pools):
            p_obj = self.starter_deck_db.pools[pool_filter]
            p_sum = p_obj.total_weight
            self.starter_slots_sum_var.set(f"Pool {pool_filter} Suma: {p_sum}/2048 (Tiros: {p_obj.draws})")
        else:
            self.starter_slots_sum_var.set("7 Pools Activos (40 cartas mazo)")
        self.starter_count_var.set(f"Cartas en vista: {matched_count}")

        # Select first item if nothing selected
        if self.starter_tree.get_children() and not self.starter_tree.selection():
            first_id = self.starter_tree.get_children()[0]
            self.starter_tree.selection_set(first_id)
            self._on_starter_card_selected()

    def _filter_starter_cards_tree(self):
        self._refresh_starter_deck_table()

    def _on_starter_card_selected(self, _event=None):
        sel = self.starter_tree.selection()
        if not sel:
            return
        try:
            cid = int(sel[0])
        except ValueError:
            return

        self.selected_starter_card_id = cid
        cname = self.get_card_display_name(cid)
        self.edit_starter_card_name_var.set(f"#{cid:03d} {cname}")

        pool_idx = self._parse_selected_pool_filter()
        if pool_idx is None:
            pool_idx = self.starter_deck_db.route_card_to_pool(cid)

        pool_options = [
            "Pool 0: Monstruos Menores (16 cartas)",
            "Pool 1: Monstruos Medios (16 cartas)",
            "Pool 2: Monstruos Mayores (4 cartas)",
            "Pool 3: Monstruos Clave / Jefes (1 carta)",
            "Pool 4: Magias de Limpieza (1 carta)",
            "Pool 5: Magias de Campo (1 carta)",
            "Pool 6: Magias de Equipo (1 carta)"
        ]
        if 0 <= pool_idx < len(pool_options):
            self.edit_starter_pool_var.set(pool_options[pool_idx])

        weight = self.starter_deck_db.get_pool_weight(cid, pool_idx)
        self.edit_starter_weight_var.set(str(weight))
        if hasattr(self, 'starter_slider'):
            self.starter_slider.set(weight)

        pool_pct = self.starter_deck_db.get_card_percentage(cid, pool_index=pool_idx)
        deck_prob = self.starter_deck_db.get_authentic_probability_in_deck(cid)
        expected = self.starter_deck_db.get_authentic_expected_copies(cid)

        self.edit_starter_pool_pct_var.set(f"{pool_pct:.3f} %")
        self.edit_starter_deck_prob_var.set(f"{deck_prob:.2f} %")
        self.edit_starter_expected_var.set(f"{expected:.2f} copias")

        # Render preview
        card = self.get_card_object(cid)
        if hasattr(self, 'starter_card_renderer'):
            self.starter_card_renderer.render(card, width=185, height=270)

    def _on_starter_pool_changed(self, _event=None):
        cid = self.selected_starter_card_id
        if not cid:
            return
        p_txt = self.edit_starter_pool_var.get()
        p_idx = int(p_txt.split(":")[0].replace("Pool", "").strip())
        w = self.starter_deck_db.get_pool_weight(cid, p_idx)
        self.edit_starter_weight_var.set(str(w))
        if hasattr(self, 'starter_slider'):
            self.starter_slider.set(w)
        self._update_starter_prob_labels(w)

    def _on_starter_weight_typed(self, _event=None):
        try:
            val = int(self.edit_starter_weight_var.get().strip())
            val = max(0, min(2048, val))
            if hasattr(self, 'starter_slider'):
                self.starter_slider.set(val)
            self._update_starter_prob_labels(val)
        except ValueError:
            pass

    def _on_starter_slider_moved(self, val_str):
        try:
            val = int(float(val_str))
            self.edit_starter_weight_var.set(str(val))
            self._update_starter_prob_labels(val)
        except ValueError:
            pass

    def _update_starter_prob_labels(self, weight: int):
        cid = self.selected_starter_card_id
        if not cid:
            return
        p_txt = self.edit_starter_pool_var.get()
        try:
            p_idx = int(p_txt.split(":")[0].replace("Pool", "").strip())
        except (ValueError, IndexError):
            p_idx = 0
        pool_pct = (weight / 2048.0) * 100.0
        draws = self.starter_deck_db.pools[p_idx].draws if p_idx < len(self.starter_deck_db.pools) else 1
        p_none = (1.0 - (weight / 2048.0)) ** draws if weight < 2048 else 0.0
        deck_prob = max(0.0, min(100.0, (1.0 - p_none) * 100.0))
        expected = draws * (weight / 2048.0)

        self.edit_starter_pool_pct_var.set(f"{pool_pct:.3f} %")
        self.edit_starter_deck_prob_var.set(f"{deck_prob:.2f} %")
        self.edit_starter_expected_var.set(f"{expected:.2f} copias")

    def _on_quick_set_starter_weight(self, weight: int):
        self.edit_starter_weight_var.set(str(weight))
        if hasattr(self, 'starter_slider'):
            self.starter_slider.set(weight)
        self._update_starter_prob_labels(weight)
        self._on_save_starter_card_weight()

    def _on_save_starter_card_weight(self):
        cid = self.selected_starter_card_id
        if not cid:
            messagebox.showinfo("Atención", "Por favor selecciona una carta primero.")
            return

        try:
            new_weight = int(self.edit_starter_weight_var.get().strip())
            new_weight = max(0, min(2048, new_weight))
        except ValueError:
            messagebox.showerror("Error", "El peso debe ser un número entero entre 0 y 2048.")
            return

        p_txt = self.edit_starter_pool_var.get()
        try:
            p_idx = int(p_txt.split(":")[0].replace("Pool", "").strip())
        except (ValueError, IndexError):
            p_idx = 0

        self.starter_deck_db.set_pool_card_weight(p_idx, cid, new_weight)
        cname = self.get_card_display_name(cid)
        msg = f"Peso actualizado para #{cid:03d} {cname} en Pool {p_idx}: {new_weight} / 2048."
        self.status_var.set(msg)
        self.log(msg)
        self._refresh_starter_deck_table()
        if self.starter_tree.exists(str(cid)):
            self.starter_tree.selection_set(str(cid))
            self.starter_tree.see(str(cid))

    def _on_remove_starter_card(self):
        cid = self.selected_starter_card_id
        if not cid:
            messagebox.showinfo("Atención", "Por favor selecciona una carta primero.")
            return

        cname = self.get_card_display_name(cid)
        p_txt = self.edit_starter_pool_var.get()
        try:
            p_idx = int(p_txt.split(":")[0].replace("Pool", "").strip())
        except (ValueError, IndexError):
            p_idx = 0
        if messagebox.askyesno("Confirmar eliminación", f"¿Deseas quitar a #{cid:03d} {cname} de Pool {p_idx} (peso 0)?"):
            self.starter_deck_db.remove_card(cid, pool_index=p_idx)
            self._refresh_starter_deck_table()
            self.status_var.set(f"#{cid:03d} {cname} eliminada de Pool {p_idx}.")

    def _on_normalize_starter_deck(self):
        p_filter = self._parse_selected_pool_filter()
        self.starter_deck_db.normalize(pool_index=p_filter)
        self._refresh_starter_deck_table()
        msg = f"Pool {p_filter} normalizado a 2048." if p_filter is not None else "Todos los 7 pools normalizados a 2048."
        self.status_var.set(msg)
        messagebox.showinfo("Normalización Exitosa", f"{msg}\nSuma de pesos verificada en 2048 por pool.")

    def _on_reset_starter_deck(self):
        if messagebox.askyesno("Confirmar restablecimiento", "¿Deseas restablecer los 7 pools del mazo inicial a los valores originales de Vanilla?"):
            self.starter_deck_db.reset_to_vanilla()
            self._refresh_starter_deck_table()
            self.status_var.set("Mazo inicial restablecido a Vanilla (7 pools).")
            messagebox.showinfo("Restablecido", "Los 7 pools del mazo inicial han sido restaurados con la distribución original de Yu-Gi-Oh! Forbidden Memories.")

    def _on_quick_add_starter_card(self):
        query = self.quick_add_starter_var.get().strip()
        if not query:
            return
        cid = self._resolve_card_input(query)
        if not cid:
            messagebox.showerror("Carta no encontrada", f"No se encontró ninguna carta que coincida con '{query}'.\nIngresa un número (1-722) o parte del nombre.")
            return

        cname = self.get_card_display_name(cid)
        curr = self.starter_deck_db.get_weight(cid)
        new_weight = curr + 10 if curr > 0 else 10
        self.starter_deck_db.set_card_weight(cid, new_weight)
        self._refresh_starter_deck_table()
        if self.starter_tree.exists(str(cid)):
            self.starter_tree.selection_set(str(cid))
            self.starter_tree.see(str(cid))
            self._on_starter_card_selected()
        self.quick_add_starter_var.set("")
        p_idx = self.starter_deck_db.route_card_to_pool(cid)
        pw = self.starter_deck_db.get_pool_weight(cid, p_idx)
        msg = f"#{cid:03d} {cname} asignada a Pool {p_idx} con peso {pw}/2048 ({new_weight} slots)."
        self.status_var.set(msg)
        self.log(msg)

    def _on_quick_add_with_prob_prompt(self):
        """Open the focused probability prompt for the card entered in quick add, or for the selected card."""
        query = self.quick_add_starter_var.get().strip()
        if query:
            cid = self._resolve_card_input(query)
            if not cid:
                messagebox.showerror("Carta no encontrada", f"No se encontró ninguna carta que coincida con '{query}'.\nIngresa un número (1-722) o parte del nombre.")
                return
            self.quick_add_starter_var.set("")
            self._on_prompt_add_card_to_starter(card_id=cid)
        else:
            self._on_prompt_add_card_to_starter()

    def _on_add_inspected_card_to_starter(self):
        if not self.active_card:
            messagebox.showinfo("Atención", "Por favor selecciona una carta en el catálogo primero.")
            return
        cid = self.active_card.card_id
        self._on_prompt_add_card_to_starter(card_id=cid)

    def _on_prompt_add_card_to_starter(self, card_id: Optional[int] = None):
        """Prompt the user directly for the probability / pool to add or update a card in the starter deck.
        Does NOT open a catalog search window.
        """
        if card_id is None:
            if self.active_card:
                card_id = self.active_card.card_id
            elif hasattr(self, 'starter_tree') and self.starter_tree.selection():
                try:
                    card_id = int(self.starter_tree.selection()[0])
                except ValueError:
                    card_id = None

        if card_id is None:
            inp = simpledialog.askstring("Añadir al Mazo Inicial", "Ingresa el ID (1-722) o nombre de la carta:", parent=self)
            if not inp or not inp.strip():
                return
            card_id = self._resolve_card_input(inp.strip())
            if not card_id:
                messagebox.showerror("Error", f"No se encontró ninguna carta que coincida con '{inp}'.")
                return

        cid = int(card_id)
        if not (1 <= cid <= 722):
            messagebox.showerror("Error", f"ID de carta #{cid} fuera de rango (1-722).")
            return

        cname = self.get_card_display_name(cid)
        card = self.get_card_object(cid)

        # Determine best starting pool
        curr_pool_idx = self._parse_selected_pool_filter()
        if curr_pool_idx is None:
            curr_pool_idx = self.starter_deck_db.route_card_to_pool(cid)

        curr_w = self.starter_deck_db.get_pool_weight(cid, curr_pool_idx)
        curr_pct = self.starter_deck_db.get_card_percentage(cid, pool_index=curr_pool_idx)

        dlg = tk.Toplevel(self)
        dlg.title(f"🎴 Asignar al Mazo Inicial - #{cid:03d} {cname}")
        dlg.geometry("540x510")
        dlg.minsize(500, 480)
        dlg.configure(bg="#1E1E24")
        dlg.transient(self)
        dlg.grab_set()

        # Header with Card Info badge
        header_frame = tk.Frame(dlg, bg="#252532", bd=1, relief=tk.RIDGE)
        header_frame.pack(fill=tk.X, padx=16, pady=(14, 8))

        tk.Label(
            header_frame,
            text=f"#{cid:03d}  {cname}",
            font=("Segoe UI", 12, "bold"),
            fg="#00D2FF",
            bg="#252532"
        ).pack(anchor="w", padx=12, pady=(10, 2))

        if card:
            tname = CARD_TYPES[card.type_id] if card.type_id < len(CARD_TYPES) else "Monstruo"
            if card.type_id < 20:
                details_txt = f"Tipo: {tname} | ATK: {card.atk} / DEF: {card.def_} | GS1: {card.gs1_name}"
            else:
                details_txt = f"Tipo: {tname} | Magia / Trampa / Ritual"
        else:
            details_txt = "Carta Yu-Gi-Oh! Forbidden Memories"

        tk.Label(
            header_frame,
            text=details_txt,
            font=("Segoe UI", 9),
            fg="#E0E0E0",
            bg="#252532"
        ).pack(anchor="w", padx=12, pady=(0, 4))

        status_lbl = tk.Label(
            header_frame,
            text=f"✔ Ya en Pool {curr_pool_idx} con peso {curr_w}/2048 ({curr_pct:.2f}%)" if curr_w > 0 else "⚪ No incluida actualmente en este pool (0 peso)",
            font=("Segoe UI", 9, "bold"),
            fg="#00FF66" if curr_w > 0 else "#A0A0A0",
            bg="#252532"
        )
        status_lbl.pack(anchor="w", padx=12, pady=(0, 10))

        # Body: Probability input & calculations
        body_frame = tk.Frame(dlg, bg="#1E1E24")
        body_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # Pool selection row
        pool_row = ttk.Frame(body_frame)
        pool_row.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(pool_row, text="Pool de Asignación:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

        pool_options = [
            "Pool 0: Monstruos Menores (16 cartas)",
            "Pool 1: Monstruos Medios (16 cartas)",
            "Pool 2: Monstruos Mayores (4 cartas)",
            "Pool 3: Monstruos Clave / Jefes (1 carta)",
            "Pool 4: Magias de Limpieza (1 carta)",
            "Pool 5: Magias de Campo (1 carta)",
            "Pool 6: Magias de Equipo (1 carta)"
        ]
        var_pool = tk.StringVar(value=pool_options[curr_pool_idx])
        cb_pool = ttk.Combobox(pool_row, textvariable=var_pool, values=pool_options, state="readonly", width=32)
        cb_pool.pack(side=tk.LEFT, padx=10)

        # Weight input row
        input_row = ttk.Frame(body_frame)
        input_row.pack(fill=tk.X, pady=(4, 6))

        ttk.Label(
            input_row,
            text="Peso en Pool (1 a 2048):",
            font=("Segoe UI", 10, "bold")
        ).pack(side=tk.LEFT)

        default_w = curr_w if curr_w > 0 else 48
        var_weight = tk.StringVar(value=str(default_w))

        spin_weight = ttk.Spinbox(
            input_row,
            from_=1,
            to=2048,
            textvariable=var_weight,
            width=8,
            font=("Segoe UI", 10, "bold")
        )
        spin_weight.pack(side=tk.LEFT, padx=10)

        # Scale slider for intuitive adjustment
        slider_var = tk.DoubleVar(value=float(default_w))
        scale_slider = ttk.Scale(
            body_frame,
            from_=1,
            to=2048,
            variable=slider_var,
            orient=tk.HORIZONTAL
        )
        scale_slider.pack(fill=tk.X, pady=(2, 8))

        # Live calculation statistics box
        stats_box = tk.LabelFrame(
            body_frame,
            text=" Estimación en Partida Nueva (Mazo Inicial de 40 cartas) ",
            font=("Segoe UI", 9, "bold"),
            fg="#00D2FF",
            bg="#1E1E24"
        )
        stats_box.pack(fill=tk.X, pady=(2, 8))

        stats_inner = tk.Frame(stats_box, bg="#1E1E24")
        stats_inner.pack(fill=tk.X, padx=10, pady=8)

        lbl_prob_shot = tk.Label(stats_inner, text="", font=("Segoe UI", 9), fg="#FFFFFF", bg="#1E1E24", anchor="w")
        lbl_prob_shot.pack(fill=tk.X, pady=1)

        lbl_prob_deck = tk.Label(stats_inner, text="", font=("Segoe UI", 9, "bold"), fg="#FFD700", bg="#1E1E24", anchor="w")
        lbl_prob_deck.pack(fill=tk.X, pady=1)

        lbl_expected = tk.Label(stats_inner, text="", font=("Segoe UI", 9), fg="#00FF66", bg="#1E1E24", anchor="w")
        lbl_expected.pack(fill=tk.X, pady=1)

        _updating = [False]

        def get_selected_pool_index():
            txt = var_pool.get()
            try:
                return int(txt.split(":")[0].replace("Pool", "").strip())
            except (ValueError, IndexError):
                return 0

        def update_stats(*args):
            if _updating[0]:
                return
            _updating[0] = True
            try:
                raw_text = var_weight.get().strip()
                if not raw_text:
                    return
                val = int(raw_text)
                val = max(1, min(2048, val))
            except ValueError:
                return
            finally:
                _updating[0] = False

            if slider_var.get() != float(val):
                slider_var.set(float(val))

            p_idx = get_selected_pool_index()
            draws = self.starter_deck_db.pools[p_idx].draws if p_idx < len(self.starter_deck_db.pools) else 1
            pool_pct = (val / 2048.0) * 100.0
            p_none = (1.0 - (val / 2048.0)) ** draws if val < 2048 else 0.0
            deck_prob = max(0.0, min(100.0, (1.0 - p_none) * 100.0))
            expected = draws * (val / 2048.0)

            p_name = self.starter_deck_db.pools[p_idx].name
            lbl_prob_shot.config(text=f"• Probabilidad por tiro en {p_name} ({draws} tiros): {val}/2048 ({pool_pct:.2f}%)")
            lbl_prob_deck.config(text=f"• Probabilidad de tener ≥1 copia en el Mazo Inicial: {deck_prob:.1f}%")
            lbl_expected.config(text=f"• Copias promedio esperadas en el mazo: {expected:.2f}")

        def on_slider_changed(val_str):
            if _updating[0]:
                return
            try:
                v = int(round(float(val_str)))
                v = max(1, min(2048, v))
                var_weight.set(str(v))
                update_stats()
            except ValueError:
                pass

        def on_pool_changed(e=None):
            p_idx = get_selected_pool_index()
            w = self.starter_deck_db.get_pool_weight(cid, p_idx)
            if w > 0:
                var_weight.set(str(w))
                status_lbl.config(
                    text=f"✔ Ya en Pool {p_idx} con peso {w}/2048 ({(w/2048.0)*100:.2f}%)",
                    fg="#00FF66"
                )
            else:
                status_lbl.config(
                    text=f"⚪ No incluida actualmente en Pool {p_idx} (0 peso)",
                    fg="#A0A0A0"
                )
            update_stats()

        cb_pool.bind("<<ComboboxSelected>>", on_pool_changed)
        scale_slider.config(command=on_slider_changed)
        spin_weight.bind("<KeyRelease>", update_stats)
        spin_weight.bind("<FocusOut>", update_stats)

        # Quick Presets Buttons
        presets_frame = ttk.LabelFrame(body_frame, text=" Presets Rápidos ")
        presets_frame.pack(fill=tk.X, pady=(0, 8))

        p_row = ttk.Frame(presets_frame)
        p_row.pack(fill=tk.X, padx=6, pady=6)

        def set_preset_val(w: int):
            var_weight.set(str(w))
            slider_var.set(float(w))
            update_stats()

        ttk.Button(p_row, text="⭐ Frecuente (120)", command=lambda: set_preset_val(120)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(p_row, text="🌟 Alta (512)", command=lambda: set_preset_val(512)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(p_row, text="🔥 Casi Segura (1024)", command=lambda: set_preset_val(1024)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(p_row, text="👑 Garantizada (2048 - 100%)", command=lambda: set_preset_val(2048)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        update_stats()

        # Bottom Buttons
        bottom_frame = ttk.Frame(dlg)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=16, pady=(0, 14))

        action_label = "💾 Guardar en Mazo Inicial"

        def confirm_add():
            try:
                w = int(var_weight.get().strip())
                if not (1 <= w <= 2048):
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Error", "Por favor ingresa un peso válido entre 1 y 2048.", parent=dlg)
                return

            p_idx = get_selected_pool_index()
            self.starter_deck_db.set_pool_card_weight(p_idx, cid, w)
            self._refresh_starter_deck_table()

            if hasattr(self, 'starter_tree') and self.starter_tree.exists(str(cid)):
                self.starter_tree.selection_set(str(cid))
                self.starter_tree.see(str(cid))
                self._on_starter_card_selected()

            pool_pct = (w / 2048.0) * 100.0
            draws = self.starter_deck_db.pools[p_idx].draws if p_idx < len(self.starter_deck_db.pools) else 1
            p_none = (1.0 - (w / 2048.0)) ** draws if w < 2048 else 0.0
            deck_prob = max(0.0, min(100.0, (1.0 - p_none) * 100.0))

            msg = f"#{cid:03d} {cname} asignada a Pool {p_idx} con peso {w}/2048 ({pool_pct:.2f}% tiro, {deck_prob:.1f}% en mazo)."
            self.status_var.set(msg)
            self.log(msg)
            dlg.destroy()
            messagebox.showinfo(
                "Mazo Inicial Actualizado",
                f"¡#{cid:03d} {cname} asignada exitosamente a Pool {p_idx}!\n\n"
                f"• Peso asignado: {w} / 2048\n"
                f"• Probabilidad por tiro en pool: {pool_pct:.2f}%\n"
                f"• Probabilidad en Mazo Inicial (40 cartas): {deck_prob:.1f}%\n\n"
                f"Al exportar la ROM, el cambio quedará grabado directamente en DATA/WA_MRG.MRG (sector 7983)."
            )

        btn_confirm = ttk.Button(bottom_frame, text=action_label, style="Action.TButton", command=confirm_add)
        btn_confirm.pack(side=tk.RIGHT, padx=(6, 0))

        btn_cancel = ttk.Button(bottom_frame, text="Cancelar", command=dlg.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=6)

        spin_weight.focus_set()

    def _on_add_starter_card_dialog(self, preselect_card_id: Optional[int] = None):
        dlg = tk.Toplevel(self)
        dlg.title("➕ Catálogo y Asignación de Cartas al Mazo Inicial")
        dlg.geometry("870x590")
        dlg.minsize(790, 520)
        dlg.configure(bg="#1E1E24")
        dlg.transient(self)
        dlg.grab_set()

        top_box = ttk.Frame(dlg)
        top_box.pack(fill=tk.X, padx=14, pady=(12, 6))

        tk.Label(top_box, text="📚 Catálogo de Cartas y Probabilidad del Mazo Inicial",
                 font=("Segoe UI", 12, "bold"), fg="#00D2FF", bg="#1E1E24").pack(anchor="w")
        tk.Label(top_box, text="Busca cualquier carta de las 722 disponibles para incorporarla o cambiar sus slots en el pool inicial.",
                 font=("Segoe UI", 9), fg="#A0A0A0", bg="#1E1E24").pack(anchor="w", pady=(2, 4))

        # Filter bar
        filter_bar = ttk.Frame(top_box)
        filter_bar.pack(fill=tk.X, pady=4)

        ttk.Label(filter_bar, text="Buscar:").pack(side=tk.LEFT, padx=(0, 4))
        var_search = tk.StringVar()
        ent_search = ttk.Entry(filter_bar, textvariable=var_search, width=22)
        ent_search.pack(side=tk.LEFT, padx=4)

        ttk.Label(filter_bar, text="Tipo:").pack(side=tk.LEFT, padx=(8, 4))
        var_type = tk.StringVar(value="Todos")
        cb_type = ttk.Combobox(filter_bar, textvariable=var_type, values=["Todos"] + CARD_TYPES, state="readonly", width=14)
        cb_type.pack(side=tk.LEFT, padx=4)

        lbl_count = tk.Label(filter_bar, text="Cartas: 722", font=("Segoe UI", 9), fg="#00FF66", bg="#2A2A36", padx=6, pady=2, relief=tk.RIDGE)
        lbl_count.pack(side=tk.RIGHT, padx=4)

        # PanedWindow: Left Table / Right Inspector & Card Art
        paned = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        # LEFT: 722 Catalog Treeview
        left_p = ttk.Frame(paned)
        paned.add(left_p, weight=3)

        cols = ("id", "name", "type", "stats", "pool_slots")
        cat_tree = ttk.Treeview(left_p, columns=cols, show="headings", selectmode="browse")
        cat_tree.heading("id", text="#")
        cat_tree.heading("name", text="Nombre de Carta")
        cat_tree.heading("type", text="Tipo")
        cat_tree.heading("stats", text="ATK / DEF")
        cat_tree.heading("pool_slots", text="En Pool Inicial")

        cat_tree.column("id", width=42, anchor="center")
        cat_tree.column("name", width=175, anchor="w")
        cat_tree.column("type", width=95, anchor="center")
        cat_tree.column("stats", width=85, anchor="center")
        cat_tree.column("pool_slots", width=105, anchor="center")

        cat_scroll = ttk.Scrollbar(left_p, orient=tk.VERTICAL, command=cat_tree.yview)
        cat_tree.configure(yscrollcommand=cat_scroll.set)
        cat_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cat_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # RIGHT: Inspector & Preview
        right_p = ttk.LabelFrame(paned, text=" Inspector y Asignación de Slots ")
        paned.add(right_p, weight=2)

        insp_box = ttk.Frame(right_p)
        insp_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        sel_card_var = tk.StringVar(value="Selecciona una carta")
        tk.Label(insp_box, textvariable=sel_card_var, font=("Segoe UI", 11, "bold"), fg="#00D2FF", bg="#1E1E24", wraplength=280).pack(anchor="w", pady=(0, 4))

        status_pool_var = tk.StringVar(value="Estado: 0 slots (0.00%)")
        tk.Label(insp_box, textvariable=status_pool_var, font=("Segoe UI", 9), fg="#A0A0A0", bg="#1E1E24").pack(anchor="w", pady=(0, 4))

        # Mini card canvas
        dlg_card_canvas = tk.Canvas(insp_box, width=150, height=220, bg="#101014", highlightthickness=1, highlightbackground="#33333E")
        dlg_card_canvas.pack(anchor="center", pady=(0, 4))
        dlg_renderer = CardCanvasRenderer(dlg_card_canvas, graphics_db=self.graphics_db)

        # Weight / Probability Controls
        w_box = ttk.Frame(insp_box)
        w_box.pack(fill=tk.X, pady=4)
        ttk.Label(w_box, text="Slots (0 a 1024):", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        var_weight = tk.StringVar(value="10")
        ent_w = ttk.Spinbox(w_box, from_=0, to=1024, textvariable=var_weight, width=6)
        ent_w.pack(side=tk.LEFT, padx=6)

        # Dynamic Stats
        prob_stats_var = tk.StringVar(value="Tiro: 0.98% | Mazo 40: 32.5% | Copias: 0.39")
        tk.Label(insp_box, textvariable=prob_stats_var, font=("Segoe UI", 8, "italic"), fg="#00FF66", bg="#1E1E24").pack(anchor="w", pady=2)

        def update_dlg_stats(*args):
            try:
                w = int(var_weight.get().strip())
                w = max(0, min(1024, w))
            except ValueError:
                return
            pool_pct = (w / 1024.0) * 100.0
            p_none = (1.0 - (w / 1024.0)) ** 40 if w < 1024 else 0.0
            deck_prob = max(0.0, min(100.0, (1.0 - p_none) * 100.0))
            expected = 40.0 * (w / 1024.0)
            prob_stats_var.set(f"Tiro: {pool_pct:.2f}% | Mazo 40: {deck_prob:.1f}% | Copias: {expected:.2f}")

        ent_w.bind("<KeyRelease>", update_dlg_stats)
        ent_w.bind("<FocusOut>", update_dlg_stats)

        # Presets Buttons Frame
        p_frame = ttk.LabelFrame(insp_box, text=" Presets Rápidos ")
        p_frame.pack(fill=tk.X, pady=4)

        p_row_a = ttk.Frame(p_frame)
        p_row_a.pack(fill=tk.X, padx=4, pady=2)

        def set_preset(w: int):
            var_weight.set(str(w))
            update_dlg_stats()

        ttk.Button(p_row_a, text="⭐ Normal (10)", command=lambda: set_preset(10)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(p_row_a, text="🌟 Frecuente (40)", command=lambda: set_preset(40)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        p_row_b = ttk.Frame(p_frame)
        p_row_b.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(p_row_b, text="🔥 Alta (120)", command=lambda: set_preset(120)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(p_row_b, text="👑 Garantizada (256)", command=lambda: set_preset(256)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Action Buttons in dialog
        btn_box = ttk.Frame(insp_box)
        btn_box.pack(fill=tk.X, pady=(6, 0))

        cur_selected_dlg_cid = [preselect_card_id if preselect_card_id else 1]

        def on_cat_card_selected(_event=None):
            sel = cat_tree.selection()
            if not sel:
                return
            try:
                cid = int(sel[0])
            except ValueError:
                return
            cur_selected_dlg_cid[0] = cid
            cname = self.get_card_display_name(cid)
            card = self.get_card_object(cid)
            sel_card_var.set(f"#{cid:03d} {cname}")

            cur_w = self.starter_deck_db.get_weight(cid)
            if cur_w > 0:
                cur_pct = (cur_w / 1024.0) * 100.0
                status_pool_var.set(f"En Pool Actual: {cur_w} slots ({cur_pct:.2f}%)")
                var_weight.set(str(cur_w))
            else:
                status_pool_var.set("En Pool Actual: No incluida (0 slots)")
                if int(var_weight.get() or "0") == 0:
                    var_weight.set("10")

            update_dlg_stats()
            if card:
                dlg_renderer.render(card, width=150, height=220)

        cat_tree.bind("<<TreeviewSelect>>", on_cat_card_selected)

        def populate_catalog():
            q = var_search.get().strip().lower()
            t_filter = var_type.get()

            for item in cat_tree.get_children():
                cat_tree.delete(item)

            shown = 0
            for cid in range(1, 723):
                card = self.get_card_object(cid)
                cname = self.get_card_display_name(cid)
                tname = CARD_TYPES[card.type_id] if card and card.type_id < len(CARD_TYPES) else "Monster"

                if t_filter != "Todos" and tname != t_filter:
                    continue

                if q and (q not in cname.lower() and q not in str(cid) and q not in tname.lower()):
                    continue

                cur_w = self.starter_deck_db.get_weight(cid)
                pool_txt = f"✔ {cur_w} slots" if cur_w > 0 else "—"
                stats_txt = f"{card.atk}/{card.def_}" if card and card.type_id < 20 else "—"

                cat_tree.insert("", tk.END, iid=str(cid), values=(
                    f"#{cid:03d}",
                    cname,
                    tname,
                    stats_txt,
                    pool_txt
                ))
                shown += 1

            lbl_count.configure(text=f"Cartas: {shown} / 722")

            # Selection
            target_sel = str(cur_selected_dlg_cid[0])
            if cat_tree.exists(target_sel):
                cat_tree.selection_set(target_sel)
                cat_tree.see(target_sel)
                on_cat_card_selected()
            elif cat_tree.get_children():
                first = cat_tree.get_children()[0]
                cat_tree.selection_set(first)
                cat_tree.see(first)
                on_cat_card_selected()

        ent_search.bind("<KeyRelease>", lambda e: populate_catalog())
        cb_type.bind("<<ComboboxSelected>>", lambda e: populate_catalog())

        def apply_add_to_pool():
            cid = cur_selected_dlg_cid[0]
            if not cid or not (1 <= cid <= 722):
                return
            try:
                w = int(var_weight.get().strip())
                w = max(0, min(2048, w))
            except ValueError:
                messagebox.showerror("Error", "El peso debe ser un número entero entre 0 y 2048.", parent=dlg)
                return

            self.starter_deck_db.set_card_weight(cid, w)
            self._refresh_starter_deck_table()
            cname = self.get_card_display_name(cid)

            if cat_tree.exists(str(cid)):
                card = self.get_card_object(cid)
                tname = CARD_TYPES[card.type_id] if card and card.type_id < len(CARD_TYPES) else "Monster"
                stats_txt = f"{card.atk}/{card.def_}" if card and card.type_id < 20 else "—"
                pool_txt = f"✔ {w} peso" if w > 0 else "—"
                cat_tree.item(str(cid), values=(f"#{cid:03d}", cname, tname, stats_txt, pool_txt))

            if w > 0:
                cur_pct = (w / 2048.0) * 100.0
                status_pool_var.set(f"En Pool Actual: {w}/2048 ({cur_pct:.2f}%)")
                msg = f"#{cid:03d} {cname} agregada/actualizada con peso {w}/2048 en el Mazo Inicial."
            else:
                status_pool_var.set("En Pool Actual: No incluida (0 peso)")
                msg = f"#{cid:03d} {cname} retirada del Mazo Inicial (0 peso)."

            self.status_var.set(msg)
            self.log(msg)

        ttk.Button(btn_box, text="➕ Aplicar al Mazo Inicial", style="Action.TButton", command=apply_add_to_pool).pack(fill=tk.X, pady=2)
        ttk.Button(btn_box, text="🗑️ Quitar del Mazo (0 peso)", command=lambda: [var_weight.set("0"), apply_add_to_pool()]).pack(fill=tk.X, pady=2)
        ttk.Button(btn_box, text="✔️ Cerrar Ventana", command=dlg.destroy).pack(fill=tk.X, pady=2)

        populate_catalog()

    def _on_import_starter_deck_dialog(self):
        path = filedialog.askopenfilename(
            title="Seleccionar Mod/ISO para importar Mazo Inicial",
            filetypes=[("Imágenes de Disco PS1", "*.iso *.bin *.img"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        try:
            iso = PS1DiscImage(path)
            slus_key = None
            wa_key = None
            for k in iso.file_table:
                if any(x in k.upper() for x in ("SLUS_", "SLES_", "SLPM_")):
                    slus_key = k
                elif "WA_MRG.MRG" in k.upper():
                    wa_key = k

            slus_key = slus_key or "SLUS_014.11"
            exe_bytes = iso.extract_file(slus_key) if slus_key in iso.file_table else None
            wa_bytes = iso.extract_file(wa_key) if wa_key and wa_key in iso.file_table else None

            loaded = 0
            if wa_bytes is not None:
                loaded = self.starter_deck_db.import_from_mod(wa_bytes, exe_bytes)
            elif exe_bytes is not None:
                loaded = self.starter_deck_db.import_from_mod(exe_bytes)

            if loaded > 0:
                self._refresh_starter_deck_table()
                msg = f"¡Mazo inicial importado con éxito ({loaded} slots / 7 pools) de {os.path.basename(path)}!"
                self.status_var.set(msg)
                self.log(msg)
            else:
                messagebox.showwarning("Atención", "No se encontró una configuración válida de mazo inicial en el archivo.")
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al importar mazo inicial:\n{str(e)}")

    # ------------------------------------------------------------------
    # Card Effect & Trigger Generator Dialog
    # ------------------------------------------------------------------

    def _open_effect_generator_dialog(self):
        """Interactive effect & trigger builder modal for Forbidden Memories."""
        if not self.active_card:
            messagebox.showinfo("Atención", "Por favor selecciona una carta primero en la lista.")
            return

        c = self.active_card

        win = tk.Toplevel(self)
        win.title(f"⚡ Generador de Efectos y Disparadores - #{c.card_id:03d} {c.name}")
        win.geometry("640x600")
        win.minsize(580, 540)
        win.configure(bg="#1E1E24")
        win.transient(self)
        win.grab_set()

        # Header
        header = ttk.Frame(win)
        header.pack(fill=tk.X, padx=14, pady=10)
        tk.Label(header, text=f"⚡ Asistente de Efectos: #{c.card_id:03d} {c.name}",
                 font=("Segoe UI", 12, "bold"), fg="#00D2FF", bg="#1E1E24").pack(anchor="w")
        tk.Label(header, text="Configura el disparador (trigger), la acción del efecto y formatea la descripción para PS1.",
                 font=("Segoe UI", 9), fg="#A0A0A0", bg="#1E1E24").pack(anchor="w")

        body = ttk.LabelFrame(win, text=" Configuración de Disparadores y Efectos ")
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        # 1. Tipo de Carta
        row1 = ttk.Frame(body)
        row1.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row1, text="Tipo de Carta:", width=18).pack(side=tk.LEFT)
        cur_tname = "Trap" if c.type_id == 21 else ("Magic" if c.type_id in (20, 23) else ("Ritual" if c.type_id == 22 else "Monster"))
        type_var = tk.StringVar(value=cur_tname)
        type_combo = ttk.Combobox(row1, textvariable=type_var, values=["Magic", "Trap", "Ritual", "Equip", "Monster"], state="readonly", width=18)
        type_combo.pack(side=tk.LEFT, padx=4)

        # 2. Disparador / Trigger
        row2 = ttk.Frame(body)
        row2.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row2, text="Disparador (Trigger):", width=18).pack(side=tk.LEFT)
        trigger_var = tk.StringVar(value="Al recibir ataque enemigo (Trampa)" if c.type_id == 21 else "Al activarse directamente desde mano (Mágica)")
        trigger_combo = ttk.Combobox(row2, textvariable=trigger_var, values=[
            "Al recibir ataque enemigo (Trampa)",
            "Al invocar enemigo monstruo con ATK <= Umbral",
            "Al invocar enemigo monstruo con ATK >= Umbral",
            "Al activarse directamente desde mano (Mágica)",
            "Al activar enemigo Mágica/Trampa (Contratrampa)",
            "Efecto pasivo continuo en campo (Terreno/Equipo)",
            "Al ofrecer 3 sacrificios específicos (Ritual)",
        ], state="readonly", width=38)
        trigger_combo.pack(side=tk.LEFT, padx=4)

        # 3. Acción Principal
        row3 = ttk.Frame(body)
        row3.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row3, text="Acción Principal:", width=18).pack(side=tk.LEFT)
        action_var = tk.StringVar(value="Destruir el monstruo atacante" if c.type_id == 21 else "Destruir todos los monstruos enemigos (Raigeki)")
        action_combo = ttk.Combobox(row3, textvariable=action_var, values=[
            "Destruir el monstruo atacante",
            "Destruir todos los monstruos en el campo (Dark Hole)",
            "Destruir todos los monstruos enemigos (Raigeki)",
            "Destruir todas las magias/trampas enemigas (Feather Duster)",
            "Infligir daño directo a los LP enemigos (Burn)",
            "Recuperar Puntos de Vida propios (Heal)",
            "Inmovilizar / Congelar ataques enemigos (Swords)",
            "Modificar ATK y DEF (+500 / +1000 ATK/DEF)",
            "Cambiar posición de batalla a Modo Defensa",
            "Invocación Ritual de monstruo supremo",
        ], state="readonly", width=38)
        action_combo.pack(side=tk.LEFT, padx=4)

        # 4. Parámetros dinámicos
        param_frame = ttk.Frame(body)
        param_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(param_frame, text="Parámetro / Valor:", width=18).pack(side=tk.LEFT)
        param_val_var = tk.StringVar(value="1500")
        param_ent = ttk.Entry(param_frame, textvariable=param_val_var, width=12)
        param_ent.pack(side=tk.LEFT, padx=4)
        param_lbl = ttk.Label(param_frame, text="ATK / LP / Turnos", foreground="#00D2FF")
        param_lbl.pack(side=tk.LEFT, padx=6)

        # Idioma
        lang_var = tk.StringVar(value="English")
        lang_frame = ttk.Frame(body)
        lang_frame.pack(fill=tk.X, padx=10, pady=4)
        ttk.Label(lang_frame, text="Idioma de Texto:", width=18).pack(side=tk.LEFT)
        ttk.Radiobutton(lang_frame, text="Inglés (Oficial Konami)", variable=lang_var, value="English", command=lambda: update_generated_text()).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(lang_frame, text="Español", variable=lang_var, value="Spanish", command=lambda: update_generated_text()).pack(side=tk.LEFT, padx=6)

        # 5. Vista Previa de Texto Generado
        txt_frame = ttk.LabelFrame(body, text=" Vista Previa Formateada para PS1 (Max 24 car/línea) ")
        txt_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        gen_text = tk.Text(txt_frame, height=4, width=40, wrap=tk.WORD,
                           bg="#141419", fg="#00FFCC", insertbackground="#00D2FF",
                           font=("Consolas", 10))
        gen_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Technical engine signature box
        mips_lbl = tk.Label(body, text="", font=("Consolas", 8), fg="#FFD700", bg="#1E1E24", justify=tk.LEFT)
        mips_lbl.pack(fill=tk.X, padx=10, pady=(0, 4))

        def update_generated_text(*args):
            t_type = type_var.get()
            trig = trigger_var.get()
            act = action_var.get()
            val = param_val_var.get().strip() or "1000"
            is_es = (lang_var.get() == "Spanish")

            lines = []
            mips_info = ""

            if "Dark Hole" in act:
                lines = ["¡Absorbe todas las", "cartas de monstruo", "en el campo!"] if is_es else ["Sucks up every card", "in play on the field!"]
                mips_info = "⚡ Rutina MIPS: 0x80036C40 [Board Clear]. Afecta todas las casillas de monstruo."
            elif "Raigeki" in act:
                lines = ["¡Destruye todos los", "monstruos enemigos", "con un rayo veloz!"] if is_es else ["Destroys every", "opposing monster", "with a stroke", "of lightning!"]
                mips_info = "⚡ Rutina MIPS: 0x80036CA8 [Opponent Field Wipe]. Elimina monstruos 6 a 10."
            elif "Feather Duster" in act:
                lines = ["¡Barre todas las", "cartas mágicas y", "trampas del rival!"] if is_es else ["Wipes out all of", "your opponent's", "magic and trap cards!"]
                mips_info = "⚡ Rutina MIPS: 0x80036D20 [Spell Trap Sweep]. Limpia slots de magia/trampa rival."
            elif "Burn" in act or "daño" in act.lower():
                lines = [f"¡Inflige {val} puntos", "de daño directo", "a los LP rivales!"] if is_es else [f"Inflicts {val} points", "of direct damage", "to opponent's LP!"]
                mips_info = f"⚡ Rutina MIPS: 0x80037100 [Burn Subroutine]. Resta {val} de LP enemigo."
            elif "Heal" in act or "recuperar" in act.lower():
                lines = [f"¡Restaura {val} puntos", "a tus Puntos de Vida!"] if is_es else [f"Restores {val} points", "to your Life Points!"]
                mips_info = f"⚡ Rutina MIPS: 0x80037200 [Heal Routine]. Suma {val} a LP jugador."
            elif "Swords" in act or "congelar" in act.lower():
                lines = ["¡Inmoviliza a los", "monstruos rivales", f"durante {val} turnos!"] if is_es else ["Freezes all opposing", "monsters and prevents", f"attacks for {val} turns!"]
                mips_info = f"⚡ Rutina MIPS: 0x80037340 [Stun Flag]. Activa contador por {val} turnos."
            elif "atacante" in act.lower():
                lines = ["¡Destruye al monstruo", "enemigo cuando este", "declara un ataque!"] if is_es else ["Destroys the opposing", "monster when it", "declares an attack!"]
                mips_info = "⚡ Rutina MIPS: Disparador 0x80038200 [On Attack Trigger]. Destruye target atacante."
            elif "<= Umbral" in trig:
                lines = [f"Destruye al monstruo", f"rival con ATK {val}", "o menor al invocarse."] if is_es else [f"Destroys any enemy", f"monster with ATK {val}", "or less when summoned."]
                mips_info = f"⚡ Rutina MIPS: 0x80038310. Opcode: slti v0, a0, {val}. Destruye en invocación."
            elif ">= Umbral" in trig:
                lines = [f"Destruye al monstruo", f"rival con ATK {val}", "o mayor al invocarse."] if is_es else [f"Destroys any enemy", f"monster with ATK {val}", "or more when summoned."]
                mips_info = f"⚡ Rutina MIPS: 0x80038360. Opcode: slti v0, a0, {val}. Destruye pesados."
            elif "Ritual" in t_type or "Ritual" in trig:
                lines = ["Sacrifica 3 monstruos", "específicos para", "invocar una entidad", "legendaria."] if is_es else ["Sacrifices 3 specific", "monsters from field", "or hand to summon", "a legendary entity!"]
                mips_info = "⚡ Rutina MIPS: 0x80039000 [Ritual Dispatch]. Valida 3 materiales en tabla WA_MRG."
            elif "Equip" in t_type or "Modificar" in act:
                lines = [f"Aumenta el ATK y DEF", f"en {val} puntos a los", "monstruos compatibles."] if is_es else [f"Increases ATK and DEF", f"by {val} points for", "compatible monsters."]
                mips_info = f"⚡ Rutina MIPS: Tabla de compatibilidad en WA_MRG.MRG. Aplica +{val} ATK/DEF."
            else:
                lines = ["Activa poderes y", "efectos en el campo."] if is_es else ["Activates special", "powers on the field."]
                mips_info = "⚡ Rutina estándar de magia/habilidad de Yu-Gi-Oh! Forbidden Memories."

            full_desc = "\n".join(lines)
            gen_text.delete("1.0", tk.END)
            gen_text.insert("1.0", full_desc)
            mips_lbl.config(text=mips_info)

        type_combo.bind("<<ComboboxSelected>>", update_generated_text)
        trigger_combo.bind("<<ComboboxSelected>>", update_generated_text)
        action_combo.bind("<<ComboboxSelected>>", update_generated_text)
        param_ent.bind("<KeyRelease>", update_generated_text)

        update_generated_text()

        # Bottom buttons
        btn_box = ttk.Frame(win)
        btn_box.pack(fill=tk.X, padx=14, pady=(0, 12))

        def apply_effect():
            chosen_type = type_var.get()
            chosen_desc = gen_text.get("1.0", tk.END).strip()
            if chosen_type in CARD_TYPES:
                self.curr_type_var.set(chosen_type)
            if hasattr(self, 'curr_desc_text'):
                self.curr_desc_text.delete("1.0", tk.END)
                self.curr_desc_text.insert("1.0", chosen_desc)
            if self.active_card:
                if chosen_type in CARD_TYPES:
                    self.active_card.type_id = CARD_TYPES.index(chosen_type)
                self.active_card.description = chosen_desc
                self._render_current_card_from_ui()
            win.destroy()
            self.status_var.set(f"Efecto y disparador configurados para #{c.card_id:03d} {c.name}.")

        ttk.Button(btn_box, text="⚡ Aplicar a la Carta Actual", style="Action.TButton", command=apply_effect).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_box, text="Cancelar", command=win.destroy).pack(side=tk.RIGHT, padx=4)

    # ------------------------------------------------------------------
    # Duel Fields & Arenas Tab (Campos de Duelo / Terrenos)
    # ------------------------------------------------------------------

    FIELD_OPTIONS = [
        "0: 🏛️ Normal (Coliseo Egipcio - Neutral)",
        "1: 🌲 Bosque (Forest #301 - Insecto, Bestia, Planta, Guerrero-Bestia)",
        "2: 🏜️ Páramo / Desierto (Wasteland #302 - Dinosaurio, Zombi, Roca, Máquina)",
        "3: ⛰️ Montaña (Mountain #303 - Dragón, Bestia Alada, Trueno)",
        "4: 🌾 Pradera (Sogen #304 - Guerrero, Guerrero-Bestia)",
        "5: 🌊 Mar / Océano (Umi #305 - Pez, Serpiente Marina, Trueno, Aqua | -Piro)",
        "6: 🔮 Oscuridad (Yami #306 - Lanzador de Conjuros, Demonio | -Hada)",
    ]

    FIELD_SAMPLE_MONSTERS = [
        {"id": 1, "name": "Blue-Eyes White Dragon", "type": "Dragon", "atk": 3000, "def": 2500, "disp": "001: Blue-Eyes White Dragon [Dragon - 3000/2500]"},
        {"id": 35, "name": "Dark Magician", "type": "Spellcaster", "atk": 2500, "def": 2100, "disp": "035: Dark Magician [Spellcaster - 2500/2100]"},
        {"id": 22, "name": "Summoned Skull", "type": "Fiend", "atk": 2500, "def": 1200, "disp": "022: Summoned Skull [Fiend - 2500/1200]"},
        {"id": 713, "name": "Meteor B. Dragon", "type": "Dragon", "atk": 3500, "def": 2000, "disp": "713: Meteor B. Dragon [Dragon - 3500/2000]"},
        {"id": 28, "name": "Flame Swordsman", "type": "Warrior", "atk": 1800, "def": 1600, "disp": "028: Flame Swordsman [Warrior - 1800/1600]"},
        {"id": 361, "name": "Firegrass", "type": "Plant", "atk": 700, "def": 600, "disp": "361: Firegrass [Plant - 700/600]"},
        {"id": 149, "name": "Great White", "type": "Fish", "atk": 1600, "def": 800, "disp": "149: Great White [Fish - 1600/800]"},
        {"id": 364, "name": "Fire Reaper", "type": "Pyro", "atk": 700, "def": 500, "disp": "364: Fire Reaper [Pyro - 700/500]"},
        {"id": 367, "name": "Gyakutenno Megami", "type": "Fairy", "atk": 1800, "def": 2000, "disp": "367: Gyakutenno Megami [Fairy - 1800/2000]"},
        {"id": 365, "name": "Labyrinth Wall", "type": "Rock", "atk": 0, "def": 3000, "disp": "365: Labyrinth Wall [Rock - 0/3000]"},
        {"id": 78, "name": "Hercules Beetle", "type": "Insect", "atk": 1500, "def": 2000, "disp": "078: Hercules Beetle [Insect - 1500/2000]"},
        {"id": 110, "name": "Armored Zombie", "type": "Zombie", "atk": 1500, "def": 0, "disp": "110: Armored Zombie [Zombie - 1500/0]"},
        {"id": 124, "name": "Megazowler", "type": "Dinosaur", "atk": 1800, "def": 2000, "disp": "124: Megazowler [Dinosaur - 1800/2000]"},
    ]

    def _build_fields_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" 🏟️ Campos de Duelo (Terrenos) ")

        # Top Bar: Field selector, Presets, Actions
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=14, pady=(10, 6))

        ttk.Label(bar, text="Campo de Duelo:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        field_cb = ttk.Combobox(
            bar, textvariable=self.field_selector_var,
            values=self.FIELD_OPTIONS,
            state="readonly", width=42
        )
        field_cb.pack(side=tk.LEFT, padx=4)
        field_cb.bind("<<ComboboxSelected>>", self._on_field_selected)

        ttk.Label(bar, text="Estilo Preset:").pack(side=tk.LEFT, padx=(12, 4))
        preset_cb = ttk.Combobox(
            bar, textvariable=self.field_preset_var,
            values=list(FIELD_PRESETS.keys()), state="readonly", width=26
        )
        preset_cb.pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="⚡ Aplicar Estilo", style="Action.TButton", command=self._on_apply_field_preset).pack(side=tk.LEFT, padx=4)

        # Action buttons
        ttk.Button(bar, text="🔄 Reset Vanilla", command=self._on_reset_field_colors).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bar, text="📥 Cargar JSON", command=self._on_import_fields_json).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bar, text="💾 Exportar JSON", command=self._on_export_fields_json).pack(side=tk.RIGHT, padx=3)

        # Paned Window (Left Board Preview | Right Inspector)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        # LEFT: Board Battlefield Canvas Preview
        left_f = ttk.LabelFrame(paned, text=" Vista Previa del Campo de Duelo (Perspectiva 3D 5x2 Casillas) ")
        paned.add(left_f, weight=3)

        board_inner = ttk.Frame(left_f)
        board_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self.field_board_canvas = tk.Canvas(board_inner, width=570, height=365, bg="#0E0E14", highlightthickness=1, highlightbackground="#33333E")
        self.field_board_canvas.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self.duel_board_renderer = DuelBoardRenderer(self.field_board_canvas, graphics_db=self.graphics_db)

        # Test monster bar
        test_bar = ttk.Frame(board_inner)
        test_bar.pack(fill=tk.X, pady=2)

        ttk.Label(test_bar, text="Probar Carta en Campo:").pack(side=tk.LEFT, padx=(0, 4))
        m_opts = [m["disp"] for m in self.FIELD_SAMPLE_MONSTERS]
        cb_m = ttk.Combobox(test_bar, textvariable=self.field_test_monster_var, values=m_opts, state="readonly", width=38)
        cb_m.pack(side=tk.LEFT, padx=4)
        cb_m.bind("<<ComboboxSelected>>", self._on_field_monster_selected)

        ttk.Label(test_bar, text="Casilla:").pack(side=tk.LEFT, padx=(6, 4))
        cb_slot = ttk.Combobox(test_bar, textvariable=self.field_test_slot_var, values=["M1", "M2", "M3 (Centro)", "M4", "M5"], state="readonly", width=12)
        cb_slot.pack(side=tk.LEFT, padx=4)
        cb_slot.bind("<<ComboboxSelected>>", self._on_field_monster_selected)

        self.field_stat_badge_lbl = tk.Label(board_inner, textvariable=self.field_boost_info_var, font=("Segoe UI", 9, "bold"), fg="#FFD700", bg="#1E1E24", padx=8, pady=4, relief=tk.RIDGE)
        self.field_stat_badge_lbl.pack(fill=tk.X, pady=(4, 0))

        # RIGHT: Inspector & Color Studio
        right_f = ttk.LabelFrame(paned, text=" Personalización del Campo y Terreno ")
        paned.add(right_f, weight=2)

        right_nb = ttk.Notebook(right_f)
        right_nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Subtab 1: Paleta de Colores
        sub_col = ttk.Frame(right_nb)
        right_nb.add(sub_col, text=" 🎨 Paleta de Colores ")

        col_box = ttk.Frame(sub_col)
        col_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        parts = [
            ("ground", "Terreno / Suelo Principal", "Color del suelo o textura base"),
            ("grid", "Líneas de Cuadrícula / Casillas", "Bordes de las casillas de cartas"),
            ("monster_zone", "Zona de Monstruos (M1-M5)", "Relleno de casillas de monstruo"),
            ("spell_zone", "Zona de Magias/Trampas (S1-S5)", "Relleno de casillas de magia"),
            ("border", "Borde Exterior del Coliseo", "Anillo y horizonte del campo"),
            ("sky", "Cielo / Atmósfera / Niebla", "Tinte de la bóveda celeste"),
        ]

        self._field_swatch_widgets = {}
        for r_idx, (pkey, plabel, pdesc) in enumerate(parts):
            row_frame = ttk.Frame(col_box)
            row_frame.pack(fill=tk.X, pady=4)

            swatch = tk.Canvas(row_frame, width=32, height=22, bg="#333333", highlightthickness=1, highlightbackground="#555555")
            swatch.pack(side=tk.LEFT, padx=(0, 6))
            self._field_swatch_widgets[pkey] = swatch

            text_sub = ttk.Frame(row_frame)
            text_sub.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ttk.Label(text_sub, text=plabel, font=("Segoe UI", 9, "bold")).pack(anchor="w")
            ttk.Label(text_sub, text=pdesc, font=("Segoe UI", 8), foreground="#888888").pack(anchor="w")

            ttk.Button(row_frame, text="🎨 Cambiar...", command=lambda k=pkey: self._pick_field_color(k)).pack(side=tk.RIGHT, padx=4)

        # Subtab 2: Imagen y Textura Personalizada
        sub_img = ttk.Frame(right_nb)
        right_nb.add(sub_img, text=" 🖼️ Textura / Imagen ")

        img_box = ttk.Frame(sub_img)
        img_box.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        ttk.Label(img_box, text="Carga una imagen o textura personalizada para este campo de duelo:", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
        ttk.Label(img_box, text="La imagen sustituye el suelo procedural por una textura auténtica en alta resolución.", font=("Segoe UI", 8), foreground="#888888").pack(anchor="w", pady=(0, 10))

        img_status_box = ttk.LabelFrame(img_box, text=" Textura Activa ")
        img_status_box.pack(fill=tk.X, pady=6)
        tk.Label(img_status_box, textvariable=self.field_image_path_var, font=("Segoe UI", 8), fg="#00D2FF", bg="#1E1E24", wraplength=260, justify=tk.LEFT).pack(anchor="w", padx=8, pady=8)

        img_btn_row = ttk.Frame(img_box)
        img_btn_row.pack(fill=tk.X, pady=10)
        ttk.Button(img_btn_row, text="🖼️ Cargar Imagen (PNG/JPG)...", style="Action.TButton", command=self._on_load_field_image).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(img_btn_row, text="✖ Quitar Textura", command=self._on_clear_field_image).pack(side=tk.LEFT, padx=(4, 0))

        # Subtab 3: Efectos y Parches WA_MRG
        sub_fx = ttk.Frame(right_nb)
        right_nb.add(sub_fx, text=" ⚔️ Bonificaciones y WA_MRG ")

        fx_box = ttk.Frame(sub_fx)
        fx_box.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.field_fx_title_lbl = tk.Label(fx_box, text="🏛️ Terreno Neutral", font=("Segoe UI", 11, "bold"), fg="#00D2FF", bg="#1E1E24")
        self.field_fx_title_lbl.pack(anchor="w", pady=(0, 4))

        self.field_fx_desc_lbl = tk.Label(fx_box, text="", font=("Segoe UI", 9), fg="#EDEDED", bg="#1E1E24", wraplength=270, justify=tk.LEFT)
        self.field_fx_desc_lbl.pack(anchor="w", pady=(0, 8))

        wa_info_frame = ttk.LabelFrame(fx_box, text=" Región de Memoria en PS1 WA_MRG.MRG ")
        wa_info_frame.pack(fill=tk.X, pady=6)
        self.field_wa_offset_lbl = tk.Label(wa_info_frame, text="Offset: 0x00B85000 | Stride: 481,280 bytes", font=("Consolas", 8), fg="#FFD700", bg="#1E1E24")
        self.field_wa_offset_lbl.pack(anchor="w", padx=8, pady=6)

        fx_btn_row = ttk.Frame(fx_box)
        fx_btn_row.pack(fill=tk.X, pady=10)
        ttk.Button(fx_btn_row, text="💾 Guardar Cambios de Campo", style="Action.TButton", command=self._on_save_field_changes).pack(fill=tk.X, pady=2)
        ttk.Button(fx_btn_row, text="🛠️ Sincronizar con WA_MRG.MRG", command=self._on_patch_fields_to_wa).pack(fill=tk.X, pady=2)

        self._refresh_fields_ui()

    def _on_field_selected(self, _event=None):
        val = self.field_selector_var.get()
        try:
            fid = int(val.split(":")[0])
            self.selected_field_id = fid
        except (ValueError, IndexError):
            self.selected_field_id = 0
        self._refresh_fields_ui()

    def _on_field_monster_selected(self, _event=None):
        self._refresh_fields_ui()

    def _refresh_fields_ui(self):
        if not hasattr(self, 'duel_board_renderer') or not hasattr(self, 'field_board_canvas'):
            return

        fid = getattr(self, 'selected_field_id', 0)
        fdata = self.field_spells_db.get_field(fid)

        # Update Swatches
        for pkey, swatch in getattr(self, '_field_swatch_widgets', {}).items():
            col = fdata.colors.get(pkey, "#333333")
            swatch.configure(bg=col)

        # Update Image status label
        if hasattr(self, 'field_image_path_var'):
            if fdata.custom_image_path and os.path.exists(fdata.custom_image_path):
                self.field_image_path_var.set(f"📷 {os.path.basename(fdata.custom_image_path)}\n({fdata.custom_image_path})")
            else:
                self.field_image_path_var.set("Procedural (Sin imagen externa / Colores en juego)")

        # Update FX info labels
        meta = FIELD_METADATA.get(fid, {})
        if hasattr(self, 'field_fx_title_lbl'):
            self.field_fx_title_lbl.configure(text=f"{meta.get('symbol', '🏟️')} {fdata.name_es}")
        if hasattr(self, 'field_fx_desc_lbl'):
            self.field_fx_desc_lbl.configure(text=fdata.description)
        if hasattr(self, 'field_wa_offset_lbl'):
            self.field_wa_offset_lbl.configure(text=f"Arena {fid} en WA_MRG: 0x{fdata.wa_offset:08X}\nTamaño bloque: {ARENA_STRIDE:,} bytes (0x{ARENA_STRIDE:X})")

        # Resolve selected test monster
        m_disp = self.field_test_monster_var.get()
        matched_m = self.FIELD_SAMPLE_MONSTERS[0]
        for m in self.FIELD_SAMPLE_MONSTERS:
            if m["disp"] == m_disp:
                matched_m = m
                break

        # Resolve slot index (0..4)
        slot_str = self.field_test_slot_var.get()
        slot_idx = 2
        if "M1" in slot_str:
            slot_idx = 0
        elif "M2" in slot_str:
            slot_idx = 1
        elif "M3" in slot_str:
            slot_idx = 2
        elif "M4" in slot_str:
            slot_idx = 3
        elif "M5" in slot_str:
            slot_idx = 4

        # Calculate live boost
        atk_bonus, def_bonus = self.field_spells_db.calculate_stat_modifier(fid, matched_m["type"])
        fin_atk = max(0, matched_m["atk"] + atk_bonus)
        fin_def = max(0, matched_m["def"] + def_bonus)

        if atk_bonus > 0:
            badge_text = f"⭐ ¡BONIFICACIÓN ACTIVA! {matched_m['name']} [{matched_m['type']}] -> Base: {matched_m['atk']}/{matched_m['def']}  |  En {fdata.name_es}: {fin_atk}/{fin_def} (+{atk_bonus} ATK/DEF)"
            if hasattr(self, 'field_stat_badge_lbl'):
                self.field_stat_badge_lbl.configure(fg="#00FF66")
        elif atk_bonus < 0:
            badge_text = f"⚠️ ¡PENALIZACIÓN ACTIVA! {matched_m['name']} [{matched_m['type']}] -> Base: {matched_m['atk']}/{matched_m['def']}  |  En {fdata.name_es}: {fin_atk}/{fin_def} ({atk_bonus} ATK/DEF)"
            if hasattr(self, 'field_stat_badge_lbl'):
                self.field_stat_badge_lbl.configure(fg="#FF5555")
        else:
            badge_text = f"Terreno Neutral para {matched_m['name']} [{matched_m['type']}]: {matched_m['atk']}/{matched_m['def']} (+0 ATK/DEF)"
            if hasattr(self, 'field_stat_badge_lbl'):
                self.field_stat_badge_lbl.configure(fg="#FFD700")

        self.field_boost_info_var.set(badge_text)

        # Render Canvas
        try:
            self.duel_board_renderer.render(
                field_data=fdata,
                width=570,
                height=365,
                test_monster=matched_m,
                test_slot=slot_idx
            )
        except Exception:
            pass

    def _on_apply_field_preset(self):
        pname = self.field_preset_var.get()
        if self.field_spells_db.apply_preset(pname):
            self._refresh_fields_ui()
            msg = f"Estilo de campo '{pname}' aplicado a las 7 arenas de duelo."
            self.status_var.set(msg)
            self.log(msg)

    def _on_reset_field_colors(self):
        fid = getattr(self, 'selected_field_id', 0)
        if fid in DEFAULT_FIELD_COLORS:
            self.field_spells_db.fields[fid].colors.update(dict(DEFAULT_FIELD_COLORS[fid]))
            self.field_spells_db.clear_field_image(fid)
            self._refresh_fields_ui()
            fname = self.field_spells_db.get_field(fid).name_es
            msg = f"Colores del campo '{fname}' restablecidos a los originales de Vanilla PS1."
            self.status_var.set(msg)
            self.log(msg)

    def _pick_field_color(self, color_key: str):
        fid = getattr(self, 'selected_field_id', 0)
        fdata = self.field_spells_db.get_field(fid)
        curr = fdata.colors.get(color_key, "#FFFFFF")
        chosen = colorchooser.askcolor(color=curr, title=f"Seleccionar color para {color_key} ({fdata.name_es})")
        if chosen and chosen[1]:
            self.field_spells_db.set_field_color(fid, color_key, chosen[1])
            self._refresh_fields_ui()
            self.status_var.set(f"Color {color_key} actualizado a {chosen[1]} en {fdata.name_es}.")

    def _on_load_field_image(self):
        fid = getattr(self, 'selected_field_id', 0)
        fdata = self.field_spells_db.get_field(fid)
        path = filedialog.askopenfilename(
            title=f"Cargar Textura/Imagen de Fondo para {fdata.name_es}",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.webp"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
        if self.field_spells_db.set_field_image(fid, path):
            self._refresh_fields_ui()
            msg = f"Textura personalizada asignada a {fdata.name_es}: {os.path.basename(path)}."
            self.status_var.set(msg)
            self.log(msg)
        else:
            messagebox.showerror("Error", "No se pudo cargar la imagen seleccionada.")

    def _on_clear_field_image(self):
        fid = getattr(self, 'selected_field_id', 0)
        self.field_spells_db.clear_field_image(fid)
        self._refresh_fields_ui()
        fname = self.field_spells_db.get_field(fid).name_es
        msg = f"Textura eliminada de {fname}. Regresando a renderizado procedural."
        self.status_var.set(msg)
        self.log(msg)

    def _on_export_fields_json(self):
        path = filedialog.asksaveasfilename(
            title="Exportar Configuración de Campos de Duelo",
            defaultextension=".json",
            filetypes=[("Archivo JSON", "*.json")]
        )
        if not path:
            return
        if self.field_spells_db.save_to_json_file(path):
            msg = f"Configuración de los 7 campos de duelo exportada a: {os.path.basename(path)}"
            self.status_var.set(msg)
            self.log(msg)
            messagebox.showinfo("Exportación Exitosa", msg)
        else:
            messagebox.showerror("Error", "No se pudo exportar el archivo JSON.")

    def _on_import_fields_json(self):
        path = filedialog.askopenfilename(
            title="Importar Configuración de Campos de Duelo",
            filetypes=[("Archivo JSON", "*.json"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
        count = self.field_spells_db.load_from_json_file(path)
        if count > 0:
            self._refresh_fields_ui()
            msg = f"¡{count} campos de duelo importados exitosamente desde {os.path.basename(path)}!"
            self.status_var.set(msg)
            self.log(msg)
            messagebox.showinfo("Importación Exitosa", msg)
        else:
            messagebox.showerror("Error", "No se pudo cargar la configuración desde el archivo JSON.")

    def _on_save_field_changes(self):
        fid = getattr(self, 'selected_field_id', 0)
        fname = self.field_spells_db.get_field(fid).name_es
        msg = f"Cambios del campo de duelo '{fname}' guardados en memoria del proyecto."
        self.status_var.set(msg)
        self.log(msg)
        messagebox.showinfo("Guardado", msg)

    def _on_patch_fields_to_wa(self):
        msg = "Las 7 arenas de duelo están listas para ser inyectadas en DATA/WA_MRG.MRG al compilar la ROM."
        self.status_var.set(msg)
        self.log(msg)
        messagebox.showinfo("Sincronización WA_MRG", f"{msg}\n\nOffset base: 0x00B85000 | Stride: 481,280 bytes (7 arenas).")

    # ------------------------------------------------------------------
    # Color Studio & Suite Theme Tab
    # ------------------------------------------------------------------

    def _build_colors_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" 🎨 Estudio de Colores / Temas ")

        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Left: Controls Notebook (Frames, Stars, UI Theme)
        left_box = ttk.Frame(paned)
        paned.add(left_box, weight=3)

        color_notebook = ttk.Notebook(left_box)
        color_notebook.pack(fill=tk.BOTH, expand=True)

        # --------------------------------------------------------------
        # Subtab 1: Marcos de Cartas (Normal, Ritual, Magic, Trap)
        # --------------------------------------------------------------
        subtab_frames = ttk.Frame(color_notebook)
        color_notebook.add(subtab_frames, text=" 🃏 Marcos de Cartas ")

        # Presets row
        preset_bar = ttk.Frame(subtab_frames)
        preset_bar.pack(fill=tk.X, padx=10, pady=(10, 6))
        ttk.Label(preset_bar, text="Paleta Predeterminada:").pack(side=tk.LEFT, padx=(0, 6))
        preset_cb = ttk.Combobox(preset_bar, textvariable=self.frame_preset_var,
                                 values=list(FRAME_COLOR_PRESETS.keys()), state="readonly", width=28)
        preset_cb.pack(side=tk.LEFT, padx=4)

        def on_apply_frame_preset():
            p_name = self.frame_preset_var.get()
            apply_frame_preset(p_name)
            self._refresh_color_studio_swatches()
            self._render_color_preview_card()
            self._render_current_card()
            self.status_var.set(f"Paleta de cartas '{p_name}' aplicada.")

        ttk.Button(preset_bar, text="Aplicar Paleta", command=on_apply_frame_preset).pack(side=tk.LEFT, padx=4)

        reset_frames_btn = ttk.Button(preset_bar, text="🔄 Restablecer", command=self._on_reset_frame_colors)
        reset_frames_btn.pack(side=tk.RIGHT, padx=4)

        # Frame Cards Grid
        grid_frame = ttk.Frame(subtab_frames)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        self._frame_swatch_widgets = {}
        frame_types = [
            ("Normal", "Monstruo Normal (Ocre)"),
            ("Ritual", "Monstruo Ritual (Azul)"),
            ("Magic", "Carta Mágica (Verde Esmeralda)"),
            ("Trap", "Carta Trampa (Magenta / Rosa)"),
        ]

        for row_idx, (ftype, fdesc) in enumerate(frame_types):
            row_box = ttk.LabelFrame(grid_frame, text=f" {fdesc} ")
            row_box.pack(fill=tk.X, pady=4, padx=4)

            parts = [
                ("frame", "Color Marco"),
                ("border", "Borde Exterior"),
                ("inner", "Bisel Interior"),
                ("box", "Caja Texto/Lore"),
            ]

            inner_p = ttk.Frame(row_box)
            inner_p.pack(fill=tk.X, padx=8, pady=6)

            for col_idx, (part_key, part_label) in enumerate(parts):
                col_box = ttk.Frame(inner_p)
                col_box.pack(side=tk.LEFT, expand=True, padx=4)

                swatch = tk.Canvas(col_box, width=28, height=18, bg=FRAME_THEMES[ftype][part_key],
                                   highlightthickness=1, highlightbackground="#555555")
                swatch.pack(side=tk.LEFT, padx=3)
                self._frame_swatch_widgets[(ftype, part_key)] = swatch

                btn = ttk.Button(col_box, text=part_label,
                                 command=lambda ft=ftype, pk=part_key: self._pick_frame_color(ft, pk))
                btn.pack(side=tk.LEFT, padx=2)

        # --------------------------------------------------------------
        # Subtab 2: Estrellas Guardianas (10 Estrellas)
        # --------------------------------------------------------------
        subtab_stars = ttk.Frame(color_notebook)
        color_notebook.add(subtab_stars, text=" ⭐ Estrellas Guardianas ")

        star_top = ttk.Frame(subtab_stars)
        star_top.pack(fill=tk.X, padx=10, pady=(10, 4))
        ttk.Label(star_top, text="Colores y Símbolos de las 10 Estrellas Guardianas del Zodíaco Konami:").pack(side=tk.LEFT)
        ttk.Button(star_top, text="🔄 Restablecer Estrellas", command=self._on_reset_star_colors).pack(side=tk.RIGHT)

        stars_grid = ttk.Frame(subtab_stars)
        stars_grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        self._star_swatch_widgets = {}
        for sid in range(1, 11):
            sdata = GUARDIAN_STAR_DATA[sid]
            r = (sid - 1) // 2
            c = (sid - 1) % 2

            s_cell = ttk.Frame(stars_grid)
            s_cell.grid(row=r, column=c, sticky="w", padx=12, pady=5)

            sym_lbl = tk.Label(s_cell, text=sdata["sym"], font=("Segoe UI", 12, "bold"), fg="#FFD700", bg="#1E1E24", width=3)
            sym_lbl.pack(side=tk.LEFT)

            name_lbl = ttk.Label(s_cell, text=sdata["name"], width=12)
            name_lbl.pack(side=tk.LEFT, padx=4)

            swatch = tk.Canvas(s_cell, width=28, height=18, bg=sdata["color"],
                               highlightthickness=1, highlightbackground="#555555")
            swatch.pack(side=tk.LEFT, padx=4)
            self._star_swatch_widgets[sid] = swatch

            btn = ttk.Button(s_cell, text="🎨 Cambiar...", command=lambda s=sid: self._pick_star_color(s))
            btn.pack(side=tk.LEFT, padx=4)

        # --------------------------------------------------------------
        # Subtab 3: Temas de la Suite UI
        # --------------------------------------------------------------
        subtab_theme = ttk.Frame(color_notebook)
        color_notebook.add(subtab_theme, text=" 🖥️ Temas de la Suite ")

        th_bar = ttk.Frame(subtab_theme)
        th_bar.pack(fill=tk.X, padx=10, pady=12)

        ttk.Label(th_bar, text="Tema de Interfaz:").pack(side=tk.LEFT, padx=(0, 6))
        theme_cb = ttk.Combobox(th_bar, textvariable=self.theme_preset_var,
                                values=list(UI_THEME_PRESETS.keys()), state="readonly", width=32)
        theme_cb.pack(side=tk.LEFT, padx=4)

        def on_apply_ui_theme():
            th_name = self.theme_preset_var.get()
            if th_name in UI_THEME_PRESETS:
                self._apply_ui_theme(UI_THEME_PRESETS[th_name])
                self.status_var.set(f"Tema de interfaz '{th_name}' aplicado.")

        ttk.Button(th_bar, text="⚡ Aplicar Tema", style="Action.TButton", command=on_apply_ui_theme).pack(side=tk.LEFT, padx=6)

        th_info_box = ttk.LabelFrame(subtab_theme, text=" Paletas Visuales de la Suite ")
        th_info_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        th_desc = (
            "Esquemas temáticos inspirados en Yu-Gi-Oh! Forbidden Memories:\n\n"
            "• Dark Cyber Cyan: Esquema moderno oscuro con acentos cian de alta visibilidad.\n"
            "• Oro Faraónico: Inspirado en los artefactos del milenio y papiro del Antiguo Egipto.\n"
            "• Mago Oscuro: Tonos púrpuras y violetas místicos inspirados en el hechicero supremo.\n"
            "• KaibaCorp Blue: Azul cibernético y blanco plateado en honor al Blue-Eyes White Dragon.\n"
            "• Retro PS1 1999: Interfaz en tonos grises clásicos de la PlayStation 1 original.\n"
            "• Dragón Negro de Ojos Rojos: Carmesí volcánico y carbón de gran contraste."
        )
        tk.Label(th_info_box, text=th_desc, font=("Segoe UI", 9), justify=tk.LEFT,
                 fg="#C0C0C0", bg="#1E1E24", wraplength=480).pack(padx=14, pady=12, anchor="w")

        # --------------------------------------------------------------
        # Right: Live Interactive Card Canvas Preview
        # --------------------------------------------------------------
        right_box = ttk.LabelFrame(paned, text=" Representación Gráfica en Tiempo Real ")
        paned.add(right_box, weight=2)

        preview_top = ttk.Frame(right_box)
        preview_top.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(preview_top, text="Carta de Prueba:").pack(side=tk.LEFT, padx=2)
        card_sel_combo = ttk.Combobox(
            preview_top,
            textvariable=self.color_preview_card_var,
            values=[
                "Monstruo Normal (Blue-Eyes White Dragon #001)",
                "Monstruo de Efecto / Mago (#035)",
                "Monstruo Ritual (Magician of Black Chaos #722)",
                "Carta Mágica (Dark Hole #336)",
                "Carta Trampa (Widespread Ruin #689)",
            ],
            state="readonly",
            width=36
        )
        card_sel_combo.pack(side=tk.LEFT, padx=4)
        card_sel_combo.bind("<<ComboboxSelected>>", lambda e: self._render_color_preview_card())

        self.color_canvas = tk.Canvas(right_box, width=250, height=365, bg="#121214",
                                      highlightthickness=1, highlightbackground="#00D2FF")
        self.color_canvas.pack(padx=8, pady=8)
        self.color_card_renderer = CardCanvasRenderer(self.color_canvas, graphics_db=self.graphics_db)

        # Initial render of preview card
        self.after(250, self._render_color_preview_card)

    def _pick_frame_color(self, ftype: str, part_key: str):
        curr_hex = FRAME_THEMES[ftype][part_key]
        color = colorchooser.askcolor(color=curr_hex, title=f"Seleccionar Color para {ftype} - {part_key}")
        if color and color[1]:
            new_hex = color[1]
            FRAME_THEMES[ftype][part_key] = new_hex
            if (ftype, part_key) in self._frame_swatch_widgets:
                self._frame_swatch_widgets[(ftype, part_key)].configure(bg=new_hex)
            self._render_color_preview_card()
            self._render_current_card()
            if hasattr(self, 'opp_card_renderer') and self.active_card:
                self.opp_card_renderer.render(self.active_card, width=185, height=270)

    def _on_reset_frame_colors(self):
        reset_frame_colors()
        self._refresh_color_studio_swatches()
        self._render_color_preview_card()
        self._render_current_card()
        self.status_var.set("Colores de marcos de cartas restablecidos a los originales.")

    def _refresh_color_studio_swatches(self):
        for (ftype, part_key), swatch in getattr(self, '_frame_swatch_widgets', {}).items():
            if ftype in FRAME_THEMES and part_key in FRAME_THEMES[ftype]:
                swatch.configure(bg=FRAME_THEMES[ftype][part_key])
        for sid, swatch in getattr(self, '_star_swatch_widgets', {}).items():
            if sid in GUARDIAN_STAR_DATA:
                swatch.configure(bg=GUARDIAN_STAR_DATA[sid]["color"])

    def _pick_star_color(self, sid: int):
        curr_hex = GUARDIAN_STAR_DATA[sid]["color"]
        color = colorchooser.askcolor(color=curr_hex, title=f"Seleccionar Color para Estrella {GUARDIAN_STAR_DATA[sid]['name']}")
        if color and color[1]:
            new_hex = color[1]
            GUARDIAN_STAR_DATA[sid]["color"] = new_hex
            if sid in self._star_swatch_widgets:
                self._star_swatch_widgets[sid].configure(bg=new_hex)
            self._render_color_preview_card()
            self._render_current_card()

    def _on_reset_star_colors(self):
        for k, v in DEFAULT_GUARDIAN_STAR_DATA.items():
            GUARDIAN_STAR_DATA[k] = dict(v)
        self._refresh_color_studio_swatches()
        self._render_color_preview_card()
        self._render_current_card()
        self.status_var.set("Colores de estrellas guardianas restablecidos a los originales.")

    def _render_color_preview_card(self):
        if not hasattr(self, 'color_card_renderer'):
            return
        sel_text = self.color_preview_card_var.get()
        if "001" in sel_text:
            cid = 1
        elif "035" in sel_text:
            cid = 35
        elif "722" in sel_text:
            cid = 722
        elif "336" in sel_text:
            cid = 336
        elif "689" in sel_text:
            cid = 689
        else:
            cid = 1

        card = self.get_card_object(cid)
        self.color_card_renderer.render(card)

    def _apply_ui_theme(self, theme_dict: dict):
        bg = theme_dict["bg"]
        panel_bg = theme_dict["panel_bg"]
        accent = theme_dict["accent"]
        btn_primary = theme_dict["btn_primary"]
        fg = theme_dict["fg"]
        tab_bg = theme_dict.get("tab_bg", panel_bg)

        self.configure(bg=bg)
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabelframe", background=bg, foreground=fg)
        self.style.configure("TLabelframe.Label", background=bg, foreground=accent)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("Action.TButton", background=btn_primary, foreground="#FFFFFF")
        self.style.configure("TNotebook", background=bg)
        self.style.configure("TNotebook.Tab", background=tab_bg, foreground=fg)
        self.style.map("TNotebook.Tab", background=[("selected", btn_primary)], foreground=[("selected", "#FFFFFF")])
        self.style.configure("Treeview", background=panel_bg, foreground=fg, fieldbackground=panel_bg)
        self.style.configure("Treeview.Heading", background=bg, foreground=accent)
        self.style.map("Treeview", background=[("selected", btn_primary)])

    def _build_engine_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" ⚙️ Motor y Recompensas ")

        container = ttk.Frame(tab)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # Drop Section
        drop_group = ttk.LabelFrame(container, text=" Configuración de Recompensas de Duelo ")
        drop_group.pack(fill=tk.X, pady=8, padx=6)

        drop_inner = ttk.Frame(drop_group)
        drop_inner.pack(fill=tk.X, padx=16, pady=12)

        ttk.Label(drop_inner, text="Multiplicador de Drops (Cartas por duelo):", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        drop_spin = ttk.Spinbox(drop_inner, from_=1, to=100, textvariable=self.drop_multiplier_var, width=6, font=("Segoe UI", 10))
        drop_spin.pack(side=tk.LEFT, padx=(10, 16))

        ttk.Label(drop_inner, text="(Valores válidos: 1 a 100 cartas)", foreground="#A0A0A0").pack(side=tk.LEFT)

        # Quick Presets
        presets_bar = ttk.Frame(drop_group)
        presets_bar.pack(fill=tk.X, padx=16, pady=(0, 10))
        ttk.Label(presets_bar, text="Presets Rápidos:", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 8))
        for val, label in [("1", "x1 (Original)"), ("5", "x5"), ("10", "x10"), ("15", "x15 (Dream)"), ("50", "x50"), ("100", "x100 (Express)")]:
            btn = ttk.Button(presets_bar, text=label, width=13, command=lambda v=val: self.drop_multiplier_var.set(v))
            btn.pack(side=tk.LEFT, padx=3)

        # Options Section
        opt_group = ttk.LabelFrame(container, text=" Opciones de Estabilidad y Pantalla de Victoria ")
        opt_group.pack(fill=tk.X, pady=8, padx=6)

        opt_inner = ttk.Frame(opt_group)
        opt_inner.pack(fill=tk.X, padx=16, pady=12)

        cb1 = ttk.Checkbutton(
            opt_inner,
            text="Pantalla de Victoria Nativa de Vanilla Express: Despliega la animación de victoria, rango y cartas sin sobrecarga de VRAM.",
            variable=self.trunk_deposit_var
        )
        cb1.pack(anchor="w", pady=4)

        cb2 = ttk.Checkbutton(
            opt_inner,
            text="Depósito Directo al Baúl: Muestra hasta 4 cartas en pantalla y deposita el resto directamente en el baúl para evitar cuelgues.",
            variable=self.trunk_deposit_var
        )
        cb2.pack(anchor="w", pady=4)

        cb3 = ttk.Checkbutton(
            opt_inner,
            text="Preservar IA y Estabilidad: Protege la ejecución de la IA en memoria para evitar congelamientos en el turno del CPU.",
            variable=self.preserve_ai_var
        )
        cb3.pack(anchor="w", pady=4)

        cb4 = ttk.Checkbutton(
            opt_inner,
            text="Importar Dificultad de CPU y Fusiones del Mod: Aplica la agresividad de fusiones (hasta 75%) y combos de los 39 duelistas del mod.",
            variable=self.import_cpu_ai_var
        )
        cb4.pack(anchor="w", pady=4)

    def _build_logs_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=" 📜 Registro y Consola ")

        self.log_text = tk.Text(tab, bg="#121214", fg="#00FF66", font=("Consolas", 9), wrap=tk.WORD)
        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)

    def log(self, text: str):
        try:
            if hasattr(self, 'log_text') and self.log_text.winfo_exists():
                self.log_text.insert(tk.END, text + "\n")
                self.log_text.see(tk.END)
        except Exception:
            pass

    def _on_browse_base_iso(self):
        path = filedialog.askopenfilename(
            title="Seleccionar ROM / ISO de Yu-Gi-Oh! Forbidden Memories",
            filetypes=[("Imágenes de Disco PS1", "*.iso *.bin *.img"), ("Todos los archivos", "*.*")]
        )
        if path:
            self.base_path_var.set(path)
            self._async_load_base_iso(path)

    def _async_load_base_iso(self, path: str):
        self.status_var.set(f"Cargando {os.path.basename(path)}...")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(10)

        def task():
            try:
                self.log(f"Abriendo imagen de disco: {path}")
                iso = PS1DiscImage(path)
                slus_key = None
                wa_key = None
                for k in iso.file_table:
                    if "SLUS_" in k.upper() or "SLES_" in k.upper() or "SLPM_" in k.upper():
                        slus_key = k
                    elif "WA_MRG.MRG" in k.upper():
                        wa_key = k
                slus_key = slus_key or "SLUS_014.11"
                wa_key = wa_key or "DATA/WA_MRG.MRG"

                exe_bytes = iso.extract_file(slus_key)
                wa_bytes = iso.extract_file(wa_key)

                c_count = self.card_db.load_from_exe_and_wa(exe_bytes, wa_bytes)
                f_count = self.fusion_db.load_from_wa(wa_bytes)
                self.deck_db.load_from_wa_and_exe(wa_bytes, exe_bytes)
                d_count = self.drop_db.load_from_wa(wa_bytes, exe_bytes)
                s_count = self.starter_deck_db.load_from_wa(wa_bytes)
                if s_count == 0:
                    s_count = self.starter_deck_db.load_from_exe(exe_bytes)
                self.graphics_db.set_wa_data(wa_bytes)

                self.base_iso_path = path

                def on_done():
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate", value=100)
                    self.iso_badge_var.set(f"📁 [ROM]: {os.path.basename(path)}")
                    self.status_var.set(f"Cargado: {os.path.basename(path)} ({c_count} cartas, {f_count:,} fusiones, {d_count} drops, {s_count} starter slots)")
                    self.cards_count_var.set(f"Cartas: {c_count} / 722")
                    self.fusions_count_var.set(f"Fusiones: {f_count:,}")
                    self.log(f"Base de datos cargada con éxito: {c_count} cartas, {f_count:,} fusiones, 39 mazos, 39 drops, {s_count} starter slots.")
                    self._populate_cards_tree()
                    self._populate_fusions_tree()
                    self._populate_opponents_tree()
                    self._populate_drop_duelists_tree()
                    self._refresh_drops_table()
                    self._refresh_starter_deck_table()
                    if self.deck_db.decks:
                        self.opp_tree.selection_set("1")
                        self._on_opponent_selected()
                    self._render_current_card()

                try:
                    self.after(0, on_done)
                except Exception:
                    pass
            except Exception as e:
                def on_error(err=e):
                    try:
                        self.progress_bar.stop()
                        self.status_var.set("Error al cargar la imagen.")
                        self.log(f"ERROR: {str(err)}")
                        messagebox.showerror("Error al cargar ISO", f"No se pudo cargar la imagen:\n{str(err)}")
                    except Exception:
                        pass
                try:
                    self.after(0, on_error)
                except Exception:
                    pass

        threading.Thread(target=task, daemon=True).start()

    def _populate_cards_tree(self):
        for item in self.cards_tree.get_children():
            self.cards_tree.delete(item)

        for card_id in range(1, 723):
            c = self.card_db.get(card_id)
            if not c:
                continue
            self.cards_tree.insert(
                "",
                tk.END,
                iid=str(card_id),
                values=(
                    f"#{c.card_id:03d}",
                    c.name,
                    c.atk,
                    c.def_,
                    c.type_name,
                    c.gs1_name,
                    c.gs2_name,
                    f"{c.star_cost:,}"
                )
            )

    def _filter_cards_tree(self):
        query = self.search_card_var.get().strip().lower()
        selected_type = self.filter_type_var.get()

        for item in self.cards_tree.get_children():
            self.cards_tree.delete(item)

        matched = 0
        for card_id in range(1, 723):
            c = self.card_db.get(card_id)
            if not c:
                continue
            if query and (query not in c.name.lower() and query not in str(c.card_id)):
                continue
            if selected_type != "Todos" and c.type_name != selected_type:
                continue

            self.cards_tree.insert(
                "",
                tk.END,
                iid=str(card_id),
                values=(
                    f"#{c.card_id:03d}",
                    c.name,
                    c.atk,
                    c.def_,
                    c.type_name,
                    c.gs1_name,
                    c.gs2_name,
                    f"{c.star_cost:,}"
                )
            )
            matched += 1

        self.cards_count_var.set(f"Filtradas: {matched} / 722")

    def _on_card_selected(self, event):
        sel = self.cards_tree.selection()
        if not sel:
            return
        card_id = int(sel[0])
        c = self.card_db.get(card_id)
        if not c:
            return

        self.active_card = c
        self.curr_card_id_var.set(f"#{c.card_id:03d}")
        self.curr_name_var.set(c.name)
        self.curr_atk_var.set(str(c.atk))
        self.curr_def_var.set(str(c.def_))
        self.curr_type_var.set(c.type_name)
        self.curr_gs1_var.set(c.gs1_name)
        self.curr_gs2_var.set(c.gs2_name)
        self.curr_password_var.set(c.password)
        self.curr_cost_var.set(str(c.star_cost))
        if hasattr(self, 'curr_desc_text'):
            self.curr_desc_text.delete("1.0", tk.END)
            self.curr_desc_text.insert("1.0", c.description or "")
        self.card_renderer.set_custom_image("")
        self._render_current_card()

    def _on_desc_text_edited(self):
        if self.active_card and hasattr(self, 'curr_desc_text'):
            self.active_card.description = self.curr_desc_text.get("1.0", tk.END).strip()
            self._render_current_card_from_ui()

    def _on_save_card_changes(self):
        if not self.active_card:
            messagebox.showinfo("Atención", "Por favor selecciona una carta primero.")
            return

        try:
            new_name = self.curr_name_var.get().strip()
            if new_name:
                self.active_card.name = new_name

            new_atk = int(self.curr_atk_var.get().strip())
            new_def = int(self.curr_def_var.get().strip())
            new_cost = int(self.curr_cost_var.get().strip().replace(",", ""))
            pwd = self.curr_password_var.get().strip()

            type_name = self.curr_type_var.get()
            type_id = CARD_TYPES.index(type_name) if type_name in CARD_TYPES else self.active_card.type_id

            gs1_name = self.curr_gs1_var.get()
            gs1_id = GUARDIAN_STARS.index(gs1_name) if gs1_name in GUARDIAN_STARS else self.active_card.gs1

            gs2_name = self.curr_gs2_var.get()
            gs2_id = GUARDIAN_STARS.index(gs2_name) if gs2_name in GUARDIAN_STARS else self.active_card.gs2

            self.active_card.atk = max(0, min(5110, (new_atk // 10) * 10))
            self.active_card.def_ = max(0, min(5110, (new_def // 10) * 10))
            self.active_card.type_id = type_id
            self.active_card.gs1 = gs1_id
            self.active_card.gs2 = gs2_id
            self.active_card.password = pwd.zfill(8)[:8]
            self.active_card.star_cost = max(0, min(999999, new_cost))
            if hasattr(self, 'curr_desc_text'):
                self.active_card.description = self.curr_desc_text.get("1.0", tk.END).strip()

            # Update item in tree if present
            if self.cards_tree.exists(str(self.active_card.card_id)):
                self.cards_tree.item(
                    str(self.active_card.card_id),
                    values=(
                        f"#{self.active_card.card_id:03d}",
                        self.active_card.name,
                        self.active_card.atk,
                        self.active_card.def_,
                        self.active_card.type_name,
                        self.active_card.gs1_name,
                        self.active_card.gs2_name,
                        f"{self.active_card.star_cost:,}"
                    )
                )
            self._render_current_card()
            self.status_var.set(f"Carta #{self.active_card.card_id:03d} actualizada con éxito en memoria.")
            self.log(f"Carta #{self.active_card.card_id:03d} ({self.active_card.name}) guardada: ATK={self.active_card.atk}, DEF={self.active_card.def_}")
        except Exception as e:
            messagebox.showerror("Error al guardar carta", f"Valores numéricos no válidos: {str(e)}")

    def _render_current_card(self):
        """Renders the authentic card representation on the canvas."""
        if not self.active_card or not hasattr(self, 'card_renderer'):
            return
        self.card_renderer.render(self.active_card)

    def _render_current_card_from_ui(self, _event=None):
        """Live updates the visual card from active UI entries as the user types."""
        if not self.active_card or not hasattr(self, 'card_renderer'):
            return
        try:
            raw_atk = self.curr_atk_var.get().strip()
            raw_def = self.curr_def_var.get().strip()
            atk = int(raw_atk) if raw_atk.isdigit() else self.active_card.atk
            def_ = int(raw_def) if raw_def.isdigit() else self.active_card.def_

            type_name = self.curr_type_var.get()
            type_id = CARD_TYPES.index(type_name) if type_name in CARD_TYPES else self.active_card.type_id

            gs1_name = self.curr_gs1_var.get()
            gs1_id = GUARDIAN_STARS.index(gs1_name) if gs1_name in GUARDIAN_STARS else self.active_card.gs1

            gs2_name = self.curr_gs2_var.get()
            gs2_id = GUARDIAN_STARS.index(gs2_name) if gs2_name in GUARDIAN_STARS else self.active_card.gs2

            pwd = self.curr_password_var.get().strip() or self.active_card.password
            cost_raw = self.curr_cost_var.get().strip().replace(",", "")
            cost = int(cost_raw) if cost_raw.isdigit() else self.active_card.star_cost

            desc = self.curr_desc_text.get("1.0", tk.END).strip() if hasattr(self, 'curr_desc_text') else self.active_card.description

            temp_c = Card(
                card_id=self.active_card.card_id,
                name=self.curr_name_var.get().strip() or self.active_card.name,
                atk=atk,
                def_=def_,
                type_id=type_id,
                gs1=gs1_id,
                gs2=gs2_id,
                password=pwd,
                star_cost=cost,
                description=desc
            )
            self.card_renderer.render(temp_c)
        except Exception:
            pass

    def _on_load_card_artwork(self):
        """Allows user to select and load custom artwork for the active card."""
        if not self.active_card:
            messagebox.showinfo("Atención", "Por favor selecciona una carta primero.")
            return

        path = filedialog.askopenfilename(
            title="Seleccionar Ilustración para la Carta",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.webp"), ("Todos los archivos", "*.*")]
        )
        if path:
            self.card_renderer.set_custom_image(path)
            try:
                from PIL import Image
                custom_img = Image.open(path)
                self.graphics_db.set_custom_art(self.active_card.card_id, custom_img)
            except Exception:
                pass
            self._render_current_card_from_ui()
            msg = f"Ilustración asignada a #{self.active_card.card_id:03d} {self.active_card.name}: {os.path.basename(path)}"
            self.status_var.set(msg)
            self.log(msg)

    def _on_clear_card_artwork(self):
        """Removes custom artwork and restores default procedural/in-game card art."""
        if hasattr(self, 'card_renderer'):
            self.card_renderer.set_custom_image("")
            if self.active_card:
                self.graphics_db.clear_custom_art(self.active_card.card_id)
            self._render_current_card_from_ui()

    def _on_export_card_png(self):
        """Exports the active card as a high-resolution PNG image."""
        if not self.active_card:
            messagebox.showinfo("Atención", "Por favor selecciona una carta primero.")
            return

        default_fn = f"Carta_{self.active_card.card_id:03d}_{self.active_card.name.replace(' ', '_')}.png"
        out_path = filedialog.asksaveasfilename(
            title="Guardar Carta como Imagen PNG",
            initialfile=default_fn,
            defaultextension=".png",
            filetypes=[("Imagen PNG", "*.png")]
        )
        if not out_path:
            return

        try:
            raw_atk = self.curr_atk_var.get().strip()
            raw_def = self.curr_def_var.get().strip()
            atk = int(raw_atk) if raw_atk.isdigit() else self.active_card.atk
            def_ = int(raw_def) if raw_def.isdigit() else self.active_card.def_

            type_name = self.curr_type_var.get()
            type_id = CARD_TYPES.index(type_name) if type_name in CARD_TYPES else self.active_card.type_id

            temp_c = Card(
                card_id=self.active_card.card_id,
                name=self.curr_name_var.get().strip() or self.active_card.name,
                atk=atk,
                def_=def_,
                type_id=type_id,
                password=self.curr_password_var.get().strip(),
                star_cost=int(self.curr_cost_var.get().strip().replace(",", "") or "0")
            )
            ok = export_card_to_png(
                temp_c,
                out_path,
                custom_image_path=self.card_renderer.custom_image_path,
                graphics_db=self.graphics_db
            )
            if ok:
                msg = f"¡Carta exportada exitosamente como imagen en alta resolución!\n\n{out_path}"
                messagebox.showinfo("Exportación Exitosa", msg)
                self.log(f"Carta exportada a PNG: {out_path}")
            else:
                messagebox.showerror("Error", "No se pudo exportar la imagen (requiere módulo Pillow).")
        except Exception as e:
            messagebox.showerror("Error al exportar imagen", str(e))


    def _populate_fusions_tree(self):
        for item in self.fusions_tree.get_children():
            self.fusions_tree.delete(item)

        items_to_add = []
        count = 0
        for (a, b), r in self.fusion_db.fusions.items():
            if count > 2000:
                break  # Populate initial 2000 for rapid display
            name_a = self.get_card_display_name(a)
            name_b = self.get_card_display_name(b)
            name_r = self.get_card_display_name(r)
            items_to_add.append((f"#{a:03d} {name_a}", f"#{b:03d} {name_b}", "➔", f"#{r:03d} {name_r}"))
            count += 1

        for it in items_to_add:
            self.fusions_tree.insert("", tk.END, values=it)

        first_items = self.fusions_tree.get_children()
        if first_items:
            self.fusions_tree.selection_set(first_items[0])
            self._on_fusion_selected()

    def _filter_fusions_tree(self):
        query = self.search_fusion_var.get().strip().lower()
        for item in self.fusions_tree.get_children():
            self.fusions_tree.delete(item)

        matched = 0
        for (a, b), r in self.fusion_db.fusions.items():
            name_a = self.get_card_display_name(a)
            name_b = self.get_card_display_name(b)
            name_r = self.get_card_display_name(r)

            full_line = f"{name_a} {name_b} {name_r} {a} {b} {r}".lower()
            if query and query not in full_line:
                continue

            self.fusions_tree.insert("", tk.END, values=(f"#{a:03d} {name_a}", f"#{b:03d} {name_b}", "➔", f"#{r:03d} {name_r}"))
            matched += 1
            if matched >= 500:
                break

        first_items = self.fusions_tree.get_children()
        if first_items:
            self.fusions_tree.selection_set(first_items[0])
            self._on_fusion_selected()

    def _on_fusion_selected(self, _event=None):
        sel = self.fusions_tree.selection()
        if not sel:
            return
        item = self.fusions_tree.item(sel[0])
        vals = item.get("values", [])
        if len(vals) < 4:
            return
        try:
            cid_a = int(str(vals[0]).split()[0].replace("#", ""))
            cid_b = int(str(vals[1]).split()[0].replace("#", ""))
            cid_r = int(str(vals[3]).split()[0].replace("#", ""))
            self._active_fusion_triple = (cid_a, cid_b, cid_r)
            self._render_active_fusion_card()
        except (ValueError, IndexError):
            pass

    def _set_fusion_preview_mode(self, mode: str):
        self.fusion_preview_mode.set(mode)
        self._render_active_fusion_card()

    def _render_active_fusion_card(self):
        cid_a, cid_b, cid_r = self._active_fusion_triple
        mode = self.fusion_preview_mode.get()
        if mode == "mat_a":
            target_cid = cid_a
            role_text = "Material A"
        elif mode == "mat_b":
            target_cid = cid_b
            role_text = "Material B"
        else:
            target_cid = cid_r
            role_text = "Resultado"

        if 1 <= target_cid <= 722:
            card = self.get_card_object(target_cid)
            self.fusion_info_lbl.configure(text=f"Mostrando {role_text}: #{target_cid:03d} {card.name}")
            if hasattr(self, 'fusion_card_renderer'):
                self.fusion_card_renderer.render(card, width=185, height=270)

    def _resolve_card_input(self, text: str) -> Optional[int]:
        txt = text.strip()
        if not txt:
            return None
        if txt.isdigit():
            val = int(txt)
            if 1 <= val <= 722:
                return val
        if txt.startswith("#"):
            parts = txt[1:].split()
            if parts and parts[0].isdigit():
                val = int(parts[0])
                if 1 <= val <= 722:
                    return val
        txt_lower = txt.lower()
        for cid in range(1, 723):
            cname = self.get_card_display_name(cid).lower()
            if txt_lower == cname:
                return cid
        for cid in range(1, 723):
            cname = self.get_card_display_name(cid).lower()
            if txt_lower in cname:
                return cid
        return None

    def _on_add_fusion_dialog(self):
        """Modal dialog to add a new fusion recipe."""
        dlg = tk.Toplevel(self)
        dlg.title("➕ Agregar Nueva Fusión")
        dlg.geometry("520x330")
        dlg.configure(bg="#1E1E24")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="➕ Crear Nueva Receta de Fusión", font=("Segoe UI", 12, "bold"), fg="#00D2FF", bg="#1E1E24").pack(pady=(12, 8))

        form = ttk.Frame(dlg)
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=4)

        var_a = tk.StringVar()
        var_b = tk.StringVar()
        var_res = tk.StringVar()

        lbl_a = tk.Label(form, text="—", font=("Segoe UI", 9), fg="#A0A0A0", bg="#1E1E24", anchor="w")
        lbl_b = tk.Label(form, text="—", font=("Segoe UI", 9), fg="#A0A0A0", bg="#1E1E24", anchor="w")
        lbl_res = tk.Label(form, text="—", font=("Segoe UI", 9, "bold"), fg="#00FF66", bg="#1E1E24", anchor="w")

        def update_label(var, lbl):
            cid = self._resolve_card_input(var.get())
            if cid:
                lbl.configure(text=f"#{cid:03d} {self.get_card_display_name(cid)}")
            else:
                lbl.configure(text="No identificada (escribe ID 1-722 o nombre)")

        ttk.Label(form, text="Material A:").grid(row=0, column=0, sticky="w", pady=6)
        ent_a = ttk.Entry(form, textvariable=var_a, width=22)
        ent_a.grid(row=0, column=1, sticky="w", padx=6, pady=6)
        lbl_a.grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ent_a.bind("<KeyRelease>", lambda e: update_label(var_a, lbl_a))

        ttk.Label(form, text="Material B:").grid(row=1, column=0, sticky="w", pady=6)
        ent_b = ttk.Entry(form, textvariable=var_b, width=22)
        ent_b.grid(row=1, column=1, sticky="w", padx=6, pady=6)
        lbl_b.grid(row=1, column=2, sticky="w", padx=6, pady=6)
        ent_b.bind("<KeyRelease>", lambda e: update_label(var_b, lbl_b))

        ttk.Label(form, text="Resultado:").grid(row=2, column=0, sticky="w", pady=6)
        ent_res = ttk.Entry(form, textvariable=var_res, width=22)
        ent_res.grid(row=2, column=1, sticky="w", padx=6, pady=6)
        lbl_res.grid(row=2, column=2, sticky="w", padx=6, pady=6)
        ent_res.bind("<KeyRelease>", lambda e: update_label(var_res, lbl_res))

        def do_add():
            cid_a = self._resolve_card_input(var_a.get())
            cid_b = self._resolve_card_input(var_b.get())
            cid_res = self._resolve_card_input(var_res.get())

            if not cid_a:
                messagebox.showerror("Error", "Material A no es una carta válida.", parent=dlg)
                return
            if not cid_b:
                messagebox.showerror("Error", "Material B no es una carta válida.", parent=dlg)
                return
            if not cid_res:
                messagebox.showerror("Error", "Carta Resultado no es una carta válida.", parent=dlg)
                return

            ok = self.fusion_db.add_fusion(cid_a, cid_b, cid_res)
            if ok:
                name_a = self.get_card_display_name(cid_a)
                name_b = self.get_card_display_name(cid_b)
                name_res = self.get_card_display_name(cid_res)

                val_tuple = (f"#{cid_a:03d} {name_a}", f"#{cid_b:03d} {name_b}", "➔", f"#{cid_res:03d} {name_res}")
                item_id = self.fusions_tree.insert("", 0, values=val_tuple)
                self.fusions_tree.selection_set(item_id)
                self.fusions_tree.see(item_id)
                self._on_fusion_selected()

                self.fusions_count_var.set(f"Fusiones: {len(self.fusion_db.fusions):,}")
                msg = f"Fusión agregada: #{cid_a:03d} + #{cid_b:03d} ➔ #{cid_res:03d} ({name_res})"
                self.status_var.set(msg)
                self.log(msg)
                dlg.destroy()
                messagebox.showinfo("Fusión Creada", f"¡Receta creada con éxito!\n\n{name_a} + {name_b} ➔ {name_res}\n\nSe sincronizará en las 7 arenas al compilar.")
            else:
                messagebox.showerror("Error", "No se pudo agregar la fusión al archivo de datos.", parent=dlg)

        btn_bar = ttk.Frame(dlg)
        btn_bar.pack(fill=tk.X, padx=20, pady=16)
        ttk.Button(btn_bar, text="➕ Guardar Fusión", style="Action.TButton", command=do_add).pack(side=tk.RIGHT)
        ttk.Button(btn_bar, text="Cancelar", command=dlg.destroy).pack(side=tk.RIGHT, padx=8)

    def _on_edit_fusion_dialog(self):
        """Modal dialog to change the outcome card of the selected fusion."""
        sel = self.fusions_tree.selection()
        if not sel:
            messagebox.showinfo("Atención", "Por favor selecciona una fusión en la lista primero.")
            return

        item = self.fusions_tree.item(sel[0])
        vals = item.get("values", [])
        if len(vals) < 4:
            return

        try:
            cid_a = int(str(vals[0]).split()[0].replace("#", ""))
            cid_b = int(str(vals[1]).split()[0].replace("#", ""))
            current_res = int(str(vals[3]).split()[0].replace("#", ""))
        except (ValueError, IndexError):
            return

        name_a = self.get_card_display_name(cid_a)
        name_b = self.get_card_display_name(cid_b)
        curr_name_res = self.get_card_display_name(current_res)

        dlg = tk.Toplevel(self)
        dlg.title("✏️ Cambiar Resultado de Fusión")
        dlg.geometry("520x290")
        dlg.configure(bg="#1E1E24")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="✏️ Modificar Resultado de Fusión", font=("Segoe UI", 12, "bold"), fg="#00D2FF", bg="#1E1E24").pack(pady=(12, 8))

        form = ttk.Frame(dlg)
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=4)

        ttk.Label(form, text="Materiales:").grid(row=0, column=0, sticky="w", pady=4)
        tk.Label(form, text=f"#{cid_a:03d} {name_a}  +  #{cid_b:03d} {name_b}", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#1E1E24").grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Resultado Actual:").grid(row=1, column=0, sticky="w", pady=4)
        tk.Label(form, text=f"#{current_res:03d} {curr_name_res}", font=("Segoe UI", 9), fg="#A0A0A0", bg="#1E1E24").grid(row=1, column=1, sticky="w", pady=4)

        var_res = tk.StringVar(value=str(current_res))
        lbl_res = tk.Label(form, text=f"#{current_res:03d} {curr_name_res}", font=("Segoe UI", 9, "bold"), fg="#00FF66", bg="#1E1E24", anchor="w")

        ttk.Label(form, text="Nuevo Resultado:").grid(row=2, column=0, sticky="w", pady=8)
        ent_res = ttk.Entry(form, textvariable=var_res, width=22)
        ent_res.grid(row=2, column=1, sticky="w", pady=8)
        lbl_res.grid(row=3, column=1, sticky="w")

        def update_res(e=None):
            cid = self._resolve_card_input(var_res.get())
            if cid:
                lbl_res.configure(text=f"#{cid:03d} {self.get_card_display_name(cid)}")
            else:
                lbl_res.configure(text="No identificada")
        ent_res.bind("<KeyRelease>", update_res)

        def do_save():
            new_cid = self._resolve_card_input(var_res.get())
            if not new_cid:
                messagebox.showerror("Error", "Carta de resultado no válida.", parent=dlg)
                return

            self.fusion_db.modify_fusion(cid_a, cid_b, new_cid)
            new_name = self.get_card_display_name(new_cid)

            self.fusions_tree.item(sel[0], values=(
                f"#{cid_a:03d} {name_a}",
                f"#{cid_b:03d} {name_b}",
                "➔",
                f"#{new_cid:03d} {new_name}"
            ))
            self._active_fusion_triple = (cid_a, cid_b, new_cid)
            self._render_active_fusion_card()

            msg = f"Fusión modificada: #{cid_a:03d} + #{cid_b:03d} ➔ #{new_cid:03d} ({new_name})"
            self.status_var.set(msg)
            self.log(msg)
            dlg.destroy()
            messagebox.showinfo("Fusión Actualizada", f"¡Resultado actualizado con éxito!\n\n{name_a} + {name_b} ➔ {new_name}")

        btn_bar = ttk.Frame(dlg)
        btn_bar.pack(fill=tk.X, padx=20, pady=16)
        ttk.Button(btn_bar, text="💾 Guardar Cambio", style="Action.TButton", command=do_save).pack(side=tk.RIGHT)
        ttk.Button(btn_bar, text="Cancelar", command=dlg.destroy).pack(side=tk.RIGHT, padx=8)

    def _on_delete_fusion(self):
        """Deletes the currently selected fusion."""
        sel = self.fusions_tree.selection()
        if not sel:
            messagebox.showinfo("Atención", "Por favor selecciona una fusión en la lista primero.")
            return

        item = self.fusions_tree.item(sel[0])
        vals = item.get("values", [])
        if len(vals) < 4:
            return

        try:
            cid_a = int(str(vals[0]).split()[0].replace("#", ""))
            cid_b = int(str(vals[1]).split()[0].replace("#", ""))
            name_a = self.get_card_display_name(cid_a)
            name_b = self.get_card_display_name(cid_b)
        except (ValueError, IndexError):
            return

        confirm = messagebox.askyesno(
            "Confirmar Eliminación",
            f"¿Estás seguro de que deseas eliminar la receta de fusión:\n\n"
            f"#{cid_a:03d} {name_a}  +  #{cid_b:03d} {name_b}?\n\n"
            f"Esta receta dejará de funcionar en las 7 arenas del juego."
        )
        if not confirm:
            return

        ok = self.fusion_db.delete_fusion(cid_a, cid_b)
        if ok:
            self.fusions_tree.delete(sel[0])
            self.fusions_count_var.set(f"Fusiones: {len(self.fusion_db.fusions):,}")
            msg = f"Fusión eliminada: #{cid_a:03d} {name_a} + #{cid_b:03d} {name_b}"
            self.status_var.set(msg)
            self.log(msg)
            first_items = self.fusions_tree.get_children()
            if first_items:
                self.fusions_tree.selection_set(first_items[0])
                self._on_fusion_selected()

    def _on_import_mod_dialog(self):
        path = filedialog.askopenfilename(
            title="Seleccionar Mod a Importar (ej. Dream Mod 15x)",
            filetypes=[("Imágenes de Disco PS1", "*.iso *.bin *.img"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        self.status_var.set(f"Importando assets de {os.path.basename(path)}...")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(10)

        def task():
            try:
                mod_disc = PS1DiscImage(path)
                slus_key = None
                wa_key = None
                for k in mod_disc.file_table:
                    if "SLUS_" in k.upper() or "SLES_" in k.upper() or "SLPM_" in k.upper():
                        slus_key = k
                    elif "WA_MRG.MRG" in k.upper():
                        wa_key = k
                slus_key = slus_key or "SLUS_014.11"
                wa_key = wa_key or "DATA/WA_MRG.MRG"

                mod_exe = mod_disc.extract_file(slus_key)
                mod_wa = mod_disc.extract_file(wa_key)

                # 1. Import Cards
                self.card_db.import_cards_from_mod(mod_exe, mod_wa)

                # 2. Import Fusions
                f_count = self.fusion_db.import_from_mod_wa(mod_wa)

                # 3. Import Decks & Difficulty
                deck_count = self.deck_db.import_from_mod(mod_wa, mod_exe)

                # 4. Import Drops (39 duelists, all 4 rank pools)
                drop_count = self.drop_db.import_from_mod(mod_wa, mod_exe)

                # 5. Import Starter Deck (Authentic 7 Pools from WA_MRG + SLUS)
                s_count = self.starter_deck_db.import_from_mod(mod_wa, mod_exe)

                # 6. Import Graphics directly from WA_MRG
                self.graphics_db.set_wa_data(mod_wa)

                self.imported_mod_path = path

                def on_done():
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate", value=100)
                    drop_fmt = "16-bit (Dream Mod)" if self.drop_db.is_16bit else "8-bit (Vanilla/Estándar)"
                    self.status_var.set(f"¡Importación completa! 722 cartas, {f_count:,} fusiones, {deck_count} mazos, {drop_count} drops, {s_count} starter slots.")
                    self.fusions_count_var.set(f"Fusiones: {f_count:,}")
                    self.log(f"Importados con éxito datos de {os.path.basename(path)}.")
                    self._populate_cards_tree()
                    self._populate_fusions_tree()
                    self._populate_opponents_tree()
                    self._populate_drop_duelists_tree()
                    self._refresh_drops_table()
                    self._refresh_starter_deck_table()
                    if self.deck_db.decks:
                        self.opp_tree.selection_set("1")
                        self._on_opponent_selected()
                    self._render_current_card()
                    messagebox.showinfo(
                        "Importación Completa de Mod",
                        f"Se han importado con éxito todos los componentes de {os.path.basename(path)}:\n\n"
                        f"• 722 Cartas (estadísticas, nombres, guardian stars, contraseñas y costes)\n"
                        f"• {f_count:,} Recetas de fusión sincronizadas en las 7 arenas\n"
                        f"• {deck_count} Mazos de CPU y niveles de dificultad de IA\n"
                        f"• {drop_count} Tablas de recompensas (formato {drop_fmt})\n"
                        f"• {s_count} Probabilidades del Mazo Inicial y Baúl\n"
                        f"• Gráficos auténticos de cartas extraídos directamente de la ROM"
                    )

                self.after(0, on_done)
            except Exception as e:
                def on_error(err=e):
                    self.progress_bar.stop()
                    self.status_var.set("Error al importar mod.")
                    self.log(f"ERROR: {str(err)}")
                    messagebox.showerror("Error al importar", f"Ocurrió un error al leer el mod:\n{str(err)}")
                self.after(0, on_error)

        threading.Thread(target=task, daemon=True).start()

    def _on_compile_rom(self):
        if not self.base_iso_path or not os.path.isfile(self.base_iso_path):
            messagebox.showwarning("Atención", "Por favor carga una imagen ROM / ISO base primero.")
            return

        default_out = os.path.join(
            os.path.dirname(self.base_iso_path),
            f"YGO_FM_Modded_Drop{self.drop_multiplier_var.get()}.iso"
        )

        out_path = filedialog.asksaveasfilename(
            title="Guardar Nueva ROM / ISO Compilada",
            initialfile=os.path.basename(default_out),
            filetypes=[("Imagen ISO PlayStation", "*.iso"), ("Imagen BIN PlayStation", "*.bin")]
        )
        if not out_path:
            return

        try:
            drop_mult = int(self.drop_multiplier_var.get())
        except ValueError:
            drop_mult = 100

        self.compile_btn.configure(state=tk.DISABLED)
        self.progress_bar.configure(mode="determinate", value=0)
        self.status_var.set("Iniciando compilación de la nueva ROM...")

        def update_prog(pct: float, text: str):
            self.after(0, lambda: self._on_build_progress(pct, text))

        def task():
            try:
                res = DiscRecompiler.build(
                    base_disc_path=self.base_iso_path,
                    output_image_path=out_path,
                    card_db=self.card_db,
                    fusion_db=self.fusion_db,
                    deck_db=self.deck_db,
                    drop_db=self.drop_db,
                    starter_deck_db=self.starter_deck_db,
                    graphics_db=self.graphics_db,
                    field_spells_db=self.field_spells_db,
                    express_ref_disc_path=self.ref_express_path if (self.ref_express_path and os.path.isfile(self.ref_express_path)) else None,
                    mod_disc_path=self.imported_mod_path if self.import_cpu_ai_var.get() else None,
                    drop_multiplier=drop_mult,
                    enable_fast_exit=False,
                    progress_cb=update_prog
                )

                def on_success():
                    self.compile_btn.configure(state=tk.NORMAL)
                    self.status_var.set("¡Nueva ROM PS1 compilada y lista para jugar!")
                    self.log(f"Compilación finalizada: {res.output_iso} ({res.output_bin}, {res.output_cue})")
                    messagebox.showinfo(
                        "Compilación Exitosa",
                        f"¡Tu nueva ROM ha sido generada exitosamente!\n\n"
                        f"• ISO: {os.path.basename(res.output_iso)}\n"
                        f"• CUE: {os.path.basename(res.output_cue)}\n"
                        f"• Sectores recalculados con paridades EDC y Reed-Solomon L-EC.\n\n"
                        f"¡Ya puedes abrirla en DuckStation, ePSXe o RetroArch!"
                    )

                self.after(0, on_success)
            except Exception as e:
                def on_error(err=e):
                    self.compile_btn.configure(state=tk.NORMAL)
                    self.status_var.set("Error durante la compilación.")
                    self.log(f"ERROR: {str(err)}")
                    messagebox.showerror("Error al compilar", f"Fallo al compilar la imagen:\n{str(err)}")
                self.after(0, on_error)

        threading.Thread(target=task, daemon=True).start()

    def _on_build_progress(self, pct: float, text: str):
        self.progress_bar["value"] = int(pct * 100)
        self.status_var.set(text)
        self.log(text)


def run_gui():
    app = ROMSuiteGUI()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
