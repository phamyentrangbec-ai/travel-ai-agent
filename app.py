"""
Flask server for Trip Buddy Travel AI Agent.
"""
from flask import Flask, request, jsonify, send_from_directory
from agent_entrypoint import travel_agent
import json as json_module
import os
import random
import logging

app = Flask(__name__, static_folder='static')

# In-memory session state
session_state = {}

# ---------------------------------------------------------------------------
# Load genz_spots + fallback_spots at startup for alternative enrichment
# ---------------------------------------------------------------------------
_genz_spots = {}
try:
    _genz_spots_path = os.path.join(os.path.dirname(__file__), 'data', 'genz_spots.json')
    with open(_genz_spots_path, encoding='utf-8') as _f:
        _genz_spots = json_module.load(_f)
except Exception as e:
    logging.warning(f'Failed to load genz_spots.json: {e}')

_fallback_spots = {}
try:
    _fb_path = os.path.join(os.path.dirname(__file__), 'data', 'fallback_spots.json')
    with open(_fb_path, encoding='utf-8') as _f:
        _fallback_spots = json_module.load(_f)
except Exception as e:
    logging.warning(f'Failed to load fallback_spots.json: {e}')

# Map result['city'] values (from .pyc) to genz_spots keys
_CITY_KEY_MAP = {
    'Quang Ninh':       'Ha Long',
    'Ba Ria Vung Tau':  'Vung Tau',
    'Dak Lak':          'Buon Ma Thuot',
    'Khanh Hoa':        'Nha Trang',
    'Lam Dong':         'Da Lat',
    'Binh Thuan':       'Mui Ne',
    'Thua Thien Hue':   'Hue',
    'Quang Nam':        'Hoi An',
    'Lao Cai':          'Sa Pa',
    'Ha Giang Province':'Ha Giang',
    'Ninh Binh Province':'Ninh Binh',
    'Can Tho City':     'Can Tho',
}


# ---------------------------------------------------------------------------
# Deduplication helper
# ---------------------------------------------------------------------------

def deduplicate_itinerary(result_data):
    """Post-process: remove duplicate spot names across all days/slots.
    If main spot is a dup, promote first unused alternative.
    If no alternative available, clear the slot.
    """
    seen = set()
    for day in result_data.get('days', []):
        for slot in ['morning', 'afternoon', 'evening', 'night']:
            item = day.get(slot)
            if not item or not item.get('name'):
                continue
            name = item['name'].strip()
            if name in seen:
                alts = item.get('alternatives', [])
                promoted = False
                for alt in alts:
                    alt_name = (alt.get('name') or '').strip()
                    if alt_name and alt_name not in seen:
                        remaining_alts = [a for a in alts if a.get('name') != alt_name]
                        day[slot] = {
                            'name': alt_name,
                            'desc': alt.get('desc', ''),
                            'price': alt.get('price', ''),
                            'alternatives': remaining_alts,
                        }
                        seen.add(alt_name)
                        promoted = True
                        break
                if not promoted:
                    day[slot] = None
            else:
                seen.add(name)
    return result_data


# ---------------------------------------------------------------------------
# Alternative enrichment helper
# ---------------------------------------------------------------------------

_SLOT_FALLBACK = {
    'morning':   ['morning', 'trending'],
    'afternoon': ['afternoon', 'trending'],
    'evening':   ['evening', 'night', 'trending'],
    'night':     ['night', 'evening', 'trending'],
}

# Patterns that indicate a generic placeholder spot (from _generic_slot in agent_entrypoint)
_GENERIC_PATTERNS = [
    'Khám phá buổi sáng',
    'Tham quan',
    'Cà phê hoàng hôn',
    'Ăn tối & đặc sản',
    'Khám phá buổi chiều',
    'Khám phá buổi tối',
    'Trải nghiệm',
]

def _is_generic(name):
    return any(p in name for p in _GENERIC_PATTERNS)


