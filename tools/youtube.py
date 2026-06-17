import os, requests

def get_trending_videos(city, max_results=3):
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        return []
    try:
        url = 'https://www.googleapis.com/youtube/v3/search'
        params = {
            'part': 'snippet',
            'q': f'{city} travel 2025 tiktok vlog',
            'type': 'video',
            'maxResults': max_results,
            'key': api_key,
            'relevanceLanguage': 'vi',
            'regionCode': 'VN'
        }
        r = requests.get(url, params=params, timeout=5)
        if r.ok:
            items = r.json().get('items', [])
            return [
                {
                    'name': i['snippet']['title'],
                    'url': f"https://youtube.com/watch?v={i['id']['videoId']}",
                    'source': 'YouTube'
                }
                for i in items
            ]
    except Exception:
        pass
    return []
