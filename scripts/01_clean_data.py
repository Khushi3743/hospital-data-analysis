"""
01_clean_data.py
Cleans the real UCI "Diabetes 130-US Hospitals for Years 1999-2008" dataset
and adds analysis fields.

Source : Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014). Diabetes 130-US
         Hospitals for Years 1999-2008 [Dataset]. UCI Machine Learning Repository.
         https://doi.org/10.24432/C5230J   (licence: CC BY 4.0)
Input  : data/raw/diabetic_data.csv, data/raw/IDS_mapping.csv
Output : data/processed/hospital_encounters_clean.csv
         data/processed/cleaning_log.csv

Metric definitions (used identically in Python, SQL, Power BI and the dashboard)
- length_of_stay: time_in_hospital, in days (1-14 by the dataset's design).
- readmitted_30d: the dataset's own label readmitted == "<30".
- readmit_eligible: excludes encounters that ended in death or discharge to
  hospice, because those patients cannot be readmitted (as in Strack et al. 2014).
- 30-day readmission rate = readmitted_30d / readmit_eligible encounters.
- bed_days: length_of_stay summed over encounters (resource-use measure; the
  dataset has no cost field).
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "diabetic_data.csv"
OUT = ROOT / "data" / "processed" / "hospital_encounters_clean.csv"
LOG = ROOT / "data" / "processed" / "cleaning_log.csv"
log = []


def note(step, rows, detail):
    log.append({"step": step, "rows_affected": int(rows), "detail": detail})
    print(f"- {step}: {rows:,} | {detail}")


ADMISSION_TYPE = {1: "Emergency", 7: "Emergency", 2: "Urgent", 3: "Elective",
                  4: "Other", 5: "Unknown", 6: "Unknown", 8: "Unknown"}
ADMISSION_SOURCE = {7: "Emergency Room", 1: "Referral", 2: "Referral", 3: "Referral",
                    4: "Transfer", 5: "Transfer", 6: "Transfer", 10: "Transfer", 18: "Transfer",
                    22: "Transfer", 25: "Transfer", 26: "Transfer"}
DISCHARGE = {1: "Home", 6: "Home with care", 8: "Home with care",
             3: "Nursing/rehab facility", 4: "Nursing/rehab facility", 22: "Nursing/rehab facility",
             23: "Nursing/rehab facility", 24: "Nursing/rehab facility",
             2: "Other facility", 5: "Other facility", 9: "Other facility", 10: "Other facility",
             15: "Other facility", 27: "Other facility", 28: "Other facility", 29: "Other facility",
             30: "Other facility", 7: "Left against advice",
             11: "Expired", 19: "Expired", 20: "Expired", 21: "Expired",
             13: "Hospice", 14: "Hospice", 12: "Other", 16: "Other", 17: "Other"}
AGE = {"[0-10)": "Under 40", "[10-20)": "Under 40", "[20-30)": "Under 40", "[30-40)": "Under 40",
       "[40-50)": "40-49", "[50-60)": "50-59", "[60-70)": "60-69", "[70-80)": "70-79",
       "[80-90)": "80+", "[90-100)": "80+"}
AGE_MID = {"[0-10)": 5, "[10-20)": 15, "[20-30)": 25, "[30-40)": 35, "[40-50)": 45,
           "[50-60)": 55, "[60-70)": 65, "[70-80)": 75, "[80-90)": 85, "[90-100)": 95}


def icd9_group(code):
    """Group a primary ICD-9 code into the broad categories used by Strack et al. (2014)."""
    if pd.isna(code):
        return "Other"   # 21 encounters have no primary diagnosis code
    c = str(code)
    if c.startswith(("V", "E")):
        return "Other"
    v = float(c)
    if 250 <= v < 251:
        return "Diabetes"
    if 390 <= v <= 459 or int(v) == 785:
        return "Circulatory"
    if 460 <= v <= 519 or int(v) == 786:
        return "Respiratory"
    if 520 <= v <= 579 or int(v) == 787:
        return "Digestive"
    if 800 <= v <= 999:
        return "Injury"
    if 710 <= v <= 739:
        return "Musculoskeletal"
    if 580 <= v <= 629 or int(v) == 788:
        return "Genitourinary"
    if 140 <= v <= 239:
        return "Neoplasms"
    return "Other"


def specialty_group(s):
    if pd.isna(s):
        return "Not recorded"
    if s.startswith("Surgery") or s == "Surgeon":
        return "Surgery"
    if s.startswith("Orthopedics"):
        return "Orthopedics"
    keep = {"InternalMedicine": "Internal Medicine", "Emergency/Trauma": "Emergency/Trauma",
            "Family/GeneralPractice": "Family/General Practice", "Cardiology": "Cardiology",
            "Nephrology": "Nephrology", "Radiologist": "Radiology", "Pulmonology": "Pulmonology"}
    return keep.get(s, "Other")


def main():
    df = pd.read_csv(RAW, dtype=str)
    note("Load raw file", len(df), "101,766 encounters expected (UCI)")
    sentinel = (df == "?").sum()
    note("'?' used as missing marker", int(sentinel.sum()),
         "cells; top columns: " + ", ".join(f"{k} {v:,}" for k, v in sentinel.sort_values(ascending=False).head(4).items()))
    df = df.replace("?", np.nan)

    dup = df["encounter_id"].duplicated().sum()
    note("Duplicate encounter_id", dup, "should be 0")

    bad_gender = df["gender"].eq("Unknown/Invalid")
    df = df[~bad_gender]
    note("Remove invalid gender", bad_gender.sum(), "gender recorded as Unknown/Invalid")

    for c in ["weight", "max_glu_serum"]:
        note(f"Drop {c}", int(df[c].isna().sum()), f"{df[c].isna().mean():.1%} missing - too sparse to use")
    df = df.drop(columns=["weight", "max_glu_serum"])

    for c, label in [("race", "Unknown"), ("payer_code", "Unknown"), ("medical_specialty", None)]:
        n = df[c].isna().sum()
        if label:
            df[c] = df[c].fillna(label)
        note(f"Missing {c}", n, f"{n/len(df):.1%} - labelled '{label}'" if label else f"{n/len(df):.1%} - grouped as 'Not recorded'")

    ints = ["admission_type_id", "discharge_disposition_id", "admission_source_id", "time_in_hospital",
            "num_lab_procedures", "num_procedures", "num_medications", "number_outpatient",
            "number_emergency", "number_inpatient", "number_diagnoses"]
    df[ints] = df[ints].astype(int)

    df["admission_type"] = df["admission_type_id"].map(ADMISSION_TYPE).fillna("Unknown")
    df["admission_source"] = df["admission_source_id"].map(ADMISSION_SOURCE).fillna("Other/Unknown")
    df["discharge_group"] = df["discharge_disposition_id"].map(DISCHARGE).fillna("Unknown")
    note("Map coded IDs to labels", len(df), "admission type, admission source, discharge disposition via IDS_mapping.csv")

    df["age_group"] = df["age"].map(AGE)
    df["age_mid"] = df["age"].map(AGE_MID)
    df["diag_group"] = df["diag_1"].map(icd9_group)
    df["specialty_group"] = df["medical_specialty"].map(specialty_group)
    note("Group primary ICD-9 diagnosis", len(df), "into 9 categories (Strack et al. 2014 scheme)")

    df["length_of_stay"] = df["time_in_hospital"]
    df["prior_visits"] = df["number_outpatient"] + df["number_emergency"] + df["number_inpatient"]
    df["prior_inpatient_band"] = pd.cut(df["number_inpatient"], [-1, 0, 1, 2, 99],
                                        labels=["0", "1", "2", "3+"]).astype(str)
    df["a1c_tested"] = df["A1Cresult"].notna()
    df["med_changed"] = df["change"].eq("Ch")
    df["expired"] = df["discharge_group"].eq("Expired")
    df["readmit_eligible"] = ~df["discharge_group"].isin(["Expired", "Hospice"])
    df["readmitted_30d"] = df["readmitted"].eq("<30") & df["readmit_eligible"]
    note("Readmission-eligible encounters", df["readmit_eligible"].sum(),
         "excludes deaths and discharges to hospice")
    note("Readmitted within 30 days", df["readmitted_30d"].sum(), "label readmitted == '<30' among eligible")
    note("Encounter is a repeat visit", df["patient_nbr"].duplicated().sum(),
         "patients with more than one encounter - model split is grouped by patient")

    cols = ["encounter_id", "patient_nbr", "race", "gender", "age", "age_group", "age_mid",
            "admission_type", "admission_source", "discharge_group", "medical_specialty", "specialty_group",
            "payer_code", "diag_1", "diag_group", "length_of_stay", "num_lab_procedures", "num_procedures",
            "num_medications", "number_diagnoses", "number_outpatient", "number_emergency", "number_inpatient",
            "prior_visits", "prior_inpatient_band", "A1Cresult", "a1c_tested", "insulin", "med_changed",
            "diabetesMed", "expired", "readmitted", "readmit_eligible", "readmitted_30d"]
    df = df[cols]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    note("Write clean file", len(df), str(OUT.relative_to(ROOT)))
    pd.DataFrame(log).to_csv(LOG, index=False)


if __name__ == "__main__":
    main()
