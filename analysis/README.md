# Analysis code

This folder contains the Python layer of the pipeline. The SQL layer does the
heavy lifting for cleaning, entity resolution, cohort construction and analysis
dataset preparation.

## Run order

1. `00_import_excel.py`
2. `01_run_sql.py`
3. `02_descriptive_profile.py`
4. `03_direction1_matching.py`
5. `04_direction2_modeling.py`
6. `05_score_enterprise.py` (only when scoring a candidate CSV)

## Responsibilities

- `00_import_excel.py`: reads the three Excel files into SQLite raw tables.
- `01_run_sql.py`: executes `sql/01` through `sql/04` in dependency order.
- `02_descriptive_profile.py`: produces descriptive tables and portfolio charts.
- `03_direction1_matching.py`: coarsened exact matching, within-cell nearest
  matching, SMD balance checks and paired bootstrap intervals.
- `04_direction2_modeling.py`: nested high-tech models, 5-fold validation,
  calibration, feature-group permutation importance and model artifacts.
- `05_score_enterprise.py`: loads the saved models and scores a candidate CSV.

## Design rules

- Do not repeat business cleaning in Python if it can be expressed in SQL.
- Keep SQL result tables as the source of truth for cohort and feature definitions.
- Keep model evaluation out-of-fold; do not score the training data and call it
  validation.
- The score is a reference-conditional stacking-potential score, not a high-tech
  certification probability.
