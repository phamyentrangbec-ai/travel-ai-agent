"""
Trip Buddy Travel AI Agent - Core state machine entrypoint.
v8 — Rich knowledge base format + alternatives + YouTube/Foursquare + AI Q&A
"""
import re
import json
import unicodedata
import os
import sys
import logging
import requests as _requests
from pathlib import Path as _Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Load 63 tỉnh thành aliases from JSON (bypasses .pyc cache)
# ---------------------------------------------------------------------------
_ALIASES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'city_aliases.json')
with open(_ALIASES_PATH, 'r', encoding='utf-8') as _f:
    CITY_ALIASES = json.load(_f)

# ---------------------------------------------------------------------------
# City data loader — inlined to bypass .pyc cache on tools/static_data.py
# ---------------------------------------------------------------------------
_APP_ROOT = _Path(os.path.abspath(__file__)).parent
_KB_DIR   = _APP_ROOT / 'data' / 'knowledge_bases'
_LEGACY_PATH = _APP_ROOT / 'data' / 'genz_spots.json'
_FALLBACK_PATH = _APP_ROOT / 'data' / 'fallback_spots.json'

# Load fallback spots for sub-destinations
_FALLBACK_SPOTS = {}
try:
    if _FALLBACK_PATH.exists():
        with open(_FALLBACK_PATH, 'r', encoding='utf-8') as _fbf:
            _FALLBACK_SPOTS = json.load(_fbf)
except Exception:
    pass

_CITY_SLUG_MAP = {
    'Da Lat': 'da_lat', 'Hoi An': 'hoi_an', 'Da Nang': 'da_nang',
    'Ha Noi': 'ha_noi', 'TP HCM': 'tp_hcm', 'Nha Trang': 'nha_trang',
    'Phu Quoc': 'phu_quoc', 'Hue': 'hue', 'Ha Long': 'ha_long',
    'Sa Pa': 'sa_pa', 'Ninh Binh': 'ninh_binh', 'Vung Tau': 'vung_tau',
    'Ha Giang': 'ha_giang', 'Mui Ne': 'mui_ne', 'Binh Thuan': 'mui_ne',
    'Can Tho': 'can_tho', 'Quang Ninh': 'ha_long',
}

def _slug_for(city):
    if city in _CITY_SLUG_MAP:
        return _CITY_SLUG_MAP[city]
    return city.lower().replace(' ', '_').replace('-', '_')

def load_city_data(city):
    """Load city data. Returns dict with '_format': 'rich'|'legacy', or None."""
    slug = _slug_for(city)
    kb_path = _KB_DIR / f'{slug}.json'
    if kb_path.exists():
        try:
            with open(kb_path, 'r', encoding='utf-8') as _kf:
                _d = json.load(_kf)
            _d['_format'] = 'rich'
            return _d
        except Exception:
            pass
    if _LEGACY_PATH.exists():
        try:
            with open(_LEGACY_PATH, 'r', encoding='utf-8') as _lf:
                _all = json.load(_lf)
            _leg = _all.get(city)
            if _leg:
                _leg = dict(_leg)
                _leg['_format'] = 'legacy'
                return _leg
        except Exception:
            pass
    return None

# ---------------------------------------------------------------------------
# KB rich-format adapter — inlined to bypass kb_loader.py .pyc cache
# ---------------------------------------------------------------------------

def _extract_slot_inline(items):
    """Convert a list of itinerary items into {name, address, desc, price, alternatives}."""
    if not items:
        return None
    item = dict(items[0])
    sub = item.pop('options', None) or item.pop('places', None) or item.pop('cafe_options', None)
    if sub:
        item.update(sub[0])
        item['_xalts'] = sub[1:]
    name = (item.get('name') or item.get('activity') or '').strip()
    address = item.get('address', '')
    desc = item.get('note') or item.get('tip') or ''
    price = item.get('price', '')
    alts_raw = list(item.get('alternatives', [])) + item.get('_xalts', [])
    for extra in items[1:]:
        if isinstance(extra, dict) and extra.get('name'):
            alts_raw.append(extra)
    seen, alts = {name}, []
    for a in alts_raw:
        an = (a.get('name') or '').strip()
        if an and an not in seen:
            seen.add(an)
            alts.append({'name': an, 'address': a.get('address', ''), 'desc': a.get('note', ''), 'price': a.get('price', '')})
        if len(alts) >= 3:
            break
    return {'name': name, 'address': address, 'desc': desc, 'price': price, 'alternatives': alts}


def _kb_to_days(kb, duration):
    """Convert rich KB itinerary to API day list."""
    itin = kb.get('itinerary', {})
    keys = sorted(itin.keys())
    days = []
    for day_num in range(1, duration + 1):
        key = keys[(day_num - 1) % len(keys)] if keys else None
        dd = itin.get(key, {}) if key else {}
        title = dd.get('title', f'Ngay {day_num}')
        mi = dd.get('morning', [])
        ai = dd.get('afternoon', [])
        ei = dd.get('evening', [])
        mf = [x for x in mi if x.get('type') == 'food' or x.get('category') == 'breakfast']
        af = [x for x in ai if x.get('category') == 'lunch' or x.get('type') == 'food']
        ef = [x for x in ei if x.get('category') == 'dinner' or x.get('type') == 'food']
        ni = [x for x in ei if x.get('type') in ('market', 'attraction', 'neighborhood', 'entertainment')]
        days.append({
            'day': day_num, 'title': title,
            'morning':   _extract_slot_inline(mf or mi),
            'afternoon': _extract_slot_inline(af or ai),
            'evening':   _extract_slot_inline(ef or ei),
            'night':     _extract_slot_inline(ni or (ei[-1:] if ei else [])),
        })
    return days


