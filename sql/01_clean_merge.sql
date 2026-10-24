-- ============================================================================
-- 01_clean_merge.sql
-- Three-pool cleaning, deduplication, cross-pool detection, and derivation.
-- Engine: SQLite (chosen because DuckDB is unavailable in the current Python
-- environment). Business logic is kept in SQL; Python is only used to run the
-- script, calculate quartiles, and draw charts.
-- Analysis date: 2026-10-17 (Asia/Shanghai)
-- ============================================================================

PRAGMA temp_store = MEMORY;

DROP TABLE IF EXISTS raw_union;
DROP TABLE IF EXISTS normalized_raw;
DROP TABLE IF EXISTS pool_audit;
DROP TABLE IF EXISTS within_pool_ranked;
DROP TABLE IF EXISTS dedup_audit;
DROP TABLE IF EXISTS within_pool_dedup;
DROP TABLE IF EXISTS cross_pool;
DROP TABLE IF EXISTS cross_pool_distribution;
DROP TABLE IF EXISTS merged_clean;

-- 1. UNION ALL: one qualification label per source pool.
CREATE TABLE raw_union AS
SELECT
    '科技小巨人' AS qualification,
    'xiao_ju_ren' AS source_table,
    'xiao_ju_ren#' || CAST(rowid AS TEXT) AS source_row_id,
    sequence_no, frequency, policy_category, enterprise_name, city_raw,
    district_raw, award_year, patent_count_raw, copyright_count_raw,
    registration_status_raw, legal_representative, registered_capital_raw,
    paid_in_capital_raw, establishment_date_raw, establishment_year_raw,
    enterprise_age_raw, approval_date_raw, province, registered_city, county,
    credit_code_raw, taxpayer_id, registration_no, org_code, business_status,
    insured_count_raw, insured_report_year, enterprise_type, enterprise_size_raw,
    industry_category, industry_major, industry_medium, industry_minor
FROM xiao_ju_ren
UNION ALL
SELECT
    '高新技术企业' AS qualification,
    'gao_qi' AS source_table,
    'gao_qi#' || CAST(rowid AS TEXT) AS source_row_id,
    sequence_no, frequency, policy_category, enterprise_name, city_raw,
    district_raw, award_year, patent_count_raw, copyright_count_raw,
    registration_status_raw, legal_representative, registered_capital_raw,
    paid_in_capital_raw, establishment_date_raw, establishment_year_raw,
    enterprise_age_raw, approval_date_raw, province, registered_city, county,
    credit_code_raw, taxpayer_id, registration_no, org_code, business_status,
    insured_count_raw, insured_report_year, enterprise_type, enterprise_size_raw,
    industry_category, industry_major, industry_medium, industry_minor
FROM gao_qi
UNION ALL
SELECT
    '专精特新中小企业' AS qualification,
    'zhuan_jing_te_xin' AS source_table,
    'zhuan_jing_te_xin#' || CAST(rowid AS TEXT) AS source_row_id,
    sequence_no, frequency, policy_category, enterprise_name, city_raw,
    district_raw, award_year, patent_count_raw, copyright_count_raw,
    registration_status_raw, legal_representative, registered_capital_raw,
    paid_in_capital_raw, establishment_date_raw, establishment_year_raw,
    enterprise_age_raw, approval_date_raw, province, registered_city, county,
    credit_code_raw, taxpayer_id, registration_no, org_code, business_status,
    insured_count_raw, insured_report_year, enterprise_type, enterprise_size_raw,
    industry_category, industry_major, industry_medium, industry_minor
FROM zhuan_jing_te_xin;

