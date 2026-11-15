"""Builds notebooks/hospital_analysis.ipynb from cells below (run, then execute with nbconvert)."""
import nbformat as nbf
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Hospital Data Analysis — Length of Stay, Readmissions & Cost

**Goal:** answer practical hospital-management questions from de-identified admissions data and feed a dashboard.

| # | Business question |
|---|---|
| Q1 | How is the hospital doing at a glance? (admissions, average stay, readmission rate, cost) |
| Q2 | Who is being admitted, and when? |
| Q3 | Which patient groups and conditions stay longer? |
| Q4 | Which patients are more likely to return within 30 days? |
| Q5 | Which departments, conditions and admission types cost the most? |

> **Data & ethics:** the dataset is synthetic and fully de-identified (see `data/DATA_DICTIONARY.md`). Findings describe patterns in data — not medical advice and not proof of cause.
""")

code("""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
FIG = ROOT / "reports" / "figures"; FIG.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "data" / "processed"

sns.set_theme(style="whitegrid", context="notebook")
BLUE, GREY, RED = "#2a6f97", "#9aa5b1", "#c8553d"
plt.rcParams.update({"figure.dpi": 110, "axes.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False})

def save(fig, name):
    fig.tight_layout(); fig.savefig(FIG / f"{name}.png", dpi=150, bbox_inches="tight")

df = pd.read_csv(OUT / "hospital_admissions_clean.csv", parse_dates=["admission_date", "discharge_date"])
elig = df[df.readmit_eligible]
print(f"{len(df):,} admissions | {df.patient_id.nunique():,} patients | {df.admission_date.min():%d %b %Y} – {df.admission_date.max():%d %b %Y}")
df.head()
""")

md("## 0. Data quality — what cleaning changed")
code("""
log = pd.read_csv(OUT / "cleaning_log.csv")
log
""")
code("""
# Remaining checks after cleaning
checks = {
    "duplicate admission_id": int(df.admission_id.duplicated().sum()),
    "negative length of stay": int((df.length_of_stay < 0).sum()),
    "missing total_cost (excluded from cost metrics)": int(df.total_cost.isna().sum()),
    "ages imputed": int(df.age_imputed.sum()),
    "readmission-eligible stays": int(df.readmit_eligible.sum()),
    "class balance: readmitted (%)": round(elig.readmitted_30d.mean() * 100, 1),
}
pd.Series(checks, name="value").to_frame()
""")
md("""
**Class imbalance note:** only ~13% of eligible stays are readmissions. Any model or comparison must look at rates within groups, not raw counts, and accuracy alone would be misleading (predicting "no readmission" for everyone is ~87% accurate).
""")

md("## Q1. Hospital performance at a glance")
code("""
kpi = {
    "admissions": len(df),
    "unique_patients": df.patient_id.nunique(),
    "avg_los_days": round(df.length_of_stay.mean(), 2),
    "median_los_days": float(df.length_of_stay.median()),
    "readmission_rate_30d_pct": round(elig.readmitted_30d.mean() * 100, 1),
    "avg_cost_per_stay_inr": round(df.total_cost.mean()),
    "total_cost_inr_crore": round(df.total_cost.sum() / 1e7, 2),
    "mortality_pct": round((df.discharge_disposition == "Expired").mean() * 100, 2),
    "emergency_share_pct": round((df.admission_type == "Emergency").mean() * 100, 1),
}
by_year = df.groupby("admission_year").agg(admissions=("admission_id", "size"), avg_los=("length_of_stay", "mean"),
                                           avg_cost=("total_cost", "mean")).round(2)
by_year["readmit_rate_pct"] = (elig.groupby("admission_year").readmitted_30d.mean() * 100).round(1)
json.dump(kpi, open(OUT / "kpis.json", "w"), indent=2)
display(pd.Series(kpi).to_frame("value")); by_year
""")

md("## Q2. Who is admitted, and when?")
code("""
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ag = df.age_group.value_counts().reindex(["0-17","18-34","35-49","50-64","65-79","80+"])
ag.plot.bar(ax=ax[0], color=BLUE); ax[0].set(title="Admissions by age group", xlabel="", ylabel="Admissions"); ax[0].tick_params(axis="x", rotation=0)
m = df.groupby(df.admission_date.dt.to_period("M")).size(); m.index = m.index.to_timestamp()
ax[1].plot(m.index, m.values, color=BLUE, marker="o", ms=3); ax[1].set(title="Monthly admissions", ylabel="Admissions")
save(fig, "q2_admissions_age_month")
""")
code("""
season = df.groupby(df.admission_date.dt.month).size() / 2  # 2 years -> avg per month
wd = df.admission_weekday.value_counts().reindex(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"])
mix = pd.crosstab(df.department, df.admission_type, normalize="index").mul(100).round(1)
print("Avg admissions by calendar month:", season.round(0).astype(int).to_dict())
print("Winter (Dec-Feb) vs summer (May-Jun) avg/month:",
      round(season[[12,1,2]].mean()), "vs", round(season[[5,6]].mean()))
display(df.gender.value_counts(normalize=True).mul(100).round(1).to_frame("% of admissions"))
display(df.admission_source.value_counts(normalize=True).mul(100).round(1).to_frame("% of admissions"))
mix
""")

md("## Q3. Which patient groups and conditions stay longer?")
code("""
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
ax[0].hist(df.length_of_stay.clip(upper=30), bins=30, color=BLUE)
ax[0].axvline(df.length_of_stay.mean(), color=RED, ls="--", label=f"Mean {df.length_of_stay.mean():.1f}")
ax[0].axvline(df.length_of_stay.median(), color="k", ls=":", label=f"Median {df.length_of_stay.median():.0f}")
ax[0].set(title="Length of stay distribution (capped at 30)", xlabel="Days", ylabel="Stays"); ax[0].legend()
los_age = df.groupby("age_group").length_of_stay.agg(["mean","median"]).reindex(["0-17","18-34","35-49","50-64","65-79","80+"])
los_age["mean"].plot.bar(ax=ax[1], color=BLUE); ax[1].set(title="Average stay by age group", xlabel="", ylabel="Days"); ax[1].tick_params(axis="x", rotation=0)
save(fig, "q3_los_distribution_age")
los_age.round(2)
""")
code("""
los_diag = df.groupby("primary_diagnosis").agg(stays=("admission_id","size"), avg_los=("length_of_stay","mean"),
                                               median_los=("length_of_stay","median"), pct_icu=("icu_days", lambda s: (s>0).mean()*100)
                                               ).sort_values("avg_los", ascending=False).round(1)
fig, ax = plt.subplots(figsize=(8, 5.5))
ax.barh(los_diag.index[::-1], los_diag.avg_los[::-1], color=[RED if v >= los_diag.avg_los.quantile(.75) else BLUE for v in los_diag.avg_los[::-1]])
ax.axvline(df.length_of_stay.mean(), color="k", ls="--", lw=1); ax.set(title="Average length of stay by diagnosis", xlabel="Days")
save(fig, "q3_los_by_diagnosis")
los_diag.to_csv(OUT / "summary_los_by_diagnosis.csv"); los_diag
""")
code("""
display(df.groupby("admission_type").length_of_stay.agg(["mean","median","size"]).round(2))
display(df.groupby("comorbidity_band").length_of_stay.agg(["mean","median","size"]).round(2))
# Adjusted view: does age still matter once diagnosis, comorbidities and admission type are held constant?
los_model = smf.ols("np.log1p(length_of_stay) ~ C(age_group, Treatment('35-49')) + comorbidity_count + C(admission_type) + C(primary_diagnosis)", data=df).fit()
eff = (np.exp(los_model.params[[i for i in los_model.params.index if ("age_group" in i or "comorbidity" in i or "admission_type" in i)]]) - 1).mul(100).round(1)
print(f"R² = {los_model.rsquared:.2f}. % change in length of stay (approx), holding diagnosis constant:")
eff.to_frame("% change vs baseline")
""")

md("## Q4. Who is more likely to be readmitted within 30 days?")
code("""
def rate(col, order=None):
    t = elig.groupby(col).agg(stays=("readmitted_30d","size"), readmissions=("readmitted_30d","sum"))
    t["rate_pct"] = (t.readmissions / t.stays * 100).round(1)
    return t.reindex(order) if order else t.sort_values("rate_pct", ascending=False)

r_diag = rate("primary_diagnosis"); r_diag.to_csv(OUT / "summary_readmit_by_diagnosis.csv")
overall = elig.readmitted_30d.mean() * 100
fig, ax = plt.subplots(figsize=(8, 5.5))
ax.barh(r_diag.index[::-1], r_diag.rate_pct[::-1], color=[RED if v > overall*1.5 else BLUE for v in r_diag.rate_pct[::-1]])
ax.axvline(overall, color="k", ls="--", lw=1, label=f"Hospital {overall:.1f}%"); ax.legend(loc="lower right")
ax.set(title="30-day readmission rate by diagnosis", xlabel="% of eligible stays")
save(fig, "q4_readmit_by_diagnosis")
r_diag
""")
code("""
elig = elig.assign(prior_band=pd.cut(elig.prior_admissions_12m, [-1,0,1,2,99], labels=["0","1","2","3+"]).astype(str))
fig, ax = plt.subplots(1, 3, figsize=(15, 4))
for a, (col, order, title) in zip(ax, [("age_group", ["0-17","18-34","35-49","50-64","65-79","80+"], "by age group"),
                                      ("prior_band", ["0","1","2","3+"], "by admissions in prior 12 months"),
                                      ("discharge_disposition", None, "by discharge type")]):
    t = rate(col, order); t = t[t.index != "Unknown"]
    a.bar(t.index.astype(str), t.rate_pct, color=BLUE); a.axhline(overall, color="k", ls="--", lw=1)
    a.set(title=f"Readmission rate {title}", ylabel="%"); a.tick_params(axis="x", rotation=25 if col=="discharge_disposition" else 0)
save(fig, "q4_readmit_drivers")
display(rate("age_group", ["0-17","18-34","35-49","50-64","65-79","80+"]))
display(rate("prior_band", ["0","1","2","3+"]))
rate("discharge_disposition")
""")
code("""
# Which factors matter when looked at together? Logistic regression (association, not causation)
m = smf.logit("readmitted_30d ~ age + comorbidity_count + prior_admissions_12m + length_of_stay + C(admission_type) "
              "+ C(discharge_disposition, Treatment('Home')) + C(insurance_type)",
              data=elig[elig.discharge_disposition != "Unknown"].assign(readmitted_30d=lambda d: d.readmitted_30d.astype(int))).fit(disp=0)
ci = np.exp(m.conf_int()); orr = pd.DataFrame({"odds_ratio": np.exp(m.params), "ci_low": ci[0], "ci_high": ci[1], "p_value": m.pvalues}).drop("Intercept").round(3)
orr.to_csv(OUT / "readmission_odds_ratios.csv")
print(f"Pseudo R² = {m.prsquared:.3f}  (n = {int(m.nobs):,})")
orr.sort_values("odds_ratio", ascending=False)
""")
code("""
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
d = elig[elig.discharge_disposition != "Unknown"].assign(y=lambda x: x.readmitted_30d.astype(int))
tr, te = train_test_split(d, test_size=0.3, random_state=0, stratify=d.y)
mm = smf.logit("y ~ age + comorbidity_count + prior_admissions_12m + length_of_stay + C(admission_type) + C(discharge_disposition) + C(primary_diagnosis)", data=tr).fit(disp=0)
p = mm.predict(te); auc = roc_auc_score(te.y, p)
te = te.assign(risk=p, decile=pd.qcut(p, 10, labels=False, duplicates="drop"))
top = te[te.decile == te.decile.max()]
print(f"Hold-out AUC = {auc:.2f}. Top-10% risk group readmission rate = {top.y.mean()*100:.1f}% vs {te.y.mean()*100:.1f}% overall; "
      f"it contains {top.y.sum()/te.y.sum()*100:.0f}% of all readmissions.")
json.dump({"auc": round(auc, 3), "top_decile_rate_pct": round(top.y.mean()*100, 1),
           "top_decile_share_of_readmissions_pct": round(top.y.sum()/te.y.sum()*100, 1)}, open(OUT / "risk_model.json", "w"), indent=2)
""")

md("## Q5. Where does the money go?")
code("""
cost_dept = df.groupby("department").agg(stays=("admission_id","size"), total_cost_cr=("total_cost", lambda s: s.sum()/1e7),
                                         avg_cost=("total_cost","mean"), avg_cost_per_day=("cost_per_day","mean"),
                                         avg_los=("length_of_stay","mean")).sort_values("total_cost_cr", ascending=False).round(2)
cost_dept["share_of_total_pct"] = (cost_dept.total_cost_cr / cost_dept.total_cost_cr.sum() * 100).round(1)
cost_dept.to_csv(OUT / "summary_cost_by_department.csv")
fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
ax[0].barh(cost_dept.index[::-1], cost_dept.total_cost_cr[::-1], color=BLUE); ax[0].set(title="Total cost by department (₹ crore)", xlabel="₹ crore")
ax[1].barh(cost_dept.index[::-1], cost_dept.avg_cost[::-1]/1000, color=GREY); ax[1].set(title="Average cost per stay (₹ thousand)", xlabel="₹ thousand")
save(fig, "q5_cost_by_department")
cost_dept
""")
code("""
cost_diag = df.groupby("primary_diagnosis").agg(stays=("admission_id","size"), avg_cost=("total_cost","mean"),
                                                total_cost_cr=("total_cost", lambda s: s.sum()/1e7)).sort_values("total_cost_cr", ascending=False).round(1)
cost_diag.to_csv(OUT / "summary_cost_by_diagnosis.csv")
display(cost_diag.head(8))
display(df.groupby("admission_type").agg(avg_cost=("total_cost","mean"), avg_cost_per_day=("cost_per_day","mean")).round(0))
hc = df.groupby("high_cost").agg(share_stays=("admission_id","size"), cost=("total_cost","sum"), avg_los=("length_of_stay","mean"),
                                 pct_icu=("icu_days", lambda s: (s>0).mean()*100), avg_age=("age","mean"))
hc["share_stays"] = (hc.share_stays / hc.share_stays.sum() * 100).round(1); hc["share_cost"] = (hc.cost / hc.cost.sum() * 100).round(1)
print("High-cost stays (top 10%) vs the rest:")
hc.drop(columns="cost").round(1)
""")
code("""
icu = df.assign(icu=df.icu_days > 0).groupby("icu").agg(stays=("admission_id","size"), avg_cost=("total_cost","mean"), avg_los=("length_of_stay","mean")).round(0)
readmit_cost = df[df.readmitted_30d].total_cost.sum()  # cost of index stays that were followed by readmission
next_cost = df.sort_values("admission_date").groupby("patient_id").total_cost.shift(-1)[df.readmitted_30d].sum()
print(f"Cost of readmission stays (the return visits): ₹{next_cost/1e7:.2f} crore "
      f"= {next_cost/df.total_cost.sum()*100:.1f}% of total spend")
json.dump({"readmission_stay_cost_cr": round(next_cost/1e7, 2), "readmission_cost_share_pct": round(next_cost/df.total_cost.sum()*100, 1)},
          open(OUT / "readmission_cost.json", "w"), indent=2)
icu
""")

md("## Key findings (generated from the numbers above)")
code("""
k = kpi; top_los = los_diag.index[:3].tolist(); top_r = r_diag.index[:3].tolist(); top_c = cost_dept.index[:2].tolist()
r_age = rate("age_group"); r_prior = rate("prior_band")
findings = [
 f"The hospital handled {k['admissions']:,} admissions from {k['unique_patients']:,} patients in 2023–24; average stay {k['avg_los_days']} days (median {k['median_los_days']:.0f}), "
 f"30-day readmission rate {k['readmission_rate_30d_pct']}%, average cost ₹{k['avg_cost_per_stay_inr']:,} per stay.",
 f"Stay length rises steadily with age: {los_age.loc['80+','mean']:.1f} days for 80+ vs {los_age.loc['18-34','mean']:.1f} for 18–34. Longest-stay conditions: {', '.join(top_los)}.",
 f"Readmissions concentrate in chronic conditions — {', '.join(top_r)} — each well above the {overall:.1f}% average.",
 f"Patients with 3+ admissions in the prior year are readmitted at {r_prior.loc['3+','rate_pct']}% vs {r_prior.loc['0','rate_pct']}% for first-time patients; "
 f"those who left against medical advice at {rate('discharge_disposition').loc['Left Against Advice','rate_pct']}%.",
 f"{top_c[0]} and {top_c[1]} account for {cost_dept.share_of_total_pct.iloc[:2].sum():.0f}% of total cost. The top 10% most expensive stays take {hc.loc[True,'share_cost']}% of spend.",
]
for i, f in enumerate(findings, 1): print(f"{i}. {f}")
""")
md("""
### Recommendations (for a hospital manager)
1. **Targeted discharge follow-up** for heart failure, COPD and kidney disease patients and anyone with 2+ admissions in the past year — e.g. a phone call within 72 hours and an early clinic slot. These groups are a small share of patients but a large share of readmissions.
2. **Reduce "left against advice" discharges**: review why patients leave early (cost, waiting, communication); this group is readmitted at roughly twice the average rate.
3. **Plan beds for the December peak**: December admissions run ~25% above the monthly average, while March–June is the quietest stretch; shift elective procedures and leave toward the quieter months.
4. **Review long stays in elderly patients**: early discharge planning and rehab coordination for 65+ patients, where stays are longest.
5. **Cost focus on Cardiology and Orthopedics**: review ICU use and implant/procedure costs, which drive the high-cost tail.

*Caveat: synthetic data; associations only. A real deployment would need clinical review and validation on real, governed data.*
""")

nb["cells"] = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, ROOT / "notebooks" / "hospital_analysis.ipynb")
print("notebook written")
