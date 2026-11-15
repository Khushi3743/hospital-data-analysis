# Power BI Build Guide — Hospital Performance Dashboard

Time needed: about 2–3 hours. Tool: Power BI Desktop (free, Windows).
Target numbers to check against are at the bottom — if your cards match, the build is right.

## 1. Load and prepare the data (Power Query)
1. **Home → Get data → Text/CSV** → `data/processed/hospital_admissions_clean.csv` → **Transform Data**.
2. Rename the query to `Admissions`.
3. Set column types:
   - `admission_date`, `discharge_date` → Date
   - `age`, `comorbidity_count`, `prior_admissions_12m`, `length_of_stay`, `icu_days`, `admission_year` → Whole number
   - `total_cost`, `cost_per_day` → Decimal number (blanks stay blank — do **not** replace with 0)
   - `readmitted_30d`, `readmit_eligible`, `high_cost`, `age_imputed`, `cost_corrected` → True/False
4. **Close & Apply**.
5. **Modeling → New table** → paste the `Calendar` table from `DAX_measures.dax`. Mark it as a date table (*Table tools → Mark as date table*, column `Date`).
6. **Model view**: drag `Calendar[Date]` onto `Admissions[admission_date]` (one-to-many, single direction).
7. Sort-by columns: `Calendar[Month]` by `Month No`; `Calendar[Weekday]` by `Weekday No`. The `age_group` labels (0-17, 18-34 … 80+) already sort correctly alphabetically.

## 2. Add measures
Create a blank table `_Measures` (*Enter data* → one empty column → load) and add every measure from `DAX_measures.dax` into it (*New measure* → paste). Format:
- `% ` measures → Percentage, 1 decimal
- Cost measures → Currency ₹ (*Format → Currency → ₹ English (India)*), 0 decimals
- `Avg LOS` → Decimal, 1 decimal

## 3. Theme
*View → Themes → Customize*: primary `#2A6F97`, accent/alert `#C8553D`, neutral `#9AA5B1`, background `#F7F9FB`. Font Segoe UI. Keep the rest neutral — colour should only highlight problems.

## 4. Pages

### Page 1 — Overview ("How are we doing?")
| Visual | Fields |
|---|---|
| 5 × Card (top row) | `Admissions`, `Avg LOS`, `Readmission Rate %`, `Avg Cost per Stay`, `Mortality %` |
| Line chart | X `Calendar[Year-Month]`, Y `Admissions`; secondary Y `Readmission Rate %` |
| Clustered bar | Y `department`, X `Total Cost (Cr)` sorted desc |
| Donut (or 100% bar) | Legend `admission_type`, Values `Admissions` |
| Slicers (left rail) | `Calendar[Year]`, `department`, `age_group`, `gender`, `insurance_type` |
| Text box | 3 key insights (copy from the report) |

### Page 2 — Length of Stay
| Visual | Fields |
|---|---|
| Column chart | X `age_group`, Y `Avg LOS` |
| Bar chart | Y `primary_diagnosis`, X `Avg LOS`, sort desc; reference line = hospital average (*Analytics pane → Constant line 6.4*) |
| Column chart | X `los_band`, Y `Admissions` (distribution) |
| Matrix | Rows `department`, Columns `admission_type`, Values `Avg LOS` with colour-scale background |

### Page 3 — Readmissions
| Visual | Fields |
|---|---|
| Card | `Readmission Rate %`, `Readmissions` |
| Bar chart | Y `primary_diagnosis`, X `Readmission Rate %`; *Format → Bars → Colour → fx → Field value → `Readmission Flag Colour`* |
| Column chart | X `age_group`, Y `Readmission Rate %` |
| Column chart | X `prior_admissions_12m` (group 3+ via *New group*), Y `Readmission Rate %` |
| Bar chart | Y `discharge_disposition`, X `Readmission Rate %` |
| Table | `primary_diagnosis`, `Eligible Stays`, `Readmissions`, `Readmission Rate %`, `Readmission Rate vs Hospital` |

### Page 4 — Cost
| Visual | Fields |
|---|---|
| Cards | `Total Cost (Cr)`, `Avg Cost per Day`, `High-Cost Share of Spend %` |
| Treemap | Group `department`, Details `primary_diagnosis`, Values `Total Cost` |
| Scatter | X `Avg LOS`, Y `Avg Cost per Stay`, Size `Admissions`, Legend/Details `primary_diagnosis` |
| Bar chart | Y `insurance_type`, X `Avg Cost per Stay` |
| Clustered column | X `admission_type`, Y `Avg Cost per Stay` and `Avg Cost per Day` |

### Page 5 — Demographics & Admissions
| Visual | Fields |
|---|---|
| Column | X `age_group`, Y `Admissions`, Legend `gender` |
| Column | X `Calendar[Month]`, Y `Admissions` (seasonality) |
| Column | X `Calendar[Weekday]`, Y `Admissions` |
| Bar | Y `admission_source`, X `Admissions` |

## 5. Interactions & polish
- *Format → Edit interactions*: make the slicers filter every page (*View → Sync slicers*).
- Add a **drill-through** page "Diagnosis detail": drill-through field `primary_diagnosis`, show its KPIs, LOS distribution and monthly trend.
- Tooltips: add `Admissions` and `Readmission Rate %` to every bar chart tooltip.
- Add a small footer text box on each page: *"Synthetic, de-identified data · 2023–24 · patterns are associations, not causes."*

## 6. Validation — your cards should show (no filters)
| Measure | Expected |
|---|---|
| Admissions | 10,209 |
| Unique Patients | 7,200 |
| Avg LOS | 6.37 days (median 5) |
| Readmission Rate % | 13.4% (1,264 of 9,412 eligible stays) |
| Avg Cost per Stay | ₹1,08,971 |
| Total Cost (Cr) | ₹109.58 Cr |
| Mortality % | 1.67% |
| Cardiology share of cost | 29.6% |
| Heart Failure readmission rate | 26.8% |

If a number differs, check (1) booleans were typed True/False, (2) blank costs were not replaced with 0, (3) `Readmission Rate %` divides by **eligible** stays, not all stays.

## 7. Publish / share
*File → Export → PDF* for the report appendix, and take screenshots of each page for your GitHub README (`reports/figures/powerbi_*.png`). If you have a work/school account, *Publish → My workspace* gives you a shareable link.

---

## Tableau equivalent (optional comparison)
Calculated fields:
```
Readmission Rate     SUM(IF [Readmitted 30D] THEN 1 ELSE 0 END) / SUM(IF [Readmit Eligible] THEN 1 ELSE 0 END)
Avg LOS              AVG([Length Of Stay])
Total Cost (Cr)      SUM([Total Cost]) / 10000000
Cost Share           SUM([Total Cost]) / TOTAL(SUM([Total Cost]))     // table calc
Above Avg Readmit    [Readmission Rate] >= 1.5 * {FIXED : SUM(IF [Readmitted 30D] THEN 1 ELSE 0 END) / SUM(IF [Readmit Eligible] THEN 1 ELSE 0 END)}
```
Build the same five sheets, combine into a dashboard with filters set to *Apply to all worksheets using this data source*.
