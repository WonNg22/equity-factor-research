"""Import the first monthly, value-weighted French table into a research database."""
from pathlib import Path
from io import StringIO
from zipfile import ZipFile
from urllib.request import urlopen
import hashlib
import json
import re
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data/factors.sqlite"
OUT = ROOT / "results"
MONTHS = pd.period_range("2005-01", "2026-09", freq="M")
SORTS = {"Momentum": "25_Portfolios_ME_Prior_12_2",
         "Reversal": "25_Portfolios_ME_Prior_1_0",
         "Low volatility": "25_Portfolios_ME_VAR_5x5"}
FACTORS = ["F-F_Momentum_Factor", "F-F_ST_Reversal_Factor", "F-F_Research_Data_Factors"]
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"


def monthly_table(source):
    lines = source.splitlines()
    first = next(i for i, line in enumerate(lines) if re.match(r"^\s*\d{6},", line))
    end = first
    while end < len(lines) and re.match(r"^\s*\d{6},", lines[end]):
        end += 1
    df = pd.read_csv(StringIO("\n".join(lines[first-1:end])), index_col=0)
    df.columns = df.columns.str.strip()
    df.index = pd.to_datetime(df.index.astype(str), format="%Y%m").to_period("M")
    if not df.index.is_unique:
        raise ValueError("Duplicate months")
    df = df.replace([-99.99, -999.0], float("nan")).reindex(MONTHS) / 100
    if df.isna().any().any():
        raise ValueError("Incomplete sample or missing cell")
    return df


def build():
    cache = ROOT / "data/cache"
    cache.mkdir(parents=True, exist_ok=True)
    manifest = ROOT / "data/sources.json"
    expected = json.loads(manifest.read_text()) if manifest.exists() else {}
    records, benchmarks, sources = [], [], {}
    for name in [*SORTS.values(), *FACTORS]:
        path = cache / (name + ".zip")
        url = BASE + name + "_CSV.zip"
        if not path.exists():
            with urlopen(url, timeout=60) as response:
                path.write_bytes(response.read())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected and digest != expected[name]["sha256"]:
            raise ValueError(f"Upstream vintage changed for {name}. Use the bundled database for the published results.")
        with ZipFile(path) as archive:
            raw = archive.read(archive.namelist()[0]).decode("latin1")
        sources[name] = dict(url=url, sha256=digest, vintage=raw.splitlines()[0].strip())
        df = monthly_table(raw)
        df.index = df.index.astype(str)
        if name in FACTORS:
            benchmarks.append(df)
            continue
        if "Average Value Weighted Returns -- Monthly" not in raw.split(df.columns[0])[0]:
            raise ValueError("Unexpected source table")
        suffix = "VAR" if name.endswith("5x5") else "PRIOR"
        headers = [f"ME{s} {suffix}{q}" for s in range(1, 6) for q in range(1, 6)]
        headers[0],headers[4] = "SMALL Lo"+suffix,"SMALL Hi"+suffix
        headers[20],headers[24] = "BIG Lo"+suffix,"BIG Hi"+suffix
        if list(df.columns) != headers:
            raise ValueError(f"Unexpected column labels in {name}")
        signal = next(key for key, value in SORTS.items() if value == name)
        for i, col in enumerate(df.columns):
            records.extend((month, signal, i//5+1, i%5+1, ret) for month, ret in df[col].items())
    tmp = DB.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    with sqlite3.connect(tmp) as conn:
        conn.execute("""CREATE TABLE portfolios (month TEXT, signal TEXT, size_q INTEGER,
                     signal_q INTEGER, ret REAL NOT NULL, PRIMARY KEY(month,signal,size_q,signal_q))""")
        conn.executemany("INSERT INTO portfolios VALUES (?,?,?,?,?)", records)
        pd.concat(benchmarks, axis=1).rename_axis("month").to_sql("benchmarks", conn)
    conn.close()
    tmp.replace(DB)
    manifest.write_text(json.dumps(sources, indent=2)+"\n")


if __name__ == "__main__":
    build()
