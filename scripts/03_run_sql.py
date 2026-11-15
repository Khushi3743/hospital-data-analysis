"""Loads the clean CSV into SQLite and runs every query in sql/analysis_queries.sql.
Output: data/processed/hospital.db and printed results."""
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
db = ROOT / "data" / "processed" / "hospital.db"
con = sqlite3.connect(db)
pd.read_csv(ROOT / "data" / "processed" / "hospital_admissions_clean.csv").astype(
    {c: str for c in ["readmitted_30d", "readmit_eligible", "high_cost", "age_imputed", "cost_corrected"]}
).to_sql("admissions", con, if_exists="replace", index=False)

sql = (ROOT / "sql" / "analysis_queries.sql").read_text()
blocks = [b.strip() for b in sql.split(";") if "SELECT" in b.upper()]
for b in blocks:
    title = next((l for l in b.splitlines() if l.startswith("-- Q")), "query")
    print(f"\n{title}")
    print(pd.read_sql(b, con).head(20).to_string(index=False))
con.close()
