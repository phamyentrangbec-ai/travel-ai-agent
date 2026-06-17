# Trip Buddy - Travel AI Agent

> GreenNode Claw-a-thon 2026 | Track: Chat Agent

## Giới thiệu

Trip Buddy là AI agent hỗ trợ lên kế hoạch du lịch Việt Nam, tập trung vào trải nghiệm Gen Z. Chỉ cần nói tên thành phố, agent sẽ gợi ý lịch trình chi tiết theo ngày với những điểm đến đang trending trên TikTok, Instagram.

## Tính năng chính

- **112 điểm đến** khắp Việt Nam (63 tỉnh + 49 sub-destinations)
- **AI-powered itinerary** với DeepSeek V4 Pro
- **Live trending** từ TikTok/IG/YouTube (Serper + YouTube API)
- **Gen Z curation** — ưu tiên aesthetic, unique, check-in đẹp
- **Smart city detection** — Longest-match-first trên 112 aliases
- **Voice input** bằng giọng nói (Web Speech API)
- **Expense splitter** — chia tiền nhóm, AI parse tiếng Việt tự nhiên
- **PDF export** lịch trình

## Tech Stack

- **Backend:** Python/Flask
- **Frontend:** HTML/Tailwind CSS/Vanilla JS (SPA)
- **LLM:** GreenNode AI Platform (DeepSeek V4 Pro)
- **APIs:** Serper.dev, YouTube Data API v3, Foursquare Places API
- **Deploy:** GreenNode AgentBase (Docker)

## Cách chạy local

```bash
pip install -r requirements.txt
cp .env.example .env
# Điền API keys vào .env
python main.py
# → http://localhost:8080
```

## Cấu trúc project

```
main.py                  # Entry point (port 8080)
app.py                   # Flask routes + post-processing
agent_entrypoint.py      # Core logic: state machine, AI, data pipeline
Dockerfile               # Docker build cho AgentBase
requirements.txt         # Python dependencies
static/index.html        # Frontend SPA
data/
  city_aliases.json      # 112 destinations + aliases
  genz_spots.json        # 67 tỉnh: spots theo time slot
  fallback_spots.json    # 30 sub-destinations
  knowledge_bases/       # 15 thành phố: KB chi tiết
```

## Flow hoạt động

1. User nhập tên thành phố → detect_city() (longest-match-first)
2. Hỏi thêm: số người, thời gian, ngân sách, phong cách
3. build_result() → tạo lịch trình từ KB / GenZ spots / AI / fallback
4. Post-processing → deduplicate + enrich alternatives
5. Hiển thị: lịch trình theo ngày + trending + budget + tips

## Data Pipeline (3-layer fallback)

| Layer | Nguồn | Coverage |
|-------|--------|----------|
| 1 | Knowledge Base | 15 thành phố lớn |
| 2 | GenZ Spots | 67 tỉnh thành |
| 3a | AI (DeepSeek) | Unlimited |
| 3b | Fallback Spots | 30 sub-destinations |
| 3c | Generic Templates | Last resort |

## Team

- **Track:** Chat Agent
- **Platform:** GreenNode AgentBase
- **Scope:** Du lịch nội địa Việt Nam, Gen Z focus
