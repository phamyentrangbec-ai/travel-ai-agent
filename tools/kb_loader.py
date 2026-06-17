"""
kb_loader.py — Load rich knowledge base JSONs and convert to API format.

Rich format: data/knowledge_bases/{city_slug}.json
  → metadata, itinerary (day_1/day_2/day_3), places_directory

Output: dict compatible with build_result() API response structure
"""
import json
import os
import re
import unicodedata

_KB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'knowledge_bases')

# City name → filename slug mapping
_CITY_SLUG_MAP = {
    'Da Lat':       'da_lat',
    'Hoi An':       'hoi_an',
    'Da Nang':      'da_nang',
    'Ha Noi':       'ha_noi',
    'TP HCM':       'tp_hcm',
    'Nha Trang':    'nha_trang',
    'Phu Quoc':     'phu_quoc',
    'Hue':          'hue',
    'Ha Long':      'ha_long',
    'Sa Pa':        'sa_pa',
    'Ninh Binh':    'ninh_binh',
    'Vung Tau':     'vung_tau',
    'Ha Giang':     'ha_giang',
    'Mui Ne':       'mui_ne',
    'Binh Thuan':   'mui_ne',   # alias
    'Can Tho':      'can_tho',
}


def _strip_accents(text):
    text = text.replace('đ', 'd').replace('Đ', 'D')
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def get_slug(city_name):
    """Return file slug for a city name, or None if not found."""
    if city_name in _CITY_SLUG_MAP:
        return _CITY_SLUG_MAP[city_name]
    norm = _strip_accents(city_name.lower().replace(' ', '_'))
    for canonical, slug in _CITY_SLUG_MAP.items():
        if _strip_accents(canonical.lower().replace(' ', '_')) == norm:
            return slug
    return None


def load_kb(city_name):
    """Load raw knowledge base JSON for a city. Returns dict or None."""
    slug = get_slug(city_name)
    if not slug:
        return None
    path = os.path.join(_KB_DIR, f'{slug}.json')
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _extract_slot(items, time_of_day):
    """
    Extract a primary + alternatives slot dict from a list of itinerary items.
    Returns: {name, desc, address, price, alternatives: [{name, address, price}]}
    """
    if not items:
        return None

    primary_item = items[0]

    # Handle item that has "options" or "places" sub-list
    if 'options' in primary_item:
        opts = primary_item['options']
        if opts:
            primary_item = dict(primary_item)
            primary_item.update(opts[0])
            primary_item['_extra_alts'] = opts[1:]
    elif 'places' in primary_item:
        places = primary_item['places']
        if places:
            primary_item = dict(primary_item)
            primary_item.update(places[0])
            primary_item['_extra_alts'] = places[1:]
    elif 'cafe_options' in primary_item:
        opts = primary_item.get('cafe_options', [])
        if opts:
            primary_item = dict(primary_item)
            primary_item.update(opts[0])
            primary_item['_extra_alts'] = opts[1:]

    name = (primary_item.get('name') or primary_item.get('activity') or '').strip()
    address = primary_item.get('address', '')
    desc = primary_item.get('note') or primary_item.get('tip') or ''
    price = primary_item.get('price', '')

    # Build alternatives from:
    # 1. explicit 'alternatives' key on primary item
    # 2. _extra_alts (from options/places)
    # 3. remaining items in the slot
    alts_raw = list(primary_item.get('alternatives', []))
    alts_raw += primary_item.get('_extra_alts', [])
    for extra in items[1:]:
        if isinstance(extra, dict):
            extra_name = extra.get('name') or extra.get('activity', '')
            if extra_name and extra_name != name:
                alts_raw.append(extra)

    seen = {name}
    alternatives = []
    for a in alts_raw:
        aname = (a.get('name') or '').strip()
        if aname and aname not in seen:
            seen.add(aname)
            alternatives.append({
                'name': aname,
                'address': a.get('address', ''),
                'desc': a.get('note', ''),
                'price': a.get('price', ''),
            })
        if len(alternatives) >= 3:
            break

    return {
        'name': name,
        'address': address,
        'desc': desc,
        'price': price,
        'alternatives': alternatives,
    }


def _pick_day_spots(day_data):
    """Convert a day dict {morning:[...], afternoon:[...], evening:[...]} to slot format."""
    morning_items   = day_data.get('morning', [])
    afternoon_items = day_data.get('afternoon', [])
    evening_items   = day_data.get('evening', [])

    # Split morning into actual morning + map first food to morning, sights to afternoon if needed
    morning_food   = [x for x in morning_items if x.get('type') in ('food',) or x.get('category') in ('breakfast',)]
    morning_sights = [x for x in morning_items if x.get('type') in ('attraction', 'viewpoint', 'landmark', 'nature')]
    afternoon_food = [x for x in afternoon_items if x.get('category') in ('lunch',) or x.get('type') == 'food']
    evening_food   = [x for x in evening_items if x.get('category') in ('dinner',) or x.get('type') == 'food']
    night_items    = [x for x in evening_items if x.get('type') in ('market', 'attraction', 'bar', 'entertainment', 'neighborhood')]

    # Use full lists as fallbacks
    morning_slot   = _extract_slot(morning_food or morning_items, 'morning')
    afternoon_slot = _extract_slot(afternoon_food or afternoon_items, 'afternoon')
    evening_slot   = _extract_slot(evening_food or evening_items, 'evening')
    night_slot     = _extract_slot(night_items or evening_items[-1:] if evening_items else [], 'night')

    return morning_slot, afternoon_slot, evening_slot, night_slot


def kb_to_api_days(kb, duration):
    """
    Convert knowledge base itinerary to API days format.
    Returns list of day dicts compatible with build_result() output.
    """
    itinerary = kb.get('itinerary', {})
    day_keys = sorted(itinerary.keys())  # day_1, day_2, day_3
    days = []

    for day_num in range(1, duration + 1):
        # Cycle through available itinerary days
        key = day_keys[(day_num - 1) % len(day_keys)] if day_keys else None
        day_data = itinerary.get(key, {}) if key else {}
        title = day_data.get('title', f'Ngày {day_num}')

        morning, afternoon, evening, night = _pick_day_spots(day_data)

        days.append({
            'day': day_num,
            'title': title,
            'morning':   morning,
            'afternoon': afternoon,
            'evening':   evening,
            'night':     night,
        })

    return days


def kb_to_trending(kb, limit=6):
    """Extract trending spots from knowledge base attractions."""
    places_dir = kb.get('places_directory', {})
    attractions = places_dir.get('attractions', {}).get('places', [])
    trending = []
    for a in attractions[:limit]:
        trending.append({
            'name': a.get('name', ''),
            'type': a.get('type', 'attraction'),
            'vibe': a.get('note', ''),
            'tiktok': True,  # mark as trending
        })
    return trending


def kb_to_hidden_gems(kb, limit=5):
    """Extract hidden gem tips from knowledge base."""
    places_dir = kb.get('places_directory', {})
    # Look for snack/specialty/unique items
    food = places_dir.get('food', {})
    snacks = food.get('snack', {}).get('places', [])
    specialty = food.get('specialty', {}).get('places', [])
    gems = snacks + specialty
    result = []
    seen = set()
    for g in gems[:limit]:
        name = g.get('name', '')
        if name and name not in seen:
            seen.add(name)
            result.append({'name': name, 'desc': g.get('note', g.get('address', ''))})
    return result