# Sub-destination → parent genz_spots key (fallback when sub has no own data)
_SUB_TO_PARENT = {
    'Vinh Hy': 'Ninh Thuan', 'Ninh Chu': 'Ninh Thuan',
    'Phu Quy': 'Binh Thuan', 'Mui Ne': 'Binh Thuan',
    'Cu Lao Cham': 'Hoi An', 'Ba Na Hills': 'Da Nang',
    'Tam Dao': 'Vinh Phuc', 'Ly Son': 'Quang Ngai',
    'Co To': 'Ha Long', 'Quan Lan': 'Ha Long', 'Cat Ba': 'Ha Long',
    'Phong Nha': 'Quang Binh', 'Trang An': 'Ninh Binh', 'Hang Mua': 'Ninh Binh',
    'Mai Chau': 'Hoa Binh', 'Mu Cang Chai': 'Yen Bai', 'Ta Xua': 'Son La',
    'Mang Den': 'Kon Tum', 'Ta Dung': 'Dak Nong',
    'Bac Ha': 'Sa Pa', 'Y Ty': 'Sa Pa', 'Dong Van': 'Ha Giang',
    'Hoang Su Phi': 'Ha Giang', 'Ho Tram': 'Vung Tau',
    'Sam Son': 'Thanh Hoa', 'Cua Lo': 'Nghe An',
    'Ky Co Eo Gio': 'Quy Nhon', 'Cu Lao Xanh': 'Quy Nhon',
    'Binh Ba': 'Nha Trang', 'Diep Son': 'Nha Trang', 'Binh Hung': 'Nha Trang',
    'Nam Du': 'Phu Quoc', 'Hon Son': 'Kien Giang', 'Hon Thom': 'Phu Quoc',
    'Hai Tac': 'Kien Giang', 'Pu Luong': 'Thanh Hoa',
    'Binh Lieu': 'Ha Long', 'Bach Ma': 'Hue', 'Cuc Phuong': 'Ninh Binh',
    'Moc Chau': 'Son La', 'Lac Duong': 'Da Lat',
    'Quy Nhon': 'Binh Dinh', 'Buon Ma Thuot': 'Gia Lai',
    'Ha Long': 'Ha Long',
}


def _resolve_city_spots(raw_city):
    """Resolve spot data: fallback_spots (specific) → genz_spots (direct) → genz_spots (parent province)."""
    # 1. Try fallback_spots.json first (specific sub-destination data)
    spots = _fallback_spots.get(raw_city)
    if spots:
        return spots
    # 2. Try genz_spots direct match
    city = _CITY_KEY_MAP.get(raw_city, raw_city)
    spots = _genz_spots.get(city)
    if spots:
        return spots
    # 3. Try parent province fallback
    parent = _SUB_TO_PARENT.get(raw_city) or _SUB_TO_PARENT.get(city)
    if parent:
        spots = _genz_spots.get(parent)
        if spots:
            return spots
    return None


def _pick_spot(candidates, used):
    """Pick a random unused spot from candidates, return (spot, remaining) or (None, [])."""
    random.shuffle(candidates)
    for i, spot in enumerate(candidates):
        n = spot.get('name', '').strip()
        if n and n not in used:
            return spot, candidates[:i] + candidates[i+1:]
    return None, []


