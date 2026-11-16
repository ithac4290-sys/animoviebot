import base64
import json
import logging
import re
import urllib.parse
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional
import aiohttp

logger = logging.getLogger("GeminiSearch")

GEMINI_MODELS = ["gemini-flash-lite-latest", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite-preview"]


def has_cyrillic(text: str) -> bool:
    """Matnda kirill harflari (ruscha) mavjudligini aniqlash"""
    return bool(re.search(r"[\u0400-\u04FF]", text or ""))


async def translate_text(text: str, target_lang: str) -> str:
    """Matnni ko'rsatilgan tilga (uz, ru) tarjima qilish"""
    if not text:
        return ""
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q=" + urllib.parse.quote(text)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    res = "".join([p[0] for p in data[0] if p and p[0]])
                    if res and res.strip():
                        return res.strip()
    except Exception as e:
        logger.warning(f"Tarjima xatoligi ({target_lang}): {e}")
    return text


async def get_shikimori_russian(query: str) -> str:
    """Shikimori anime bazasidan rasmiy ruscha nomni olish"""
    if not query:
        return ""
    try:
        url = "https://shikimori.one/api/animes?search=" + urllib.parse.quote(query) + "&limit=1"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(url, headers={"User-Agent": "AniMovieBot/1.0"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and isinstance(data, list):
                        ru_name = data[0].get("russian")
                        if ru_name and has_cyrillic(ru_name):
                            return ru_name.strip()
    except Exception as e:
        logger.warning(f"Shikimori ruscha nom olishda xatolik: {e}")
    return ""


async def ensure_multilingual_titles(title_en: str, title_uz: str, title_ru: str,
                                     matched_db_title: str = "") -> tuple[str, str, str]:
    """
    3 ta tildagi nomlarning to'g'ri va bir-birini aynan takrorlamasligini ta'minlash:
    - EN: Inglizcha yoki Romaji nomi
    - RU: Haqiqiy ruscha (kirill) nomi (Shikimori yoki Google Translate)
    - UZ: O'zbekcha tarjima yoki bazadagi mahalliylashtirilgan o'zbekcha nomi
    """
    en = (title_en or "").strip() or "Noma'lum anime"
    uz = (title_uz or "").strip()
    ru = (title_ru or "").strip()

    # 1. Ruscha nomni to'g'rilash (kirill bo'lishi shart)
    if not ru or not has_cyrillic(ru) or ru.lower() == en.lower():
        shiki_ru = await get_shikimori_russian(en)
        if shiki_ru:
            ru = shiki_ru
        else:
            translated_ru = await translate_text(en, "ru")
            if has_cyrillic(translated_ru):
                ru = translated_ru
            else:
                ru = en

    # 2. O'zbekcha nomni to'g'rilash (inglizcha bilan bir xil bo'lib qolmasligi kerak)
    if matched_db_title and not has_cyrillic(matched_db_title):
        uz = matched_db_title
    elif not uz or uz.lower() == en.lower():
        translated_uz = await translate_text(en, "uz")
        if translated_uz and translated_uz.lower() != en.lower():
            uz = translated_uz
        else:
            uz = en

    return en, uz, ru


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

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
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
                                if parsed.get("found") is not False:
                                    parsed["found"] = True
                                    parsed["source"] = "gemini"
                                    return parsed
                    else:
                        resp_text = await resp.text()
                        logger.warning(f"Gemini API {model} status {resp.status}: {resp_text[:200]}")
            except Exception as e:
                logger.error(f"Gemini API {model} so'rovida xatolik: {type(e).__name__}: {e}")

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
                        if similarity >= 0.82:
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
    3. Aniqlangan nomlarni 3 ta tilga (EN, UZ, RU) to'liq o'girish
    """
    result = None
    if gemini_key:
        result = await identify_anime_with_gemini(image_bytes, gemini_key)

    if not result or not result.get("found"):
        result = await identify_anime_with_trace_moe(image_bytes, trace_key)

    if result and result.get("found"):
        raw_en = result.get("title_en") or result.get("title_ja") or ""
        raw_uz = result.get("title_uz") or ""
        raw_ru = result.get("title_ru") or ""

        en, uz, ru = await ensure_multilingual_titles(raw_en, raw_uz, raw_ru)
        result["title_en"] = en
        result["title_uz"] = uz
        result["title_ru"] = ru

        alts = result.get("alt_titles") or []
        for cand in [en, uz, ru, raw_en, result.get("title_ja")]:
            if cand and cand not in alts:
                alts.append(cand)
        result["alt_titles"] = alts

    return result


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
        if isinstance(a_data, str):
            try:
                a_data = json.loads(a_data)
            except Exception:
                a_data = {}
        elif not isinstance(a_data, dict):
            a_data = {}

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
