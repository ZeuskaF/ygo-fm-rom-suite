"""
Field Spells & Duel Arenas Database and Customizer for Yu-Gi-Oh! Forbidden Memories.
Manages the 7 duel battlefields (Normal Stone Coliseum and the 6 Field Magic cards #301-#306),
including arena colors, custom background textures/images, boosted/weakened monster types,
and PS1 WA_MRG.MRG arena offsets.
"""

import base64
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

# Offsets for the 7 duel arenas in DATA/WA_MRG.MRG
# Each arena block has a stride of 0x75800 (481,280 bytes)
ARENA_STRIDE = 0x75800
ARENA_WA_OFFSETS = {
    0: 0x00B85000,  # Arena 0: Normal (Coliseo de Piedra / Neutral)
    1: 0x00BFA800,  # Arena 1: Bosque (Forest - Card #301)
    2: 0x00C70000,  # Arena 2: Páramo / Desierto (Wasteland - Card #302)
    3: 0x00CE5800,  # Arena 3: Montaña (Mountain - Card #303)
    4: 0x00D5B000,  # Arena 4: Pradera (Sogen - Card #304)
    5: 0x00DD0800,  # Arena 5: Mar / Océano (Umi - Card #305)
    6: 0x00E46000,  # Arena 6: Oscuridad (Yami - Card #306)
}

# Authentic PS1 default colors for each arena
DEFAULT_FIELD_COLORS: Dict[int, Dict[str, str]] = {
    0: {  # Normal (Coliseo de Piedra)
        "ground":       "#8C7B65",
        "grid":         "#D4C2A5",
        "monster_zone": "#5C5042",
        "spell_zone":   "#4A3F33",
        "border":       "#BFAF96",
        "sky":          "#1C1424",
    },
    1: {  # Bosque (Forest #301)
        "ground":       "#1C4D25",
        "grid":         "#48A359",
        "monster_zone": "#13371A",
        "spell_zone":   "#0F2B15",
        "border":       "#2A6E35",
        "sky":          "#0B2613",
    },
    2: {  # Yermo / Páramo (Wasteland #302)
        "ground":       "#7A4D2E",
        "grid":         "#C28555",
        "monster_zone": "#56341C",
        "spell_zone":   "#432815",
        "border":       "#9A6038",
        "sky":          "#3B2011",
    },
    3: {  # Montaña (Mountain #303)
        "ground":       "#485567",
        "grid":         "#8FA3BC",
        "monster_zone": "#313B49",
        "spell_zone":   "#252C37",
        "border":       "#687B94",
        "sky":          "#151F2E",
    },
    4: {  # Pradera (Sogen #304)
        "ground":       "#556B2F",
        "grid":         "#A4C639",
        "monster_zone": "#3E4E22",
        "spell_zone":   "#2D3918",
        "border":       "#7D9B42",
        "sky":          "#1E2A12",
    },
    5: {  # Mar / Océano (Umi #305)
        "ground":       "#1A4B75",
        "grid":         "#3EB4E4",
        "monster_zone": "#103250",
        "spell_zone":   "#0C243B",
        "border":       "#2670A8",
        "sky":          "#081926",
    },
    6: {  # Oscuridad (Yami #306)
        "ground":       "#3B1B54",
        "grid":         "#B25CF2",
        "monster_zone": "#261137",
        "spell_zone":   "#1B0B28",
        "border":       "#672E94",
        "sky":          "#0F0617",
    },
}

