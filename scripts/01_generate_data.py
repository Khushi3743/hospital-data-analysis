"""
01_generate_data.py
Generates a SYNTHETIC, fully de-identified hospital admissions dataset.

No real patient data is used. Relationships (e.g. older patients with more
comorbidities stay longer and are readmitted more) are built in so the analysis
has realistic patterns to find. Data-quality problems (duplicates, missing
values, inconsistent labels, bad dates, outliers) are injected on purpose so
the cleaning step mirrors real-world work.

Output: data/raw/hospital_admissions_raw.csv
"""
from pathlib import Path
import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "hospital_admissions_raw.csv"

N_PATIENTS = 7200
START, END = pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31")

# diagnosis -> (department, base LOS median days, base readmit prob, procedure cost INR)
DIAGNOSES = {
    "Heart Failure":           ("Cardiology",       5.5, 0.20, 45000),
    "Acute Myocardial Infarction": ("Cardiology",   4.5, 0.15, 160000),
    "Arrhythmia":              ("Cardiology",       2.5, 0.09, 30000),
    "Pneumonia":               ("General Medicine", 4.5, 0.14, 12000),
    "COPD Exacerbation":       ("Pulmonology",      4.0, 0.19, 10000),
    "Asthma":                  ("Pulmonology",      2.0, 0.07, 6000),
    "Diabetes Complications":  ("Endocrinology",    3.5, 0.15, 15000),
    "Sepsis":                  ("General Medicine", 7.5, 0.18, 55000),
    "Stroke":                  ("Neurology",        6.5, 0.13, 70000),
    "Hip/Knee Replacement":    ("Orthopedics",      3.0, 0.05, 210000),
    "Fracture":                ("Orthopedics",      3.5, 0.06, 65000),
    "Appendicitis":            ("General Surgery",  2.5, 0.04, 55000),
    "Gallbladder Disease":     ("General Surgery",  2.0, 0.05, 60000),
    "Kidney Disease":          ("Nephrology",       4.5, 0.17, 25000),
    "Normal Delivery":         ("Obstetrics",       2.0, 0.02, 25000),
    "C-Section":               ("Obstetrics",       3.5, 0.04, 70000),
}
DEPT_DAILY_RATE = {  # room + nursing + routine care, INR per day
    "Cardiology": 9000, "General Medicine": 5500, "Pulmonology": 6000,
    "Endocrinology": 5500, "Neurology": 8000, "Orthopedics": 7000,
    "General Surgery": 7000, "Nephrology": 6500, "Obstetrics": 5000,
}
DIAG_NAMES = list(DIAGNOSES)


def diagnosis_probs(age, gender):
    w = np.ones(len(DIAG_NAMES))
    for i, d in enumerate(DIAG_NAMES):
        if d in ("Normal Delivery", "C-Section"):
            w[i] = 0 if (gender != "Female" or not 18 <= age <= 42) else 6
        elif d in ("Heart Failure", "Acute Myocardial Infarction", "Stroke",
                   "COPD Exacerbation", "Kidney Disease", "Hip/Knee Replacement"):
            w[i] = 0.2 + max(0, age - 40) / 12
        elif d in ("Appendicitis", "Asthma"):
            w[i] = 2.5 if age < 40 else 0.6
        elif d == "Fracture":
            w[i] = 1.5 if (age < 30 or age > 70) else 0.8
    return w / w.sum()


def make_patients():
    age = np.clip(RNG.gamma(4.5, 11.5, N_PATIENTS), 0, 98).astype(int)
    age = np.where(RNG.random(N_PATIENTS) < 0.04, RNG.integers(0, 15, N_PATIENTS), age)
    gender = RNG.choice(["Male", "Female"], N_PATIENTS, p=[0.48, 0.52])
    insurance = RNG.choice(["Private", "Government Scheme", "Self-Pay", "Corporate"],
                           N_PATIENTS, p=[0.34, 0.38, 0.16, 0.12])
    comorb = np.clip(RNG.poisson(np.maximum(0.2, (age - 20) / 22)), 0, 8)
    return pd.DataFrame({"patient_id": [f"P{100000+i}" for i in range(N_PATIENTS)],
                         "base_age": age, "gender": gender,
                         "insurance_type": insurance, "comorbidity_count": comorb})