def _kb_to_trending(kb, limit=6):
    """Extract trending spots from KB attractions."""
    places = kb.get('places_directory', {}).get('attractions', {}).get('places', [])
    return [{'name': p.get('name', ''), 'type': p.get('type', 'attraction'), 'vibe': p.get('note', ''), 'tiktok': True}
            for p in places[:limit]]


def _kb_to_tips(kb, limit=5):
    """Extract hidden gem tips from KB snack/specialty items."""
    food = kb.get('places_directory', {}).get('food', {})
    gems = food.get('snack', {}).get('places', []) + food.get('specialty', {}).get('places', [])
    seen, tips = set(), []
    for g in gems:
        n = g.get('name', '')
        if n and n not in seen:
            seen.add(n)
            tips.append({'name': n, 'desc': g.get('note', g.get('address', ''))})
        if len(tips) >= limit:
            break
    return tips


# ---------------------------------------------------------------------------
# Text normalization helpers
# ---------------------------------------------------------------------------

def _strip_accents(text):
    """Normalize Vietnamese accented characters to ASCII."""
    text = text.replace('đ', 'd').replace('Đ', 'D')
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


# ---------------------------------------------------------------------------
# Detection functions
# ---------------------------------------------------------------------------

def _build_sorted_aliases():
    """Pre-build alias list sorted by length descending for longest-match-first."""
    pairs = []
    for city, aliases in CITY_ALIASES.items():
        for alias in aliases:
            pairs.append((_strip_accents(alias.lower()), city))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs

_SORTED_ALIASES = _build_sorted_aliases()


def detect_city(text):
    """Map user input to canonical city name (longest alias wins)."""
    normalized = _strip_accents(text.lower().strip())
    for alias_norm, city in _SORTED_ALIASES:
        if alias_norm in normalized:
            return city
    return None


def detect_companions(text):
    """Detect travel companions type."""
    normalized = _strip_accents(text.lower().strip())
    if re.search(r'\b1\b', text) or any(w in normalized for w in ['solo', 'mot minh', 'di mot', 'minh toi', 'ca nhan']):
        return 'solo'
    if re.search(r'\b2\b', text) or any(w in normalized for w in ['cap doi', 'doi', 'couple', 'ban trai', 'ban gai', 'nguoi yeu', '2 nguoi']):
        return 'couple'
    if re.search(r'\b3\b', text) or any(w in normalized for w in ['nhom ban', 'ban be', 'hoi ban', 'hoi', 'friends', 'ban', 'nhom']):
        return 'friends'
    if re.search(r'\b4\b', text) or any(w in normalized for w in ['gia dinh', 'family', 'bo me', 'con cai', 'ba me']):
        return 'family'
    return None


def detect_duration(text):
    """Detect trip duration. Returns (days, label) tuple or None."""
    # Strip emojis and extra whitespace first
    clean = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE).strip()
    normalized = _strip_accents(text.lower().strip())
    clean_norm = _strip_accents(clean.lower().strip())

    # Handle "XNYĐ" or "XNyD" style directly (e.g. "3N2Đ", "2N1Đ", "4N3Đ")
    m_nd = re.match(r'^(\d+)[Nn]\d+', clean.strip())
    if m_nd:
        n = int(m_nd.group(1))
        if n >= 2:
            return (n, f'{n}N{n-1}D')
        return (2, '2N1D')

    # Numbered options 1-5 from menu
    if re.search(r'^1$', clean.strip()):
        return (2, '2N1D')
    if re.search(r'^2$', clean.strip()):
        return (3, '3N2D')
    if re.search(r'^3$', clean.strip()):
        return (4, '4N3D')
    if re.search(r'^4$', clean.strip()):
        return (7, '7N6D')
    if re.search(r'^5$', clean.strip()) or 'khac' in normalized:
        return None
    if any(w in normalized for w in ['1 tuan', 'mot tuan', '7 ngay', 'tuan']):
        return (7, '7N6D')
    # Fallback: any standalone number
    m = re.search(r'(\d+)', clean)
    if m:
        n = int(m.group(1))
        if 2 <= n <= 30:
            return (n, f'{n}N{n-1}D')
        if n == 1:
            return (2, '2N1D')
    return None


def detect_budget(text):
    """Detect budget tier."""
    normalized = _strip_accents(text.lower().strip())
    if re.search(r'^1$', text.strip()) or any(w in normalized for w in ['tiet kiem', 'budget', 're', 'gia re', 'tiet']):
        return 'budget'
    if re.search(r'^2$', text.strip()) or any(w in normalized for w in ['tam trung', 'trung binh', 'mid', 'vua']):
        return 'mid'
    if re.search(r'^3$', text.strip()) or any(w in normalized for w in ['luxury', 'cao cap', 'sang', 'vip', 'cao']):
        return 'luxury'
    if re.search(r'^4$', text.strip()) or 'khac' in normalized:
        return None
    return None


def detect_custom_budget(text):
    """Parse Vietnamese currency strings."""
    text_norm = _strip_accents(text.lower().replace(',', '.'))
    m = re.search(r'(\d+\.?\d*)\s*(trieu\b|tr\b)', text_norm)
    if m:
        return int(float(m.group(1)) * 1_000_000)
    m = re.search(r'(\d+\.?\d*)\s*(nghin|k\b)', text_norm)
    if m:
        return int(float(m.group(1)) * 1_000)
    m = re.search(r'(\d{4,})', text_norm)
    if m:
        return int(m.group(1))
    return None