# Curated arena style presets
FIELD_PRESETS: Dict[str, Dict[int, Dict[str, str]]] = {
    "Forbidden Memories Clásico (PS1)": DEFAULT_FIELD_COLORS,
    "Anime Reino de los Duelistas": {
        0: {"ground": "#968165", "grid": "#E6D4B5", "monster_zone": "#63543F", "spell_zone": "#514330", "border": "#CCA670", "sky": "#201830"},
        1: {"ground": "#16632B", "grid": "#57DE72", "monster_zone": "#0F421D", "spell_zone": "#0A2F14", "border": "#319E49", "sky": "#0E381C"},
        2: {"ground": "#8F4B23", "grid": "#E39252", "monster_zone": "#663519", "spell_zone": "#4E2610", "border": "#B8662E", "sky": "#471E09"},
        3: {"ground": "#3B5A85", "grid": "#87B9F5", "monster_zone": "#273D5C", "spell_zone": "#1B2C42", "border": "#5983B8", "sky": "#112038"},
        4: {"ground": "#638228", "grid": "#BDE848", "monster_zone": "#43591A", "spell_zone": "#304212", "border": "#87B334", "sky": "#25380E"},
        5: {"ground": "#145999", "grid": "#4DE2FF", "monster_zone": "#0D3C69", "spell_zone": "#082847", "border": "#2B87DE", "sky": "#07203B"},
        6: {"ground": "#4A1878", "grid": "#D466FF", "monster_zone": "#300D52", "spell_zone": "#210738", "border": "#8324D6", "sky": "#150226"},
    },
    "Cyber Neón 3D / Tron": {
        0: {"ground": "#14141A", "grid": "#FFE066", "monster_zone": "#22222E", "spell_zone": "#1A1A24", "border": "#FFCC00", "sky": "#0A0A10"},
        1: {"ground": "#0B1A10", "grid": "#00FF66", "monster_zone": "#122919", "spell_zone": "#0E1F13", "border": "#00CC52", "sky": "#050D08"},
        2: {"ground": "#1F140A", "grid": "#FF9933", "monster_zone": "#332110", "spell_zone": "#26190C", "border": "#CC7A29", "sky": "#100A05"},
        3: {"ground": "#0D1824", "grid": "#33CCFF", "monster_zone": "#142538", "spell_zone": "#0F1C2B", "border": "#29A3CC", "sky": "#060C12"},
        4: {"ground": "#161F0A", "grid": "#CCFF33", "monster_zone": "#243310", "spell_zone": "#1B260C", "border": "#A3CC29", "sky": "#0B1005"},
        5: {"ground": "#0A1826", "grid": "#00F0FF", "monster_zone": "#10263D", "spell_zone": "#0C1D2E", "border": "#00C0CC", "sky": "#050C13"},
        6: {"ground": "#1C0A26", "grid": "#FF33F0", "monster_zone": "#2E103D", "spell_zone": "#230C2E", "border": "#CC29C0", "sky": "#0E0513"},
    },
    "Noche Egipcia Milenaria": {
        0: {"ground": "#29242E", "grid": "#FFD700", "monster_zone": "#3B3442", "spell_zone": "#2B2433", "border": "#DAA520", "sky": "#0B0714"},
        1: {"ground": "#1A2E20", "grid": "#D4AF37", "monster_zone": "#26422E", "spell_zone": "#1B3021", "border": "#C5A028", "sky": "#09120C"},
        2: {"ground": "#3B281E", "grid": "#F4C430", "monster_zone": "#4F3628", "spell_zone": "#38261C", "border": "#E5B820", "sky": "#140D0A"},
        3: {"ground": "#202A3B", "grid": "#E6CA65", "monster_zone": "#2E3B54", "spell_zone": "#202A3B", "border": "#CDB04A", "sky": "#0A0E17"},
        4: {"ground": "#2E331A", "grid": "#E0CE53", "monster_zone": "#3E4523", "spell_zone": "#2C3119", "border": "#C7B53E", "sky": "#0F1208"},
        5: {"ground": "#142838", "grid": "#70D6FF", "monster_zone": "#1C3950", "spell_zone": "#142838", "border": "#4ABAE5", "sky": "#071018"},
        6: {"ground": "#291438", "grid": "#E0A3FF", "monster_zone": "#3A1C50", "spell_zone": "#291438", "border": "#B866E5", "sky": "#0E0616"},
    },
    "Abismo de las Sombras": {
        0: {"ground": "#212126", "grid": "#8A8A99", "monster_zone": "#2D2D33", "spell_zone": "#1E1E24", "border": "#555566", "sky": "#0D0D12"},
        1: {"ground": "#13261A", "grid": "#4E7A5A", "monster_zone": "#1D3827", "spell_zone": "#152B1E", "border": "#365940", "sky": "#0A140E"},
        2: {"ground": "#2E1B15", "grid": "#7A4E40", "monster_zone": "#3D251D", "spell_zone": "#2B1A14", "border": "#5E382D", "sky": "#140A07"},
        3: {"ground": "#182230", "grid": "#4A6180", "monster_zone": "#223145", "spell_zone": "#192433", "border": "#354861", "sky": "#0B1017"},
        4: {"ground": "#242B15", "grid": "#61733B", "monster_zone": "#333D1E", "spell_zone": "#242B15", "border": "#475429", "sky": "#101308"},
        5: {"ground": "#102330", "grid": "#3A688A", "monster_zone": "#183245", "spell_zone": "#102330", "border": "#284D69", "sky": "#07111A"},
        6: {"ground": "#240E30", "grid": "#7F3E9E", "monster_zone": "#331445", "spell_zone": "#240E30", "border": "#5E2978", "sky": "#100517"},
    },
}

