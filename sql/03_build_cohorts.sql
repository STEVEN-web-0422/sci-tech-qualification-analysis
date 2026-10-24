-- ============================================================================
-- 03_build_cohorts.sql
-- Build one row per identifiable enterprise and define high-tech cohorts.
-- Direction 1 and Direction 2 both use high_tech_cohort.
-- ============================================================================

DROP TABLE IF EXISTS enterprise_master;
DROP TABLE IF EXISTS high_tech_cohort;
DROP TABLE IF EXISTS cohort_summary;

CREATE TABLE enterprise_master AS
WITH base AS (
    SELECT
        credit_code,
        qualification,
        enterprise_name,
        city,
        district,
        award_year,
        registration_status,
        establishment_date,
        approval_date,
        registered_capital_wan,
        paid_in_capital_wan,
        insured_count,
        enterprise_type,
        industry_category,
        industry_major,
        patent_count,
        copyright_count,
        ip_total,
        ip_density,
        enterprise_age,
        enterprise_age_band,
        paid_in_rate,
        scale_band
    FROM merged_clean
    WHERE credit_code IS NOT NULL
)
SELECT
    credit_code,
    MAX(CASE WHEN qualification = '科技小巨人' THEN 1 ELSE 0 END) AS small_giant,
    MAX(CASE WHEN qualification = '高新技术企业' THEN 1 ELSE 0 END) AS high_tech,
    MAX(CASE WHEN qualification = '专精特新中小企业' THEN 1 ELSE 0 END) AS specialized,
    MAX(CASE WHEN qualification = '科技小巨人' THEN enterprise_name END) AS enterprise_name,
    MAX(CASE WHEN qualification = '高新技术企业' THEN city END) AS city,
    MAX(CASE WHEN qualification = '高新技术企业' THEN district END) AS district,
    MAX(CASE WHEN qualification = '高新技术企业' THEN award_year END) AS award_year,
    MAX(CASE WHEN qualification = '高新技术企业' THEN registration_status END) AS registration_status,
    MAX(CASE WHEN qualification = '高新技术企业' THEN establishment_date END) AS establishment_date,
    MAX(CASE WHEN qualification = '高新技术企业' THEN approval_date END) AS approval_date,
    MAX(CASE WHEN qualification = '高新技术企业' THEN registered_capital_wan END) AS registered_capital_wan,
    MAX(CASE WHEN qualification = '高新技术企业' THEN paid_in_capital_wan END) AS paid_in_capital_wan,
    MAX(CASE WHEN qualification = '高新技术企业' THEN insured_count END) AS insured_count,
    MAX(CASE WHEN qualification = '高新技术企业' THEN enterprise_type END) AS enterprise_type,
    MAX(CASE WHEN qualification = '高新技术企业' THEN industry_category END) AS industry_category,
    MAX(CASE WHEN qualification = '高新技术企业' THEN industry_major END) AS industry_major,
    MAX(CASE WHEN qualification = '高新技术企业' THEN patent_count END) AS patent_count,
    MAX(CASE WHEN qualification = '高新技术企业' THEN copyright_count END) AS copyright_count,
    MAX(CASE WHEN qualification = '高新技术企业' THEN ip_total END) AS ip_total,
    MAX(CASE WHEN qualification = '高新技术企业' THEN ip_density END) AS ip_density,
    MAX(CASE WHEN qualification = '高新技术企业' THEN enterprise_age END) AS enterprise_age,
    MAX(CASE WHEN qualification = '高新技术企业' THEN enterprise_age_band END) AS enterprise_age_band,
    MAX(CASE WHEN qualification = '高新技术企业' THEN paid_in_rate END) AS paid_in_rate,
    MAX(CASE WHEN qualification = '高新技术企业' THEN scale_band END) AS scale_band
FROM base
GROUP BY credit_code;

ALTER TABLE enterprise_master ADD COLUMN cohort TEXT;
ALTER TABLE enterprise_master ADD COLUMN any_stacking INTEGER;
ALTER TABLE enterprise_master ADD COLUMN stacking_count INTEGER;

UPDATE enterprise_master
SET stacking_count = small_giant + specialized,
    any_stacking = CASE WHEN small_giant = 1 OR specialized = 1 THEN 1 ELSE 0 END,
    cohort = CASE
        WHEN high_tech = 0 THEN '非高企'
        WHEN small_giant = 1 AND specialized = 1 THEN '三重叠加'
        WHEN small_giant = 1 THEN '高企+小巨人'
        WHEN specialized = 1 THEN '高企+专精特新'
        ELSE '纯高企'
    END;

CREATE TABLE high_tech_cohort AS
SELECT *
FROM enterprise_master
WHERE high_tech = 1;

CREATE TABLE cohort_summary AS
SELECT
    cohort,
    COUNT(*) AS enterprises,
    ROUND(AVG(any_stacking), 4) AS any_stacking_rate,
    ROUND(AVG(small_giant), 4) AS small_giant_rate,
    ROUND(AVG(specialized), 4) AS specialized_rate,
    ROUND(AVG(ip_total), 2) AS mean_ip_total,
    ROUND(AVG(ip_density), 4) AS mean_ip_density
FROM high_tech_cohort
GROUP BY cohort
ORDER BY CASE cohort
    WHEN '纯高企' THEN 1
    WHEN '高企+专精特新' THEN 2
    WHEN '高企+小巨人' THEN 3
    WHEN '三重叠加' THEN 4
    ELSE 5 END;

CREATE INDEX idx_enterprise_cohort ON enterprise_master(cohort);
CREATE INDEX idx_high_tech_cohort ON high_tech_cohort(cohort);
