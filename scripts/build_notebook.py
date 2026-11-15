"""Builds notebooks/hospital_analysis.ipynb (run, then execute with nbconvert)."""
import nbformat as nbf
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Hospital Readmission Analysis — 101,766 Real Encounters from 130 US Hospitals

**Goal:** answer practical hospital-management questions from real, de-identified hospital data and feed a dashboard.

**Data:** *Diabetes 130-US Hospitals for Years 1999–2008* — Clore, Cios, DeShazo & Strack (2014), UCI Machine Learning Repository,
[doi:10.24432/C5230J](https://doi.org/10.24432/C5230J), licence CC BY 4.0. Each row is one inpatient encounter of a patient with diabetes (stay of 1–14 days).

| # | Business question |
|---|---|
| Q1 | How is the hospital network doing at a glance? |
| Q2 | Who is admitted, and how? |
| Q3 | Which patient groups and conditions stay longer? |
| Q4 | Which patients are more likely to be readmitted within 30 days? |
| Q5 | Where do hospital resources (bed-days, tests, medications) go? |

> Findings describe associations in observational data — not medical advice and not proof of cause.
""")

code("""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
FIG = ROOT / "reports" / "figures"; FIG.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "data" / "processed"
sns.set_theme(style="whitegrid", context="notebook")
BLUE, GREY, RED = "#2a6f97", "#9aa5b1", "#c8553d"
plt.rcParams.update({"figure.dpi": 110, "axes.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False})
def save(fig, name):
    fig.tight_layout(); fig.savefig(FIG / f"{name}.png", dpi=150, bbox_inches="tight")

df = pd.read_csv(OUT / "hospital_encounters_clean.csv", low_memory=False)
elig = df[df.readmit_eligible]
AGES = ["Under 40", "40-49", "50-59", "60-69", "70-79", "80+"]
print(f"{len(df):,} encounters | {df.patient_nbr.nunique():,} patients | {elig.readmitted_30d.sum():,} readmissions within 30 days")
df.head()
""")

md("## 0. Data quality — what cleaning changed")
code("""
pd.read_csv(OUT / "cleaning_log.csv")
""")
md("""
**Class imbalance:** only ~11% of eligible encounters are 30-day readmissions, so rates within groups (not counts) are compared,
and the model is judged by AUC and lift, not accuracy (predicting "no readmission" for everyone would be ~89% accurate).
**Repeat patients:** 30,248 encounters belong to patients seen more than once, so the model's train/test split is grouped by patient to avoid leakage.
""")

md("## Q1. At a glance")
code("""
kpi = {
    "encounters": len(df),
    "unique_patients": int(df.patient_nbr.nunique()),
    "avg_los_days": round(df.length_of_stay.mean(), 2),
    "median_los_days": float(df.length_of_stay.median()),
    "readmit_eligible": int(df.readmit_eligible.sum()),
    "readmissions_30d": int(elig.readmitted_30d.sum()),
    "readmission_rate_30d_pct": round(elig.readmitted_30d.mean() * 100, 2),
    "mortality_pct": round(df.expired.mean() * 100, 2),
    "emergency_share_pct": round((df.admission_type == "Emergency").mean() * 100, 1),
    "a1c_tested_pct": round(df.a1c_tested.mean() * 100, 1),
    "total_bed_days": int(df.length_of_stay.sum()),
    "avg_medications": round(df.num_medications.mean(), 1),
    "avg_lab_procedures": round(df.num_lab_procedures.mean(), 1),
}
json.dump(kpi, open(OUT / "kpis.json", "w"), indent=2)
pd.Series(kpi).to_frame("value")
""")

md("## Q2. Who is admitted, and how?")
code("""
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
df.age_group.value_counts().reindex(AGES).plot.bar(ax=ax[0], color=BLUE)
ax[0].set(title="Encounters by age group", xlabel="", ylabel="Encounters"); ax[0].tick_params(axis="x", rotation=0)
df.diag_group.value_counts().sort_values().plot.barh(ax=ax[1], color=BLUE)
ax[1].set(title="Encounters by primary diagnosis group", xlabel="Encounters", ylabel="")
save(fig, "q2_admissions_age_diagnosis")
for col in ["gender", "admission_type", "admission_source", "race"]:
    display(df[col].value_counts(normalize=True).mul(100).round(1).to_frame(f"% of encounters by {col}"))
""")

md("## Q3. Which patients and conditions stay longer?")
code("""
los_age = df.groupby("age_group").length_of_stay.agg(["mean", "median", "size"]).reindex(AGES)
los_diag = df.groupby("diag_group").agg(encounters=("encounter_id", "size"), avg_los=("length_of_stay", "mean"),
                                        bed_days=("length_of_stay", "sum")).sort_values("avg_los", ascending=False).round(2)
los_diag.to_csv(OUT / "summary_los_by_diagnosis.csv")
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
los_age["mean"].plot.bar(ax=ax[0], color=BLUE); ax[0].axhline(df.length_of_stay.mean(), color="k", ls="--", lw=1)
ax[0].set(title="Average length of stay by age group", xlabel="", ylabel="Days"); ax[0].tick_params(axis="x", rotation=0)
los_diag.avg_los.sort_values().plot.barh(ax=ax[1], color=BLUE); ax[1].axvline(df.length_of_stay.mean(), color="k", ls="--", lw=1)
ax[1].set(title="Average length of stay by diagnosis group", xlabel="Days", ylabel="")
save(fig, "q3_los_age_diagnosis")
display(los_age.round(2)); display(los_diag)
display(df.groupby("admission_type").length_of_stay.agg(["mean", "size"]).round(2))
los_model = smf.ols("length_of_stay ~ C(age_group, Treatment('50-59')) + C(diag_group, Treatment('Circulatory')) + C(admission_type) + number_diagnoses", data=df).fit()
print(f"OLS R² = {los_model.rsquared:.3f} — most variation in stay length is not explained by these fields.")
""")

md("## Q4. Who is readmitted within 30 days?")
code("""
overall = elig.readmitted_30d.mean() * 100
def rate(col, order=None):
    t = elig.groupby(col).agg(encounters=("readmitted_30d", "size"), readmissions=("readmitted_30d", "sum"))
    t["rate_pct"] = (t.readmissions / t.encounters * 100).round(1)
    return t.reindex(order) if order else t.sort_values("rate_pct", ascending=False)
r_prior = rate("prior_inpatient_band", ["0", "1", "2", "3+"]); r_prior.to_csv(OUT / "summary_readmit_by_prior.csv")
r_disp = rate("discharge_group"); r_disp.to_csv(OUT / "summary_readmit_by_discharge.csv")
r_diag = rate("diag_group"); r_diag.to_csv(OUT / "summary_readmit_by_diagnosis.csv")
r_age = rate("age_group", AGES)
fig, ax = plt.subplots(1, 3, figsize=(16, 4.2))
for a, (t, title) in zip(ax, [(r_prior, "by inpatient stays in prior year"), (r_disp[r_disp.encounters >= 500], "by discharge destination"), (r_age, "by age group")]):
    a.bar(t.index.astype(str), t.rate_pct, color=[RED if v >= overall * 1.4 else BLUE for v in t.rate_pct]); a.axhline(overall, color="k", ls="--", lw=1)
    a.set(title=f"30-day readmission rate {title}", ylabel="%"); a.tick_params(axis="x", rotation=25)
save(fig, "q4_readmit_drivers")
display(r_prior); display(r_disp); display(r_diag); display(r_age)
display(rate("a1c_tested")); display(rate("admission_type"))
""")

md("### Which factors matter when considered together? (logistic regression, odds ratios)")
code("""
mdf = elig[~elig.discharge_group.isin(["Other", "Unknown"])].assign(y=lambda d: d.readmitted_30d.astype(int))
logit = smf.logit("y ~ age_mid + C(gender) + number_inpatient + number_emergency + number_outpatient + length_of_stay + "
                  "num_medications + number_diagnoses + a1c_tested + med_changed + C(admission_type, Treatment('Elective')) + "
                  "C(discharge_group, Treatment('Home')) + C(diag_group, Treatment('Circulatory'))", data=mdf).fit(disp=0)
ci = np.exp(logit.conf_int())
orr = pd.DataFrame({"odds_ratio": np.exp(logit.params), "ci_low": ci[0], "ci_high": ci[1], "p_value": logit.pvalues}).drop("Intercept").round(3)
orr.to_csv(OUT / "readmission_odds_ratios.csv")
print(f"n = {int(logit.nobs):,}; pseudo R² = {logit.prsquared:.3f}")
orr.sort_values("odds_ratio", ascending=False)
""")

md("### Predicting readmission (patient-grouped train/test split)")
code("""
feats_num = ["age_mid", "length_of_stay", "num_lab_procedures", "num_procedures", "num_medications", "number_diagnoses",
             "number_outpatient", "number_emergency", "number_inpatient"]
feats_cat = ["gender", "race", "admission_type", "admission_source", "discharge_group", "diag_group", "specialty_group", "insulin"]
X = pd.get_dummies(elig[feats_num + feats_cat + ["a1c_tested", "med_changed"]], columns=feats_cat, drop_first=True).astype(float)
y = elig.readmitted_30d.astype(int).values
split = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=42)
tr, te = next(split.split(X, y, groups=elig.patient_nbr))
assert not set(elig.patient_nbr.iloc[tr]) & set(elig.patient_nbr.iloc[te])  # no patient in both sets

import statsmodels.api as sm
lr = sm.Logit(y[tr], sm.add_constant(X.iloc[tr])).fit(disp=0, maxiter=200)
p_lr = lr.predict(sm.add_constant(X.iloc[te]))
gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=42).fit(X.iloc[tr], y[tr])
p_gb = gb.predict_proba(X.iloc[te])[:, 1]
res = {}
for name, p in [("logistic_regression", p_lr), ("gradient_boosting", p_gb)]:
    dec = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
    top = y[te][dec.values == 9]
    res[name] = {"auc": round(roc_auc_score(y[te], p), 3), "top_decile_rate_pct": round(top.mean() * 100, 1),
                 "top_decile_share_pct": round(top.sum() / y[te].sum() * 100, 1),
                 "lift": round(top.mean() / y[te].mean(), 2)}
res["test_base_rate_pct"] = round(y[te].mean() * 100, 1)
res["train_encounters"], res["test_encounters"] = int(len(tr)), int(len(te))
json.dump(res, open(OUT / "risk_model.json", "w"), indent=2)
pd.DataFrame({k: v for k, v in res.items() if isinstance(v, dict)}).T
""")

md("## Q5. Where do hospital resources go?")
code("""
res_diag = df.groupby("diag_group").agg(encounters=("encounter_id", "size"), bed_days=("length_of_stay", "sum"),
                                        avg_meds=("num_medications", "mean"), avg_labs=("num_lab_procedures", "mean")).sort_values("bed_days", ascending=False)
res_diag["bed_day_share_pct"] = (res_diag.bed_days / res_diag.bed_days.sum() * 100).round(1)
res_diag = res_diag.round(1); res_diag.to_csv(OUT / "summary_resources_by_diagnosis.csv")
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.barh(res_diag.index[::-1], res_diag.bed_days[::-1] / 1000, color=[BLUE if i < 1 else GREY for i in range(len(res_diag))][::-1])
ax.set(title="Bed-days by primary diagnosis group (thousands)", xlabel="Thousand bed-days")
save(fig, "q5_bed_days_by_diagnosis")
readm_beds = df[df.readmitted == "<30"].length_of_stay.sum()
spec = df.groupby("specialty_group").agg(encounters=("encounter_id", "size"), bed_days=("length_of_stay", "sum")).sort_values("bed_days", ascending=False)
display(res_diag); display(spec)
by_prior = df.groupby("prior_inpatient_band").agg(patients_share=("encounter_id", "size"), bed_days=("length_of_stay", "sum")).reindex(["0", "1", "2", "3+"])
by_prior = (by_prior / by_prior.sum() * 100).round(1); display(by_prior)
""")

md("## Key findings (generated from the numbers above)")
code("""
k = kpi; lr_r, gb_r = res["logistic_regression"], res["gradient_boosting"]
findings = [
 f"{k['encounters']:,} encounters from {k['unique_patients']:,} patients; average stay {k['avg_los_days']} days (median {k['median_los_days']:.0f}); "
 f"30-day readmission rate {k['readmission_rate_30d_pct']}% ({k['readmissions_30d']:,} of {k['readmit_eligible']:,} eligible).",
 f"Prior inpatient use is the strongest signal: {r_prior.loc['0','rate_pct']}% readmitted with no inpatient stay in the prior year vs {r_prior.loc['3+','rate_pct']}% with 3 or more.",
 f"Discharge destination matters: {r_disp.loc['Nursing/rehab facility','rate_pct']}% for nursing/rehab facilities and {r_disp.loc['Other facility','rate_pct']}% for other facilities vs {r_disp.loc['Home','rate_pct']}% for home.",
 f"HbA1c was measured in only {k['a1c_tested_pct']}% of encounters; tested patients were readmitted at {rate('a1c_tested').loc[True,'rate_pct']}% vs {rate('a1c_tested').loc[False,'rate_pct']}%.",
 f"Circulatory conditions use {res_diag.loc['Circulatory','bed_day_share_pct']}% of all {k['total_bed_days']:,} bed-days.",
 f"Risk model (patient-grouped hold-out): logistic AUC {lr_r['auc']}, gradient boosting AUC {gb_r['auc']}; the top-risk 10% are readmitted at {gb_r['top_decile_rate_pct']}% "
 f"({gb_r['lift']}x the base rate) and hold {gb_r['top_decile_share_pct']}% of readmissions.",
]
for i, f in enumerate(findings, 1): print(f"{i}. {f}")
""")
md("""
### Recommendations
1. **Flag frequent inpatients at discharge** — patients with 2 or more inpatient stays in the past year are readmitted at 17.9–26.4%, versus 8.6% for patients with none; give them a follow-up call and an early clinic appointment.
2. **Strengthen hand-offs to nursing and rehab facilities** — these discharges are readmitted far more often than discharges home; share medication lists and a follow-up plan with the receiving facility.
3. **Measure HbA1c more consistently** — it was recorded in fewer than 1 in 5 diabetic encounters; tested patients were readmitted less often (association, consistent with Strack et al. 2014).
4. **Use the risk score to rank, not to decide** — an AUC of about 0.66 is useful for prioritising follow-up lists, not for individual clinical decisions.

*Caveats: observational data from 1999–2008; readmissions to other hospitals may be missed; associations, not causes.*
""")

nb["cells"] = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, ROOT / "notebooks" / "hospital_analysis.ipynb")
print("notebook written")