# Detailed metadata for the 7 duel arenas
FIELD_METADATA: Dict[int, Dict[str, Any]] = {
    0: {
        "field_id": 0,
        "card_id": 0,
        "name_es": "Normal (Coliseo Egipcio)",
        "name_en": "Normal (Stone Coliseum)",
        "card_name": "Terreno Neutral",
        "description": "Arena de piedra clásica egipcia. No otorga bonificaciones ni penalizaciones.",
        "boosted_types": [],
        "weakened_types": [],
        "symbol": "🏛️",
        "tag": "Neutral",
    },
    1: {
        "field_id": 1,
        "card_id": 301,
        "name_es": "Bosque (Forest)",
        "name_en": "Forest",
        "card_name": "#301 Bosque (Forest)",
        "description": "Espeso follaje y enredaderas. Aumenta ATK/DEF en +500 a Insecto, Bestia, Planta y Guerrero-Bestia.",
        "boosted_types": ["Insect", "Beast", "Plant", "Beast-Warrior"],
        "weakened_types": [],
        "symbol": "🌲",
        "tag": "+500 ATK/DEF Insecto, Bestia, Planta, Guerrero-Bestia",
    },
    2: {
        "field_id": 2,
        "card_id": 302,
        "name_es": "Yermo / Páramo (Wasteland)",
        "name_en": "Wasteland",
        "card_name": "#302 Páramo (Wasteland)",
        "description": "Terreno árido, cañones y tierra agrietada. Aumenta ATK/DEF en +500 a Dinosaurio, Zombi, Roca y Máquina.",
        "boosted_types": ["Dinosaur", "Zombie", "Rock", "Machine"],
        "weakened_types": [],
        "symbol": "🏜️",
        "tag": "+500 ATK/DEF Dinosaurio, Zombi, Roca, Máquina",
    },
    3: {
        "field_id": 3,
        "card_id": 303,
        "name_es": "Montaña (Mountain)",
        "name_en": "Mountain",
        "card_name": "#303 Montaña (Mountain)",
        "description": "Picos escarpados y tormentas de altura. Aumenta ATK/DEF en +500 a Dragón, Bestia Alada y Trueno.",
        "boosted_types": ["Dragon", "Winged Beast", "Thunder"],
        "weakened_types": [],
        "symbol": "⛰️",
        "tag": "+500 ATK/DEF Dragón, Bestia Alada, Trueno",
    },
    4: {
        "field_id": 4,
        "card_id": 304,
        "name_es": "Pradera (Sogen)",
        "name_en": "Sogen",
        "card_name": "#304 Pradera (Sogen)",
        "description": "Llanuras abiertas bañadas por el sol. Aumenta ATK/DEF en +500 a Guerrero y Guerrero-Bestia.",
        "boosted_types": ["Warrior", "Beast-Warrior"],
        "weakened_types": [],
        "symbol": "🌾",
        "tag": "+500 ATK/DEF Guerrero, Guerrero-Bestia",
    },
    5: {
        "field_id": 5,
        "card_id": 305,
        "name_es": "Mar / Océano (Umi)",
        "name_en": "Umi",
        "card_name": "#305 Mar (Umi)",
        "description": "Océano profundo y fosas abisales. Aumenta ATK/DEF en +500 a Pez, Serpiente Marina, Trueno y Aqua. Reduce ATK/DEF en -500 a Piro.",
        "boosted_types": ["Fish", "Sea Serpent", "Thunder", "Aqua"],
        "weakened_types": ["Pyro"],
        "symbol": "🌊",
        "tag": "+500 Pez, Serpiente Marina, Trueno, Aqua | -500 Piro",
    },
    6: {
        "field_id": 6,
        "card_id": 306,
        "name_es": "Oscuridad (Yami)",
        "name_en": "Yami",
        "card_name": "#306 Oscuridad (Yami)",
        "description": "Reino de las Sombras y tinieblas místicas. Aumenta ATK/DEF en +500 a Lanzador de Conjuros y Demonio. Reduce ATK/DEF en -500 a Hada.",
        "boosted_types": ["Spellcaster", "Fiend"],
        "weakened_types": ["Fairy"],
        "symbol": "🔮",
        "tag": "+500 Lanzador de Conjuros, Demonio | -500 Hada",
    },
}


@dataclass
class FieldSpellData:
    """Represents a single duel battlefield / arena configuration."""
    field_id: int
    card_id: int
    name_es: str
    name_en: str
    description: str
    boosted_types: List[str]
    weakened_types: List[str]
    wa_offset: int
    colors: Dict[str, str] = field(default_factory=dict)
    custom_image_path: Optional[str] = None
    custom_image_b64: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "card_id": self.card_id,
            "name_es": self.name_es,
            "name_en": self.name_en,
            "description": self.description,
            "boosted_types": list(self.boosted_types),
            "weakened_types": list(self.weakened_types),
            "wa_offset": self.wa_offset,
            "colors": dict(self.colors),
            "custom_image_path": self.custom_image_path,
            "custom_image_b64": self.custom_image_b64,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FieldSpellData":
        return cls(
            field_id=data["field_id"],
            card_id=data.get("card_id", 0),
            name_es=data.get("name_es", ""),
            name_en=data.get("name_en", ""),
            description=data.get("description", ""),
            boosted_types=data.get("boosted_types", []),
            weakened_types=data.get("weakened_types", []),
            wa_offset=data.get("wa_offset", 0),
            colors=data.get("colors", {}),
            custom_image_path=data.get("custom_image_path"),
            custom_image_b64=data.get("custom_image_b64"),
        )


