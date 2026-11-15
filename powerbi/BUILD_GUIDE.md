# Power BI Build Guide — Hospital Readmission Dashboard (real UCI data)

Time needed: about 2–3 hours in Power BI Desktop (free, Windows). Validation targets are at the bottom.

## 1. Load and prepare (Power Query)
1. **Get data → Text/CSV** → `data/processed/hospital_encounters_clean.csv` → **Transform Data**; rename the query `Encounters`.
2. Types: `length_of_stay`, `num_*`, `number_*`, `prior_visits`, `age_mid` → Whole number; `a1c_tested`, `med_changed`, `expired`, `readmit_eligible`, `readmitted_30d` → True/False; `encounter_id`, `patient_nbr` → Text.
3. **Close & Apply**. Add the `AgeOrder` table from `DAX_measures.dax`, relate it to `Encounters[age_group]` and sort by `age_sort`.

## 2. Measures
Create a `_Measures` table and paste every measure from `DAX_measures.dax`. Format `%` measures as Percentage (1 decimal) and `Avg LOS` with 2 decimals.

## 3. Theme
Primary `#2A6F97`, alert `#C8553D`, neutral `#9AA5B1`, background `#F7F9FB`. Use colour only to flag problems.

## 4. Pages
**Overview** — cards: `Encounters`, `Unique Patients`, `Avg LOS`, `Readmission Rate %`, `HbA1c Tested %`, `Mortality %`. Bar: `diag_group` × `Encounters`. Slicers: `age_group`, `admission_type`, `gender`, `diag_group`.

**Readmissions** — column: `prior_inpatient_band` × `Readmission Rate %` (bar colour fx → `Readmission Flag Colour`); bar: `discharge_group` × `Readmission Rate %`; column: `age_group` × `Readmission Rate %`; column: `a1c_tested` × `Readmission Rate %`; table: `diag_group`, `Eligible Encounters`, `Readmissions 30d`, `Readmission Rate %`, `Readmission Rate vs Network`.

**Length of stay** — column: `age_group` × `Avg LOS` with a constant line at 4.40; bar: `diag_group` × `Avg LOS`; matrix: `admission_type` × `diag_group` with `Avg LOS` colour scale.

**Resource use** — treemap: `diag_group` × `Bed Days`; bar: `specialty_group` × `Bed Days`; scatter: `Avg LOS` vs `Readmission Rate %` by `diag_group`, size `Encounters`.

Add on every page the footer: *"UCI Diabetes 130-US Hospitals 1999–2008 (CC BY 4.0) · associations, not causes."*

## 5. Validation — cards with no filters
| Measure | Expected |
|---|---|
| Encounters | 101,763 |
| Unique Patients | 71,515 |
| Avg LOS | 4.40 days (median 4) |
| Readmission Rate % | 11.39% (11,314 of 99,340 eligible) |
| Mortality % | 1.62% |
| HbA1c Tested % | 16.7% |
| Bed Days | 447,352 |
| Readmission rate, 3+ prior inpatient stays | 26.4% |
| Readmission rate, discharged home | 9.3% |

If a number differs: check the True/False types, and that `Readmission Rate %` divides by **eligible** encounters.

## 6. Share
Export each page as an image for the GitHub README (`reports/figures/powerbi_*.png`).
