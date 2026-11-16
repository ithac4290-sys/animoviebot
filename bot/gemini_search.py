import base64
import json
import logging
import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional
import aiohttp

logger = logging.getLogger("GeminiSearch")

GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash"]


def normalize_title(s: str) -> str:
    """Nomlarni solishtirish uchun tozalash va standartlashtirish"""
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(s.split())


def calculate_similarity(s1: str, s2: str) -> float:
    """
    Ikkita matn (anime nomlari) o'rtasidagi o'xshashlik foizini hisoblash (0.0 dan 1.0 gacha).
    SequenceMatcher, token set overlap va substring qoidalarini birlashtiradi.
    """
    n1 = normalize_title(s1)
    n2 = normalize_title(s2)

    if not n1 or not n2:
        return 0.0

    if n1 == n2:
        return 1.0

    # Substring / ichma-ich joylashish tekshiruvi (masalan: "Black Clover" va "Black Clover TV")
    if (len(n1) >= 4 and n1 in n2) or (len(n2) >= 4 and n2 in n1):
        ratio = min(len(n1), len(n2)) / max(len(n1), len(n2))
        if ratio >= 0.65:
            return max(0.85, ratio)

    # SequenceMatcher nisbati
    seq_sim = SequenceMatcher(None, n1, n2).ratio()

    # So'zlar to'plami (Jaccard / Token set)
    words1 = set(n1.split())
    words2 = set(n2.split())
    token_sim = 0.0
    if words1 and words2:
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        token_sim = intersection / union if union > 0 else 0.0

        # Agar bir nomdagi barcha so'zlar ikkinchisida mavjud bo'lsa
        if intersection == min(len(words1), len(words2)) and intersection >= 2:
            token_sim = max(token_sim, 0.90)

    return max(seq_sim, token_sim)


