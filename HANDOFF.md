# Travel AI Agent — Handoff Document
## GreenNode Claw-a-thon 2026 | Track: Chat Agent

---

## 1. Tổng quan dự án

Conversational AI agent giúp người dùng lên lịch trình du lịch nội địa Việt Nam. Người dùng chỉ cần nói/gõ điểm đến, agent trả về:
- Trending spots (live từ TikTok/Threads/YouTube/Instagram)
- Lịch trình theo ngày với lựa chọn thay thế
- Dự toán chi phí
- Bill splitting (tính tiền chia theo người)

**Deploy target**: GreenNode AgentBase  
**Demo scope**: Vietnam domestic travel, Gen Z focused

---

## 2. Cấu trúc file

```
travel-ai-agent/
├── agent_entrypoint.py   ← Core logic (state machine, API calls, output)
├── app.py                ← Flask web server + Expense Tracker API
├── main.py               ← AgentBase entrypoint (deploy)
├── requirements.txt      ← requests, python-dotenv, flask, google-api-python-client
├── .env                  ← API keys (KHÔNG commit lên GitHub)
├── DEPLOY_AGENTBASE.md   ← Hướng dẫn deploy
├── data/
│   └── genz_spots.json   ← Static data 13 thành phố
├── static/
│   └── index.html        ← Web UI (voice + expense tracker)
└── tools/                ← Utility modules (Foursquare, YouTube, static_data)
```

---

## 3. Cách chạy local

```bash
cd travel-ai-agent
pip install -r requirements.txt

# Tạo file .env nếu chưa có:
FOURSQUARE_API_KEY=your_key
YOUTUBE_API_KEY=your_key
SERPER_API_KEY=your_key

# Chạy Web UI (dùng để demo)
python app.py
# → Mở Chrome: http://localhost:5000

# Hoặc chạy terminal thuần (v7 gốc)
python agent_entrypoint.py
```

> Voice dictation chỉ hoạt động trên **Chrome** (Web Speech API).

---

## 4. Tất cả tính năng đã build

### 4.1 Core Agent (`agent_entrypoint.py`) — v7

**Conversation flow (state machine):**
```
start → companions → duration → [duration_custom] → budget → [budget_custom] → style → done
```

**13 thành phố full data** (genz_spots.json):
Da Lat, Hoi An, Ha Noi, TP.HCM, Lac Duong, Hai Phong, Con Dao, Ly Son, Da Nang, Nha Trang, Phu Quoc, Hue, Ninh Binh

**50+ tỉnh thành generic** — dùng live API nếu không có full data

**Tính năng:**
- `detect_city()` — 100+ alias mapping, normalize dấu tiếng Việt (`Đà Lạt` → `da lat`)
- `detect_companions()` — solo/couple/friends/family
- `detect_duration()` — 2–30 ngày, option "Khác" nhập tùy ý
- `detect_custom_budget()` — parse `3.5 triệu`, `5tr`, `4500000`
- `fetch_unified_trending()` — gộp YouTube + Threads + TikTok + Instagram + Facebook + Blog vào 1 pool với icon [YT][TK][TH][IG][FB][WEB]
- `foursquare_live()` — live venues sorted by POPULARITY
- `build_result()` — full data cities với alternatives [1][2][3][4] mỗi slot
- `build_generic_result()` — generic cities dùng live API
- `render_schedule()` — lịch trình theo ngày/buổi với alternatives
- `render_extra_days()` — dynamic ngày 3+ dựa trên duration + style
- `calc_budget()` — dự toán theo budget tier, scale theo custom amount
- `_strip_accents()` — normalize tiếng Việt có dấu cho voice input

**Multi-style**: gõ `1 3` = Song Ảo + Thu Giãn (chọn nhiều cùng lúc)

**Budget tiers**: Budget / Tầm trung / Luxury / Custom (nhập số tiền cụ thể)

### 4.2 Web Server (`app.py`)

**Flask routes:**
- `GET /` → serve `static/index.html`
- `POST /chat` → gọi `travel_agent()`, trả về reply
- `POST /reset` → reset conversation state
- `POST /expense/members` → set danh sách thành viên
- `POST /expense/add` → parse 1 dòng chi tiêu, trả về splits + summary
- `POST /expense/undo` → xóa khoản cuối
- `POST /expense/summary` → tổng kết toàn chuyến
- `POST /expense/reset` → xóa toàn bộ

**Expense parser logic:**
- `parse_amount()` — nhận `350k`, `1.5tr`, `200000`, `150 nghìn`
- `parse_expense_line(text, members)` — detect tên thành viên trong câu, split cost
- `_normalize()` — accent removal để match tên có dấu
- "cả nhóm" / "tất cả" → chia đều cho tất cả members
- Nếu không detect được ai → mặc định chia đều

