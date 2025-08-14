import re, unicodedata, pandas as pd
from io import StringIO
from pathlib import Path

# Selenium (Edge)
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

OUT_DIR = Path("../output"); OUT_DIR.mkdir(parents=True, exist_ok=True)

def to_slug_for_tennisabstract(full_name: str) -> str:
    n = unicodedata.normalize("NFKD", full_name)
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return re.sub(r"[^\w]", "", n)

def parse_result_and_opponent(txt: str, player_name: str):
    ccodes = re.findall(r"\[([A-Z]{3})\]", txt or "")
    t = re.sub(r"\([^)]*\)", "", txt or "")
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    if " vs " in t.lower():
        return "", "", "Live"
    parts = t.split(" d. ")
    if len(parts) != 2:
        return "", "", ""
    left, right = parts[0].strip(), parts[1].strip()
    def norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return s.lower()
    first = norm(player_name).split()[0]
    if first in norm(left):  result, opponent = "W", right
    elif first in norm(right): result, opponent = "L", left
    else: result, opponent = "", right
    return re.sub(r"\s+", " ", opponent).strip(" ,"), (ccodes[-1] if ccodes else ""), result

def scrape_player_classic(player_name: str) -> pd.DataFrame:
    slug = to_slug_for_tennisabstract(player_name)
    url = f"https://www.tennisabstract.com/cgi-bin/player-classic.cgi?p={slug}"

    opts = EdgeOptions()
    # Comment the next line to SEE the browser for debugging:
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,900")

    # If you ever get "cannot find Edge binary", set the next line to your msedge.exe path:
    # opts.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()),
                            options=opts)
    try:
        driver.get(url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#matches tbody tr"))
        )
        table_html = driver.find_element(By.ID, "matches").get_attribute("outerHTML")
        (OUT_DIR / f"{slug}.html").write_text(table_html, encoding="utf-8")
    finally:
        driver.quit()

    dfs = pd.read_html(StringIO(table_html))
    if not dfs:
        return pd.DataFrame()
    df = dfs[0]
    df.columns = [str(c).strip() for c in df.columns]

    # Find results column
    results_col = next((c for c in df.columns if str(c).strip().lower() in {"results","result"}), None)
    if results_col is None:
        for c in df.columns:
            if df[c].astype(str).str.contains(r"\bd\.\b", regex=True, na=False).any():
                results_col = c; break

    if results_col:
        opps, ccs, wls = [], [], []
        for txt in df[results_col].astype(str):
            o, cc, wl = parse_result_and_opponent(txt, player_name)
            opps.append(o); ccs.append(cc); wls.append(wl)
        df["Opponent"] = opps; df["OppCountry"] = ccs; df["ResultWL"] = wls

    want = ["Date","Tournament","Surface","Rd","Round","Rk","vRk","Score","Time","DR","A%","DF%","1stIn","1st%","2nd%","BPSvd"]
    keep = [c for c in want if c in df.columns]
    out = df[keep + [c for c in ["Opponent","OppCountry","ResultWL"] if c in df.columns]].copy()
    out.insert(0, "Player", player_name)

    if "Date" in out.columns:
        out["Date"] = (out["Date"].astype(str)
                       .str.replace("\u2011", "-").str.replace("\u2010", "-").str.replace("\u2013", "-"))
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.date.astype(str)
    return out

if __name__ == "__main__":
    player = "Jannik Sinner"
    df = scrape_player_classic(player)
    out_path = OUT_DIR / "sinner_matches.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path}")
    if not df.empty:
        print(df.head(10).to_string(index=False))