async def identify_anime_with_gemini(image_bytes: bytes, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Google Gemini Multimodal API orqali rasmdagi animeni aniqlash.
    3 tilda (Uzbek, English, Russian) va yaponcha nomlarini qaytaradi.
    """
    if not api_key:
        return None

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        "Siz anime sohasidagi professional sun'iy intellektsiz. "
        "Yuborilgan anime suratini (skrinshot, epizod kadri, poster yoki qahramon) diqqat bilan tahlil qiling.\n"
        "1. Ushbu rasm qaysi animedan ekanligini aniq aniqlang.\n"
        "2. Ushbu animening nomini 3 ta tilda keltiring:\n"
        "   - Inglizcha (title_en)\n"
        "   - O'zbekcha (title_uz)\n"
        "   - Ruscha (title_ru)\n"
        "   - Yaponcha/Romaji (title_ja)\n"
        "3. Ushbu animening boshqa mashhur qisqartma yoki muqobil nomlarini (alt_titles) ro'yxat qiling.\n"
        "4. O'xshashlik ishonchliligi (confidence) 0.0 dan 1.0 gacha bo'lsin.\n"
        "5. Quyidagi JSON formatida FAQAT JSON javob bering:\n"
        "{\n"
        '  "found": true,\n'
        '  "title_en": "Anime title in English",\n'
        '  "title_uz": "Anime nomi o\'zbek tilida",\n'
        '  "title_ru": "Название аниме на русском",\n'
        '  "title_ja": "Romaji or Japanese title",\n'
        '  "alt_titles": ["Alt title 1", "Alt title 2"],\n'
        '  "confidence": 0.95,\n'
        '  "episode": null,\n'
        '  "description": "Animening qisqacha mazmuni"\n'
        "}\n"
        "Agar animeni mutlaqo aniqlab bo'lmasa, found: false qilib qaytaring."
    )

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_image
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
        for model in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                raw_text = parts[0].get("text", "").strip()
                                # Markdown json teglarni tozalash
                                clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_text, flags=re.MULTILINE).strip()
                                parsed = json.loads(clean_json)
                                if parsed.get("found"):
                                    parsed["source"] = "gemini"
                                    return parsed
                    else:
                        resp_text = await resp.text()
                        logger.warning(f"Gemini API {model} status {resp.status}: {resp_text[:200]}")
            except Exception as e:
                logger.error(f"Gemini API {model} so'rovida xatolik: {e}")

    return None


async def identify_anime_with_trace_moe(image_bytes: bytes, trace_key: str = "") -> Optional[Dict[str, Any]]:
    """
    Zaxira qidiruv (Trace.moe API) - epizod kadrlarini aniqlash
    """
    headers = {"Content-Type": "image/jpeg"}
    if trace_key:
        headers["x-trace-secret"] = trace_key

    trace_url = "https://api.trace.moe/search?cutBorders&anilistInfo"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.post(trace_url, data=image_bytes, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("result", [])
                    if results:
                        best = results[0]
                        similarity = best.get("similarity", 0)
                        if similarity >= 0.70:
                            anilist = best.get("anilist") or {}
                            title_info = anilist.get("title") or {}
                            romaji_title = title_info.get("romaji") or ""
                            english_title = title_info.get("english") or ""
                            native_title = title_info.get("native") or ""

                            filename = best.get("filename", "")
                            clean_filename = filename.split("]")[-1].split("[")[0].strip() if "]" in filename else filename
                            clean_filename = clean_filename.split("-")[0].strip()

                            alts = [t for t in [romaji_title, clean_filename, native_title] if t]

                            return {
                                "found": True,
                                "source": "trace_moe",
                                "title_en": english_title or romaji_title or clean_filename,
                                "title_uz": english_title or romaji_title,
                                "title_ru": english_title or romaji_title,
                                "title_ja": romaji_title or native_title,
                                "alt_titles": alts,
                                "confidence": round(similarity, 2),
                                "episode": best.get("episode")
                            }
    except Exception as e:
        logger.error(f"Trace.moe API xatolik: {e}")

    return None


async def identify_anime(image_bytes: bytes, gemini_key: str = "", trace_key: str = "") -> Optional[Dict[str, Any]]:
    """
    Rasm orqali animeni aniqlash:
    1. Avval Gemini API orqali (eng kuchli va ko'p tilli qidiruv)
    2. Agar Gemini kaliti bo'lmasa yoki xato bersa, Trace.moe orqali
    """
    if gemini_key:
        result = await identify_anime_with_gemini(image_bytes, gemini_key)
        if result and result.get("found"):
            return result

    # Zaxira sifatida Trace.moe
    return await identify_anime_with_trace_moe(image_bytes, trace_key)


def match_anime_in_database(detected_data: Dict[str, Any], db_animes: List[Dict[str, Any]],
                            threshold: float = 0.80) -> List[Dict[str, Any]]:
    """
    AI aniqlagan anime nomlarini (uz, en, ru, ja, alts) bazadagi barcha animelar bilan solishtirish.
    O'xshashligi 80% (threshold) dan yuqori bo'lgan Top 3 ta animeni qaytaradi.
    """
    if not detected_data or not db_animes:
        return []

    # AI topgan barcha nomlarni yig'ish
    search_titles = []
    for key in ["title_en", "title_uz", "title_ru", "title_ja"]:
        val = detected_data.get(key)
        if val and isinstance(val, str) and val.strip():
            search_titles.append(val.strip())

    for alt in detected_data.get("alt_titles", []):
        if alt and isinstance(alt, str) and alt.strip() and alt not in search_titles:
            search_titles.append(alt.strip())

    candidates = []

    for a in db_animes:
        db_title = a.get("title") or ""
        a_data = a.get("data") or {}
        db_alts = a_data.get("alt_titles") or []
        if isinstance(db_alts, str):
            db_alts = [db_alts]

        db_all_titles = [db_title] + [alt for alt in db_alts if isinstance(alt, str)]

        best_sim = 0.0
        best_match_pair = ("", "")

        for s_title in search_titles:
            for d_title in db_all_titles:
                sim = calculate_similarity(s_title, d_title)
                if sim > best_sim:
                    best_sim = sim
                    best_match_pair = (s_title, d_title)

        if best_sim >= threshold:
            candidates.append({
                "anime": a,
                "similarity": round(best_sim * 100, 1),
                "raw_similarity": best_sim,
                "matched_db_title": best_match_pair[1],
                "matched_search_title": best_match_pair[0]
            })

    # O'xshashlik bo'yicha kamayish tartibida saralash
    candidates.sort(key=lambda x: x["raw_similarity"], reverse=True)

    # Top 3 ta eng yaqin natijani qaytarish
    return candidates[:3]