**Ví dụ expense parsing:**
```
Input:  "Ngân và Thủy ăn bánh căn 350k"  (3 members: Ngân, Thủy, Trang)
Output: Ngân: 175k | Thủy: 175k | Trang: 0đ

Input:  "cả nhóm đi taxi 120k"
Output: Ngân: 40k | Thủy: 40k | Trang: 40k

Input:  "Trang order thêm nước 50k"
Output: Ngân: 0đ | Thủy: 0đ | Trang: 50k

Summary: Ngân: 215k | Thủy: 215k | Trang: 90k
```

### 4.3 Web UI (`static/index.html`)

**Single-file HTML/JS/CSS. Không cần build tool.**

**Tính năng UI:**
- Dark mode Gen Z (purple/pink gradient)
- Tab switcher: 🗺️ Lập Lịch / 💰 Tính Tiền
- Chat bubbles (user phải, bot trái) + typing indicator (3 dots)
- Quick chips: Da Lat, Hoi An, Da Nang, Nha Trang, Phu Quoc, Ha Noi, Sa Pa
- **Voice dictation**: nút 🎤, Web Speech API `lang="vi-VN"`, nói xong tự gửi
- Expense panel (bên phải): thêm thành viên → ghi chi tiêu → bar chart real-time
- Delete khoản chi từng item hoặc undo khoản cuối
- Reset toàn bộ expense

---

## 5. Bug đã biết / cần fix tiếp

### 5.1 Layout (ưu tiên cao)
**Triệu chứng**: Chat messages không fill hết màn hình, input bar nằm sát ngay dưới messages thay vì ghim xuống đáy. Vùng dưới input bar là khoảng đen trống.

**Root cause đã xác định**: `.voice-hint` div là flex child của `.chat-panel` (column flex) nhưng có `flex-basis: 100%` → ăn hết chiều cao còn lại → `.messages` không grow được.

**Fix đã apply** (cần verify):
1. Wrap `input-bar` + `voice-hint` vào `div.input-wrap` với `flex-shrink: 0`
2. Xóa `flex-basis: 100%; order: 10` khỏi `.voice-hint`
3. Thêm `min-height: 0` vào `.main` và `.chat-panel`
4. Dùng `requestAnimationFrame` trong `scrollBottom()`

Nếu vẫn còn bug layout, kiểm tra Chrome DevTools → Elements → xem `.messages` có `height` đúng không.

### 5.2 Voice — đã fix
- `_strip_accents()` xử lý `đ/Đ` riêng trước NFD normalization
- Apply ở đầu `travel_agent()` và trong `detect_city()`
- Đã test: `Đà Lạt` → `da lat` ✓, `Hội An` → `hoi an` ✓

### 5.3 Chưa làm
- Responsive mobile (expense panel ẩn trên màn nhỏ — đã có CSS nhưng chưa test)
- Deploy lên AgentBase (xem `DEPLOY_AGENTBASE.md`)
- Output text còn là ASCII không dấu (intentional cho terminal, có thể upgrade cho web)

---

## 6. API Keys cần có

| Key | Lấy ở đâu | Dùng để |
|-----|-----------|---------|
| `FOURSQUARE_API_KEY` | developer.foursquare.com | Live venues gần đó |
| `YOUTUBE_API_KEY` | console.cloud.google.com | Trending travel videos VN |
| `SERPER_API_KEY` | serper.dev | Search Threads/TikTok/Instagram/Blog |

Tất cả đều có free tier đủ dùng để demo.

---

## 7. Test flow chuẩn để demo

```
Input: "Da Lat"
→ "3" (Nhóm bạn)
→ "2" (3 ngày 2 đêm)
→ "2" (Tầm trung)
→ "1 3" (Song Ảo + Thu Giãn)
→ Xem output lịch trình đầy đủ

Tab 💰 Tính Tiền:
→ Thêm thành viên: "Ngân, Thủy, Trang"
→ Ghi: "Ngân và Thủy ăn bánh căn 350k"
→ Ghi: "cả nhóm đi taxi 120k"
→ Xem bar chart real-time
```

---

## 8. Lịch sử version

| Version | Tính năng thêm |
|---------|---------------|
| v1-v3 | State machine, static data Da Lat, Foursquare API |
| v4 | YouTube API, Serper.dev, Google Maps links |
| v5 | Multi-style, budget per person, rating tags |
| v6 | 13 cities full + 63 tỉnh generic, 100+ alias, bug fixes |
| v7 | Duration tùy ý, budget tùy ý, unified trending pool, alternatives [1][2][3][4] |
| Web | Flask server, Web UI, Voice dictation, Expense Tracker/Bill splitting |