def detect_style(text):
    """Detect travel style(s). Returns list."""
    styles = []
    style_map = {'1': 'photo', '2': 'explore', '3': 'relax', '4': 'food', '5': 'culture'}
    normalized = _strip_accents(text.lower())
    kw_map = {
        'photo':   ['song ao', 'chup anh', 'instagram', 'tiktok', 'photo', 'check in'],
        'explore': ['kham pha', 'phieu luu', 'adventure', 'explore', 'trekking'],
        'relax':   ['thu gian', 'nghi ngoi', 'relax', 'chill', 'spa', 'bien'],
        'food':    ['am thuc', 'an uong', 'food', 'dac san', 'an ngon'],
        'culture': ['van hoa', 'lich su', 'culture', 'history', 'di tich'],
    }
    for num, style in style_map.items():
        if num in text.split():
            if style not in styles:
                styles.append(style)
    for style, keywords in kw_map.items():
        if any(kw in normalized for kw in keywords):
            if style not in styles:
                styles.append(style)
    return styles if styles else ['explore']


# ---------------------------------------------------------------------------
# Live API helpers (graceful fallback when no keys)
# ---------------------------------------------------------------------------

def fetch_unified_trending(city, kb=None):
    """Multi-query Serper (site:tiktok, site:instagram, general, KB keywords) + YouTube.

    Strategy:
      Q1  site:tiktok.com  <city> du lich 2026     -> real TikTok posts Google indexed
      Q2  site:instagram.com <city> checkin 2026   -> real IG posts
      Q3  <city> dia diem hot viral 2026 gioi tre  -> broad trending
      Q4  <kb_keywords> <city>                     -> KB-specific spots (if available)
    Deduplicates by URL and tags each result with source TK/IG/YT/TH/FB/WEB.
    """
    results = []
    seen_urls = set()

    serper_key = os.getenv('SERPER_API_KEY')
    if serper_key:
        # Pull trending_keywords from the city knowledge base when available
        kb_keywords = []
        if kb and isinstance(kb, dict):
            kb_keywords = kb.get('metadata', {}).get('trending_keywords', [])

        # Targeted platform-specific + experience-focused queries
        queries = [
            f'site:tiktok.com {city} du lich 2026 trai nghiem',
            f'site:tiktok.com {city} check in hot viral 2026',
            f'site:instagram.com {city} checkin travel 2026',
            f'{city} dia diem hot viral 2026 gioi tre trai nghiem',
            f'{city} hoat dong trai nghiem moi nhat 2026 must try',
        ]
        # Add KB-specific keyword queries for each keyword individually
        if kb_keywords:
            for kw in kb_keywords[:4]:
                queries.append(f'site:tiktok.com {kw} {city}')
            q_extra = ' '.join(kb_keywords[:3])
            queries.append(f'{q_extra} {city} review trai nghiem')

        for q in queries:
            try:
                url = 'https://google.serper.dev/search'
                headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
                payload = {'q': q, 'gl': 'vn', 'hl': 'vi', 'num': 4}
                r = _requests.post(url, headers=headers, json=payload, timeout=5)
                if r.ok:
                    for x in r.json().get('organic', [])[:4]:
                        link = x.get('link', '')
                        if not link or link in seen_urls:
                            continue
                        seen_urls.add(link)
                        if 'tiktok.com' in link:
                            src = 'TK'
                        elif 'instagram.com' in link:
                            src = 'IG'
                        elif 'youtube.com' in link or 'youtu.be' in link:
                            src = 'YT'
                        elif 'threads.net' in link:
                            src = 'TH'
                        elif 'facebook.com' in link:
                            src = 'FB'
                        else:
                            src = 'WEB'
                        results.append({'name': x.get('title', ''), 'url': link, 'source': src})
            except Exception as e:
                logging.warning(f'Serper query failed: {e}')

    # YouTube via dedicated API key (separate quota from Serper)
    yt_key = os.getenv('YOUTUBE_API_KEY')
    if yt_key:
        try:
            url = 'https://www.googleapis.com/youtube/v3/search'
            params = {'part': 'snippet', 'q': f'{city} du lich trai nghiem 2026 review', 'type': 'video',
                      'maxResults': 5, 'relevanceLanguage': 'vi', 'regionCode': 'VN',
                      'order': 'date', 'publishedAfter': '2026-01-01T00:00:00Z', 'key': yt_key}
            r = _requests.get(url, params=params, timeout=5)
            if r.ok:
                for item in r.json().get('items', []):
                    vid_id = item['id'].get('videoId', '')
                    yt_url = f'https://youtube.com/watch?v={vid_id}'
                    if yt_url not in seen_urls:
                        seen_urls.add(yt_url)
                        title = item['snippet'].get('title', '')[:70]
                        results.append({'name': title, 'url': yt_url, 'source': 'YT'})
        except Exception as e:
            logging.warning(f'YouTube API failed: {e}')

    return results


def foursquare_live(city):
    """Fetch live venues from Foursquare. Returns list of dicts."""
    api_key = os.getenv('FOURSQUARE_API_KEY')
    if not api_key:
        return []
    try:
        url = 'https://api.foursquare.com/v3/places/search'
        headers = {'Authorization': api_key}
        params = {'query': city, 'categories': '13000', 'limit': 5, 'sort': 'POPULARITY'}
        r = _requests.get(url, headers=headers, params=params, timeout=5)
        if r.ok:
            results = r.json().get('results', [])
            return [
                {
                    'name': v['name'],
                    'rating': v.get('rating', 0),
                    'address': v.get('location', {}).get('formatted_address', ''),
                    'maps_url': f"https://maps.google.com/?q={v.get('geocodes',{}).get('main',{}).get('latitude','')},{v.get('geocodes',{}).get('main',{}).get('longitude','')}"
                }
                for v in results
            ]
    except Exception as e:
        logging.warning(f'Foursquare API failed: {e}')
    return []