def enrich_alternatives(result_data, min_alts=2):
    """Post-process itinerary: replace generic/null slots with real spots from genz_spots.
    Falls back to parent province data for sub-destinations.
    """
    raw_city = result_data.get('city', '')
    city_spots = _resolve_city_spots(raw_city)
    if not city_spots:
        return result_data

    # Collect all non-generic names already present
    used = set()
    for day in result_data.get('days', []):
        for slot in ['morning', 'afternoon', 'evening', 'night']:
            item = day.get(slot)
            if not item:
                continue
            n = item.get('name', '').strip()
            if n and not _is_generic(n):
                used.add(n)
            for alt in item.get('alternatives', []):
                an = (alt.get('name') or '').strip()
                if an:
                    used.add(an)

    for day in result_data.get('days', []):
        for slot in ['morning', 'afternoon', 'evening', 'night']:
            item = day.get(slot)

            # === NEW: Fill NULL slots (e.g. removed by deduplicate_itinerary) ===
            if not item:
                candidates = []
                for src_key in _SLOT_FALLBACK.get(slot, [slot]):
                    for spot in city_spots.get(src_key, []):
                        n = spot.get('name', '').strip()
                        if n and n not in used:
                            candidates.append(spot)
                pick, remaining = _pick_spot(candidates, used)
                if pick:
                    pn = pick.get('name', '').strip()
                    new_item = {
                        'name': pn,
                        'desc': pick.get('desc', ''),
                        'price': pick.get('price', ''),
                        'alternatives': [],
                    }
                    used.add(pn)
                    # Add alternatives
                    for alt_spot in remaining[:min_alts]:
                        an = alt_spot.get('name', '').strip()
                        if an and an not in used:
                            new_item['alternatives'].append({
                                'name': an, 'desc': alt_spot.get('desc', ''),
                                'price': alt_spot.get('price', ''),
                            })
                            used.add(an)
                    day[slot] = new_item
                continue

            # Replace generic main spot with a real one from genz_spots
            main_name = item.get('name', '').strip()
            if _is_generic(main_name) or not main_name:
                candidates = []
                for src_key in _SLOT_FALLBACK.get(slot, [slot]):
                    for spot in city_spots.get(src_key, []):
                        n = spot.get('name', '').strip()
                        if n and n not in used:
                            candidates.append(spot)
                pick, remaining = _pick_spot(candidates, used)
                if pick:
                    pn = pick.get('name', '').strip()
                    item['name'] = pn
                    item['desc'] = pick.get('desc', '')
                    item['price'] = pick.get('price', '')
                    item['alternatives'] = []
                    used.add(pn)
                    for alt_spot in remaining[:min_alts]:
                        an = alt_spot.get('name', '').strip()
                        if an and an not in used:
                            item['alternatives'].append({
                                'name': an, 'desc': alt_spot.get('desc', ''),
                                'price': alt_spot.get('price', ''),
                            })
                            used.add(an)
                    continue

            # Not generic — just ensure min alternatives
            alts = item.get('alternatives', [])
            if len(alts) >= min_alts:
                continue
            needed = min_alts - len(alts)
            candidates = []
            for src_key in _SLOT_FALLBACK.get(slot, [slot]):
                for spot in city_spots.get(src_key, []):
                    n = spot.get('name', '').strip()
                    if n and n not in used:
                        candidates.append(spot)
            random.shuffle(candidates)
            for spot in candidates:
                if needed <= 0:
                    break
                n = spot.get('name', '').strip()
                if n in used:
                    continue
                alts.append({
                    'name': n, 'desc': spot.get('desc', ''),
                    'price': spot.get('price', ''),
                })
                used.add(n)
                needed -= 1
            item['alternatives'] = alts
    return result_data


# ---------------------------------------------------------------------------
# Chat routes
# ---------------------------------------------------------------------------

