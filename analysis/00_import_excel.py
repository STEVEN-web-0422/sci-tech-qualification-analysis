# -*- coding: utf-8 -*-
"""Import the three source workbooks into SQLite raw tables.

Place the source files in data/raw/ before running:
  2 高新技术企业.xlsx
  3 科技小巨人.xlsx
  6 专精特新中小企业.xlsx
"""
from pathlib import Path
import os
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("ANALYSIS_DB", ROOT / "data" / "analysis.sqlite"))
RAW_DIR = Path(os.getenv("RAW_DIR", ROOT / "data" / "raw"))
if not (RAW_DIR / "3 科技小巨人.xlsx").exists():
    fallback = ROOT.parent / "分析"
    if fallback.exists():
        RAW_DIR = fallback

SOURCES = {
    "xiao_ju_ren": RAW_DIR / "3 科技小巨人.xlsx",
    "gao_qi": RAW_DIR / "2 高新技术企业.xlsx",
    "zhuan_jing_te_xin": RAW_DIR / "6 专精特新中小企业.xlsx",
}
COLUMN_MAP = {
    "序号": "sequence_no", "频次": "frequency", "科创政策类别": "policy_category",
    "企业名称": "enterprise_name", "所在城市": "city_raw", "所在区": "district_raw",
    "获得评定的年份": "award_year", "专利数": "patent_count_raw", "著作权数": "copyright_count_raw",
    "登记状态": "registration_status_raw", "法定代表人": "legal_representative",
    "注册资本（万元人民币）": "registered_capital_raw", "实缴资本（万元人民币）": "paid_in_capital_raw",
    "成立日期": "establishment_date_raw", "成立年份": "establishment_year_raw",
    "企业年限": "enterprise_age_raw", "核准日期": "approval_date_raw", "所属省份": "province",
    "所属城市": "registered_city", "所属区县": "county", "统一社会信用代码": "credit_code_raw",
    "纳税人识别号": "taxpayer_id", "注册号": "registration_no", "组织机构代码": "org_code",
    "企业经营状态": "business_status", "参保人数": "insured_count_raw",
    "参保人数所属年报": "insured_report_year", "企业（机构）类型": "enterprise_type",
    "企业规模": "enterprise_size_raw", "国标行业门类": "industry_category",
    "国标行业大类": "industry_major", "国标行业中类": "industry_medium",
    "国标行业小类": "industry_minor",
}
DATE_COLUMNS = ["establishment_date_raw", "approval_date_raw"]


def clean_date_serial(value):
    if pd.isna(value):
        return None
    if hasattr(value, "date"):
        return value.date().isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none", "-"}:
        return None
    return text


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    audit = []
    with sqlite3.connect(DB_PATH) as con:
        for table, path in SOURCES.items():
            if not path.exists():
                raise FileNotFoundError(f"{path}. Add the source workbook to data/raw/.")
            df = pd.read_excel(path, usecols=list(COLUMN_MAP), dtype=object).rename(columns=COLUMN_MAP)
            for col in DATE_COLUMNS:
                df[col] = df[col].map(clean_date_serial)
            df.to_sql(table, con, if_exists="replace", index=False)
            audit.append({"table": table, "source_file": path.name, "rows": len(df), "columns": len(df.columns)})
            print(f"Imported {len(df):,} rows into {table}")
    pd.DataFrame(audit).to_csv(ROOT / "outputs" / "import_audit.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