# ---------------------------------------------------------------------------
# Budget calculation
# ---------------------------------------------------------------------------

def calc_budget(budget_tier, duration, custom_amount=None):
    """Return budget breakdown dict."""
    rates = {
        'budget': {'accommodation': 300000, 'food': 200000, 'transport': 100000, 'activities': 150000},
        'mid':    {'accommodation': 600000, 'food': 350000, 'transport': 150000, 'activities': 300000},
        'luxury': {'accommodation': 1500000, 'food': 600000, 'transport': 300000, 'activities': 500000},
    }
    if budget_tier == 'custom' and custom_amount:
        mid = rates['mid']
        total_mid_daily = sum(mid.values())
        factor = (custom_amount / duration) / total_mid_daily
        rate = {k: int(v * factor) for k, v in mid.items()}
    else:
        rate = rates.get(budget_tier, rates['mid'])
    per_day = sum(rate.values())
    total = per_day * duration
    return {
        'tier': budget_tier,
        'per_day': per_day,
        'total_per_person': custom_amount if (budget_tier == 'custom' and custom_amount) else total,
        'breakdown': {k: v * duration for k, v in rate.items()},
        'custom_amount': custom_amount,
    }


# ---------------------------------------------------------------------------
# Itinerary building
# ---------------------------------------------------------------------------

def build_slot(spots, primary_idx):
    """Return primary spot + alternatives list (max 3 alts)."""
    if not spots:
        return None
    n = len(spots)
    primary = dict(spots[primary_idx % n])
    alts = []
    seen = {primary['name']}
    for i in range(1, n):
        candidate = spots[(primary_idx + i) % n]
        if candidate['name'] not in seen:
            seen.add(candidate['name'])
            alts.append(dict(candidate))
            if len(alts) >= 3:
                break
    primary['alternatives'] = alts
    return primary


def get_day_title(day_num, total_days, city):
    if day_num == 1:
        return f'Ngày 1: Đến {city} & Check-in'
    if day_num == total_days:
        return f'Ngày {day_num}: Tạm Biệt & Check-out'
    titles = {2: 'Ngày 2: Khám Phá Chính', 3: 'Ngày 3: Ăn Uống & Mua Sắm', 4: 'Ngày 4: Trải Nghiệm Địa Phương'}
    return titles.get(day_num, f'Ngày {day_num}: Tiếp Tục Khám Phá')


def _generic_slot(time_of_day, city, day_num):
    """Fallback slot when no static or AI data available. Day-unique names to avoid dedup."""
    _day_themes = [
        ('trung tâm', 'khu phố chính'),
        ('ngoại ô', 'vùng lân cận'),
        ('khu vực mới', 'điểm mới'),
        ('phía bắc', 'khu vực khác'),
    ]
    theme, area = _day_themes[(day_num - 1) % len(_day_themes)]
    templates = {
        'morning':   {'name': f'Khám phá buổi sáng {theme} {city}',   'desc': f'Dạo quanh {theme}, thưởng thức đặc sản sáng địa phương', 'price': '30-80k'},
        'afternoon': {'name': f'Tham quan {area} nổi tiếng {city}',   'desc': f'Điểm check-in đặc trưng {area}, chụp ảnh lưu niệm',      'price': 'Free-100k'},
        'evening':   {'name': f'Cà phê hoàng hôn {theme} {city}',     'desc': f'Quán cà phê view đẹp nhất {theme}',                       'price': '40-80k'},
        'night':     {'name': f'Ăn tối & đặc sản {theme} {city}',     'desc': f'Thưởng thức đặc sản địa phương tại {theme}',              'price': '80-200k'},
    }
    return templates.get(time_of_day, {'name': f'Trải nghiệm {area} {city}', 'desc': 'Khám phá theo sở thích', 'price': 'Tuỳ'})


def _call_greennode(messages, max_tokens=500, temperature=0.7):
    """Call GreenNode AI Platform (OpenAI-compatible) with DeepSeek or configured model."""
    api_key = os.getenv('LLM_API_KEY')
    if not api_key:
        return None
    model = os.getenv('LLM_MODEL', 'deepseek/deepseek-v4-pro')
    url = os.getenv('LLM_BASE_URL', 'https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1') + '/chat/completions'
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {'model': model, 'messages': messages, 'max_tokens': max_tokens, 'temperature': temperature}
    try:
        r = _requests.post(url, headers=headers, json=payload, timeout=15)
        if r.ok:
            return r.json()['choices'][0]['message']['content'].strip()
        else:
            logging.warning(f'GreenNode API error {r.status_code}: {r.text[:200]}')
    except Exception as e:
        logging.warning(f'GreenNode API failed: {e}')
    return None


