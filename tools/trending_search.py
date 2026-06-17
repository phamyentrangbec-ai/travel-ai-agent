"""
Trending search tool — dùng Serper.dev API (2,500 free searches/month)
để tìm địa điểm đang hot trên Google/TikTok trong 30 ngày gần nhất.

Đăng ký free tại: https://serper.dev
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SERPER_KEY = os.environ.get("SERPER_API_KEY", "")


def search_trending_spots(city: str) -> list:
    """
    Tìm địa điểm đang hot trend trong 30 ngày gần nhất cho thành phố.
    Trả về list các địa điểm kèm snippet mô tả.
    """
    if not SERPER_KEY:
        return []

    queries = [
        f"địa điểm {city} đang hot trend tiktok 2025",
        f"{city} check in mới nhất 2025 viral",
        f"quán ăn cafe {city} mới mở hot 2025"
    ]

    results = []
    seen = set()

    for query in queries[:2]:  # Giới hạn 2 queries để tiết kiệm quota
        try:
            response = requests.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": SERPER_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "q": query,
                    "gl": "vn",
                    "hl": "vi",
                    "tbs": "qdr:m",  # Trong 1 tháng gần nhất
                    "num": 5
                },
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                for item in data.get("organic", []):
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    if title and title not in seen:
                        seen.add(title)
                        results.append({
                            "name": title,
                            "description": snippet,
                            "source": "Google Trends (30 ngày)"
                        })
        except Exception as e:
            print(f"[Serper] Lỗi: {e}")

    return results[:5]
