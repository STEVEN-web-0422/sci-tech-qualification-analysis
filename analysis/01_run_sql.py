# -*- coding: utf-8 -*-
"""Run the SQL pipeline in dependency order."""
from pathlib import Path
import os
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("ANALYSIS_DB", ROOT / "data" / "analysis.sqlite"))
SQL_FILES = [
    "01_clean_merge.sql",
    "02_ip_by_scale.sql",
    "03_build_cohorts.sql",
    "04_create_analysis_dataset.sql",
]


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} not found. Run analysis/00_import_excel.py first."
        )
    with sqlite3.connect(DB_PATH) as con:
        for filename in SQL_FILES:
            sql_path = ROOT / "sql" / filename
            print(f"Running {filename} ...")
            con.executescript(sql_path.read_text(encoding="utf-8"))
        con.commit()
    print("SQL pipeline finished.")


if __name__ == "__main__":
    main()