def _get_province_context(city):
    """Return province context string for sub-destinations."""
    _PROVINCE_MAP = {
        'Vinh Hy': 'Ninh Thuận', 'Ninh Chu': 'Ninh Thuận', 'Phu Quy': 'Bình Thuận',
        'Cu Lao Cham': 'Quảng Nam', 'Ba Na Hills': 'Đà Nẵng', 'Tam Dao': 'Vĩnh Phúc',
        'Mui Ne': 'Bình Thuận', 'Ly Son': 'Quảng Ngãi', 'Co To': 'Quảng Ninh',
        'Quan Lan': 'Quảng Ninh', 'Cat Ba': 'Hải Phòng', 'Phong Nha': 'Quảng Bình',
        'Trang An': 'Ninh Bình', 'Mai Chau': 'Hoà Bình', 'Mu Cang Chai': 'Yên Bái',
        'Ta Xua': 'Yên Bái / Sơn La', 'Mang Den': 'Kon Tum', 'Ta Dung': 'Đắk Nông',
        'Bac Ha': 'Lào Cai', 'Dong Van': 'Hà Giang', 'Ho Tram': 'Bà Rịa - Vũng Tàu',
        'Sam Son': 'Thanh Hoá', 'Cua Lo': 'Nghệ An', 'Ky Co Eo Gio': 'Bình Định',
        'Binh Ba': 'Khánh Hoà', 'Diep Son': 'Khánh Hoà', 'Nam Du': 'Kiên Giang',
        'Hon Son': 'Kiên Giang', 'Hon Thom': 'Kiên Giang / Phú Quốc',
        'Pu Luong': 'Thanh Hoá', 'Binh Hung': 'Khánh Hoà', 'Binh Lieu': 'Quảng Ninh',
        'Y Ty': 'Lào Cai', 'Hoang Su Phi': 'Hà Giang', 'Cu Lao Xanh': 'Bình Định',
        'Hai Tac': 'Kiên Giang', 'Bach Ma': 'Thừa Thiên Huế', 'Cuc Phuong': 'Ninh Bình',
        'Hang Mua': 'Ninh Bình', 'Moc Chau': 'Sơn La', 'Lac Duong': 'Lâm Đồng',
        'Quy Nhon': 'Bình Định', 'Buon Ma Thuot': 'Đắk Lắk', 'Ha Long': 'Quảng Ninh',
    }
    province = _PROVINCE_MAP.get(city, '')
    if province:
        return f' (thuộc tỉnh {province})'
    return ''


def _generate_spots_via_ai(city, styles=None):
    """Generate spots using GreenNode DeepSeek -> Gemini fallback."""
    style_hint = ', '.join(styles) if styles else 'mixed'
    province_ctx = _get_province_context(city)
    city_vi = city.replace('_', ' ')
    prompt = (
        f'Bạn là chuyên gia du lịch Việt Nam. Hãy tạo lịch trình du lịch CHI TIẾT cho {city_vi}{province_ctx}.\n'
        f'Phong cách: {style_hint}.\n\n'
        'YÊU CẦU QUAN TRỌNG:\n'
        f'- Chỉ liệt kê địa điểm THỰC SỰ CÓ THẬT tại {city_vi}, dùng đúng tên quán/địa điểm CỤ THỂ\n'
        '- Mỗi địa điểm phải có tên thật, mô tả ngắn, giá tham khảo\n'
        '- Ưu tiên địa điểm đang HOT trên TikTok/Instagram 2026, trải nghiệm Gen Z thích\n'
        '- Bao gồm: quán cafe view đẹp, quán ăn local nổi tiếng, điểm check-in, hoạt động trải nghiệm\n'
        '- KHÔNG dùng tên chung chung như "quán cafe đẹp" — phải có TÊN CỤ THỂ\n\n'
        'Trả về ONLY valid JSON (không markdown, không giải thích):\n'
        '{"trending":[{"name":"tên cụ thể","type":"experience/cafe/nature/food/nightlife","tiktok":true,"why_hot":"lý do viral"}],'
        '"morning":[{"name":"tên quán/điểm","desc":"mô tả + địa chỉ","price":"giá VND"}],'
        '"afternoon":[{"name":"...","desc":"...","price":"..."}],'
        '"evening":[{"name":"...","desc":"...","price":"..."}],'
        '"night":[{"name":"...","desc":"...","price":"..."}],'
        '"hidden_gems":[{"name":"...","desc":"..."}]}'
        '\nCung cấp 5-6 trending items và 4-5 items mỗi khung giờ. Viết bằng tiếng Việt.'
    )

    def _parse_ai_json(text):
        """Parse and validate AI-generated JSON, ensuring all slots have valid data."""
        text = re.sub(r'^```(?:json)?\n?', '', text.strip())
        text = re.sub(r'\n?```$', '', text)
        data = json.loads(text)
        if not isinstance(data, dict):
            return {}
        # Validate: ensure time slots are lists of dicts with 'name'
        for slot_key in ['morning', 'afternoon', 'evening', 'night', 'trending', 'hidden_gems']:
            items = data.get(slot_key)
            if not isinstance(items, list):
                data[slot_key] = []
                continue
            valid = []
            for item in items:
                if isinstance(item, dict) and item.get('name'):
                    if 'desc' not in item:
                        item['desc'] = ''
                    if 'price' not in item:
                        item['price'] = ''
                    valid.append(item)
            data[slot_key] = valid
        return data

    # Try GreenNode (DeepSeek) first
    text = _call_greennode([{'role': 'user', 'content': prompt}], max_tokens=2000)
    if text:
        try:
            return _parse_ai_json(text)
        except Exception as e:
            logging.warning(f'GreenNode spots JSON parse failed: {e}')

    # Fallback to Gemini
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return {}
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
    payload = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
               'generationConfig': {'maxOutputTokens': 2000, 'temperature': 0.7}}
    try:
        r = _requests.post(url, json=payload, timeout=12)
        if r.ok:
            text = r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return _parse_ai_json(text)
    except Exception as e:
        logging.warning(f'Gemini spots generation failed: {e}')
    return {}


def _safe_slot(spots, idx, slot_key, city, day_num):
    """Build a slot safely — always returns a valid dict with 'name'."""
    if spots:
        try:
            result = build_slot(spots, idx)
            if result and result.get('name'):
                return result
        except Exception as e:
            logging.warning(f'build_slot failed for {slot_key} day {day_num}: {e}')
    return {**_generic_slot(slot_key, city, day_num), 'alternatives': []}