-- 2. Normalize identifiers, dates, numeric fields, and status in SQL.
CREATE TABLE normalized_raw AS
SELECT
    qualification,
    source_table,
    source_row_id,
    sequence_no,
    frequency,
    policy_category,
    enterprise_name,
    city_raw,
    district_raw,
    award_year,
    CAST(patent_count_raw AS INTEGER)
        AS patent_count,
    CAST(copyright_count_raw AS INTEGER)
        AS copyright_count,
    registration_status_raw,
    TRIM(registration_status_raw) AS registration_status,
    legal_representative,
    CASE
        WHEN registered_capital_raw IS NULL THEN NULL
        WHEN TRIM(CAST(registered_capital_raw AS TEXT)) IN ('', '-', 'nan', 'NaN', 'None', 'NULL') THEN NULL
        WHEN TRIM(CAST(registered_capital_raw AS TEXT)) NOT GLOB '*[0-9]*' THEN NULL
        ELSE CAST(REPLACE(REPLACE(TRIM(CAST(registered_capital_raw AS TEXT)), ',', ''), '万元', '') AS REAL)
    END AS registered_capital_wan,
    CASE
        WHEN paid_in_capital_raw IS NULL THEN NULL
        WHEN TRIM(CAST(paid_in_capital_raw AS TEXT)) IN ('', '-', 'nan', 'NaN', 'None', 'NULL') THEN NULL
        WHEN TRIM(CAST(paid_in_capital_raw AS TEXT)) NOT GLOB '*[0-9]*' THEN NULL
        ELSE CAST(REPLACE(REPLACE(TRIM(CAST(paid_in_capital_raw AS TEXT)), ',', ''), '万元', '') AS REAL)
    END AS paid_in_capital_wan,
    establishment_date_raw,
    CASE WHEN date(establishment_date_raw) IS NOT NULL THEN date(establishment_date_raw) END
        AS establishment_date,
    approval_date_raw,
    CASE WHEN date(approval_date_raw) IS NOT NULL THEN date(approval_date_raw) END
        AS approval_date,
    province,
    registered_city,
    county,
    CASE
        WHEN credit_code_raw IS NULL THEN NULL
        WHEN TRIM(credit_code_raw) IN ('', '-', 'nan', 'NaN', 'None', 'NULL') THEN NULL
        ELSE UPPER(REPLACE(TRIM(credit_code_raw), ' ', ''))
    END AS credit_code,
    taxpayer_id,
    registration_no,
    org_code,
    business_status,
    CASE
        WHEN insured_count_raw IS NULL THEN NULL
        WHEN TRIM(CAST(insured_count_raw AS TEXT)) IN ('', '-', 'nan', 'NaN', 'None', 'NULL') THEN NULL
        WHEN TRIM(CAST(insured_count_raw AS TEXT)) NOT GLOB '*[0-9]*' THEN NULL
        ELSE CAST(ROUND(CAST(REPLACE(TRIM(CAST(insured_count_raw AS TEXT)), ',', '') AS REAL)) AS INTEGER)
    END AS insured_count,
    insured_report_year,
    enterprise_type,
    enterprise_size_raw,
    industry_category,
    industry_major,
    industry_medium,
    industry_minor,
    CASE
        WHEN registration_status_raw IS NULL THEN 0
        WHEN TRIM(registration_status_raw) LIKE '存续%' THEN 1
        WHEN TRIM(registration_status_raw) LIKE '在业%' THEN 1
        ELSE 0
    END AS is_active
FROM raw_union;

-- 3. Audit raw and active counts; registration filter = 存续/在业 only.
CREATE TABLE pool_audit AS
SELECT
    qualification,
    COUNT(*) AS raw_rows,
    SUM(is_active) AS active_rows_before_dedup,
    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS removed_by_status,
    SUM(CASE WHEN credit_code IS NULL THEN 1 ELSE 0 END) AS missing_credit_code_rows,
    COUNT(DISTINCT credit_code) AS unique_nonmissing_codes
FROM normalized_raw
GROUP BY qualification;

-- 4. Window deduplication inside each pool. Missing credit codes are assigned a
-- unique fallback key so that they are not incorrectly collapsed together.
CREATE TABLE within_pool_ranked AS
SELECT
    n.*,
    COALESCE(n.credit_code, n.qualification || '::MISSING::' || n.source_row_id) AS dedup_key,
    ROW_NUMBER() OVER (
        PARTITION BY n.qualification,
                     COALESCE(n.credit_code, n.qualification || '::MISSING::' || n.source_row_id)
        ORDER BY COALESCE(n.award_year, 0) DESC,
                 COALESCE(n.frequency, 0) DESC,
                 n.source_row_id DESC
    ) AS rn
FROM normalized_raw n
WHERE n.is_active = 1;

CREATE TABLE dedup_audit AS
SELECT
    qualification,
    COUNT(*) AS active_rows_for_dedup,
    COUNT(DISTINCT credit_code) AS unique_nonmissing_codes,
    SUM(CASE WHEN credit_code IS NULL THEN 1 ELSE 0 END) AS missing_code_rows_retained,
    SUM(CASE WHEN rn > 1 THEN 1 ELSE 0 END) AS duplicate_rows_removed
FROM within_pool_ranked
GROUP BY qualification;

CREATE TABLE within_pool_dedup AS
SELECT *
FROM within_pool_ranked
WHERE rn = 1;

-- 5. Cross-pool detection after within-pool deduplication. The dedup key is the
-- credit code; rows with a missing code cannot be reliably matched across pools.
CREATE TABLE cross_pool AS
SELECT
    credit_code,
    COUNT(DISTINCT qualification) AS pool_count,
    GROUP_CONCAT(DISTINCT qualification) AS qualification_labels
FROM within_pool_dedup
WHERE credit_code IS NOT NULL
GROUP BY credit_code
HAVING COUNT(DISTINCT qualification) > 1;

CREATE TABLE cross_pool_distribution AS
SELECT
    pool_count,
    qualification_labels,
    COUNT(*) AS enterprise_count
FROM cross_pool
GROUP BY pool_count, qualification_labels
ORDER BY pool_count DESC, enterprise_count DESC;

