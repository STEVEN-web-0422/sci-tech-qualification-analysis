-- ============================================================================
-- 04_create_analysis_dataset.sql
-- Build one tidy high-tech analysis table for matching and modeling.
-- Most feature grouping and cohort logic is intentionally kept in SQL so the
-- Python scripts can focus on matching, validation, and visualization.
-- ============================================================================

DROP TABLE IF EXISTS dim_industry_group;
DROP TABLE IF EXISTS dim_district_group;
DROP TABLE IF EXISTS dim_type_group;
DROP TABLE IF EXISTS high_tech_analysis;

CREATE TABLE dim_industry_group AS
WITH counts AS (
    SELECT
        COALESCE(NULLIF(TRIM(industry_category), ''), '未知') AS category,
        COUNT(*) AS n
    FROM high_tech_cohort
    GROUP BY 1
),
ranked AS (
    SELECT
        category,
        n,
        ROW_NUMBER() OVER (ORDER BY n DESC, category) AS rn
    FROM counts
)
SELECT
    category,
    rn,
    CASE WHEN rn <= 8 THEN category ELSE '其他' END AS group_name
FROM ranked;

CREATE TABLE dim_district_group AS
WITH counts AS (
    SELECT
        COALESCE(NULLIF(TRIM(district), ''), '未知') AS category,
        COUNT(*) AS n
    FROM high_tech_cohort
    GROUP BY 1
),
ranked AS (
    SELECT
        category,
        n,
        ROW_NUMBER() OVER (ORDER BY n DESC, category) AS rn
    FROM counts
)
SELECT
    category,
    rn,
    CASE WHEN rn <= 8 THEN category ELSE '其他' END AS group_name
FROM ranked;

CREATE TABLE dim_type_group AS
WITH counts AS (
    SELECT
        COALESCE(NULLIF(TRIM(enterprise_type), ''), '未知') AS category,
        COUNT(*) AS n
    FROM high_tech_cohort
    GROUP BY 1
),
ranked AS (
    SELECT
        category,
        n,
        ROW_NUMBER() OVER (ORDER BY n DESC, category) AS rn
    FROM counts
)
SELECT
    category,
    rn,
    CASE WHEN rn <= 6 THEN category ELSE '其他' END AS group_name
FROM ranked;

CREATE TABLE high_tech_analysis AS
SELECT
    h.credit_code,
    h.enterprise_name,
    h.small_giant,
    h.high_tech,
    h.specialized,
    h.any_stacking,
    h.stacking_count,
    h.cohort,
    h.city,
    h.district,
    h.industry_category,
    h.enterprise_type,
    h.award_year,
    h.establishment_date,
    h.approval_date,
    h.registered_capital_wan,
    h.paid_in_capital_wan,
    h.insured_count,
    h.patent_count,
    h.copyright_count,
    h.ip_total,
    h.ip_density,
    h.enterprise_age,
    h.enterprise_age_band,
    h.paid_in_rate,
    h.scale_band,
    COALESCE(i.group_name, '其他') AS industry_group,
    COALESCE(d.group_name, '其他') AS district_group,
    COALESCE(t.group_name, '其他') AS type_group,
    CASE
        WHEN h.registered_capital_wan IS NULL THEN '缺失'
        ELSE 'Q' || NTILE(4) OVER (ORDER BY h.registered_capital_wan)
    END AS cap_quartile
FROM high_tech_cohort h
LEFT JOIN dim_industry_group i
    ON COALESCE(NULLIF(TRIM(h.industry_category), ''), '未知') = i.category
LEFT JOIN dim_district_group d
    ON COALESCE(NULLIF(TRIM(h.district), ''), '未知') = d.category
LEFT JOIN dim_type_group t
    ON COALESCE(NULLIF(TRIM(h.enterprise_type), ''), '未知') = t.category;

CREATE INDEX idx_high_tech_analysis_cohort ON high_tech_analysis(cohort);
CREATE INDEX idx_high_tech_analysis_scale ON high_tech_analysis(scale_band);
