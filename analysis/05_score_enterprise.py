# -*- coding: utf-8 -*-
"""Score high-tech-like candidates for qualification-stacking potential.

This is NOT a probability of high-tech certification. The training data contains only
already-qualified firms, so no application/rejection outcome exists for a high-tech
eligibility model.
"""
from pathlib import Path
import argparse
import json
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "outputs" / "models"
TABLES = ROOT / "outputs" / "tables"
ANALYSIS_DATE = pd.Timestamp("2026-10-17")
TARGETS = {
    "any_stacking": "任一叠加资质",
    "small_giant": "科技小巨人",
    "specialized": "专精特新",
}
INPUT_SCHEMA = [
    ("credit_code", "否", "企业标识，可用于回填结果"),
    ("insured_count", "建议", "参保人数；缺失时模型使用中位数和缺失指示"),
    ("registered_capital_wan", "建议", "注册资本，万元"),
    ("paid_in_capital_wan", "否", "实缴资本，万元；可用于计算实缴率"),
    ("paid_in_rate", "否", "实缴率；缺失时可由实缴/注册资本计算"),
    ("establishment_date", "否", "成立日期 YYYY-MM-DD；用于计算企业年龄"),
    ("enterprise_age", "建议", "企业年龄；缺失时可由成立日期计算"),
    ("patent_count", "建议", "专利数"),
    ("copyright_count", "建议", "著作权数"),
    ("ip_density", "否", "知产密度；缺失时可由知产总数/参保人数计算"),
    ("industry_category", "建议", "国标行业门类"),
    ("district", "建议", "所在区县"),
    ("enterprise_type", "建议", "企业（机构）类型"),
    ("scale_band", "否", "规模分档；缺失时按参保人数自动生成"),
]


def top_map(series, keep):
    s = series.fillna("未知").astype(str)
    return np.where(s.isin(keep), s, "其他")


def prepare_input(df, meta):
    d = df.copy()
    d["insured_count"] = pd.to_numeric(d.get("insured_count"), errors="coerce")
    d["registered_capital_wan"] = pd.to_numeric(d.get("registered_capital_wan"), errors="coerce")
    d["paid_in_capital_wan"] = pd.to_numeric(d.get("paid_in_capital_wan"), errors="coerce")
    d["patent_count"] = pd.to_numeric(d.get("patent_count"), errors="coerce")
    d["copyright_count"] = pd.to_numeric(d.get("copyright_count"), errors="coerce")
    d["enterprise_age"] = pd.to_numeric(d.get("enterprise_age"), errors="coerce")
    if "establishment_date" in d:
        est = pd.to_datetime(d["establishment_date"], errors="coerce")
        derived_age = (ANALYSIS_DATE - est).dt.days / 365.25
        d["enterprise_age"] = d["enterprise_age"].fillna(derived_age)
    if "paid_in_rate" not in d:
        d["paid_in_rate"] = np.nan
    d["paid_in_rate"] = pd.to_numeric(d["paid_in_rate"], errors="coerce")
    derived_rate = d["paid_in_capital_wan"] / d["registered_capital_wan"].replace(0, np.nan)
    d["paid_in_rate"] = d["paid_in_rate"].fillna(derived_rate)
    if "ip_density" not in d:
        d["ip_density"] = np.nan
    d["ip_density"] = pd.to_numeric(d["ip_density"], errors="coerce")
    ip_total = d["patent_count"] + d["copyright_count"]
    derived_density = ip_total / d["insured_count"].replace(0, np.nan)
    d["ip_density"] = d["ip_density"].fillna(derived_density)
    if "scale_band" not in d:
        d["scale_band"] = pd.Series(index=d.index, dtype=object)
    d["scale_band"] = d["scale_band"].astype(object).replace({"nan": np.nan, "None": np.nan, "": np.nan})
    derived_scale = pd.cut(d["insured_count"], bins=[-0.1, 49.999, 200, np.inf], labels=["<50", "50-200", "200+"])
    d["scale_band"] = d["scale_band"].fillna(derived_scale).fillna("缺失").astype(str)
    for col, n in {"industry_group": 8, "district_group": 8, "type_group": 6}.items():
        src = {"industry_group":"industry_category", "district_group":"district", "type_group":"enterprise_type"}[col]
        if src not in d:
            d[src] = "未知"
        d[col] = top_map(d[src], meta["top_categories"][col])
    d["log_insured"] = np.log1p(d["insured_count"].clip(lower=0))
    d["log_reg_cap"] = np.log1p(d["registered_capital_wan"].clip(lower=0))
    d["log_patent"] = np.log1p(d["patent_count"].clip(lower=0))
    d["log_copyright"] = np.log1p(d["copyright_count"].clip(lower=0))
    d["log_ip_density"] = np.log1p(d["ip_density"].clip(lower=0))
    return d


def score(df, meta):
    d = prepare_input(df, meta)
    if d.empty:
        cols = ["credit_code"] if "credit_code" in d else []
        for target in TARGETS:
            cols += [f"p_{target}", f"score_{target}", f"band_{target}"]
        cols.append("scope_note")
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(index=d.index)
    for id_col in ["credit_code"]:
        if id_col in d:
            out[id_col] = d[id_col].values
    for target, label in TARGETS.items():
        model = joblib.load(MODELS / f"direction2_{target}.joblib")
        p = model.predict_proba(d)[:, 1]
        info = meta["targets"][target]
        qs = np.array(sorted(int(k) for k in info["reference_quantiles"]))
        vals = np.array([info["reference_quantiles"][str(q)] for q in qs])
        percentile = np.interp(p, vals, qs, left=0, right=100)
        out[f"p_{target}"] = p
        out[f"score_{target}"] = percentile
        out[f"band_{target}"] = pd.cut(percentile, bins=[-0.1, 50, 80, 100.1], labels=["低", "中", "高"]).astype(str)
    out["scope_note"] = "仅适用于已具备高企基础或高企-like特征的企业；分值不是高新认定概率，也不是因果效应。"
    return out


def main():
    parser = argparse.ArgumentParser(description="Score high-tech-like candidates for qualification-stacking potential.")
    parser.add_argument("--input", help="CSV containing candidate enterprise features")
    parser.add_argument("--output", default=str(ROOT / "outputs" / "scored_candidates.csv"))
    args = parser.parse_args()
    pd.DataFrame(INPUT_SCHEMA, columns=["field", "required", "description"]).to_csv(TABLES / "scoring_input_schema.csv", index=False, encoding="utf-8-sig")
    if not args.input:
        print("Input schema written to outputs/tables/scoring_input_schema.csv")
        print("Run: python analysis/04_score_enterprise.py --input examples/candidate_template.csv --output outputs/scored_candidates.csv")
        print("Important: this score is a reference-conditional stacking-potential score, not a high-tech certification probability.")
        return
    df = pd.read_csv(args.input)
    meta = json.loads((MODELS / "score_metadata.json").read_text(encoding="utf-8"))
    out = score(df, meta)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Scored {len(out):,} candidates -> {args.output}")


if __name__ == "__main__":
    main()