def simulate_stay(p, age, adm_date, prior_n, chronic_diag=None):
    if chronic_diag is not None and RNG.random() < 0.65:
        diag = chronic_diag  # readmissions often for the same condition
    else:
        diag = RNG.choice(DIAG_NAMES, p=diagnosis_probs(age, p.gender))
    dept, los_med, readmit_base, proc_cost = DIAGNOSES[diag]

    elective_diags = ("Hip/Knee Replacement", "Gallbladder Disease", "C-Section")
    if diag in elective_diags:
        adm_type = RNG.choice(["Elective", "Urgent", "Emergency"], p=[0.7, 0.2, 0.1])
    else:
        adm_type = RNG.choice(["Emergency", "Urgent", "Elective"], p=[0.62, 0.28, 0.10])
    source = {"Emergency": RNG.choice(["Emergency Dept", "Transfer"], p=[0.88, 0.12]),
              "Urgent": RNG.choice(["Physician Referral", "Emergency Dept", "Transfer"], p=[0.6, 0.3, 0.1]),
              "Elective": "Physician Referral"}[adm_type]

    los_factor = (1 + 0.012 * max(0, age - 50)) * (1 + 0.09 * p.comorbidity_count) \
        * (1.15 if adm_type == "Emergency" else 1.0) * (1.1 if prior_n >= 2 else 1.0)
    los = max(0, int(round(RNG.lognormal(np.log(los_med * los_factor), 0.45))))
    if diag in ("Normal Delivery",) and los > 4:
        los = RNG.integers(1, 4)

    icu = RNG.random() < {"Sepsis": .45, "Acute Myocardial Infarction": .40, "Stroke": .30,
                          "Heart Failure": .15}.get(diag, .03)
    icu_days = int(min(los, RNG.integers(1, 5))) if icu else 0

    # discharge disposition
    if age >= 75 and los > 6 and RNG.random() < 0.35:
        disp = "Skilled Nursing/Rehab"
    else:
        disp = RNG.choice(["Home", "Home with Care", "Skilled Nursing/Rehab", "Left Against Advice"],
                          p=[0.74, 0.14, 0.08, 0.04])
    mort_p = {"Sepsis": .07, "Stroke": .05, "Acute Myocardial Infarction": .04,
              "Heart Failure": .03}.get(diag, .003) * (1.8 if age > 75 else 1)
    if RNG.random() < mort_p:
        disp = "Expired"

    cost = (DEPT_DAILY_RATE[dept] * max(los, 1) + icu_days * 28000 + proc_cost
            + RNG.normal(0, 0.08) * proc_cost + 2500 * p.comorbidity_count)
    cost *= {"Private": 1.12, "Corporate": 1.10, "Self-Pay": 0.95, "Government Scheme": 0.85}[p.insurance_type]
    cost = round(max(cost, 3000), -1)

    # probability of a 30-day readmission
    pr = readmit_base * (1 + 0.012 * max(0, age - 55)) * (1 + 0.14 * p.comorbidity_count) \
        * (1 + 0.25 * min(prior_n, 4)) * (2.2 if disp == "Left Against Advice" else 1) \
        * (1.25 if disp == "Skilled Nursing/Rehab" else 1) * (1.15 if los <= 1 and adm_type == "Emergency" else 1)
    pr = min(pr * 0.62, 0.6)
    chronic = diag if diag in ("Heart Failure", "COPD Exacerbation", "Kidney Disease",
                               "Diabetes Complications", "Sepsis") else None
    return dict(primary_diagnosis=diag, department=dept, admission_type=adm_type,
                admission_source=source, length_of_stay=los, icu_days=icu_days,
                discharge_disposition=disp, total_cost=cost), pr, chronic


