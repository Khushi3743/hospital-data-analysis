"""Loads the clean CSV into SQLite and runs every query in sql/analysis_queries.sql.
Output: data/processed/hospital.db and printed results."""
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
con = sqlite3.connect(ROOT / "data" / "processed" / "hospital.db")
bools = ["a1c_tested", "med_changed", "expired", "readmit_eligible", "readmitted_30d"]
pd.read_csv(ROOT / "data" / "processed" / "hospital_encounters_clean.csv", low_memory=False).astype(
    {c: str for c in bools}).to_sql("encounters", con, if_exists="replace", index=False)

sql = (ROOT / "sql" / "analysis_queries.sql").read_text()
for block in [b.strip() for b in sql.split(";") if "SELECT" in b.upper()]:
    title = next((l for l in block.splitlines() if l.startswith("-- Q")), "query")
    print(f"\n{title}")
    print(pd.read_sql(block, con).to_string(index=False))
con.close()