class FieldSpellDatabase:
    """
    Manages the 7 duel arena themes, colors, background textures, and gameplay type multipliers.
    """

    def __init__(self):
        self.fields: Dict[int, FieldSpellData] = {}
        self.reset_to_defaults()

    def reset_to_defaults(self) -> None:
        """Restores all 7 duel arenas to the authentic PS1 Forbidden Memories configuration."""
        self.fields.clear()
        for fid, meta in FIELD_METADATA.items():
            def_colors = dict(DEFAULT_FIELD_COLORS[fid])
            fdata = FieldSpellData(
                field_id=fid,
                card_id=meta["card_id"],
                name_es=meta["name_es"],
                name_en=meta["name_en"],
                description=meta["description"],
                boosted_types=list(meta["boosted_types"]),
                weakened_types=list(meta["weakened_types"]),
                wa_offset=ARENA_WA_OFFSETS[fid],
                colors=def_colors,
                custom_image_path=None,
                custom_image_b64=None,
            )
            self.fields[fid] = fdata

    def get_field(self, field_id: int) -> FieldSpellData:
        """Returns the FieldSpellData for the specified field ID (0 to 6)."""
        if field_id not in self.fields:
            field_id = 0
        return self.fields[field_id]

    def get_field_by_card_id(self, card_id: int) -> Optional[FieldSpellData]:
        """Finds field data by card ID (#301 to #306). Returns None if not a field spell."""
        for f in self.fields.values():
            if f.card_id == card_id and card_id > 0:
                return f
        return None

    def set_field_color(self, field_id: int, color_key: str, hex_color: str) -> None:
        """Updates a specific color component (ground, grid, monster_zone, spell_zone, border, sky)."""
        if field_id in self.fields:
            self.fields[field_id].colors[color_key] = hex_color

    def set_field_image(self, field_id: int, file_path: str) -> bool:
        """Sets a custom background image or texture for an arena."""
        if field_id not in self.fields or not os.path.exists(file_path):
            return False

        self.fields[field_id].custom_image_path = file_path
        try:
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
                self.fields[field_id].custom_image_b64 = b64
            return True
        except Exception:
            return False

    def clear_field_image(self, field_id: int) -> None:
        """Removes the custom background image from the arena, falling back to procedural colors."""
        if field_id in self.fields:
            self.fields[field_id].custom_image_path = None
            self.fields[field_id].custom_image_b64 = None

    def calculate_stat_modifier(self, field_id: int, card_type: str) -> Tuple[int, int]:
        """
        Calculates the ATK and DEF bonus for a monster type on the given field:
        - Boosted types: (+500, +500)
        - Weakened types: (-500, -500)
        - Neutral types: (0, 0)
        """
        fdata = self.get_field(field_id)
        if card_type in fdata.boosted_types:
            return (500, 500)
        elif card_type in fdata.weakened_types:
            return (-500, -500)
        return (0, 0)

    def apply_preset(self, preset_name: str) -> bool:
        """Applies a curated arena color preset to all 7 arenas."""
        if preset_name not in FIELD_PRESETS:
            return False

        preset_data = FIELD_PRESETS[preset_name]
        for fid, col_map in preset_data.items():
            if fid in self.fields:
                self.fields[fid].colors.update(dict(col_map))
        return True

    def export_config(self) -> Dict[str, Any]:
        """Exports the entire field database configuration as a JSON-serializable dictionary."""
        return {
            "version": 1,
            "fields": {str(fid): f.to_dict() for fid, f in self.fields.items()}
        }

    def import_config(self, config_dict: Dict[str, Any]) -> int:
        """Imports arena configurations from a dictionary. Returns the number of fields updated."""
        if not isinstance(config_dict, dict) or "fields" not in config_dict:
            return 0

        count = 0
        fields_data = config_dict["fields"]
        for fid_str, data in fields_data.items():
            try:
                fid = int(fid_str)
                if fid in self.fields:
                    imported = FieldSpellData.from_dict(data)
                    self.fields[fid].colors.update(imported.colors)
                    self.fields[fid].custom_image_path = imported.custom_image_path
                    self.fields[fid].custom_image_b64 = imported.custom_image_b64
                    count += 1
            except Exception:
                continue
        return count

    def save_to_json_file(self, file_path: str) -> bool:
        """Saves current arena configurations to a JSON file."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.export_config(), f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_from_json_file(self, file_path: str) -> int:
        """Loads arena configurations from a JSON file."""
        if not os.path.exists(file_path):
            return 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self.import_config(data)
        except Exception:
            return 0
