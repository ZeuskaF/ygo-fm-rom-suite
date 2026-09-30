"""
Visual Card Renderer for Yu-Gi-Oh! Forbidden Memories.
Renders authentic Forbidden Memories card frames, celestial guardian stars,
level stars, stats boxes, and artwork on Tkinter Canvas and exports high-res PNGs via Pillow.
"""

import os
from typing import Optional, Tuple
from core.cards import Card
from core.card_data import CARD_TYPES, GUARDIAN_STARS, CARD_TYPES_ES

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


# Authentic PS1 Yu-Gi-Oh! Forbidden Memories Frame Colors
DEFAULT_FRAME_THEMES = {
    "Normal": {
        "border": "#5B3A1A",
        "frame":  "#C69248",
        "inner":  "#E2BE86",
        "box":    "#F1DEC2",
        "text":   "#201205"
    },
    "Ritual": {
        "border": "#1A2E4C",
        "frame":  "#3B6096",
        "inner":  "#6B8EBE",
        "box":    "#D4E0F0",
        "text":   "#0A1526"
    },
    "Magic": {
        "border": "#0A3D2C",
        "frame":  "#198A62",
        "inner":  "#3DB388",
        "box":    "#CFEFE3",
        "text":   "#041F16"
    },
    "Trap": {
        "border": "#4F0D33",
        "frame":  "#A9236F",
        "inner":  "#D04693",
        "box":    "#F6D5E6",
        "text":   "#280419"
    }
}

FRAME_THEMES = {k: dict(v) for k, v in DEFAULT_FRAME_THEMES.items()}

FRAME_COLOR_PRESETS = {
    "Clásico FM (PS1)": DEFAULT_FRAME_THEMES,
    "Anime Clásico Duel Monsters": {
        "Normal": {"border": "#42280C", "frame": "#D49339", "inner": "#F4D28D", "box": "#FFF3D6", "text": "#1A0E03"},
        "Ritual": {"border": "#13233C", "frame": "#4070B8", "inner": "#7DA8E8", "box": "#E3EEFF", "text": "#081324"},
        "Magic":  {"border": "#073624", "frame": "#1B9E6F", "inner": "#4AD4A0", "box": "#D8FCEF", "text": "#021A10"},
        "Trap":   {"border": "#450A2A", "frame": "#BC257A", "inner": "#E85EA7", "box": "#FFE0F1", "text": "#240315"},
    },
    "TCG Moderno / Master Duel": {
        "Normal": {"border": "#523314", "frame": "#BF893B", "inner": "#DEC085", "box": "#F7EADB", "text": "#1F1206"},
        "Ritual": {"border": "#192B45", "frame": "#3D6BA6", "inner": "#729CCF", "box": "#DCE7F5", "text": "#0B1524"},
        "Magic":  {"border": "#093828", "frame": "#168F66", "inner": "#3CBA8F", "box": "#D1F0E4", "text": "#031C13"},
        "Trap":   {"border": "#470C2E", "frame": "#A8226D", "inner": "#D44996", "box": "#F7D6E7", "text": "#260418"},
    },
    "Cyber Neón / Sintético": {
        "Normal": {"border": "#3A2800", "frame": "#E69500", "inner": "#FFCC00", "box": "#FFF4CC", "text": "#1A1000"},
        "Ritual": {"border": "#00204A", "frame": "#0066FF", "inner": "#3399FF", "box": "#CCE6FF", "text": "#001026"},
        "Magic":  {"border": "#003322", "frame": "#00CC88", "inner": "#33FFBB", "box": "#CCFFEE", "text": "#001A11"},
        "Trap":   {"border": "#4A0033", "frame": "#FF0088", "inner": "#FF66BB", "box": "#FFCCE6", "text": "#26001A"},
    },
    "Papiro Egipcio Antiguo": {
        "Normal": {"border": "#4D3818", "frame": "#AA8844", "inner": "#D4B877", "box": "#EFE5C8", "text": "#2B1E0A"},
        "Ritual": {"border": "#28343E", "frame": "#5A7285", "inner": "#8B9FA8", "box": "#D8DEE2", "text": "#1A2228"},
        "Magic":  {"border": "#284034", "frame": "#4E7C67", "inner": "#7BA894", "box": "#D4E2DC", "text": "#14241C"},
        "Trap":   {"border": "#4A2838", "frame": "#8C5572", "inner": "#B5849E", "box": "#E6D7DF", "text": "#28141E"},
    },
    "GameBoy Retro Monocromo": {
        "Normal": {"border": "#0F380F", "frame": "#306230", "inner": "#8BAC0F", "box": "#9BBC0F", "text": "#0F380F"},
        "Ritual": {"border": "#0F380F", "frame": "#306230", "inner": "#8BAC0F", "box": "#9BBC0F", "text": "#0F380F"},
        "Magic":  {"border": "#0F380F", "frame": "#306230", "inner": "#8BAC0F", "box": "#9BBC0F", "text": "#0F380F"},
        "Trap":   {"border": "#0F380F", "frame": "#306230", "inner": "#8BAC0F", "box": "#9BBC0F", "text": "#0F380F"},
    }
}

