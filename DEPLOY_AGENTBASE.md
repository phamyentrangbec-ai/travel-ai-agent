# Deploy lên GreenNode AgentBase

## File dùng để deploy: `agent_entrypoint.py`
(Khác với main.py — file này không cần folder tools/ hay data/, tất cả code nằm trong 1 file duy nhất)

---

## Bước 1 — Mở AgentBase

Vào: https://agentbase.greennode.ai (hoặc link ban tổ chức cung cấp)
Đăng nhập bằng tài khoản hackathon.

---

## Bước 2 — Tạo Agent mới

- Click **"Create Agent"** hoặc **"New Agent"**
- Tên agent: `Travel AI Agent`
- Chọn track: **Chat Agent**

---

## Bước 3 — Upload code

Tùy giao diện AgentBase, có 2 cách:

**Cách A — Paste code trực tiếp:**
- Tìm ô "Agent Code" hoặc "Main Function"
- Copy toàn bộ nội dung file `agent_entrypoint.py`
- Paste vào

**Cách B — Upload file:**
- Upload file `agent_entrypoint.py`
- Platform tự nhận hàm `travel_agent()` làm entrypoint

---

## Bước 4 — Thêm Environment Variables

Tìm mục **"Environment Variables"** hoặc **"Secrets"** → thêm 2 biến:

| Key | Value |
|-----|-------|
| `FOURSQUARE_API_KEY` | `your_foursquare_api_key_here` |
| `YOUTUBE_API_KEY` | `your_youtube_api_key_here` |

---

## Bước 5 — Thêm Dependencies

Tìm mục **"Requirements"** hoặc **"Packages"** → thêm:
```
requests
google-api-python-client
```

---

## Bước 6 — Deploy & Test

- Click **"Deploy"** hoặc **"Publish"**
- Sau khi deploy, test thử trong chat interface:
  - "Tôi muốn đi Đà Lạt"
  - "Gợi ý Hội An"
  - "Hà Nội có gì hay?"
  - "Trip Sài Gòn"

---

## Lưu ý quan trọng

- Hàm entrypoint là `travel_agent(user_input: str) -> str`
- Nếu platform yêu cầu tên hàm khác (vd: `handler`, `run`, `main`) → đổi tên hàm trong file
- File `.env` KHÔNG upload lên — keys đã được điền vào Environment Variables của platform
