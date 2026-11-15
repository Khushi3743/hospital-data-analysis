# Data Dictionary — `hospital_encounters_clean.csv`

**Source:** *Diabetes 130-US Hospitals for Years 1999–2008* — Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014). UCI Machine Learning Repository. https://doi.org/10.24432/C5230J. Licence: CC BY 4.0. Real, de-identified records extracted from the Cerner Health Facts database.
**Introductory paper:** Strack, B. et al. (2014). *Impact of HbA1c Measurement on Hospital Readmission Rates: Analysis of 70,000 Clinical Database Patient Records.* BioMed Research International, Article ID 781670.
**Scope:** inpatient encounters of patients with any diabetes diagnosis, with a stay of 1–14 days, lab tests performed and medication given.
**Grain:** one row = one hospital encounter. A patient can have several rows (30,248 repeat encounters).
**Size after cleaning:** 101,763 encounters, 71,515 patients (3 rows with invalid gender removed from 101,766).

| Column | Type | Description |
|---|---|---|
| encounter_id | id | Unique encounter identifier (primary key). |
| patient_nbr | id | Pseudonymous patient identifier. |
| race, gender | text | Demographics as recorded (race missing → Unknown). |
| age | text | Original 10-year band, e.g. `[70-80)`. |
| age_group | derived | Under 40, 40-49, 50-59, 60-69, 70-79, 80+. |
| age_mid | derived | Midpoint of the 10-year band (for modelling). |
| admission_type | derived | Emergency (incl. trauma), Urgent, Elective, Other, Unknown — mapped from `admission_type_id`. |
| admission_source | derived | Emergency Room, Referral, Transfer, Other/Unknown — mapped from `admission_source_id`. |
| discharge_group | derived | Home, Home with care, Nursing/rehab facility, Other facility, Left against advice, Expired, Hospice, Other, Unknown — mapped from `discharge_disposition_id`. |
| medical_specialty / specialty_group | text / derived | Admitting physician's specialty (49% not recorded) and a grouped version. |
| payer_code | text | Payer (40% missing → Unknown). |
| diag_1 / diag_group | text / derived | Primary ICD-9 diagnosis and its group: Circulatory, Respiratory, Digestive, Diabetes, Injury, Musculoskeletal, Genitourinary, Neoplasms, Other. |
| length_of_stay | int | Days in hospital (`time_in_hospital`, 1–14). |
| num_lab_procedures, num_procedures, num_medications, number_diagnoses | int | Resource and complexity counts for the encounter. |
| number_outpatient, number_emergency, number_inpatient | int | Visits of each type in the year before the encounter. |
| prior_visits | derived | Sum of the three prior-visit counts. |
| prior_inpatient_band | derived | 0, 1, 2, 3+ inpatient stays in the prior year. |
| A1Cresult / a1c_tested | text / derived | HbA1c result (>8, >7, Norm) and whether it was measured at all. |
| insulin, med_changed, diabetesMed | text / bool | Insulin dosage change, any diabetes medication change, any diabetes medication prescribed. |
| expired | derived bool | Encounter ended in death. |
| readmitted | text | Original label: `<30`, `>30`, `NO`. |
| readmit_eligible | derived bool | False for encounters ending in death or discharge to hospice. |
| readmitted_30d | derived bool | `readmitted == "<30"` and eligible. |

## Metric definitions (identical in Python, SQL, Power BI and the dashboard)

| Metric | Definition |
|---|---|
| Encounters | Count of rows. |
| Average length of stay | Mean of `length_of_stay`. |
| 30-day readmission rate | Sum of `readmitted_30d` ÷ count of `readmit_eligible` encounters. |
| In-hospital mortality | Share of encounters with `discharge_group = Expired`. |
| Bed-days | Sum of `length_of_stay` (resource-use measure; the dataset has no cost field). |

## Known limitations
- Observational data from 1999–2008; clinical practice and coding (ICD-9 → ICD-10) have changed since.
- The readmission label comes with the dataset; readmissions to hospitals outside the database are probably recorded as "no readmission".
- No cost, admission date, severity score or social factors; ages are 10-year bands; stays longer than 14 days are excluded by design.
- Associations, not causes.