DEFAULT_GUARDIAN_STAR_DATA = {
    0:  {"sym": "—",  "name": "Ninguna",  "color": "#888888"},
    1:  {"sym": "☀️",  "name": "Sol",      "color": "#FFCC00"},
    2:  {"sym": "☿",  "name": "Mercurio", "color": "#00DDFF"},
    3:  {"sym": "♀",  "name": "Venus",    "color": "#FF77AA"},
    4:  {"sym": "🌙", "name": "Luna",     "color": "#E0E0FF"},
    5:  {"sym": "♂",  "name": "Marte",    "color": "#FF4422"},
    6:  {"sym": "♃",  "name": "Júpiter",  "color": "#FFAA33"},
    7:  {"sym": "♄",  "name": "Saturno",  "color": "#DDAA55"},
    8:  {"sym": "♅",  "name": "Urano",    "color": "#33FFAA"},
    9:  {"sym": "♇",  "name": "Plutón",   "color": "#AA55FF"},
    10: {"sym": "♆",  "name": "Neptuno",  "color": "#3388FF"},
}

GUARDIAN_STAR_DATA = {k: dict(v) for k, v in DEFAULT_GUARDIAN_STAR_DATA.items()}

def apply_frame_preset(preset_name: str):
    """Applies a named preset to the FRAME_THEMES dictionary."""
    if preset_name in FRAME_COLOR_PRESETS:
        preset = FRAME_COLOR_PRESETS[preset_name]
        for k, v in preset.items():
            if k in FRAME_THEMES:
                FRAME_THEMES[k].update(v)

def reset_frame_colors():
    """Resets FRAME_THEMES to default Forbidden Memories palette."""
    apply_frame_preset("Clásico FM (PS1)")


def get_card_theme(type_id: int) -> dict:
    """Returns the visual color theme based on card type."""
    # 20: Magic, 21: Trap, 22: Ritual, 23: Equip
    if type_id == 21:
        return FRAME_THEMES["Trap"]
    elif type_id in (20, 23):
        return FRAME_THEMES["Magic"]
    elif type_id == 22:
        return FRAME_THEMES["Ritual"]
    return FRAME_THEMES["Normal"]


def calculate_level_stars(card: Card) -> int:
    """Calculates the authentic Level Stars (1 to 12) for a monster card."""
    if card.type_id in (20, 21, 23):
        return 0  # Magic, Trap, Equip have no level stars
    top_stat = max(card.atk, card.def_)
    if top_stat <= 400:
        return 1
    elif top_stat <= 700:
        return 2
    elif top_stat <= 1100:
        return 3
    elif top_stat <= 1500:
        return 4
    elif top_stat <= 1900:
        return 5
    elif top_stat <= 2300:
        return 6
    elif top_stat <= 2650:
        return 7
    elif top_stat <= 3000:
        return 8
    elif top_stat <= 3500:
        return 9
    elif top_stat <= 4000:
        return 10
    elif top_stat <= 4500:
        return 11
    return 12


