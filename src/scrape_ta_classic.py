import re
import unicodedata
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path

OUT_DIR = Path("../output"); OUT_DIR.mkdir(parents=True, exist_ok=True)
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36")
}

def to_slug_for_tennisabstract(full_name: str) -> str:
    n = unicodedata.normalize("NFKD", full_name)
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return re.sub(r"[^\w]", "", n)  # remove spaces/punct/accents

def text_or_blank(el):
    return el.get_text(" ", strip=True) if el else ""

def parse_results_td(td, player_name: str):
    """Return (opponent, opp_country, result_wl).
    result_wl: 'W','L','Live','' """
    txt = text_or_blank(td)
    # opponent: first <a> inside results cell is the opponent
    a = td.find("a")
    opponent = a.get_text(strip=True) if a else ""
    # country code inside [XXX]
    mcc = re.search(r"\[([A-Z]{3})\]", txt)
    opp_country = mcc.group(1) if mcc else ""

    # Win/Loss/Live: check order of player's last name vs ' d. '
    lastname = player_name.split()[-1]
    low = txt.lower()
    pos_d = low.find(" d. ")
    pos_vs = low.find(" vs ")
    if pos_vs != -1:
        return opponent, opp_country, "Live"
    if pos_d == -1:
        return opponent, opp_country, ""
    pos_last = low.find(lastname.lower())
    if pos_last == -1:
        return opponent, opp_country, ""
    return (opponent, opp_country, "W" if pos_last < pos_d else "L")

def scrape_player_classic(player_name: str) -> pd.DataFrame:
    slug = to_slug_for_tennisabstract(player_name)
    url = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={slug}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    table = soup.find("table", id="matches")
    if not table:
        raise RuntimeError("Matches table (#matches) not found")

    rows = []
    for tr in table.select("tbody > tr"):
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue  # skip malformed rows

        date_raw = text_or_blank(tds[0]).replace("-", "-")  # normalize narrow hyphen
        tournament = text_or_blank(tds[1])
        surface = text_or_blank(tds[2])
        rd = text_or_blank(tds[3])

        def to_int(s):
            s = s.replace(",", "").strip()
            return int(s) if s.isdigit() else None

        rk  = to_int(text_or_blank(tds[4]))
        vrk = to_int(text_or_blank(tds[5]))

        opponent, opp_cc, wl = parse_results_td(tds[6], player_name)
        score = text_or_blank(tds[7])

        # “More” column may contain a chart link (ch)
        more_link = ""
        alink = tds[8].find("a") if len(tds) > 8 else None
        if alink and alink.has_attr("href"):
            more_link = alink["href"]

        # Optional stats columns (may be blank)
        get = lambda i: text_or_blank(tds[i]) if i < len(tds) else ""
        dr     = get(9)
        a_pct  = get(10)
        df_pct = get(11)
        first_in = get(12)
        first_pct = get(13)
        second_pct = get(14)
        bpsvd  = get(15)
        ttime  = get(16)

        rows.append({
            "player": player_name,
            "date": date_raw,
            "tournament": tournament,
            "surface": surface,
            "round": rd,
            "rk": rk,
            "vrk": vrk,
            "opponent": opponent,
            "opp_country": opp_cc,
            "score": score,
            "result_wl": wl,
            "chart_link": more_link,
            "DR": dr,
            "A%": a_pct,
            "DF%": df_pct,
            "1stIn": first_in,
            "1st%": first_pct,
            "2nd%": second_pct,
            "BPSvd": bpsvd,
            "time": ttime,
        })

    df = pd.DataFrame(rows)
    # Parse dates to ISO if possible
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype(str)

    return df

if __name__ == "__main__":
    player = "Jannik Sinner"
    df = scrape_player_classic(player)
    out_path = OUT_DIR / "sinner_matches.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path}")
    print(df.head(10).to_string(index=False))
