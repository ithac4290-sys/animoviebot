import logging
from io import BytesIO
from typing import Optional
from PIL import Image

logger = logging.getLogger("ImageSearch")


def compute_image_hash(image_bytes: bytes) -> str:
    """
    Rasmdan 64-bit dHash (difference hash) hisoblash.
    Ushbu hash rasm masshtabi, siqilishi va kichik o'zgarishlariga juda chidamli.
    """
    try:
        img = Image.open(BytesIO(image_bytes)).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())
        difference = []
        for row in range(8):
            for col in range(8):
                pixel_left = pixels[row * 9 + col]
                pixel_right = pixels[row * 9 + col + 1]
                difference.append(pixel_left > pixel_right)

        decimal_val = 0
        for index, val in enumerate(difference):
            if val:
                decimal_val |= 1 << index
        return f"{decimal_val:016x}"
    except Exception as e:
        logger.error(f"Image hash hisoblashda xatolik: {e}")
        return ""


def hash_similarity(hash1: str, hash2: str) -> float:
    """
    Ikkita dHash o'rtasidagi o'xshashlik foizini qaytaradi (0.0 dan 1.0 gacha).
    Hamming masofasi formulasi: (64 - masofa) / 64
    """
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 0.0
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        dist = bin(val1 ^ val2).count("1")
        return (64 - dist) / 64.0
    except Exception:
        return 0.0