def build_generic_result(city, duration, duration_label, companions, budget_tier, styles, custom_budget, budget):
    """Build itinerary for cities without knowledge base — uses AI + fallback_spots + generic."""
    ai_spots = _generate_spots_via_ai(city, styles)
    # Merge with fallback_spots.json if AI returned empty/partial data
    fb = _FALLBACK_SPOTS.get(city, {})
    ms = ai_spots.get('morning', []) or fb.get('morning', [])
    af = ai_spots.get('afternoon', []) or fb.get('afternoon', [])
    ev = ai_spots.get('evening', []) or fb.get('evening', [])
    ni = ai_spots.get('night', []) or fb.get('night', [])
    days = []
    for day_num in range(1, duration + 1):
        idx = day_num - 1
        days.append({
            'day': day_num,
            'title': get_day_title(day_num, duration, city),
            'morning':   _safe_slot(ms, idx, 'morning',   city, day_num),
            'afternoon': _safe_slot(af, idx, 'afternoon', city, day_num),
            'evening':   _safe_slot(ev, idx, 'evening',   city, day_num),
            'night':     _safe_slot(ni, idx, 'night',     city, day_num),
        })
    return {
        'city': city, 'duration': duration_label, 'companions': companions, 'styles': styles,
        'trending': ai_spots.get('trending', []) or fb.get('trending', []),
        'live_trending': [],
        'days': days, 'budget': budget,
        'tips': ai_spots.get('hidden_gems', []),
    }


def build_result(city, companions, duration_label, duration, budget_tier, styles, custom_budget=None):
    """Build full itinerary result as a dict."""
    data = load_city_data(city)
    budget = calc_budget(budget_tier, duration, custom_budget)

    live_trending = fetch_unified_trending(city, kb=data)
    fsq_venues = foursquare_live(city)
    if fsq_venues:
        for v in fsq_venues[:3]:
            live_trending.insert(0, {'name': v['name'], 'url': v.get('maps_url', ''), 'source': 'FSQ'})

    # Pinned trending items per city (always show first)
    _PINNED = {
        'Da Lat': [
            {'name': 'Tắm onsen nước nóng Đà Lạt', 'url': 'https://www.tiktok.com/@julepe.sheen/video/7536187016325762312', 'source': 'TK'},
            {'name': 'Check in Tháp Vinaphone Đà Lạt', 'url': 'https://www.tiktok.com/@thaoleader/video/7631247439030209813', 'source': 'TK'},
        ],
    }
    pinned = _PINNED.get(city, [])
    if pinned:
        live_trending = pinned + [x for x in live_trending if x.get('url') not in {p['url'] for p in pinned}]

    if not data:
        result = build_generic_result(city, duration, duration_label, companions, budget_tier, styles, custom_budget, budget)
        result['live_trending'] = live_trending
        return result

    fmt = data.get('_format', 'legacy')

    # Rich knowledge base format
    if fmt == 'rich':
        days = _kb_to_days(data, duration)
        trending = _kb_to_trending(data)
        tips = _kb_to_tips(data)
        return {
            'city': city, 'duration': duration_label, 'companions': companions, 'styles': styles,
            'trending': trending, 'live_trending': live_trending,
            'days': days, 'budget': budget, 'tips': tips,
        }

    # Legacy genz_spots.json format
    morning_spots   = data.get('morning', [])
    afternoon_spots = data.get('afternoon', [])
    evening_spots   = data.get('evening', [])
    night_spots     = data.get('night', [])
    days = []
    for day_num in range(1, duration + 1):
        idx = day_num - 1
        days.append({
            'day': day_num,
            'title': get_day_title(day_num, duration, city),
            'morning':   _safe_slot(morning_spots,   idx, 'morning',   city, day_num),
            'afternoon': _safe_slot(afternoon_spots, idx, 'afternoon', city, day_num),
            'evening':   _safe_slot(evening_spots,   idx, 'evening',   city, day_num),
            'night':     _safe_slot(night_spots,     idx, 'night',     city, day_num),
        })
    return {
        'city': city, 'duration': duration_label, 'companions': companions, 'styles': styles,
        'trending': data.get('trending', [])[:6], 'live_trending': live_trending,
        'days': days, 'budget': budget, 'tips': data.get('hidden_gems', []),
    }


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

