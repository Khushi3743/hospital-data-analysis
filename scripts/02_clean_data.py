"""
02_clean_data.py
Cleans the raw admissions file and adds analysis fields.

Input : data/raw/hospital_admissions_raw.csv
Output: data/processed/hospital_admissions_clean.csv
        data/processed/cleaning_log.csv   (what was changed and how many rows)

Metric definitions (agreed for the whole project)
- length_of_stay (LOS): discharge_date - admission_date in days; same-day = 0.
- readmitted_30d: the patient has another admission starting within 30 days
  of this discharge (any cause). Index stays ending in death are excluded, and
  stays discharged in the last 30 days of the data window are excluded because
  their follow-up period is incomplete (column readmit_eligible = False).
- cost_per_day: total_cost / max(LOS, 1).
- high_cost: total_cost in the top 10% of all stays.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "hospital_admissions_raw.csv"
OUT = ROOT / "data" / "processed" / "hospital_admissions_clean.csv"
LOG = ROOT / "data" / "processed" / "cleaning_log.csv"
DATA_END = pd.Timestamp("2024-12-31")

log = []


def note(step, rows, detail):
    log.append({"step": step, "rows_affected": int(rows), "detail": detail})
    print(f"- {step}: {rows:,} rows | {detail}")


def main():
    df = pd.read_csv(RAW, dtype=str)
    note("Load raw file", len(df), "all columns read as text first")

    # 1. exact duplicates
    before = len(df)
    df = df.drop_duplicates()
    note("Remove exact duplicate rows", before - len(df), "double-loaded records")
    dup_ids = df["admission_id"].duplicated().sum()
    note("Check duplicate admission_id", dup_ids, "should be 0 after removing exact duplicates")

    # 2. text categories: trim + consistent case
    for c in ["gender", "department", "insurance_type", "admission_type",
              "admission_source", "discharge_disposition", "primary_diagnosis"]:
        df[c] = df[c].str.strip()
    gmap = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}
    bad = (~df["gender"].isin(["Male", "Female"])).sum()
    df["gender"] = df["gender"].str.lower().map(gmap)
    note("Standardise gender", bad, "M/male/MALE/F/female -> Male/Female")

    canon = ["Cardiology", "General Medicine", "Pulmonology", "Endocrinology", "Neurology",
             "Orthopedics", "General Surgery", "Nephrology", "Obstetrics"]
    lookup = {d.lower(): d for d in canon}
    lookup.update({d.lower().replace("general ", "gen. "): d for d in canon if d.startswith("General")})
    bad = (~df["department"].isin(canon)).sum()
    df["department"] = df["department"].str.lower().map(lookup)
    note("Standardise department", bad, "case, spaces and 'Gen.' abbreviation fixed")
    assert df["department"].notna().all()

    for c in ["insurance_type", "admission_source", "discharge_disposition"]:
        n = df[c].isna().sum()
        df[c] = df[c].fillna("Unknown")
        note(f"Fill missing {c}", n, "labelled 'Unknown' (kept, not dropped)")

    # 3. dates: two formats in source
    iso = pd.to_datetime(df["admission_date"], format="%Y-%m-%d", errors="coerce")
    dmy = pd.to_datetime(df["admission_date"], format="%d/%m/%Y", errors="coerce")
    note("Parse mixed date formats", iso.isna().sum(), "DD/MM/YYYY rows converted to ISO")
    df["admission_date"] = iso.fillna(dmy)
    df["discharge_date"] = pd.to_datetime(df["discharge_date"], format="%Y-%m-%d")
    assert df["admission_date"].notna().all()

    swapped = df["discharge_date"] < df["admission_date"]
    df.loc[swapped, ["admission_date", "discharge_date"]] = \
        df.loc[swapped, ["discharge_date", "admission_date"]].values
    note("Fix discharge before admission", swapped.sum(), "dates were swapped at entry; swapped back")

    # 4. numerics
    df["comorbidity_count"] = df["comorbidity_count"].astype(int)
    df["icu_days"] = df["icu_days"].astype(int)
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    invalid = ~df["age"].between(0, 110) & df["age"].notna()
    df.loc[invalid, "age"] = np.nan
    note("Invalid ages set to missing", invalid.sum(), "age outside 0-110 (typos like 150, -1)")

    # impute age: same patient's other stays first (age +/- years between), else diagnosis median
    df["age_imputed"] = df["age"].isna()
    df = df.sort_values(["patient_id", "admission_date"])
    birth_year = (df["admission_date"].dt.year - df["age"])
    df["_by"] = birth_year.groupby(df["patient_id"]).transform("median")
    from_patient = df["age"].isna() & df["_by"].notna()
    df.loc[from_patient, "age"] = df.loc[from_patient, "admission_date"].dt.year - df.loc[from_patient, "_by"]
    from_diag = df["age"].isna()
    df.loc[from_diag, "age"] = df.groupby("primary_diagnosis")["age"].transform("median")[from_diag]
    df["age"] = df["age"].round().astype(int)
    note("Impute missing age", from_patient.sum() + from_diag.sum(),
         f"{from_patient.sum()} from patient's other stays, {from_diag.sum()} from diagnosis median; flagged age_imputed")
    df = df.drop(columns="_by")

    cost_txt = df["total_cost"].str.contains("Rs", na=False)
    df["total_cost"] = pd.to_numeric(df["total_cost"].str.replace(r"[^0-9.]", "", regex=True),
                                     errors="coerce")
    note("Convert text costs to numbers", cost_txt.sum(), "'Rs 1,23,000' style values parsed")

    # 5. derived fields
    df["length_of_stay"] = (df["discharge_date"] - df["admission_date"]).dt.days
    df["cost_per_day"] = df["total_cost"] / df["length_of_stay"].clip(lower=1)

    # mis-keyed cost outliers: cost per day > 6x the diagnosis median
    med = df.groupby("primary_diagnosis")["cost_per_day"].transform("median")
    outlier = df["cost_per_day"] > 6 * med
    df["cost_corrected"] = outlier
    df.loc[outlier, "total_cost"] = df.loc[outlier, "total_cost"] / 10
    df["cost_per_day"] = df["total_cost"] / df["length_of_stay"].clip(lower=1)
    note("Correct mis-keyed cost outliers", outlier.sum(),
         ">6x diagnosis median cost/day; extra zero removed (/10); flagged cost_corrected")
    note("Missing total_cost left as missing", df["total_cost"].isna().sum(),
         "not imputed; excluded from cost metrics only")

    bins = [-1, 17, 34, 49, 64, 79, 200]
    labels = ["0-17", "18-34", "35-49", "50-64", "65-79", "80+"]
    df["age_group"] = pd.cut(df["age"], bins=bins, labels=labels).astype(str)
    df["los_band"] = pd.cut(df["length_of_stay"], [-1, 1, 3, 7, 14, 999],
                            labels=["0-1 days", "2-3 days", "4-7 days", "8-14 days", "15+ days"]).astype(str)
    df["admission_month"] = df["admission_date"].dt.to_period("M").astype(str)
    df["admission_year"] = df["admission_date"].dt.year
    df["admission_weekday"] = df["admission_date"].dt.day_name()
    df["comorbidity_band"] = pd.cut(df["comorbidity_count"], [-1, 0, 2, 4, 99],
                                    labels=["0", "1-2", "3-4", "5+"]).astype(str)

    # prior admissions in previous 365 days (computed, not trusted from source)
    df = df.sort_values(["patient_id", "admission_date"]).reset_index(drop=True)
    prior = np.zeros(len(df), dtype=int)
    for _, g in df.groupby("patient_id").groups.items():
        dates = df.loc[g, "admission_date"].values
        for k, i in enumerate(g):
            prior[i] = ((dates[:k] >= dates[k] - np.timedelta64(365, "D"))).sum()
    df["prior_admissions_12m"] = prior

    # readmission within 30 days
    nxt = df.groupby("patient_id")["admission_date"].shift(-1)
    df["days_to_next_admission"] = (nxt - df["discharge_date"]).dt.days
    df["readmit_eligible"] = (df["discharge_disposition"] != "Expired") & \
                             (df["discharge_date"] <= DATA_END - pd.Timedelta(days=30))
    df["readmitted_30d"] = (df["days_to_next_admission"].between(0, 30)) & df["readmit_eligible"]
    note("Readmission eligible stays", df["readmit_eligible"].sum(),
         "excludes deaths and discharges in final 30 days of data")

    q90 = df["total_cost"].quantile(0.90)
    df["high_cost"] = df["total_cost"] >= q90
    note("High-cost threshold (90th percentile)", df["high_cost"].sum(), f"INR {q90:,.0f}")

    cols = ["admission_id", "patient_id", "admission_date", "discharge_date", "admission_year",
            "admission_month", "admission_weekday", "age", "age_group", "age_imputed", "gender",
            "insurance_type", "comorbidity_count", "comorbidity_band", "prior_admissions_12m",
            "primary_diagnosis", "department", "admission_type", "admission_source",
            "length_of_stay", "los_band", "icu_days", "discharge_disposition", "total_cost",
            "cost_per_day", "cost_corrected", "high_cost", "days_to_next_admission",
            "readmit_eligible", "readmitted_30d"]
    df = df[cols].sort_values("admission_date")
    df["admission_date"] = df["admission_date"].dt.strftime("%Y-%m-%d")
    df["discharge_date"] = df["discharge_date"].dt.strftime("%Y-%m-%d")
    df["cost_per_day"] = df["cost_per_day"].round(2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    note("Write clean file", len(df), str(OUT.relative_to(ROOT)))
    pd.DataFrame(log).to_csv(LOG, index=False)


if __name__ == "__main__":
    main()
