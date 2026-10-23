
import requests
import json
from config import API_KEY, BASE_URL
 
r = requests.get(
    f"{BASE_URL}/Opportunity/Search",
    params={"apikey": API_KEY, "top": 2, "skip": 0},
    headers={"Content-Type": "application/json"},
    timeout=30,
)
r.raise_for_status()
 
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
 
