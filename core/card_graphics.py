"""
Card Graphics Extractor and Injector for Yu-Gi-Oh! Forbidden Memories.

Directly extracts and injects authentic in-game card artwork from DATA/WA_MRG.MRG:
  - 722 Card Miniatures (40x32, 64-color CLUT) located at sectors 0..721.
  - 722 Large Card Artworks (102x96, 256-color CLUT) located at sectors 722..5775 (7 sectors per card).
"""

import struct
from typing import Dict, Optional, Tuple

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# WA_MRG layout for card graphics
SECTOR_SIZE = 2048
MINI_START_SECTOR = 0           # 40x32 miniatures (1 sector each, 722 cards)
MINI_PIXELS = 40 * 32           # 1280 bytes
MINI_CLUT_COLORS = 64           # 128 bytes (uint16 BGR555 LE)

LARGE_START_SECTOR = 722        # 102x96 large artwork (7 sectors = 14336 bytes each)
LARGE_SECTORS_PER_CARD = 7
LARGE_WIDTH = 102
LARGE_HEIGHT = 96
LARGE_PIXELS = LARGE_WIDTH * LARGE_HEIGHT  # 9792 bytes
LARGE_CLUT_COLORS = 256         # 512 bytes (uint16 BGR555 LE)


def bgr555_to_rgb(val: int) -> Tuple[int, int, int]:
    """Converts 16-bit PS1 BGR555 color into 24-bit RGB (r, g, b)."""
    r = (val & 0x1F) << 3
    g = ((val >> 5) & 0x1F) << 3
    b = ((val >> 10) & 0x1F) << 3
    return (r, g, b)


def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """Converts 24-bit RGB color into 16-bit PS1 BGR555."""
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return r5 | (g5 << 5) | (b5 << 10)


