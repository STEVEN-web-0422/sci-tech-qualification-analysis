# SQL pipeline

| Script | Responsibility | Main SQL techniques |
|---|---|---|
| `01_clean_merge.sql` | Normalize three source tables, filter status, deduplicate and flag cross-pool firms | `UNION ALL`, `ROW_NUMBER`, `CASE`, string/number normalization |
| `02_ip_by_scale.sql` | Stratified IP aggregation with sample sizes | Window-function median, grouped aggregation |
| `03_build_cohorts.sql` | Build one row per enterprise and define the four high-tech cohorts | `GROUP BY`, `CASE`, `MAX(CASE WHEN ...)` |
| `04_create_analysis_dataset.sql` | Build the common matching/modeling table and top-category groups | `ROW_NUMBER`, `NTILE`, mapping tables, joins |

## Why SQL is used heavily

The project is intentionally SQL-first. Entity resolution, status filtering,
cohort definitions and model feature groupings are all reproducible from the
database, so the Python scripts can focus on matching, model validation and
visualization.

## Database

The local SQLite database is `data/analysis.sqlite`. It is ignored by Git because
it contains enterprise-level records. The public repository only keeps aggregate
tables, charts and model artifacts.
