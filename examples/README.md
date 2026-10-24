# Scoring input example

`candidate_template.csv` contains the header only, intentionally without fabricated firms.

Required fields are listed in `outputs/tables/scoring_input_schema.csv`.
Use real candidate records and run:

```bash
python analysis/04_score_enterprise.py --input examples/candidate_template.csv --output outputs/scored_candidates.csv
```

The score is a **reference-conditional qualification-stacking potential score** among observed high-tech firms. It is not a high-tech certification probability.