class CardCanvasRenderer:
    """
    Renders an interactive, visually faithful representation of a Forbidden Memories
    card on a Tkinter Canvas widget, utilizing authentic extracted graphics from WA_MRG
    or custom loaded artwork.
    """

    def __init__(self, canvas, graphics_db=None):
        self.canvas = canvas
        self.graphics_db = graphics_db
        self.cached_photo: Optional[ImageTk.PhotoImage] = None if HAS_PILLOW else None
        self.custom_image_path: str = ""

    def set_custom_image(self, image_path: str):
        """Sets a custom artwork path to display inside the card."""
        if os.path.isfile(image_path):
            self.custom_image_path = image_path
        else:
            self.custom_image_path = ""

    def render(self, card: Card, width: int = 250, height: int = 365):
        """Draws the complete card onto the canvas with proportional scaling."""
        c = self.canvas
        c.delete("all")
        theme = get_card_theme(card.type_id)

        # Scale factors relative to baseline (250x365)
        sx = width / 250.0
        sy = height / 365.0
        s_min = min(sx, sy)

        def fsize(base: int, minimum: int = 6) -> int:
            return max(minimum, int(round(base * s_min)))

        # 1. Outer Card Frame & Bevel
        c.create_rectangle(int(4*sx), int(4*sy), width - int(4*sx), height - int(4*sy),
                           fill=theme["frame"], outline=theme["border"], width=max(1, int(3*s_min)))
        c.create_rectangle(int(10*sx), int(10*sy), width - int(10*sx), height - int(10*sy),
                           fill="", outline=theme["inner"], width=max(1, int(2*s_min)))

        # 2. Card Name Banner (Top)
        name_bg = "#111111" if card.type_id in (20, 21, 22) else "#2B1A0A"
        c.create_rectangle(int(14*sx), int(14*sy), width - int(14*sx), int(42*sy),
                           fill=name_bg, outline=theme["inner"], width=max(1, int(1.5*s_min)))
        name_display = card.name if len(card.name) <= 22 else card.name[:20] + "…"
        c.create_text(int(20*sx), int(28*sy), text=name_display, anchor="w",
                      font=("Segoe UI", fsize(9), "bold"), fill="#FFFFFF")

        # 3. Guardian Stars Emblems (Top Right)
        gs1 = GUARDIAN_STAR_DATA.get(card.gs1, GUARDIAN_STAR_DATA[0])
        gs2 = GUARDIAN_STAR_DATA.get(card.gs2, GUARDIAN_STAR_DATA[0])
        gs_text = f"{gs1['sym']} {gs2['sym']}" if card.gs1 or card.gs2 else ""
        if gs_text:
            c.create_text(width - int(18*sx), int(28*sy), text=gs_text, anchor="e",
                          font=("Segoe UI", fsize(10), "bold"), fill="#FFD700")

        # 4. Level Stars Row (Under Name, for Monsters)
        stars = calculate_level_stars(card)
        if stars > 0:
            stars_str = "★ " * stars
            c.create_text(width - int(18*sx), int(52*sy), text=stars_str.strip(), anchor="e",
                          font=("Segoe UI", fsize(8), "bold"), fill="#FFCC00")
        else:
            # Magic / Trap Badge
            type_label = "【 CARTA MÁGICA 】" if card.type_id in (20, 23) else "【 CARTA TRAMPA 】"
            c.create_text(width - int(18*sx), int(52*sy), text=type_label, anchor="e",
                          font=("Segoe UI", fsize(8), "bold"), fill="#FFFFFF")

        # 5. Card Artwork Window
        art_x1, art_y1 = int(20 * sx), int(64 * sy)
        art_x2, art_y2 = width - int(20 * sx), int(218 * sy)
        art_w = max(10, art_x2 - art_x1)
        art_h = max(10, art_y2 - art_y1)

        art_loaded = False
        pil_source_img = None

        # Priority 1: Custom image loaded by user
        if HAS_PILLOW and self.custom_image_path and os.path.isfile(self.custom_image_path):
            try:
                pil_source_img = Image.open(self.custom_image_path).convert("RGBA")
            except Exception:
                pil_source_img = None

        # Priority 2: In-game authentic artwork extracted from WA_MRG
        if pil_source_img is None and HAS_PILLOW and self.graphics_db:
            pil_source_img = self.graphics_db.get_card_art(card.card_id)

        if pil_source_img is not None:
            try:
                resized = pil_source_img.resize((art_w, art_h), Image.Resampling.LANCZOS)
                self.cached_photo = ImageTk.PhotoImage(resized)
                c.create_image(art_x1, art_y1, image=self.cached_photo, anchor="nw")
                art_loaded = True
            except Exception:
                art_loaded = False

        if not art_loaded:
            # Procedural Retro Artwork Box
            c.create_rectangle(art_x1, art_y1, art_x2, art_y2, fill="#0F0F16",
                               outline=theme["inner"], width=max(1, int(2*s_min)))
            cx, cy = (art_x1 + art_x2) // 2, (art_y1 + art_y2) // 2
            r1 = int(45 * s_min)
            r2 = int(25 * s_min)
            c.create_oval(cx - r1, cy - r1, cx + r1, cy + r1, outline=theme["inner"], fill="#1A1A2E", width=1)
            c.create_oval(cx - r2, cy - r2, cx + r2, cy + r2, outline="#FFD700", width=1)

            type_name = CARD_TYPES[card.type_id] if 0 <= card.type_id < len(CARD_TYPES) else "Monster"
            c.create_text(cx, cy - int(8*sy), text=type_name.upper(),
                          font=("Segoe UI", fsize(9), "bold"), fill="#00D2FF")
            gs_desc = f"{gs1['name']} / {gs2['name']}" if card.gs1 or card.gs2 else "Sin Estrella"
            c.create_text(cx, cy + int(10*sy), text=gs_desc,
                          font=("Segoe UI", fsize(7)), fill="#A0A0A0")
            c.create_text(cx, cy + int(26*sy), text=f"ID #{card.card_id:03d}",
                          font=("Consolas", fsize(7), "italic"), fill="#777777")
        else:
            c.create_rectangle(art_x1, art_y1, art_x2, art_y2, fill="",
                               outline=theme["inner"], width=max(1, int(2*s_min)))

        # 6. Description / Lore Box
        box_y1 = int(224 * sy)
        box_y2 = height - int(42 * sy)
        c.create_rectangle(int(14*sx), box_y1, width - int(14*sx), box_y2,
                           fill=theme["box"], outline=theme["inner"], width=max(1, int(1.5*s_min)))

        # Type Bracket [Dragón]
        c_type_es = CARD_TYPES_ES[card.type_id] if 0 <= card.type_id < len(CARD_TYPES_ES) else "Monstruo"
        type_str = f"【 {c_type_es} 】"
        c.create_text(int(18*sx), box_y1 + int(12*sy), text=type_str, anchor="w",
                      font=("Segoe UI", fsize(8), "bold"), fill=theme["text"])

        # Stats Row (ATK / DEF) for monsters
        if card.type_id not in (20, 21, 23):
            stat_str = f"ATK/{card.atk} DEF/{card.def_}"
            c.create_text(width - int(18*sx), box_y2 - int(11*sy), text=stat_str, anchor="e",
                          font=("Consolas", fsize(8), "bold"), fill=theme["text"])
            c.create_line(int(16*sx), box_y2 - int(21*sy), width - int(16*sx), box_y2 - int(21*sy),
                          fill=theme["inner"])
            desc_lines = card.description.strip().split("\n") if card.description else []
            line_y = box_y1 + int(24*sy)
            for d_line in desc_lines[:3]:
                if line_y < box_y2 - int(23*sy):
                    d_txt = d_line if len(d_line) <= 26 else d_line[:24] + "…"
                    c.create_text(int(18*sx), line_y, text=d_txt, anchor="w",
                                  font=("Segoe UI", fsize(6)), fill=theme["text"])
                    line_y += int(11*sy)
        else:
            desc_lines = card.description.strip().split("\n") if card.description else []
            if desc_lines:
                line_y = box_y1 + int(24*sy)
                for d_line in desc_lines[:5]:
                    if line_y < box_y2 - int(6*sy):
                        d_txt = d_line if len(d_line) <= 26 else d_line[:24] + "…"
                        c.create_text(int(18*sx), line_y, text=d_txt, anchor="w",
                                      font=("Segoe UI", fsize(6), "italic"), fill=theme["text"])
                        line_y += int(11*sy)
            else:
                effect_str = "Activa efectos especiales y altera el campo." if card.type_id in (20, 23) else "Emboscada defensiva contra el adversario."
                c.create_text(int(18*sx), box_y1 + int(28*sy), text=effect_str, anchor="w",
                              font=("Segoe UI", fsize(7), "italic"), fill=theme["text"])

        # 7. Card Footer (Password & Star Chip Cost)
        foot_y = height - int(22 * sy)
        pwd_str = f"Pass: {card.password}"
        c.create_text(int(14*sx), foot_y, text=pwd_str, anchor="w",
                      font=("Consolas", fsize(7), "bold"), fill="#EDEDED")

        cost_str = f"{card.star_cost:,} ★"
        c.create_text(width - int(14*sx), foot_y, text=cost_str, anchor="e",
                      font=("Segoe UI", fsize(7), "bold"), fill="#FFD700")


