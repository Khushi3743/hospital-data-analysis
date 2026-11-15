-- =====================================================================
-- Hospital analytics — SQL version of the core analysis
-- Table: admissions  (load data/processed/hospital_admissions_clean.csv)
-- Tested on SQLite (scripts/03_run_sql.py). Uses standard SQL, so it runs on
-- PostgreSQL / MySQL / SQL Server with minor date-function changes.
-- Booleans are stored as 'True'/'False' text in the CSV -> compared as text.
-- =====================================================================

-- Q1. Headline KPIs -----------------------------------------------------
SELECT
    COUNT(*)                                                    AS admissions,
    COUNT(DISTINCT patient_id)                                  AS unique_patients,
    ROUND(AVG(length_of_stay), 2)                               AS avg_los_days,
    ROUND(100.0 * SUM(CASE WHEN readmitted_30d = 'True' THEN 1 ELSE 0 END)
          / SUM(CASE WHEN readmit_eligible = 'True' THEN 1 ELSE 0 END), 1) AS readmission_rate_pct,
    ROUND(AVG(total_cost), 0)                                   AS avg_cost_per_stay,
    ROUND(SUM(total_cost) / 1e7, 2)                             AS total_cost_crore,
    ROUND(100.0 * AVG(CASE WHEN discharge_disposition = 'Expired' THEN 1.0 ELSE 0 END), 2) AS mortality_pct
FROM admissions;

-- Q2. Admissions by month and admission type ---------------------------
SELECT admission_month,
       COUNT(*) AS admissions,
       SUM(CASE WHEN admission_type = 'Emergency' THEN 1 ELSE 0 END) AS emergency,
       SUM(CASE WHEN admission_type = 'Elective'  THEN 1 ELSE 0 END) AS elective
FROM admissions
GROUP BY admission_month
ORDER BY admission_month;

-- Q3. Length of stay by age group --------------------------------------
SELECT age_group,
       COUNT(*)                     AS stays,
       ROUND(AVG(length_of_stay),2) AS avg_los,
       MAX(length_of_stay)          AS max_los
FROM admissions
GROUP BY age_group
ORDER BY age_group;

-- Q3b. Diagnoses whose average stay is above the hospital average --------
WITH h AS (SELECT AVG(length_of_stay) AS hosp_avg FROM admissions)
SELECT a.primary_diagnosis,
       COUNT(*)                         AS stays,
       ROUND(AVG(a.length_of_stay), 1)  AS avg_los,
       ROUND(AVG(a.length_of_stay) - h.hosp_avg, 1) AS days_above_avg
FROM admissions a CROSS JOIN h
GROUP BY a.primary_diagnosis, h.hosp_avg
HAVING AVG(a.length_of_stay) > h.hosp_avg
ORDER BY avg_los DESC;

-- Q4. 30-day readmission rate by diagnosis (eligible stays only) ---------
SELECT primary_diagnosis,
       COUNT(*) AS eligible_stays,
       SUM(CASE WHEN readmitted_30d = 'True' THEN 1 ELSE 0 END) AS readmissions,
       ROUND(100.0 * AVG(CASE WHEN readmitted_30d = 'True' THEN 1.0 ELSE 0 END), 1) AS readmit_rate_pct
FROM admissions
WHERE readmit_eligible = 'True'
GROUP BY primary_diagnosis
ORDER BY readmit_rate_pct DESC;

-- Q4b. Re-derive the readmission flag from raw dates with a window function
--      (checks that the Python-derived flag is correct)
WITH ordered AS (
    SELECT admission_id, patient_id, discharge_date, discharge_disposition, readmitted_30d,
           LEAD(admission_date) OVER (PARTITION BY patient_id ORDER BY admission_date) AS next_admission
    FROM admissions
)
SELECT
    SUM(CASE WHEN next_admission IS NOT NULL
              AND julianday(next_admission) - julianday(discharge_date) BETWEEN 0 AND 30
              AND discharge_disposition <> 'Expired'
              AND discharge_date <= '2024-12-01'
             THEN 1 ELSE 0 END)                                    AS readmissions_sql,
    SUM(CASE WHEN readmitted_30d = 'True' THEN 1 ELSE 0 END)       AS readmissions_python
FROM ordered;

-- Q4c. Readmission rate by number of prior admissions -------------------
SELECT CASE WHEN prior_admissions_12m >= 3 THEN '3+' ELSE CAST(prior_admissions_12m AS TEXT) END AS prior_admissions,
       COUNT(*) AS eligible_stays,
       ROUND(100.0 * AVG(CASE WHEN readmitted_30d = 'True' THEN 1.0 ELSE 0 END), 1) AS readmit_rate_pct
FROM admissions
WHERE readmit_eligible = 'True'
GROUP BY 1
ORDER BY 1;

-- Q5. Cost by department with share of total ---------------------------
SELECT department,
       COUNT(*)                                    AS stays,
       ROUND(SUM(total_cost) / 1e7, 2)             AS total_cost_crore,
       ROUND(AVG(total_cost), 0)                   AS avg_cost,
       ROUND(100.0 * SUM(total_cost) / (SELECT SUM(total_cost) FROM admissions), 1) AS share_pct,
       RANK() OVER (ORDER BY SUM(total_cost) DESC) AS cost_rank
FROM admissions
GROUP BY department
ORDER BY total_cost_crore DESC;

-- Q5b. High-cost stays (top 10%) vs the rest ----------------------------
SELECT high_cost,
       COUNT(*)                                          AS stays,
       ROUND(AVG(length_of_stay), 1)                     AS avg_los,
       ROUND(100.0 * AVG(CASE WHEN icu_days > 0 THEN 1.0 ELSE 0 END), 1) AS pct_with_icu,
       ROUND(100.0 * SUM(total_cost) / (SELECT SUM(total_cost) FROM admissions), 1) AS share_of_cost_pct
FROM admissions
GROUP BY high_cost;

-- Q5c. Frequent patients: top 10 by number of stays ---------------------
SELECT patient_id,
       COUNT(*)                         AS stays,
       SUM(length_of_stay)              AS bed_days,
       ROUND(SUM(total_cost), 0)        AS total_cost,
       MAX(primary_diagnosis)           AS example_diagnosis
FROM admissions
GROUP BY patient_id
ORDER BY stays DESC, total_cost DESC
LIMIT 10;
