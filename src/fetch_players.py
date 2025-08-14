import requests
import pandas as pd

def fetch_top_100():
    url = "https://www.atptour.com/-/media/atp/rankings/rankings.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/115.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data: {response.status_code}")

    data = response.json()
    players = data["players"][:100]  # First 100 players

    df = pd.DataFrame(players)
    df.to_csv("../data/players.csv", index=False)
    print("Top 100 players saved to data/players.csv")

if __name__ == "__main__":
    fetch_top_100()