-- 6. Final analysis mart: one membership row per qualification x enterprise.
-- Cross-pool enterprises intentionally remain in each pool and are flagged,
-- because global collapse would destroy the three-pool comparison.
CREATE TABLE merged_clean AS
SELECT
    d.qualification,
    d.source_table,
    d.source_row_id,
    d.sequence_no,
    d.frequency,
    d.policy_category,
    d.enterprise_name,
    COALESCE(NULLIF(d.city_raw, ''), d.registered_city) AS city,
    COALESCE(NULLIF(d.district_raw, ''), d.county) AS district,
    d.award_year,
    d.credit_code,
    d.legal_representative,
    d.registration_status,
    d.establishment_date,
    d.approval_date,
    d.registered_capital_wan,
    d.paid_in_capital_wan,
    d.insured_count,
    d.insured_report_year,
    d.enterprise_type,
    d.enterprise_size_raw,
    d.industry_category,
    d.industry_major,
    d.industry_medium,
    d.industry_minor,
    d.patent_count,
    d.copyright_count,
    CASE WHEN d.patent_count IS NOT NULL AND d.copyright_count IS NOT NULL
         THEN d.patent_count + d.copyright_count ELSE NULL END AS ip_total,
    CASE WHEN d.establishment_date IS NULL THEN NULL
         WHEN d.establishment_date > '2026-10-17' THEN NULL
         WHEN d.establishment_date < '1900-01-01' THEN NULL
         ELSE ROUND((julianday('2026-10-17') - julianday(d.establishment_date)) / 365.25, 2)
    END AS enterprise_age,
    CASE
        WHEN d.establishment_date IS NULL THEN '缺失/无法计算'
        WHEN d.establishment_date > '2026-10-17' THEN '缺失/无法计算'
        WHEN d.establishment_date < '1900-01-01' THEN '缺失/无法计算'
        WHEN (julianday('2026-10-17') - julianday(d.establishment_date)) / 365.25 < 3 THEN '3年内'
        WHEN (julianday('2026-10-17') - julianday(d.establishment_date)) / 365.25 < 10 THEN '3-10年'
        ELSE '10年以上'
    END AS enterprise_age_band,
    CASE
        WHEN d.registered_capital_wan IS NULL OR d.registered_capital_wan <= 0 THEN NULL
        WHEN d.paid_in_capital_wan IS NULL THEN NULL
        ELSE ROUND(d.paid_in_capital_wan / d.registered_capital_wan, 4)
    END AS paid_in_rate,
    CASE
        WHEN d.insured_count IS NULL THEN '缺失'
        WHEN d.insured_count < 50 THEN '<50'
        WHEN d.insured_count <= 200 THEN '50-200'
        ELSE '200+'
    END AS scale_band,
    CASE WHEN d.patent_count IS NULL OR d.copyright_count IS NULL THEN NULL
         WHEN d.insured_count IS NULL OR d.insured_count <= 0 THEN NULL
         ELSE ROUND(1.0 * (d.patent_count + d.copyright_count) / d.insured_count, 4)
    END AS ip_density,
    CASE WHEN c.credit_code IS NULL THEN 0 ELSE 1 END AS cross_pool,
    COALESCE(c.pool_count, 1) AS pool_count,
    c.qualification_labels AS cross_pool_labels,
    CASE
        WHEN d.establishment_date_raw IS NULL OR TRIM(d.establishment_date_raw) IN ('', '-', 'nan', 'NaN', 'None', 'NULL') THEN 'missing'
        WHEN d.establishment_date IS NULL THEN 'unparseable'
        WHEN d.establishment_date > '2026-10-17' THEN 'future'
        WHEN d.establishment_date < '1900-01-01' THEN 'before_1900'
        ELSE 'ok'
    END AS establishment_date_quality,
    CASE WHEN d.registered_capital_wan IS NULL THEN 'missing'
         WHEN d.registered_capital_wan = 0 THEN 'zero'
         WHEN d.registered_capital_wan > 100000 THEN 'extreme_gt_100000'
         ELSE 'ok' END AS registered_capital_quality,
    CASE WHEN d.paid_in_capital_wan IS NULL THEN 'missing'
         WHEN d.paid_in_capital_wan = 0 THEN 'zero'
         WHEN d.paid_in_capital_wan > 100000 THEN 'extreme_gt_100000'
         ELSE 'ok' END AS paid_in_capital_quality,
    CASE WHEN d.insured_count IS NULL THEN 'missing'
         WHEN d.insured_count = 0 THEN 'zero'
         ELSE 'ok' END AS insured_quality,
    CASE WHEN d.patent_count IS NULL THEN 'missing' ELSE 'ok' END AS patent_quality,
    CASE WHEN d.copyright_count IS NULL THEN 'missing' ELSE 'ok' END AS copyright_quality,
    '2026-10-17' AS analysis_date
FROM within_pool_dedup d
LEFT JOIN cross_pool c ON d.credit_code = c.credit_code;

CREATE INDEX idx_merged_qualification ON merged_clean(qualification);
CREATE INDEX idx_merged_scale ON merged_clean(scale_band);
CREATE INDEX idx_merged_cross_pool ON merged_clean(cross_pool);
