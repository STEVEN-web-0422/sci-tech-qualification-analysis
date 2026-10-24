-- ============================================================================
-- 02_ip_by_scale.sql
-- Stratified IP aggregation: scale band x qualification.
-- SQLite has no built-in MEDIAN(), so the median is implemented with window
-- functions (ROW_NUMBER + COUNT). This is one reason the 02 script is kept in
-- SQL: the stratification and median-by-rank are fully reproducible there.
-- ============================================================================

DROP TABLE IF EXISTS ip_by_scale_sql;

CREATE TABLE ip_by_scale_sql AS
WITH scale_dim(scale_band, scale_order) AS (
    VALUES ('<50', 1), ('50-200', 2), ('200+', 3), ('缺失', 4)
),
qual_dim(qualification, qual_order) AS (
    VALUES ('科技小巨人', 1), ('高新技术企业', 2), ('专精特新中小企业', 3)
),
dims AS (
    SELECT s.scale_band, s.scale_order, q.qualification, q.qual_order
    FROM scale_dim s CROSS JOIN qual_dim q
),
base AS (
    SELECT
        scale_band,
        qualification,
        ip_total
    FROM merged_clean
    WHERE ip_total IS NOT NULL
),
ranked AS (
    SELECT
        scale_band,
        qualification,
        ip_total,
        ROW_NUMBER() OVER (
            PARTITION BY scale_band, qualification
            ORDER BY ip_total
        ) AS rn,
        COUNT(*) OVER (
            PARTITION BY scale_band, qualification
        ) AS n_ip
    FROM base
),
med AS (
    SELECT
        scale_band,
        qualification,
        MAX(n_ip) AS n_ip,
        AVG(CASE WHEN rn IN ((n_ip + 1) / 2, (n_ip + 2) / 2) THEN ip_total END)
            AS median_ip_total
    FROM ranked
    GROUP BY scale_band, qualification
)
SELECT
    d.scale_band,
    d.scale_order,
    d.qualification,
    d.qual_order,
    COALESCE(m.n_ip, 0) AS n_ip,
    m.median_ip_total,
    CASE WHEN COALESCE(m.n_ip, 0) < 30 THEN '样本不足，结论谨慎' ELSE '' END
        AS sample_warning
FROM dims d
LEFT JOIN med m
    ON d.scale_band = m.scale_band
   AND d.qualification = m.qualification
ORDER BY d.qual_order, d.scale_order;