@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@app.route('/')
def index():
    static_path = os.path.join(os.path.dirname(__file__), 'static')
    if os.path.exists(os.path.join(static_path, 'index.html')):
        return send_from_directory('static', 'index.html')
    return jsonify({'status': 'Trip Buddy API is running'})


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    session_id = data.get('session_id', 'default')

    if session_id not in session_state:
        session_state[session_id] = {}

    reply = travel_agent(message, session_state[session_id])
    stage = session_state[session_id].get('stage', 'start')

    # Fallback when Gemini Q&A unavailable (post_result returns None)
    if reply is None and stage == 'post_result':
        city = session_state[session_id].get('city', 'điểm đến')
        msg_lower = message.lower()
        if any(k in msg_lower for k in ['ca phe', 'cafe', 'cà phê', 'coffee']):
            reply = f"Tại {city}, một số quán cà phê view đẹp đang hot: check thêm TikTok '{city} cafe view 2026' để xem review mới nhất nhé! ☕"
        elif any(k in msg_lower for k in ['quan an', 'quán ăn', 'food', 'quan', 'quán', 'mon', 'món', 'ngon']):
            reply = f"Để tìm quán ăn ngon tại {city}, bạn search TikTok hoặc Google Maps với từ khoá '{city} quán ăn ngon 2026' nhé! 🍜"
        elif any(k in msg_lower for k in ['khach san', 'khách sạn', 'homestay', 'hotel', 'o dau', 'ở đâu']):
            reply = f"Chỗ ở tại {city}: homestay thường được yêu thích nhất cho nhóm bạn. Tìm trên Booking.com hoặc search '{city} homestay view đẹp' nhé! 🏡"
        elif any(k in msg_lower for k in ['di chuyen', 'di chuyển', 'xe', 'bus', 'may bay', 'máy bay', 'tau', 'tàu']):
            reply = f"Di chuyển đến {city}: xe khách giường nằm (~200-350k), máy bay (~500k-1.5tr), tàu hỏa (nếu có). Đặt vé sớm 2-4 tuần để có giá tốt! 🚌"
        elif any(k in msg_lower for k in ['gia', 'giá', 'bao nhieu', 'bao nhiêu', 'chi phi', 'chi phí', 'tien', 'tiền']):
            reply = f"Chi phí trung bình tại {city} khoảng 800k-1.5tr/người/ngày. Ngân sách cao hơn nếu muốn ở khách sạn tốt! 💰"
        else:
            reply = f"Bạn muốn biết thêm gì về {city}? Mình có thể gợi ý về: cà phê check-in, quán ăn ngon, chỗ ở, di chuyển, hoặc lịch trình chi tiết! 🗺️"

    is_result = False
    result_data = None
    try:
        parsed = json_module.loads(reply)
        if isinstance(parsed, dict) and 'days' in parsed:
            is_result = True
            result_data = deduplicate_itinerary(parsed)
            result_data = enrich_alternatives(result_data, min_alts=2)
    except Exception:
        pass

    return jsonify({
        'reply': '' if is_result else reply,
        'stage': stage,
        'is_result': is_result,
        'result': result_data if is_result else None,
    })


@app.route('/reset', methods=['POST'])
def reset():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')
    session_state[session_id] = {}
    return jsonify({'status': 'ok'})


# ---------------------------------------------------------------------------
# Expense tracker helpers
# ---------------------------------------------------------------------------

def _normalize(name):
    import unicodedata
    name = name.lower().replace('\u0111', 'd').replace('\u0110', 'd')
    nfd = unicodedata.normalize('NFD', name)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def parse_amount(text):
    import re
    text = text.lower().replace(',', '.')
    m = re.search(r'(\d+\.?\d*)\s*(tri[e\u00ea]u|trieu\b|tr\b)', text)
    if m:
        return int(float(m.group(1)) * 1_000_000)
    m = re.search(r'(\d+\.?\d*)\s*(ngh[i\u00ec]n|nghin|k\b)', text)
    if m:
        return int(float(m.group(1)) * 1_000)
    m = re.search(r'(\d{4,})', text)
    if m:
        return int(m.group(1))
    # Voice often says "15" meaning 15,000 or "150" meaning 150,000
    m = re.search(r'(\d+)', text)
    if m:
        n = int(m.group(1))
        if n < 1000:
            return n * 1000  # "15" -> 15,000\u0111, "150" -> 150,000\u0111
    return 0