class CardGraphicsDatabase:
    """
    Manages loading, extracting, caching and modifying in-game card artwork.
    """

    def __init__(self):
        self._wa_bytes: Optional[bytes] = None
        self._custom_artworks: Dict[int, Image.Image] = {}
        self._cached_images: Dict[int, Image.Image] = {}

    def set_wa_data(self, wa_bytes: bytes):
        """Sets or updates the underlying WA_MRG data source."""
        self._wa_bytes = wa_bytes
        self._cached_images.clear()

    def has_data(self) -> bool:
        return self._wa_bytes is not None and len(self._wa_bytes) >= (LARGE_START_SECTOR + 722 * LARGE_SECTORS_PER_CARD) * SECTOR_SIZE

    def get_card_art(self, card_id: int) -> Optional["Image.Image"]:
        """
        Retrieves the 102x96 artwork for card_id (1..722).
        Returns custom artwork if authored, or original extracted game artwork.
        """
        if not HAS_PIL:
            return None

        if card_id in self._custom_artworks:
            return self._custom_artworks[card_id]

        if card_id in self._cached_images:
            return self._cached_images[card_id]

        if not self.has_data():
            return None

        extracted = self._extract_large_art(card_id)
        if extracted is not None:
            self._cached_images[card_id] = extracted
        return extracted

    def set_custom_art(self, card_id: int, image: "Image.Image"):
        """Stores a custom artwork image for a card."""
        if not HAS_PIL or not (1 <= card_id <= 722):
            return
        # Ensure 102x96 dimensions
        if image.size != (LARGE_WIDTH, LARGE_HEIGHT):
            resized = image.resize((LARGE_WIDTH, LARGE_HEIGHT), Image.Resampling.LANCZOS)
        else:
            resized = image.copy()
        self._custom_artworks[card_id] = resized

    def clear_custom_art(self, card_id: int):
        """Removes custom artwork, reverting to original game art."""
        self._custom_artworks.pop(card_id, None)

    def _extract_large_art(self, card_id: int) -> Optional["Image.Image"]:
        """Extracts the 102x96 256-color image for card_id directly from WA_MRG."""
        if not (1 <= card_id <= 722) or self._wa_bytes is None:
            return None

        sec = LARGE_START_SECTOR + (card_id - 1) * LARGE_SECTORS_PER_CARD
        offset = sec * SECTOR_SIZE
        end_offset = offset + LARGE_SECTORS_PER_CARD * SECTOR_SIZE

        if end_offset > len(self._wa_bytes):
            return None

        block = self._wa_bytes[offset:end_offset]
        pixel_data = block[:LARGE_PIXELS]
        pal_data = block[LARGE_PIXELS : LARGE_PIXELS + LARGE_CLUT_COLORS * 2]

        palette = [
            bgr555_to_rgb(struct.unpack_from('<H', pal_data, i * 2)[0])
            for i in range(LARGE_CLUT_COLORS)
        ]

        img = Image.new('RGB', (LARGE_WIDTH, LARGE_HEIGHT))
        for y in range(LARGE_HEIGHT):
            row_off = y * LARGE_WIDTH
            for x in range(LARGE_WIDTH):
                idx = pixel_data[row_off + x]
                img.putpixel((x, y), palette[idx])

        return img

    def _extract_mini_art(self, card_id: int) -> Optional["Image.Image"]:
        """Extracts the 40x32 64-color miniature thumbnail for card_id."""
        if not (1 <= card_id <= 722) or self._wa_bytes is None:
            return None

        sec = MINI_START_SECTOR + (card_id - 1)
        offset = sec * SECTOR_SIZE
        if offset + SECTOR_SIZE > len(self._wa_bytes):
            return None

        sec_data = self._wa_bytes[offset : offset + SECTOR_SIZE]
        pixels = sec_data[:MINI_PIXELS]
        pal_data = sec_data[MINI_PIXELS : MINI_PIXELS + MINI_CLUT_COLORS * 2]

        palette = [
            bgr555_to_rgb(struct.unpack_from('<H', pal_data, i * 2)[0])
            for i in range(MINI_CLUT_COLORS)
        ]

        img = Image.new('RGB', (40, 32))
        for y in range(32):
            for x in range(40):
                idx = pixels[y * 40 + x] & 0x3F
                img.putpixel((x, y), palette[idx])

        return img

    def apply_to_wa(self, target_wa: bytearray) -> int:
        """
        Injects any modified/custom card artworks back into WA_MRG,
        updating both the 102x96 large artwork and the 40x32 miniature thumbnail.
        Returns the number of cards injected.
        """
        if not HAS_PIL or not self._custom_artworks:
            return 0

        injected = 0
        for card_id, img in self._custom_artworks.items():
            if not (1 <= card_id <= 722):
                continue

            # 1. Prepare 102x96 256-color image
            img_large = img.convert('RGB')
            quantized_large = img_large.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
            raw_pal = quantized_large.getpalette()[:256 * 3]

            # Convert RGB palette to 16-bit BGR555
            pal_bytes = bytearray(512)
            for i in range(len(raw_pal) // 3):
                r, g, b = raw_pal[i*3 : i*3 + 3]
                bgr555 = rgb_to_bgr555(r, g, b)
                struct.pack_into('<H', pal_bytes, i * 2, bgr555)

            large_pixels = quantized_large.tobytes()

            # Write large art
            sec = LARGE_START_SECTOR + (card_id - 1) * LARGE_SECTORS_PER_CARD
            offset = sec * SECTOR_SIZE
            if offset + LARGE_PIXELS + 512 <= len(target_wa):
                target_wa[offset : offset + LARGE_PIXELS] = large_pixels
                target_wa[offset + LARGE_PIXELS : offset + LARGE_PIXELS + 512] = pal_bytes

            # 2. Prepare 40x32 64-color thumbnail
            img_mini = img_large.resize((40, 32), Image.Resampling.LANCZOS)
            quantized_mini = img_mini.quantize(colors=64, method=Image.Quantize.MEDIANCUT)
            raw_mini_pal = quantized_mini.getpalette()[:64 * 3]

            mini_pal_bytes = bytearray(128)
            for i in range(len(raw_mini_pal) // 3):
                r, g, b = raw_mini_pal[i*3 : i*3 + 3]
                bgr555 = rgb_to_bgr555(r, g, b)
                struct.pack_into('<H', mini_pal_bytes, i * 2, bgr555)

            mini_pixels = quantized_mini.tobytes()

            # Write miniature art
            mini_sec = MINI_START_SECTOR + (card_id - 1)
            mini_offset = mini_sec * SECTOR_SIZE
            if mini_offset + SECTOR_SIZE <= len(target_wa):
                target_wa[mini_offset : mini_offset + MINI_PIXELS] = mini_pixels
                target_wa[mini_offset + MINI_PIXELS : mini_offset + MINI_PIXELS + 128] = mini_pal_bytes
                # Fill remaining 640 bytes with 0xFF
                target_wa[mini_offset + MINI_PIXELS + 128 : mini_offset + SECTOR_SIZE] = b'\xFF' * 640

            injected += 1

        return injected