def travel_agent(user_input, state):
    """Main travel agent state machine. Returns reply string (or JSON for itinerary)."""
    user_input = user_input.strip()
    stage = state.get('stage', 'start')

    # start
    if stage == 'start':
        city = detect_city(user_input)
        if city:
            state['city'] = city
            state['stage'] = 'companions'
            province_ctx = _get_province_context(city)
            return (
                f'Xin chào! Chúng ta sẽ khám phá {city}{province_ctx} nhé! 🌟\n\n'
                'Bạn đi cùng ai?\n'
                '1. Solo 🧍\n'
                '2. Cặp đôi 💑\n'
                '3. Nhóm bạn 👫\n'
                '4. Gia đình 👨‍👩‍👧‍👦'
            )
        return 'Xin chào! Tôi là Trip Buddy 🗺️\nBạn muốn đi đâu? (VD: Đà Lạt, Hà Giang, Vũng Tàu, Vĩnh Hy, Phú Quý...)'

    # companions
    elif stage == 'companions':
        companions = detect_companions(user_input)
        if companions:
            state['companions'] = companions
            state['stage'] = 'duration'
            return 'Tuyệt vời! Đi mấy ngày?\n1. 2N1Đ\n2. 3N2Đ\n3. 4N3Đ\n4. 1 tuần\n5. Khác (nhập số ngày)'
        return 'Vui lòng chọn:\n1. Solo\n2. Cặp đôi\n3. Nhóm bạn\n4. Gia đình'

    # duration
    elif stage == 'duration':
        normalized = _strip_accents(user_input.lower())
        if re.search(r'^5$', user_input.strip()) or 'khac' in normalized:
            state['stage'] = 'duration_custom'
            return 'Bạn muốn đi bao nhiêu ngày? (Nhập số, VD: 5)'
        result = detect_duration(user_input)
        if result:
            state['duration'], state['duration_label'] = result
            state['stage'] = 'budget'
            return 'Ngân sách mỗi người?\n1. Tiết kiệm (<1 triệu/ngày)\n2. Tầm trung (1-2 triệu/ngày)\n3. Luxury (>2 triệu/ngày)\n4. Khác (nhập số tiền)'
        return 'Vui lòng chọn 1-5 hoặc nhập số ngày (2-30)'

    # duration_custom
    elif stage == 'duration_custom':
        m = re.search(r'\d+', user_input)
        if m:
            n = int(m.group())
            if 1 <= n <= 30:
                state['duration'] = n
                state['duration_label'] = f'{n}N{n-1}Đ'
                state['stage'] = 'budget'
                return 'Ngân sách mỗi người?\n1. Tiết kiệm (<1 triệu/ngày)\n2. Tầm trung (1-2 triệu/ngày)\n3. Luxury (>2 triệu/ngày)\n4. Khác (nhập số tiền)'
        return 'Vui lòng nhập số ngày (1-30), VD: 5'

    # budget
    elif stage == 'budget':
        normalized = _strip_accents(user_input.lower())
        if user_input.strip() == '4' or 'khac' in normalized:
            state['stage'] = 'budget_custom'
            return 'Ngân sách tổng mỗi người cho cả chuyến?\n(VD: 3 triệu, 5tr, 4500000)'
        budget = detect_budget(user_input)
        if budget:
            state['budget'] = budget
            state['stage'] = 'style'
            return ('Phong cách du lịch? (Có thể chọn nhiều, VD: 1 3)\n'
                    '1. Sống Ảo 📸\n2. Khám Phá 🏔️\n3. Thư Giãn 🧘\n4. Ẩm Thực 🍜\n5. Văn Hóa 🏛️')
        return 'Vui lòng chọn 1-4'

    # budget_custom
    elif stage == 'budget_custom':
        amount = detect_custom_budget(user_input)
        if amount:
            state['budget'] = 'custom'
            state['custom_budget'] = amount
            state['stage'] = 'style'
            return (f'Đã ghi nhận: {amount:,}đ/người\n'
                    'Phong cách du lịch?\n1. Sống Ảo 📸\n2. Khám Phá 🏔️\n3. Thư Giãn 🧘\n4. Ẩm Thực 🍜\n5. Văn Hóa 🏛️')
        return 'Không hiểu số tiền. VD: 3 triệu, 5tr, 4500000'

    # style -> build result
    elif stage == 'style':
        styles = detect_style(user_input)
        if styles:
            state['styles'] = styles
            city = state.get('city', 'Da Lat')
            itinerary = build_result(
                city=city,
                companions=state.get('companions', 'friends'),
                duration_label=state.get('duration_label', '3N2Đ'),
                duration=state.get('duration', 3),
                budget_tier=state.get('budget', 'mid'),
                styles=styles,
                custom_budget=state.get('custom_budget'),
            )
            state['stage'] = 'post_result'
            state['last_result'] = itinerary
            return json.dumps(itinerary, ensure_ascii=False)
        return 'Vui lòng chọn phong cách (1-5), có thể chọn nhiều: VD ‘1 3’'

    # post_result / done
    elif stage in ('post_result', 'done'):
        normalized = _strip_accents(user_input.lower())
        if any(kw in normalized for kw in ['reset', 'moi', 'chuyen khac', 'bat dau lai', 'di dau khac']):
            state.clear()
            state['stage'] = 'start'
            return 'Ok! Bạn muốn đi đâu tiếp theo? 🗺️'
        city = state.get('city', '')
        last_result = state.get('last_result')
        return call_ai_qa(user_input, city, last_result)

    return 'Xin lỗi, tôi không hiểu. Thử lại nhé?'


# ---------------------------------------------------------------------------
# AI Q&A Layer — Gemini -> Claude -> Keyword Fallback
# ---------------------------------------------------------------------------

def call_ai_qa(question, city, last_result=None):
    """Route follow-up questions through AI APIs: GreenNode -> Gemini -> Claude -> keyword fallback."""
    context_lines = [f'Người dùng đang lên kế hoạch du lịch đến {city}.']
    if last_result and isinstance(last_result, dict):
        dur = last_result.get('duration', '')
        comp = last_result.get('companions', '')
        budget = last_result.get('budget', {})
        total = budget.get('total_per_person', 0)
        context_lines.append(f'Chuyến đi: {dur}, {comp}, ngân sách ~{total:,}đ/người.')
    context = ' '.join(context_lines)

    # Try GreenNode (DeepSeek) first
    system_msg = (
        f'Bạn là Trip Buddy, trợ lý du lịch AI thân thiện cho người Việt.\n{context}\n'
        'Hãy trả lời ngắn gọn, hữu ích bằng tiếng Việt. '
        'Nếu hỏi giá cả, cho số cụ thể. Dùng emoji cho sinh động. Tối đa 150 từ.'
    )
    reply = _call_greennode([
        {'role': 'system', 'content': system_msg},
        {'role': 'user', 'content': question},
    ], max_tokens=400)
    if reply:
        return reply

    reply = _call_gemini(question, city, context)
    if reply:
        return reply
    reply = _call_claude(question, city, context)
    if reply:
        return reply
    return _keyword_fallback(question, city, last_result)