def parse_expense_line(text, members):
    import re
    amount = parse_amount(text)
    desc = text
    norm_text = _normalize(text)
    if not members:
        return {'description': desc, 'amount': amount, 'splits': {}, 'payer': None}

    # Check exclusions first (e.g. "Trang không ăn", "Trang không đi")
    excluded = set()
    exclude_patterns = ['khong di', 'ko di', 'k di', 'khong tham gia', 'vang mat', 'khong an', 'ko an', 'k an']
    for member in members:
        m_norm = _normalize(member)
        for pat in exclude_patterns:
            if re.search(rf'{re.escape(m_norm)}\s+{re.escape(pat)}', norm_text):
                excluded.add(member)
                break

    if any(kw in norm_text for kw in ['ca nhom', 'tat ca', 'moi nguoi', 'chung ta']):
        participants = [m for m in members if m not in excluded]
        if not participants:
            participants = members
        per_person = amount // len(participants) if participants else amount
        splits = {m: (per_person if m in participants else 0) for m in members}
        payer = None
        for member in members:
            if member not in excluded and _normalize(member) in norm_text:
                payer = member
                break
        return {'description': desc, 'amount': amount, 'splits': splits, 'payer': payer}

    mentioned = []
    for member in members:
        if member not in excluded and _normalize(member) in norm_text:
            mentioned.append(member)

    if excluded:
        participants = [m for m in members if m not in excluded]
        if not participants:
            participants = members
        per_person = amount // len(participants) if participants else amount
        splits = {m: (per_person if m in participants else 0) for m in members}
        payer = mentioned[0] if mentioned else (participants[0] if participants else None)
    elif mentioned and len(mentioned) > 0:
        per_person = amount // len(mentioned)
        splits = {m: (per_person if m in mentioned else 0) for m in members}
        payer = mentioned[0]
    else:
        per_person = amount // len(members) if members else amount
        splits = {m: per_person for m in members}
        payer = None

    return {'description': desc, 'amount': amount, 'splits': splits, 'payer': payer}


def get_summary(session):
    members = session.get('members', [])
    expenses = session.get('expenses', [])
    paid_by = {m: 0 for m in members}    # how much each person paid out of pocket
    consumed = {m: 0 for m in members}    # how much each person consumed/owes
    total_amount = 0

    for exp in expenses:
        amt = exp.get('amount', 0)
        total_amount += amt
        payer = exp.get('payer')
        if payer and payer in paid_by:
            paid_by[payer] += amt
        for m, split_amt in exp.get('splits', {}).items():
            if m in consumed:
                consumed[m] += split_amt

    # balance = paid - consumed: positive means others owe you
    balances = {m: paid_by[m] - consumed[m] for m in members}
    totals = consumed

    debtors = sorted([(m, -b) for m, b in balances.items() if b < 0], key=lambda x: -x[1])
    creditors = sorted([(m, b) for m, b in balances.items() if b > 0], key=lambda x: -x[1])
    settlements = []

    debtors = list(debtors)
    creditors = list(creditors)
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor, debt = debtors[i]
        creditor, credit = creditors[j]
        transfer = min(debt, credit)
        if transfer > 0:
            settlements.append({'from': debtor, 'to': creditor, 'amount': transfer})
        debt -= transfer
        credit -= transfer
        if debt == 0:
            i += 1
        else:
            debtors[i] = (debtor, debt)
        if credit == 0:
            j += 1
        else:
            creditors[j] = (creditor, credit)

    return {
        'total': total_amount,
        'per_member': totals,
        'average': total_amount // len(members) if members else 0,
        'balances': balances,
        'settlements': settlements,
        'expense_count': len(expenses),
    }


# ---------------------------------------------------------------------------
# Expense tracker routes
# ---------------------------------------------------------------------------

expense_sessions = {}


@app.route('/expense/members', methods=['POST'])
def set_members():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    members = data.get('members', [])
    expense_sessions[session_id] = {'members': members, 'expenses': []}
    return jsonify({'status': 'ok', 'members': members})


@app.route('/expense/add', methods=['POST'])
def add_expense():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    text = data.get('text', '')

    session = expense_sessions.get(session_id, {'members': [], 'expenses': []})
    members = session.get('members', [])

    # Try AI parsing first, fall back to regex
    parsed = _ai_parse_expense(text, members)
    if not parsed or parsed.get('amount', 0) == 0:
        parsed = parse_expense_line(text, members)
    session['expenses'].append(parsed)
    expense_sessions[session_id] = session

    return jsonify({'expense': parsed, 'summary': get_summary(session)})