def main():
    patients = make_patients()
    rows = []
    span = (END - START).days
    for p in patients.itertuples():
        # seasonality: more admissions in winter months
        while True:
            d = START + pd.Timedelta(days=int(RNG.integers(0, span)))
            if RNG.random() < (1.25 if d.month in (12, 1, 2) else 0.85 if d.month in (5, 6) else 1.0) / 1.25:
                break
        adm, prior_n, chronic = d, 0, None
        while adm <= END:
            age = int(p.base_age + (adm - START).days / 365)
            stay, pr, chronic_new = simulate_stay(p, age, adm, prior_n, chronic)
            chronic = chronic_new or chronic
            dis = adm + pd.Timedelta(days=stay["length_of_stay"])
            rows.append(dict(patient_id=p.patient_id, admission_date=adm, discharge_date=dis,
                             age=age, gender=p.gender, insurance_type=p.insurance_type,
                             comorbidity_count=p.comorbidity_count,
                             prior_admissions_12m=prior_n, **stay))
            if stay["discharge_disposition"] == "Expired":
                break
            prior_n += 1
            if RNG.random() < pr:
                adm = dis + pd.Timedelta(days=int(RNG.integers(2, 31)))
            elif RNG.random() < 0.22 + 0.04 * p.comorbidity_count:
                adm = dis + pd.Timedelta(days=int(RNG.integers(31, 330)))
            else:
                break

    df = pd.DataFrame(rows).sort_values("admission_date").reset_index(drop=True)
    df.insert(0, "admission_id", [f"A{200000+i}" for i in range(len(df))])
    df = df.drop(columns=["length_of_stay"])  # analysts must derive LOS from dates
    # prior admissions in 12 months should not be known perfectly -> keep, but it is recomputed in cleaning
    df = df.drop(columns=["prior_admissions_12m"])

    df = inject_quality_issues(df)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df):,} rows -> {OUT.relative_to(ROOT)}")


def inject_quality_issues(df):
    n = len(df)
    df = df.copy()
    df["admission_date"] = df["admission_date"].dt.strftime("%Y-%m-%d")
    df["discharge_date"] = df["discharge_date"].dt.strftime("%Y-%m-%d")
    df["age"] = df["age"].astype("object")
    df["total_cost"] = df["total_cost"].astype("object")

    # inconsistent gender labels
    idx = RNG.choice(n, int(n * 0.12), replace=False)
    df.loc[idx, "gender"] = df.loc[idx, "gender"].map(
        lambda g: RNG.choice(["M", "male", "MALE"]) if g == "Male" else RNG.choice(["F", "female", "Female "]))
    # inconsistent department labels
    idx = RNG.choice(n, int(n * 0.06), replace=False)
    df.loc[idx, "department"] = df.loc[idx, "department"].map(
        lambda s: RNG.choice([s.lower(), s.upper(), f" {s} ", s.replace("General ", "Gen. ")]))
    # dates in a different format for one data feed
    idx = RNG.choice(n, int(n * 0.05), replace=False)
    df.loc[idx, "admission_date"] = pd.to_datetime(df.loc[idx, "admission_date"]).dt.strftime("%d/%m/%Y")
    # missing values
    for col, frac in [("age", .02), ("total_cost", .015), ("insurance_type", .03),
                      ("discharge_disposition", .01), ("admission_source", .02)]:
        idx = RNG.choice(n, int(n * frac), replace=False)
        df.loc[idx, col] = np.nan
    # cost stored as text with currency/commas
    idx = RNG.choice(df.index[df["total_cost"].notna()], int(n * 0.04), replace=False)
    df.loc[idx, "total_cost"] = df.loc[idx, "total_cost"].map(lambda c: f"Rs {float(c):,.0f}")
    # impossible ages (typos)
    idx = RNG.choice(df.index[df["age"].notna()], 12, replace=False)
    df.loc[idx, "age"] = RNG.choice([150, 199, -1, 230], 12)
    # discharge before admission (data entry swap)
    idx = RNG.choice(df.index[df["admission_date"].str.contains("-")], 15, replace=False)
    df.loc[idx, ["admission_date", "discharge_date"]] = df.loc[idx, ["discharge_date", "admission_date"]].values
    # mis-keyed cost outliers (extra zero)
    idx = RNG.choice(df.index[df["total_cost"].map(lambda v: isinstance(v, (int, float)) and v == v)], 8, replace=False)
    df.loc[idx, "total_cost"] = df.loc[idx, "total_cost"].astype(float) * 10
    # exact duplicate rows (double-loaded records)
    dups = df.sample(int(n * 0.015), random_state=7)
    df = pd.concat([df, dups]).sample(frac=1, random_state=1).reset_index(drop=True)
    return df


if __name__ == "__main__":
    main()
