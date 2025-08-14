import re
import pdfplumber
import pandas as pd
from pathlib import Path

PDF_PATH = Path("../data/race_rankings.pdf")
OUT_CSV  = Path("../output/players_top100.csv")
OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

# Very tolerant line parser:
#  - rank at start
#  - name like "Lastname, Firstname" (can include spaces like "de Minaur")
#  - optional country (CCC) with optional "(" and optional ")"
#  - first large integer after name/country = total points
# Examples handled:
# "1 Alcaraz, Carlos (ESP 7540 3700 ..."
# "12 Khachanov, Karen 2060 600 ..."
line_re = re.compile(
    r"""^\s*
        (?P<rank>\d{1,3})                              # rank
        \s+
        (?P<name>[A-Za-zÀ-ÖØ-öø-ÿ\.\-\' ]+,\s*[A-Za-zÀ-ÖØ-öø-ÿ\.\-\' ]+)   # "Lastname, Firstname"
        \s+
        (?:\(?(?P<country>[A-Z]{3})\)?)?               # optional country code, () optional
        \s*
        (?P<points>\d{3,5}(?:,\d{3})*)                 # first big number = total points
        \b
    """,
    re.VERBOSE,
)

def tidy_name(last_first: str) -> str:
    if "," in last_first:
        last, first = [p.strip() for p in last_first.split(",", 1)]
        return f"{first} {last}"
    return last_first.strip()

def main():
    if not PDF_PATH.exists():
        print(f"PDF not found at {PDF_PATH}")
        return

    rows = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw in text.splitlines():
                line = raw.strip()
                m = line_re.match(line)
                if not m:
                    continue
                rank    = int(m.group("rank"))
                name    = tidy_name(m.group("name"))
                country = m.group("country") or ""
                points  = int(m.group("points").replace(",", ""))
                if 1 <= rank <= 100:
                    rows.append((rank, name, country, points))

    if not rows:
        print("Still no matches. If you can, copy 2–3 full lines from the PDF (exactly as text) and I’ll tighten the pattern again.")
        return

    # keep first occurrence per rank, sort
    by_rank = {}
    for r, n, c, p in rows:
        by_rank.setdefault(r, (n, c, p))

    data = [(r, *by_rank[r]) for r in sorted(by_rank.keys()) if r <= 100]
    df = pd.DataFrame(data, columns=["rank", "name", "country", "points"])
    df.to_csv(OUT_CSV, index=False)
    print(f"✅ Saved {OUT_CSV} with {len(df)} players.")
    # show the first few rows for a quick check
    print(df.head(12).to_string(index=False))

if __name__ == "__main__":
    main()