def _ai_parse_expense(text, members):
    """Use DeepSeek/GreenNode to parse natural language expense into structured data."""
    import requests as _req
    api_key = os.getenv('LLM_API_KEY')
    if not api_key:
        return None
    model = os.getenv('LLM_MODEL', 'deepseek/deepseek-v4-pro')
    base_url = os.getenv('LLM_BASE_URL', 'https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1')
    prompt = (
        f'Phân tích chi tiêu từ câu nói tiếng Việt sau. Thành viên trong nhóm: {", ".join(members)}.\n'
        f'Câu nói: "{text}"\n\n'
        'Trả về JSON duy nhất (không markdown, không giải thích):\n'
        '{"payer":"tên người trả","amount":số_tiền_VND,"description":"mô tả ngắn","participants":["tên1","tên2"]}\n\n'
        'Quy tắc:\n'
        '- Số tiền: "15" hoặc "15k" = 15000, "1 triệu" = 1000000, "200" = 200000, "50" = 50000\n'
        '- Nếu nói "cả nhóm"/"mọi người" thì participants = tất cả thành viên\n'
        '- QUAN TRỌNG: Nếu có ai "không ăn"/"không đi"/"không tham gia" thì LOẠI người đó khỏi participants\n'
        '  VD: "cả nhóm ăn 300k Trang không ăn" → participants KHÔNG có Trang\n'
        '- payer là người trả tiền (người "trả", "thanh toán", "chi")\n'
        '- Chỉ trả JSON, không giải thích gì thêm'
    )
    try:
        url = base_url + '/chat/completions'
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 200, 'temperature': 0.1}
        r = _req.post(url, headers=headers, json=payload, timeout=10)
        if r.ok:
            raw = r.json()['choices'][0]['message']['content'].strip()
            import re as _re
            raw = _re.sub(r'^```(?:json)?\n?', '', raw)
            raw = _re.sub(r'\n?```$', '', raw)
            result = json_module.loads(raw)
            # Build splits from participants
            participants = result.get('participants', members)
            # Validate participants against actual members
            valid_p = [m for m in members if _normalize(m) in [_normalize(p) for p in participants]]
            if not valid_p:
                valid_p = members
            amount = int(result.get('amount', 0))
            per_person = amount // len(valid_p) if valid_p else amount
            splits = {m: (per_person if m in valid_p else 0) for m in members}
            payer_name = result.get('payer', '')
            # Match payer to actual member name
            payer = None
            for m in members:
                if _normalize(m) == _normalize(payer_name):
                    payer = m
                    break
            return {
                'description': result.get('description', text),
                'amount': amount,
                'splits': splits,
                'payer': payer,
            }
    except Exception as e:
        logging.warning(f'AI expense parse failed: {e}')
    return None


@app.route('/expense/parse', methods=['POST'])
def parse_expense_preview():
    """Parse expense text without saving -- used by voice confirmation UI."""
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')
    text = data.get('text', '')
    session = expense_sessions.get(session_id, {'members': [], 'expenses': []})
    members = session.get('members', [])
    # Try AI parsing first, fall back to regex
    parsed = _ai_parse_expense(text, members)
    if not parsed or parsed.get('amount', 0) == 0:
        parsed = parse_expense_line(text, members)
    return jsonify(parsed)


@app.route('/expense/undo', methods=['POST'])
def undo_expense():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')
    session = expense_sessions.get(session_id, {'members': [], 'expenses': []})
    if session['expenses']:
        removed = session['expenses'].pop()
        return jsonify({'removed': removed, 'summary': get_summary(session)})
    return jsonify({'error': 'No expenses to undo'}), 400


@app.route('/expense/delete', methods=['POST'])
def delete_expense():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')
    index = data.get('index', -1)
    session = expense_sessions.get(session_id, {'members': [], 'expenses': []})
    expenses = session.get('expenses', [])
    if 0 <= index < len(expenses):
        removed = expenses.pop(index)
        return jsonify({'removed': removed, 'summary': get_summary(session)})
    return jsonify({'error': 'Invalid index'}), 400


@app.route('/expense/summary', methods=['POST'])
def expense_summary():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')
    session = expense_sessions.get(session_id, {'members': [], 'expenses': []})
    return jsonify(get_summary(session))


@app.route('/expense/reset', methods=['POST'])
def reset_expense():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')
    members = expense_sessions.get(session_id, {}).get('members', [])
    expense_sessions[session_id] = {'members': members, 'expenses': []}
    return jsonify({'status': 'ok'})


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True, port=5000)