def export_card_to_png(card: Card, output_path: str, custom_image_path: str = "", graphics_db=None) -> bool:
    """Exports a high-resolution 500x730 PNG image of the card using Pillow."""
    if not HAS_PILLOW:
        return False

    width, height = 500, 730
    theme = get_card_theme(card.type_id)

    # Convert hex colors to RGB
    def h2rgb(hex_code):
        hex_code = hex_code.lstrip("#")
        return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

    img = Image.new("RGBA", (width, height), h2rgb(theme["frame"]))
    draw = ImageDraw.Draw(img)

    # Outer border
    draw.rectangle([0, 0, width - 1, height - 1], outline=h2rgb(theme["border"]), width=6)
    draw.rectangle([12, 12, width - 13, height - 13], outline=h2rgb(theme["inner"]), width=3)

    # Name Banner
    name_bg = (17, 17, 17) if card.type_id in (20, 21, 22) else (43, 26, 10)
    draw.rectangle([20, 20, width - 20, 75], fill=name_bg, outline=h2rgb(theme["inner"]), width=2)
    draw.text((36, 34), card.name, fill=(255, 255, 255))

    # Artwork Box
    art_box = (36, 115, width - 36, 420)
    art_img = None

    if custom_image_path and os.path.isfile(custom_image_path):
        try:
            art_img = Image.open(custom_image_path).convert("RGBA")
        except Exception:
            art_img = None

    if art_img is None and graphics_db:
        art_img = graphics_db.get_card_art(card.card_id)

    if art_img is not None:
        try:
            art = art_img.resize((art_box[2] - art_box[0], art_box[3] - art_box[1]), Image.Resampling.LANCZOS)
            img.paste(art, (art_box[0], art_box[1]))
        except Exception:
            draw.rectangle(art_box, fill=(15, 15, 22), outline=h2rgb(theme["inner"]), width=3)
    else:
        draw.rectangle(art_box, fill=(15, 15, 22), outline=h2rgb(theme["inner"]), width=3)

    # Description Box
    box_rect = (24, 436, width - 24, height - 70)
    draw.rectangle(box_rect, fill=h2rgb(theme["box"]), outline=h2rgb(theme["inner"]), width=2)

    # Type & Stats
    c_type_es = CARD_TYPES_ES[card.type_id] if 0 <= card.type_id < len(CARD_TYPES_ES) else "Monstruo"
    draw.text((40, 450), f"[ {c_type_es} ]", fill=h2rgb(theme["text"]))
    if card.type_id not in (20, 21, 23):
        stat_text = f"ATK / {card.atk}   DEF / {card.def_}"
        draw.text((width - 240, height - 105), stat_text, fill=h2rgb(theme["text"]))

    # Footer
    draw.text((28, height - 45), f"Pass: {card.password}", fill=(230, 230, 230))
    draw.text((width - 180, height - 45), f"Coste: {card.star_cost:,} ★", fill=(255, 215, 0))

    img.save(output_path, "PNG")
    return True
