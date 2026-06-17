import os, requests

def get_venues(city, category='food', limit=5):
    api_key = os.getenv('FOURSQUARE_API_KEY')
    if not api_key:
        return []
    try:
        url = 'https://api.foursquare.com/v3/places/search'
        headers = {'Authorization': api_key}
        params = {'query': city, 'categories': '13000', 'limit': limit, 'sort': 'POPULARITY'}
        r = requests.get(url, headers=headers, params=params, timeout=5)
        if r.ok:
            results = r.json().get('results', [])
            venues = []
            for v in results:
                geocodes = v.get('geocodes', {}).get('main', {})
                lat = geocodes.get('latitude', 0)
                lng = geocodes.get('longitude', 0)
                venues.append({
                    'name': v['name'],
                    'rating': v.get('rating', 0),
                    'address': v.get('location', {}).get('formatted_address', ''),
                    'price_range': v.get('price', ''),
                    'maps_url': f"https://maps.google.com/?q={lat},{lng}"
                })
            return venues
    except Exception:
        pass
    return []
