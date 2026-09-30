"""
Duel Board Visual Renderer for Yu-Gi-Oh! Forbidden Memories.
Renders the 3D-styled duel battlefield on a Tkinter Canvas, including:
- Custom arena ground colors, grid lines, and skybox atmosphere
- Custom background images / textures loaded by the user
- 5 Monster zones + 5 Magic/Trap zones with authentic perspective
- Active Field Spell slot, Deck slot, and Graveyard slot
- Live monster stat boost (+500 / -500) visualization based on the active field
"""

from typing import Optional, Dict, Any, Tuple
import os

try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from core.field_spells import FieldSpellData, FIELD_METADATA


class DuelBoardRenderer:
    """
    Renders the duel arena battlefield on a Tkinter Canvas.
    """

    def __init__(self, canvas, graphics_db=None):
        self.canvas = canvas
        self.graphics_db = graphics_db
        self._bg_image_ref = None  # prevent Tkinter GC
        self._field_art_ref = None
        self._monster_art_ref = None

    def render(
        self,
        field_data: FieldSpellData,
        width: int = 560,
        height: int = 360,
        test_monster: Optional[Dict[str, Any]] = None,
        test_slot: int = 2,  # Center monster slot (0..4)
    ) -> None:
        """
        Draws the complete duel battlefield on the canvas.
        """
        self.canvas.delete("all")
        self.canvas.configure(width=width, height=height)

        colors = field_data.colors
        ground_col = colors.get("ground", "#8C7B65")
        grid_col = colors.get("grid", "#D4C2A5")
        m_zone_col = colors.get("monster_zone", "#5C5042")
        s_zone_col = colors.get("spell_zone", "#4A3F33")
        border_col = colors.get("border", "#BFAF96")
        sky_col = colors.get("sky", "#1C1424")

        # 1. Sky / Horizon Section (top 22%)
        sky_h = int(height * 0.22)
        self.canvas.create_rectangle(0, 0, width, sky_h, fill=sky_col, outline="")

        # Horizon subtle stars/mist
        for sx, sy in [(width * 0.15, sky_h * 0.3), (width * 0.45, sky_h * 0.2), (width * 0.8, sky_h * 0.4), (width * 0.65, sky_h * 0.6)]:
            self.canvas.create_oval(sx - 1.5, sy - 1.5, sx + 1.5, sy + 1.5, fill="#FFF8DC", outline="")

        # Horizon line
        self.canvas.create_line(0, sky_h, width, sky_h, fill=border_col, width=2)

        # 2. Arena Ground / Floor (Trapezoidal 3D perspective)
        pts_arena = [
            width * 0.08, sky_h,             # Top-left
            width * 0.92, sky_h,             # Top-right
            width * 0.98, height - 6,        # Bottom-right
            width * 0.02, height - 6,        # Bottom-left
        ]

        # Draw custom image if loaded, else procedural arena floor
        drawn_custom_img = False
        if field_data.custom_image_path and HAS_PILLOW and os.path.exists(field_data.custom_image_path):
            try:
                pil_img = Image.open(field_data.custom_image_path).convert("RGBA")
                arena_w = int(width)
                arena_h = int(height - sky_h)
                pil_resized = pil_img.resize((arena_w, arena_h), Image.Resampling.LANCZOS)
                self._bg_image_ref = ImageTk.PhotoImage(pil_resized)
                self.canvas.create_image(0, sky_h, image=self._bg_image_ref, anchor="nw")
                drawn_custom_img = True
            except Exception:
                drawn_custom_img = False

        if not drawn_custom_img:
            # Procedural ground fill
            self.canvas.create_polygon(pts_arena, fill=ground_col, outline=border_col, width=2)
            # Arena perimeter ring line
            mid_y = sky_h + (height - sky_h) * 0.5
            self.canvas.create_line(width * 0.05, mid_y, width * 0.95, mid_y, fill=border_col, width=1, dash=(4, 4))

        # 3. Duel Card Zones (5 Monster Slots upper, 5 Spell/Trap Slots lower)
        # Perspective sizing: upper row is slightly smaller and higher than lower row
        m_row_y = int(sky_h + (height - sky_h) * 0.28)
        s_row_y = int(sky_h + (height - sky_h) * 0.68)

        card_w_top = int(width * 0.125)
        card_h_top = int(height * 0.25)
        card_w_bot = int(width * 0.135)
        card_h_bot = int(height * 0.27)

        start_x_top = int(width * 0.15)
        step_x_top = int(width * 0.14)

        start_x_bot = int(width * 0.13)
        step_x_bot = int(width * 0.15)

        # Draw 5 Monster Zones
        for i in range(5):
            cx = start_x_top + i * step_x_top
            x1 = cx - card_w_top // 2
            y1 = m_row_y - card_h_top // 2
            x2 = cx + card_w_top // 2
            y2 = m_row_y + card_h_top // 2

            # Slot rectangle
            fill_c = m_zone_col if not drawn_custom_img else ""
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill_c, outline=grid_col, width=2)

            # Slot indicator
            self.canvas.create_text(cx, y1 + 10, text=f"M{i+1}", fill=grid_col, font=("Segoe UI", 8, "bold"))

            # If this is the test monster slot and a test monster is active
            if test_monster and i == test_slot:
                self._draw_monster_on_slot(cx, m_row_y, card_w_top, card_h_top, test_monster, field_data)

        # Draw 5 Spell / Trap Zones
        for i in range(5):
            cx = start_x_bot + i * step_x_bot
            x1 = cx - card_w_bot // 2
            y1 = s_row_y - card_h_bot // 2
            x2 = cx + card_w_bot // 2
            y2 = s_row_y + card_h_bot // 2

            fill_c = s_zone_col if not drawn_custom_img else ""
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill_c, outline=grid_col, width=2, dash=(3, 2))
            self.canvas.create_text(cx, y1 + 10, text=f"S{i+1}", fill=grid_col, font=("Segoe UI", 8, "bold"))

        # 4. Field Spell Zone (Top Left)
        fz_x = int(width * 0.065)
        fz_y = int(sky_h + (height - sky_h) * 0.28)
        fw = int(width * 0.09)
        fh = int(height * 0.22)
        self.canvas.create_rectangle(fz_x - fw//2, fz_y - fh//2, fz_x + fw//2, fz_y + fh//2,
                                    fill="#101018", outline="#FFD700", width=2)
        sym = FIELD_METADATA.get(field_data.field_id, {}).get("symbol", "🏟️")
        self.canvas.create_text(fz_x, fz_y - 12, text=sym, font=("Segoe UI", 12))
        self.canvas.create_text(fz_x, fz_y + 10, text="CAMPO", fill="#FFD700", font=("Segoe UI", 7, "bold"))

        # 5. Graveyard (Top Right) & Deck (Bottom Right)
        # Graveyard (GY)
        gy_x = int(width * 0.935)
        gy_y = int(sky_h + (height - sky_h) * 0.28)
        self.canvas.create_rectangle(gy_x - fw//2, gy_y - fh//2, gy_x + fw//2, gy_y + fh//2,
                                    fill="#181820", outline="#888899", width=1)
        self.canvas.create_text(gy_x, gy_y, text="GY", fill="#888899", font=("Segoe UI", 8, "bold"))

        # Deck
        dk_x = int(width * 0.935)
        dk_y = int(sky_h + (height - sky_h) * 0.70)
        self.canvas.create_rectangle(dk_x - fw//2, dk_y - fh//2, dk_x + fw//2, dk_y + fh//2,
                                    fill="#2B1A0A", outline="#D49339", width=2)
        self.canvas.create_text(dk_x, dk_y, text="MAZO", fill="#D49339", font=("Segoe UI", 8, "bold"))

        # 6. Top Header Banner
        banner_bg = "#0D0D12"
        self.canvas.create_rectangle(0, 0, width, 24, fill=banner_bg, outline="")
        f_title = f"{sym} {field_data.name_es}"
        self.canvas.create_text(10, 12, text=f_title, anchor="w", fill="#00D2FF", font=("Segoe UI", 9, "bold"))

        # Boost badge on top right
        boost_text = FIELD_METADATA.get(field_data.field_id, {}).get("tag", "")
        if boost_text:
            self.canvas.create_text(width - 10, 12, text=boost_text, anchor="e", fill="#FFD700", font=("Segoe UI", 8))

    def _draw_monster_on_slot(
        self,
        cx: int,
        cy: int,
        w: int,
        h: int,
        monster: Dict[str, Any],
        field_data: FieldSpellData
    ) -> None:
        """
        Draws the test monster card representation inside a monster slot,
        calculating and highlighting any +500/-500 stat modifications.
        """
        x1 = cx - w // 2 + 2
        y1 = cy - h // 2 + 2
        x2 = cx + w // 2 - 2
        y2 = cy + h // 2 - 2

        # Card mini body
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#C69248", outline="#5B3A1A", width=1)

        # Card name text
        name = monster.get("name", "Monstruo")
        if len(name) > 11:
            name = name[:10] + "…"
        self.canvas.create_text(cx, y1 + 10, text=name, fill="#1A0E03", font=("Segoe UI", 7, "bold"))

        # Card Type
        mtype = monster.get("type", "Dragon")
        self.canvas.create_text(cx, y1 + 22, text=f"[{mtype}]", fill="#4A2E0A", font=("Segoe UI", 6))

        # Stat Bonus calculation
        base_atk = monster.get("atk", 0)
        base_def = monster.get("def", 0)

        atk_mod = 0
        def_mod = 0
        if mtype in field_data.boosted_types:
            atk_mod = 500
            def_mod = 500
            stat_color = "#006400"  # Dark green
            bonus_badge = "+500"
            badge_color = "#00FF66"
        elif mtype in field_data.weakened_types:
            atk_mod = -500
            def_mod = -500
            stat_color = "#8B0000"  # Dark red
            bonus_badge = "-500"
            badge_color = "#FF4444"
        else:
            stat_color = "#1A0E03"
            bonus_badge = ""
            badge_color = "#FFFFFF"

        final_atk = max(0, base_atk + atk_mod)
        final_def = max(0, base_def + def_mod)

        # Mini artwork box
        art_y1 = y1 + 28
        art_y2 = y2 - 22
        self.canvas.create_rectangle(x1 + 4, art_y1, x2 - 4, art_y2, fill="#121214", outline="#888888")

        cid = monster.get("id", 1)
        if self.graphics_db:
            img = self.graphics_db.get_card_image(cid)
            if img and HAS_PILLOW:
                try:
                    box_w = max(10, (x2 - 4) - (x1 + 4))
                    box_h = max(10, art_y2 - art_y1)
                    resized = img.resize((box_w, box_h), Image.Resampling.BILINEAR)
                    self._monster_art_ref = ImageTk.PhotoImage(resized)
                    self.canvas.create_image(x1 + 4, art_y1, image=self._monster_art_ref, anchor="nw")
                except Exception:
                    pass

        # ATK / DEF badge box
        self.canvas.create_rectangle(x1 + 2, y2 - 20, x2 - 2, y2 - 2, fill="#F1DEC2", outline="#5B3A1A")
        self.canvas.create_text(
            cx, y2 - 11,
            text=f"{final_atk}/{final_def}",
            fill=stat_color,
            font=("Segoe UI", 7, "bold")
        )

        if bonus_badge:
            # Highlight badge
            self.canvas.create_text(
                cx, y2 - 26,
                text=bonus_badge,
                fill=badge_color,
                font=("Segoe UI", 8, "bold")
            )
