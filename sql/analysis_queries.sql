-- =====================================================================
-- Hospital readmission analytics — SQL version of the core analysis
-- Data: UCI Diabetes 130-US Hospitals 1999-2008 (cleaned)
-- Table: encounters  (load data/processed/hospital_encounters_clean.csv)
-- Tested on SQLite (scripts/02_run_sql.py). Standard SQL, runs on
-- PostgreSQL / MySQL / SQL Server with minor changes.
-- Booleans are stored as 'True'/'False' text in the CSV.
-- =====================================================================

-- Q1. Headline KPIs -----------------------------------------------------
SELECT
    COUNT(*)                                                     AS encounters,
    COUNT(DISTINCT patient_nbr)                                  AS unique_patients,
    ROUND(AVG(length_of_stay), 2)                                AS avg_los_days,
    SUM(CASE WHEN readmit_eligible = 'True' THEN 1 ELSE 0 END)   AS eligible,
    SUM(CASE WHEN readmitted_30d  = 'True' THEN 1 ELSE 0 END)    AS readmissions_30d,
    ROUND(100.0 * SUM(CASE WHEN readmitted_30d = 'True' THEN 1 ELSE 0 END)
          / SUM(CASE WHEN readmit_eligible = 'True' THEN 1 ELSE 0 END), 2) AS readmission_rate_pct,
    ROUND(100.0 * AVG(CASE WHEN expired = 'True' THEN 1.0 ELSE 0 END), 2)  AS mortality_pct,
    SUM(length_of_stay)                                          AS total_bed_days
FROM encounters;

-- Q2. Encounter mix by admission type and source ------------------------
SELECT admission_type,
       admission_source,
       COUNT(*) AS encounters,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM encounters), 1) AS share_pct
FROM encounters
GROUP BY admission_type, admission_source
ORDER BY encounters DESC
LIMIT 10;

-- Q3. Length of stay by age group ---------------------------------------
SELECT age_group,
       COUNT(*)                      AS encounters,
       ROUND(AVG(length_of_stay), 2) AS avg_los,
       SUM(length_of_stay)           AS bed_days
FROM encounters
GROUP BY age_group
ORDER BY MIN(age_mid);

-- Q3b. Diagnosis groups whose average stay is above the network average -
WITH n AS (SELECT AVG(length_of_stay) AS net_avg FROM encounters)
SELECT e.diag_group,
       COUNT(*)                                  AS encounters,
       ROUND(AVG(e.length_of_stay), 2)           AS avg_los,
       ROUND(AVG(e.length_of_stay) - n.net_avg, 2) AS days_above_avg
FROM encounters e CROSS JOIN n
GROUP BY e.diag_group, n.net_avg
HAVING AVG(e.length_of_stay) > n.net_avg
ORDER BY avg_los DESC;

-- Q4. 30-day readmission rate by prior inpatient stays ------------------
SELECT prior_inpatient_band                                       AS prior_inpatient_stays,
       COUNT(*)                                                   AS eligible,
       SUM(CASE WHEN readmitted_30d = 'True' THEN 1 ELSE 0 END)   AS readmissions,
       ROUND(100.0 * AVG(CASE WHEN readmitted_30d = 'True' THEN 1.0 ELSE 0 END), 1) AS readmit_rate_pct
FROM encounters
WHERE readmit_eligible = 'True'
GROUP BY prior_inpatient_band
ORDER BY prior_inpatient_band;

-- Q4b. Readmission rate by discharge destination, ranked ----------------
SELECT discharge_group,
       COUNT(*) AS eligible,
       ROUND(100.0 * AVG(CASE WHEN readmitted_30d = 'True' THEN 1.0 ELSE 0 END), 1) AS readmit_rate_pct,
       RANK() OVER (ORDER BY AVG(CASE WHEN readmitted_30d = 'True' THEN 1.0 ELSE 0 END) DESC) AS risk_rank
FROM encounters
WHERE readmit_eligible = 'True'
GROUP BY discharge_group
HAVING COUNT(*) >= 500
ORDER BY risk_rank;

-- Q4c. Readmission rate by primary diagnosis group ----------------------
SELECT diag_group,
       COUNT(*) AS eligible,
       ROUND(100.0 * AVG(CASE WHEN readmitted_30d = 'True' THEN 1.0 ELSE 0 END), 1) AS readmit_rate_pct
FROM encounters
WHERE readmit_eligible = 'True'
GROUP BY diag_group
ORDER BY readmit_rate_pct DESC;

-- Q4d. HbA1c measured vs not measured -----------------------------------
SELECT a1c_tested,
       COUNT(*) AS eligible,
       ROUND(100.0 * AVG(CASE WHEN readmitted_30d = 'True' THEN 1.0 ELSE 0 END), 1) AS readmit_rate_pct
FROM encounters
WHERE readmit_eligible = 'True'
GROUP BY a1c_tested;

-- Q4e. Each patient's encounter sequence with a window function ---------
--      (encounter_id increases over time within a patient)
WITH seq AS (
    SELECT patient_nbr,
           ROW_NUMBER() OVER (PARTITION BY patient_nbr ORDER BY encounter_id) AS visit_no,
           COUNT(*)     OVER (PARTITION BY patient_nbr)                       AS total_visits
    FROM encounters
)
SELECT CASE WHEN total_visits >= 4 THEN '4+' ELSE CAST(total_visits AS TEXT) END AS visits_per_patient,
       COUNT(DISTINCT patient_nbr) AS patients
FROM seq
GROUP BY 1
ORDER BY 1;

-- Q5. Bed-days by diagnosis group with share of total -------------------
SELECT diag_group,
       COUNT(*)            AS encounters,
       SUM(length_of_stay) AS bed_days,
       ROUND(100.0 * SUM(length_of_stay) / (SELECT SUM(length_of_stay) FROM encounters), 1) AS bed_day_share_pct,
       ROUND(AVG(num_medications), 1)    AS avg_medications,
       ROUND(AVG(num_lab_procedures), 1) AS avg_lab_tests
FROM encounters
GROUP BY diag_group
ORDER BY bed_days DESC;