def _call_gemini(question, city, context):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
    system_prompt = (
        f'Bạn là Trip Buddy, trợ lý du lịch AI thân thiện cho người Việt.\n{context}\n'
        'Hãy trả lời ngắn gọn, hữu ích bằng tiếng Việt. '
        'Nếu hỏi giá cả, cho số cụ thể. Dùng emoji cho sinh động. Tối đa 150 từ.'
    )
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': f'{system_prompt}\n\nCâu hỏi: {question}'}]}],
        'generationConfig': {'maxOutputTokens': 400, 'temperature': 0.7},
    }
    try:
        r = _requests.post(url, json=payload, timeout=10)
        if r.ok:
            candidates = r.json().get('candidates', [])
            if candidates:
                return candidates[0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        logging.warning(f'Gemini Q&A failed: {e}')
    return None


def _call_claude(question, city, context):
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return None
    url = 'https://api.anthropic.com/v1/messages'
    headers = {'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
    payload = {
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': 400,
        'system': f'Bạn là Trip Buddy, trợ lý du lịch AI cho người Việt. {context} Trả lời ngắn gọn, hữu ích bằng tiếng Việt, tối đa 150 từ.',
        'messages': [{'role': 'user', 'content': question}],
    }
    try:
        r = _requests.post(url, headers=headers, json=payload, timeout=10)
        if r.ok:
            return r.json()['content'][0]['text'].strip()
    except Exception as e:
        logging.warning(f'Claude Q&A failed: {e}')
    return None


def _keyword_fallback(question, city, result=None):
    """Smart rule-based answers when no AI key is configured."""
    q = _strip_accents(question.lower())

    if any(k in q for k in ['bao nhieu tien', 'chi phi', 'gia ca', 'budget', 'tong tien', 'het bao nhieu']):
        if result and isinstance(result, dict) and result.get('budget'):
            b = result['budget']
            total = b.get('total_per_person', 0)
            per_day = b.get('per_day', 0)
            bd = b.get('breakdown', {})
            lines = [f'Dự tính chi phí {city}/người:']
            labels = {'accommodation': 'Lưu trú', 'food': 'Ăn uống', 'transport': 'Di chuyển', 'activities': 'Vui chơi'}
            for k, v in bd.items():
                if v:
                    lines.append(f'  {labels.get(k, k)}: ~{v:,}đ')
            lines.append(f'  Tổng: ~{total:,}đ/người (~{per_day:,}đ/ngày)')
            return '\n'.join(lines)
        return (f'Chi phí đi {city} phụ thuộc thời gian và phong cách:\n'
                '- Tiết kiệm: ~600k-900k/ngày/người\n- Tầm trung: ~1.2-1.8tr/ngày/người\n- Luxury: ~3tr+/ngày/người')

    if any(k in q for k in ['thoi tiet', 'khi hau', 'mua', 'lanh', 'nong', 'mang gi']):
        weather = {
            'Da Lat': 'Đà Lạt mát quanh năm 15-25°C. Mùa mưa tháng 5-10, mùa khô đẹp nhất tháng 12-4. Nhớ mang áo khoác!',
            'Hoi An': 'Hội An đẹp nhất tháng 2-4 (khô, ấm). Tránh tháng 10-11 (lũ). Mang áo nhẹ + kem chống nắng.',
            'Da Nang': 'Đà Nẵng lý tưởng tháng 5-8 (khô, đẹp). Tránh tháng 9-11 (bão).',
            'Ha Noi': 'Hà Nội đẹp nhất tháng 10-11 (mát, khô) và tháng 3-4.',
            'Phu Quoc': 'Phú Quốc đẹp tháng 11-4 (mùa khô, biển lặng).',
            'Ha Giang': 'Hà Giang đẹp nhất tháng 10-11 (lúa chín, tam giác mạch) và tháng 3-4 (hoa đào).',
            'Ninh Binh': 'Ninh Bình đẹp quanh năm. Đẹp nhất tháng 4-5 (lúa xanh) và tháng 9-10 (lúa vàng).',
            'Sa Pa': 'Sa Pa lạnh quanh năm 10-20°C. Đẹp nhất tháng 9-10 (lúa chín) và tháng 3-4 (hoa đào).',
            'Mui Ne': 'Mũi Né đẹp tháng 11-4 (mùa khô, lành gió). Tránh tháng 5-10 (mưa nhiều).',
            'Can Tho': 'Cần Thơ đẹp quanh năm. Sáng sớm là thời gian tốt nhất để đi chợ nổi Cái Răng.',
        }
        return weather.get(city, f'{city}: Nên check dự báo thời tiết trước 1-2 ngày. Mang áo khoác phòng và kem chống nắng!')


    if any(k in q for k in ['an gi', 'mon an', 'dac san', 'quan an', 'am thuc', 'ngon', 'an uong']):
        food = {
            'Da Lat': 'Đặc sản Đà Lạt: Bánh tráng nướng, sữa đậu nành nóng, nem nướng chợ đêm, dâu tây chấm sữa.',
            'Da Nang': 'Đà Nẵng: Bánh tráng cuộn thịt heo, Mì Quảng, Bún chả cá, Hải sản tươi.',
            'Ha Noi': 'Hà Nội: Bún chả, Phở Thìn, Bánh cuốn, Cà phê trứng, Bún đậu mắm tôm.',
            'TP HCM': 'Sài Gòn: Hủ tiếu Nam Vang, Cơm tấm, Bánh mì, Gỏi cuốn, Phở.',
        }
        food_reply = food.get(city, '')
        if food_reply:
            reply = food_reply
        else:
            reply = f'Để tìm món ngon tại {city}, bạn search TikTok hoặc Google Maps nhé! 🍜'
    else:
        return None
    return reply

