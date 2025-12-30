import requests

def fetch_character_json(character_id):
    """
    Fetches character data directly from D&D Beyond's public API endpoint.
    """
    url = f"https://character-service.dndbeyond.com/character/v5/character/{character_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Raise error if ID is wrong or site is down
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}