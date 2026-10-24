# -*- coding: utf-8 -*-
"""Build descriptive tables and figures from the SQL analysis base."""
from pathlib import Path
import json
import os
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Patch
from matplotlib.ticker import FuncFormatter, PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("ANALYSIS_DB", ROOT / "data" / "analysis.sqlite"))
TABLES_DIR = ROOT / "outputs" / "tables"
IMAGES_DIR = ROOT / "docs" / "images"
PROCESSED_DIR = ROOT / "data" / "processed"
ANALYSIS_DATE = "2026-10-17"
QUAL_ORDER = ["科技小巨人", "高新技术企业", "专精特新中小企业"]
SHORT = {"科技小巨人": "小巨人", "高新技术企业": "高企", "专精特新中小企业": "专精特新"}
COLORS = {"科技小巨人": "#D55E00", "高新技术企业": "#0072B2", "专精特新中小企业": "#009E73"}
SCALE_ORDER = ["<50", "50-200", "200+", "缺失"]
AGE_ORDER = ["3年内", "3-10年", "10年以上"]
TEXT = "#1F2937"
MUTED = "#6B7280"
GRID = "#E5E7EB"

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"],
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#D1D5DB",
    "axes.labelcolor": TEXT,
    "xtick.color": TEXT,
    "ytick.color": TEXT,
    "text.color": TEXT,
    "font.size": 10,
})


def style_ax(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8, alpha=0.8)
        ax.set_axisbelow(True)


def save_fig(fig, name):
    fig.savefig(IMAGES_DIR / name, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fmt_int(x):
    return f"{int(x):,}"


def save_table(df, name):
    df.to_csv(TABLES_DIR / name, index=False, encoding="utf-8-sig")



def stat_rows(df, metrics):
    rows = []
    for q in QUAL_ORDER:
        g = df[df["qualification"] == q]
        for label, col in metrics.items():
            s = pd.to_numeric(g[col], errors="coerce")
            v = s.dropna()
            rows.append({
                "qualification": q, "metric": label, "n_total": len(g), "n_valid": len(v),
                "n_missing": len(g) - len(v),
                "q1": v.quantile(.25), "median": v.median(), "q3": v.quantile(.75), "max": v.max(),
            })
    return pd.DataFrame(rows)


def build_tables(df, con):
    scale = stat_rows(df, {
        "注册资本": "registered_capital_wan", "实缴资本": "paid_in_capital_wan",
        "参保人数": "insured_count", "企业年龄": "enterprise_age",
    })
    ip = stat_rows(df, {
        "专利数": "patent_count", "著作权数": "copyright_count",
        "知产总数": "ip_total", "知产密度": "ip_density",
    })
    scale.to_csv(TABLES_DIR / "table_scale_compare.csv", index=False, encoding="utf-8-sig")
    ip.to_csv(TABLES_DIR / "table_ip_compare.csv", index=False, encoding="utf-8-sig")

    pool_rows = []
    for q in QUAL_ORDER:
        g = df[df["qualification"] == q]
        codes = g["credit_code"].dropna()
        cross = g.loc[g["cross_pool"] == 1, "credit_code"].dropna()
        pool_rows.append({
            "qualification": q, "membership_records": len(g),
            "unique_credit_codes": codes.nunique(), "missing_credit_codes": g["credit_code"].isna().sum(),
            "cross_pool_enterprises": cross.nunique(),
            "cross_pool_share_pct": 100 * cross.nunique() / codes.nunique() if codes.nunique() else np.nan,
        })
    pool_counts = pd.DataFrame(pool_rows)
    save_table(pool_counts, "table_pool_counts.csv")

    scale_dist_rows, age_rows = [], []
    for q in QUAL_ORDER:
        g = df[df["qualification"] == q]
        for b in SCALE_ORDER:
            n = int((g["scale_band"] == b).sum())
            scale_dist_rows.append({"qualification": q, "scale_band": b, "n": n, "share_pct": 100*n/len(g)})
        for b in AGE_ORDER + ["缺失/无法计算"]:
            n = int((g["enterprise_age_band"] == b).sum())
            age_rows.append({"qualification": q, "age_band": b, "n": n, "share_pct": 100*n/len(g)})
    scale_dist = pd.DataFrame(scale_dist_rows)
    age_dist = pd.DataFrame(age_rows)
    save_table(scale_dist, "table_scale_band_dist.csv")
    save_table(age_dist, "table_age_dist.csv")

    ip_rows = []
    for q in QUAL_ORDER:
        row = {"qualification": q}
        for b in SCALE_ORDER:
            g = df[(df["qualification"] == q) & (df["scale_band"] == b)]["ip_total"].dropna()
            row[f"{b}_n"] = len(g)
            row[f"{b}_median"] = g.median()
            row[f"{b}_q1"] = g.quantile(.25)
            row[f"{b}_q3"] = g.quantile(.75)
            row[f"{b}_warning"] = "样本不足，结论谨慎" if len(g) < 30 else ""
        ip_rows.append(row)
    ip_scale_ext = pd.DataFrame(ip_rows)
    save_table(ip_scale_ext, "table_ip_by_scale_extended.csv")
    ip_scale_rows = []
    for q in QUAL_ORDER:
        for b in SCALE_ORDER:
            cell = df[(df["qualification"] == q) & (df["scale_band"] == b)]["ip_total"].dropna()
            ip_scale_rows.append({
                "qualification": q, "scale_band": b,
                "n": int(len(cell)),
                "median_ip_total": cell.median(),
                "q1_ip_total": cell.quantile(.25),
                "q3_ip_total": cell.quantile(.75),
                "sample_warning": "样本不足，结论谨慎" if len(cell) < 30 else "",
            })
    ip_scale_long = pd.DataFrame(ip_scale_rows)
    save_table(ip_scale_long, "table_ip_by_scale.csv")

    ratio_rows = []
    for b in SCALE_ORDER:
        vals = {}
        for q in QUAL_ORDER:
            vals[q] = df[(df["qualification"] == q) & (df["scale_band"] == b)]["ip_total"].dropna().median()
        ratio_rows.append({
            "scale_band": b, "small_giant_median": vals["科技小巨人"],
            "high_tech_median": vals["高新技术企业"], "specialized_median": vals["专精特新中小企业"],
            "small_giant_over_high_tech": vals["科技小巨人"]/vals["高新技术企业"],
            "small_giant_over_specialized": vals["科技小巨人"]/vals["专精特新中小企业"],
            "specialized_over_high_tech": vals["专精特新中小企业"]/vals["高新技术企业"],
        })
    ratios = pd.DataFrame(ratio_rows)
    save_table(ratios, "table_ip_ratios.csv")

    paid_rows = []
    for q in QUAL_ORDER:
        g = df[df["qualification"] == q]
        v = g["paid_in_rate"].dropna()
        paid_rows.append({
            "qualification": q, "n_total": len(g), "n_valid": len(v), "n_missing": len(g)-len(v),
            "median": v.median(), "q1": v.quantile(.25), "q3": v.quantile(.75),
            "low_paid_n": int((v < .3).sum()),
            "low_paid_share_pct": 100*(v < .3).mean(),
            "missing_rate_pct": 100*(len(g)-len(v))/len(g),
        })
    paid = pd.DataFrame(paid_rows)
    save_table(paid, "table_paidin_compare.csv")

    comp_rows = []
    for q in QUAL_ORDER:
        g = df[df["qualification"] == q]
        comp_rows.append({
            "qualification": q, "patent_median": g["patent_count"].median(),
            "copyright_median": g["copyright_count"].median(),
            "patent_q1": g["patent_count"].quantile(.25), "patent_q3": g["patent_count"].quantile(.75),
            "copyright_q1": g["copyright_count"].quantile(.25), "copyright_q3": g["copyright_count"].quantile(.75),
        })
    comp = pd.DataFrame(comp_rows)
    save_table(comp, "table_ip_composition.csv")
    return scale, ip, pool_counts, scale_dist, age_dist, ip_scale_ext, ratios, paid, comp

def build_quality(df, con):
    raw_q = pd.read_sql_query("""
        SELECT qualification, COUNT(*) AS raw_rows,
               SUM(CASE WHEN establishment_date_raw IS NULL OR TRIM(establishment_date_raw) IN ('','-','nan','NaN','None','NULL') THEN 1 ELSE 0 END) AS raw_missing_date,
               SUM(CASE WHEN date(establishment_date_raw) > '2026-10-17' THEN 1 ELSE 0 END) AS raw_future_date,
               SUM(CASE WHEN registered_capital_wan IS NULL THEN 1 ELSE 0 END) AS raw_reg_missing,
               SUM(CASE WHEN paid_in_capital_wan IS NULL THEN 1 ELSE 0 END) AS raw_paid_missing,
               SUM(CASE WHEN insured_count IS NULL THEN 1 ELSE 0 END) AS raw_insured_missing,
               SUM(CASE WHEN credit_code IS NULL THEN 1 ELSE 0 END) AS raw_missing_credit_code
        FROM normalized_raw GROUP BY qualification
    """, con)
    clean_q = pd.read_sql_query("""
        SELECT qualification, COUNT(*) AS clean_rows,
               SUM(CASE WHEN establishment_date_quality <> 'ok' THEN 1 ELSE 0 END) AS clean_date_issue,
               SUM(CASE WHEN registered_capital_quality = 'extreme_gt_100000' THEN 1 ELSE 0 END) AS clean_reg_extreme,
               SUM(CASE WHEN paid_in_capital_quality = 'missing' THEN 1 ELSE 0 END) AS clean_paid_missing,
               SUM(CASE WHEN paid_in_capital_quality = 'extreme_gt_100000' THEN 1 ELSE 0 END) AS clean_paid_extreme,
               SUM(CASE WHEN insured_quality = 'missing' THEN 1 ELSE 0 END) AS clean_insured_missing,
               SUM(CASE WHEN insured_quality = 'zero' THEN 1 ELSE 0 END) AS clean_insured_zero,
               SUM(CASE WHEN patent_quality = 'missing' OR copyright_quality = 'missing' THEN 1 ELSE 0 END) AS clean_ip_missing,
               SUM(CASE WHEN credit_code IS NULL THEN 1 ELSE 0 END) AS clean_missing_credit_code
        FROM merged_clean GROUP BY qualification
    """, con)
    raw_q = raw_q.drop(columns=["raw_rows"])
    pool = pd.read_sql_query("SELECT * FROM pool_audit", con)
    dedup = pd.read_sql_query("SELECT * FROM dedup_audit", con)
    q = pool.merge(dedup[["qualification", "duplicate_rows_removed"]], on="qualification", how="left")
    q = q.merge(raw_q, on="qualification", how="left").merge(clean_q, on="qualification", how="left")
    q["raw_duplicate_rows"] = q["raw_rows"] - q["unique_nonmissing_codes"] - q["missing_credit_code_rows"]
    q["raw_duplicate_pct"] = 100 * q["raw_duplicate_rows"] / q["raw_rows"]
    q["paid_missing_pct"] = 100 * q["clean_paid_missing"] / q["clean_rows"]
    q["insured_missing_pct"] = 100 * q["clean_insured_missing"] / q["clean_rows"]
    q["reg_extreme_pct"] = 100 * q["clean_reg_extreme"] / q["clean_rows"]
    q["credit_missing_pct"] = 100 * q["clean_missing_credit_code"] / q["clean_rows"]
    q["qualification"] = pd.Categorical(q["qualification"], QUAL_ORDER, ordered=True)
    q = q.sort_values("qualification")
    q.to_csv(TABLES_DIR / "data_quality_summary.csv", index=False, encoding="utf-8-sig")
    return q


def build_overlap(df, con):
    sets = {q: set(df.loc[df["qualification"] == q, "credit_code"].dropna()) for q in QUAL_ORDER}
    rows = []
    for i, qa in enumerate(QUAL_ORDER):
        for qb in QUAL_ORDER[i+1:]:
            n = len(sets[qa] & sets[qb])
            rows.append({
                "membership_a": qa, "membership_b": qb, "enterprise_count": n,
                "share_a_pct": 100*n/len(sets[qa]), "share_b_pct": 100*n/len(sets[qb]),
                "note": "两资质交集",
            })
    triple = len(sets["科技小巨人"] & sets["高新技术企业"] & sets["专精特新中小企业"])
    rows.append({
        "membership_a": "小巨人+高企+专精特新", "membership_b": "三重叠加",
        "enterprise_count": triple, "share_a_pct": 100*triple/len(sets["科技小巨人"]),
        "share_b_pct": np.nan, "note": "三资质同时具备",
    })
    overlap = pd.DataFrame(rows)
    overlap.to_csv(TABLES_DIR / "table_overlap_matrix.csv", index=False, encoding="utf-8-sig")
    cross = pd.read_sql_query("SELECT * FROM cross_pool_distribution", con)
    cross["qualification_labels"] = cross["qualification_labels"].str.replace(",", " + ", regex=False).str.replace("|", " + ", regex=False)
    cross["share_pct"] = 100*cross["enterprise_count"]/cross["enterprise_count"].sum()
    cross.to_csv(TABLES_DIR / "table_cross_pool.csv", index=False, encoding="utf-8-sig")
    return overlap, cross, sets


def build_metrics(df, quality, pool_counts, paid, overlap, sets):
    qmap = quality.set_index("qualification")
    unique_codes = df["credit_code"].nunique()
    cross_codes = df.loc[df["cross_pool"] == 1, "credit_code"].nunique()
    p = paid.set_index("qualification")
    metrics = {
        "analysis_date": ANALYSIS_DATE,
        "raw_total": int(qmap["raw_rows"].sum()),
        "status_removed": int(qmap["removed_by_status"].sum()),
        "active_before_dedup": int(qmap["active_rows_before_dedup"].sum()),
        "duplicate_removed": int(qmap["duplicate_rows_removed"].sum()),
        "clean_rows": int(len(df)),
        "unique_codes": int(unique_codes),
        "cross_unique": int(cross_codes),
        "cross_share": 100*cross_codes/unique_codes,
        "raw_duplicate_rows": int(qmap["raw_duplicate_rows"].sum()),
        "pools": {},
        "overlap": {},
        "paid_median": {},
        "low_paid_share": {},
        "ip_median": {},
        "ip_density_median": {},
        "reg_cap_median": {},
        "insured_median": {},
        "age_median": {},
        "high_tech_raw_rows": int(qmap.loc["高新技术企业", "raw_rows"]),
        "high_tech_clean_rows": int(qmap.loc["高新技术企业", "clean_rows"]),
        "max_establishment_date": str(df["establishment_date"].max()),
        "max_approval_date": str(df["approval_date"].max()),
        "max_award_year": int(pd.to_numeric(df["award_year"], errors="coerce").max()),
    }
    for q in QUAL_ORDER:
        g = df[df["qualification"] == q]
        metrics["pools"][q] = {
            "rows": int(len(g)), "unique_codes": int(g["credit_code"].nunique()),
            "cross_rows": int((g["cross_pool"] == 1).sum()),
            "cross_unique": int(g.loc[g["cross_pool"] == 1, "credit_code"].nunique()),
        }
        metrics["paid_median"][q] = float(p.loc[q, "median"])
        metrics["low_paid_share"][q] = float(p.loc[q, "low_paid_share_pct"])
        metrics["ip_median"][q] = float(g["ip_total"].median())
        metrics["ip_density_median"][q] = float(g["ip_density"].median())
        metrics["reg_cap_median"][q] = float(g["registered_capital_wan"].median())
        metrics["insured_median"][q] = float(g["insured_count"].median())
        metrics["age_median"][q] = float(g["enterprise_age"].median())
    for _, r in overlap.iterrows():
        key = f"{r['membership_a']}|{r['membership_b']}"
        metrics["overlap"][key] = {
            "count": int(r["enterprise_count"]),
            "share_a": None if pd.isna(r["share_a_pct"]) else float(r["share_a_pct"]),
            "share_b": None if pd.isna(r["share_b_pct"]) else float(r["share_b_pct"]),
        }
    metrics["all_three"] = int(len(sets["科技小巨人"] & sets["高新技术企业"] & sets["专精特新中小企业"]))
    metrics["small_giant_high_share"] = float(100*len(sets["科技小巨人"] & sets["高新技术企业"])/len(sets["科技小巨人"]))
    metrics["small_giant_specialized_share"] = float(100*len(sets["科技小巨人"] & sets["专精特新中小企业"])/len(sets["科技小巨人"]))
    metrics["specialized_high_share"] = float(100*len(sets["专精特新中小企业"] & sets["高新技术企业"])/len(sets["专精特新中小企业"]))
    (ROOT / "outputs" / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics

def plot_overview(metrics):
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    y = np.arange(len(QUAL_ORDER))
    specs = [
        (axes[0,0], [metrics["pools"][q]["rows"] for q in QUAL_ORDER], "会员记录数", "条", "{:,.0f}", False),
        (axes[0,1], [metrics["reg_cap_median"][q] for q in QUAL_ORDER], "注册资本中位数", "万元", "{:,.0f}", False),
        (axes[1,0], [metrics["ip_median"][q] for q in QUAL_ORDER], "知产总数中位数", "件", "{:,.0f}", True),
        (axes[1,1], [metrics["low_paid_share"][q] for q in QUAL_ORDER], "低实缴占比", "%", "{:.1f}%", True),
    ]
    for ax, vals, title, unit, fmt, highlight in specs:
        bars = ax.barh(y, vals, color=[COLORS[q] for q in QUAL_ORDER], alpha=.88, height=.58)
        ax.set_yticks(y)
        ax.set_yticklabels([SHORT[q] for q in QUAL_ORDER])
        ax.invert_yaxis()
        ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=14)
        style_ax(ax, grid_axis="x")
        ax.set_xlabel(unit)
        for bar, v in zip(bars, vals):
            ax.text(v, bar.get_y()+bar.get_height()/2, "  "+fmt.format(v), va="center", ha="left", fontsize=9, color=TEXT)
        ax.set_xlim(0, max(vals)*1.22 if max(vals) else 1)
        if highlight:
            ax.axvline(np.mean(vals), color=MUTED, lw=1, ls=":", alpha=.7)
    fig.suptitle("三类科创资质池：规模、知产与实缴概览", x=.06, ha="left", fontsize=19, fontweight="bold")
    fig.text(.06, .94, f"分析日 {ANALYSIS_DATE} ｜ 同一企业可能出现在多个资质池 ｜ 所有数值为描述性统计", fontsize=9, color=MUTED)
    fig.text(.06, .01, "数据来源：三份资质名单 Excel；SQL 清洗合并，Python 统计绘图。", fontsize=8, color=MUTED)
    fig.tight_layout(rect=[0, .04, 1, .9])
    save_fig(fig, "00_overview_dashboard.png")


def plot_funnel(metrics):
    stages = ["原始记录", "存续/在业", "去重后成员记录", "唯一信用代码企业"]
    vals = [metrics["raw_total"], metrics["active_before_dedup"], metrics["clean_rows"], metrics["unique_codes"]]
    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    colors = ["#DCE6F2", "#9ECAE1", "#4292C6", "#08519C"]
    y = np.arange(len(stages))
    bars = ax.barh(y, vals, color=colors, height=.62)
    ax.set_yticks(y)
    ax.set_yticklabels(stages)
    ax.invert_yaxis()
    ax.set_xlabel("记录数 / 企业数")
    ax.set_title("样本漏斗：从原始名单到可分析企业", loc="left", fontsize=17, fontweight="bold", pad=16)
    style_ax(ax, grid_axis="x")
    for bar, v in zip(bars, vals):
        pct = 100*v/vals[0]
        ax.text(v, bar.get_y()+bar.get_height()/2, f"  {v:,}  ({pct:.1f}%)", va="center", fontsize=10, fontweight="bold")
    ax.set_xlim(0, vals[0]*1.24)
    fig.text(.08, .01, "注：第三阶段为“资质×企业”成员记录，因此大于唯一企业数；跨池企业保留多条资质记录。", fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=[0, .04, 1, 1])
    save_fig(fig, "01_sample_funnel.png")


def plot_overlap(sets, metrics):
    a = len(sets["科技小巨人"]); h = len(sets["高新技术企业"]); z = len(sets["专精特新中小企业"])
    ah = len(sets["科技小巨人"] & sets["高新技术企业"])
    az = len(sets["科技小巨人"] & sets["专精特新中小企业"])
    hz = len(sets["高新技术企业"] & sets["专精特新中小企业"])
    all3 = len(sets["科技小巨人"] & sets["高新技术企业"] & sets["专精特新中小企业"])
    a_only = a-ah-az+all3; h_only = h-ah-hz+all3; z_only = z-az-hz+all3
    ah_only = ah-all3; az_only = az-all3; hz_only = hz-all3
    fig, ax = plt.subplots(figsize=(10.5, 7.6))
    circles = [
        Circle((.40,.61), .30, facecolor=COLORS["科技小巨人"], alpha=.22, edgecolor=COLORS["科技小巨人"], lw=2),
        Circle((.62,.61), .30, facecolor=COLORS["高新技术企业"], alpha=.18, edgecolor=COLORS["高新技术企业"], lw=2),
        Circle((.51,.40), .30, facecolor=COLORS["专精特新中小企业"], alpha=.20, edgecolor=COLORS["专精特新中小企业"], lw=2),
    ]
    for c in circles: ax.add_patch(c)
    ax.set_xlim(.02,.98); ax.set_ylim(.02,.95); ax.axis("off")
    ax.set_title("资质叠加关系：三池不是独立总体", fontsize=18, fontweight="bold", loc="left", pad=12)
    labels = [
        (.22,.79,a_only), (.80,.79,h_only), (.51,.17,z_only),
        (.51,.76,ah_only), (.32,.42,az_only), (.70,.42,hz_only), (.51,.54,all3),
    ]
    for x,y,v in labels:
        ax.text(x,y,f"{v:,}", ha="center", va="center", fontsize=13, fontweight="bold",
                bbox=dict(facecolor="white", edgecolor="none", alpha=.86, pad=1.8))
    ax.text(.40,.90,"科技小巨人",color=COLORS["科技小巨人"],ha="center",fontsize=11,fontweight="bold")
    ax.text(.62,.90,"高新技术企业",color=COLORS["高新技术企业"],ha="center",fontsize=11,fontweight="bold")
    ax.text(.51,.08,"专精特新中小企业",color=COLORS["专精特新中小企业"],ha="center",fontsize=11,fontweight="bold")
    ax.text(.02,.01,f"可识别信用代码企业 {metrics['unique_codes']:,} 家；不含信用代码缺失的 {metrics['clean_rows']-metrics['unique_codes']} 条成员记录。",fontsize=8.5,color=MUTED)
    fig.tight_layout()
    save_fig(fig, "02_qualification_overlap.png")


def plot_scale_gradient(scale):
    specs = [("注册资本", "万元", True), ("参保人数", "人", True), ("企业年龄", "年", False)]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.8))
    y = np.arange(len(QUAL_ORDER))[::-1]
    s = scale.set_index(["qualification","metric"])
    for ax, (metric, unit, logx) in zip(axes, specs):
        for yi,q in zip(y, QUAL_ORDER):
            r = s.loc[(q,metric)]
            ax.plot([r["q1"],r["q3"]],[yi,yi], color=COLORS[q], lw=8, alpha=.28, solid_capstyle="round")
            ax.scatter(r["median"], yi, s=95, color=COLORS[q], edgecolor="white", linewidth=1.5, zorder=3)
            ax.text(r["median"], yi+.22, f"{r['median']:.1f}", ha="center", va="bottom", fontsize=9, color=COLORS[q], fontweight="bold")
        ax.set_yticks(y)
        ax.set_yticklabels([SHORT[q] for q in QUAL_ORDER])
        ax.set_title(metric, loc="left", fontsize=13, fontweight="bold")
        ax.set_xlabel(unit)
        if logx: ax.set_xscale("log")
        style_ax(ax, grid_axis="x")
    fig.suptitle("规模梯度：小巨人最高，高企最低", x=.06, ha="left", fontsize=18, fontweight="bold")
    fig.text(.06,.01,"点=中位数；横线=Q1–Q3。注册资本和参保人数使用对数轴；资本单位为万元。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,.93])
    save_fig(fig, "03_scale_gradient.png")


def plot_structure(scale_dist, age_dist):
    fig, axes = plt.subplots(1,2,figsize=(14.5,5.8))
    scale_cols = [("<50","#0B6E99"),("50-200","#4FA3C7"),("200+","#A9D6E5"),("缺失","#D1D5DB")]
    age_cols = [("3年内","#E9C46A"),("3-10年","#F4A261"),("10年以上","#E76F51")]
    def draw(ax, data, cols, title):
        left = np.zeros(len(QUAL_ORDER))
        for cat,color in cols:
            vals = [float(data.loc[(q,cat),"share_pct"]) if (q,cat) in data.index else 0 for q in QUAL_ORDER]
            ax.barh(np.arange(len(QUAL_ORDER)), vals, left=left, color=color, label=cat, height=.55)
            for i,v in enumerate(vals):
                if v>=8: ax.text(left[i]+v/2,i,f"{v:.1f}%",ha="center",va="center",fontsize=8.5,color="white",fontweight="bold")
            left += np.array(vals)
        ax.set_yticks(np.arange(len(QUAL_ORDER))); ax.set_yticklabels([SHORT[q] for q in QUAL_ORDER]); ax.invert_yaxis()
        ax.set_xlim(0,100); ax.set_xlabel("占比（%）"); ax.set_title(title,loc="left",fontsize=13,fontweight="bold")
        style_ax(ax,grid_axis="x"); ax.legend(ncol=len(cols), loc="upper center", bbox_to_anchor=(.5,-.22), frameon=False, fontsize=8.5)
    draw(axes[0], scale_dist.set_index(["qualification","scale_band"]), scale_cols, "参保人数规模分档")
    draw(axes[1], age_dist.set_index(["qualification","age_band"]), age_cols, "企业年龄分档")
    fig.suptitle("样本结构：高企更偏小微、三池均以成熟企业为主",x=.06,ha="left",fontsize=18,fontweight="bold")
    fig.text(.06,.01,"年龄按分析日 2026-10-17 与成立日期计算；数据最新成立日期为 2022-12-30，因此三池均无“3年内”企业。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.06,1,.93])
    save_fig(fig,"04_population_structure.png")

def plot_ip_by_scale(ip_scale_ext):
    x = np.arange(len(SCALE_ORDER))
    width = .25
    fig, ax = plt.subplots(figsize=(13.5, 6.8))
    for i,q in enumerate(QUAL_ORDER):
        row = ip_scale_ext.set_index("qualification").loc[q]
        vals = [row[f"{b}_median"] for b in SCALE_ORDER]
        ns = [int(row[f"{b}_n"]) for b in SCALE_ORDER]
        bars = ax.bar(x+(i-1)*width, vals, width, label=SHORT[q], color=COLORS[q], alpha=.88)
        for bar,v,n in zip(bars,vals,ns):
            label = f"{v:.1f}\nn={n:,}"
            if n < 30: label += "\n样本不足*"
            ax.text(bar.get_x()+bar.get_width()/2, v+2, label, ha="center", va="bottom",
                    fontsize=8, color="#B00020" if n<30 else TEXT, fontweight="bold" if n<30 else "normal")
    ax.set_xticks(x); ax.set_xticklabels(SCALE_ORDER)
    ax.set_xlabel("规模分档（参保人数）"); ax.set_ylabel("知产总数中位数（件）")
    ax.set_title("控制规模后，小巨人的知产总量优势仍然存在但逐步收窄", loc="left", fontsize=17, fontweight="bold", pad=14)
    style_ax(ax); ax.legend(title="资质池", frameon=False, ncol=3, loc="upper left")
    ax.set_ylim(0, max(145, float(ip_scale_ext[[f"{b}_median" for b in SCALE_ORDER]].max().max())*1.28))
    fig.text(.06,.01,"柱顶为中位数与有效样本量；* n<30，样本不足，结论谨慎。同一企业可能进入多个资质池。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,1])
    save_fig(fig,"05_ip_by_scale.png")


def plot_ip_density(df, ip):
    fig, ax = plt.subplots(figsize=(11.5,5.8))
    vals, labels = [], []
    s = ip.set_index(["qualification","metric"])
    for q in QUAL_ORDER:
        v = df.loc[df["qualification"]==q,"ip_density"].dropna()
        vals.append(v.values); labels.append(f"{SHORT[q]}\n(n={len(v):,})")
    bp = ax.boxplot(vals, tick_labels=labels, vert=False, patch_artist=True, widths=.52,
                    medianprops={"color":"white","linewidth":2},
                    flierprops={"marker":"o","markersize":2.3,"alpha":.25})
    for patch,q in zip(bp["boxes"],QUAL_ORDER):
        patch.set_facecolor(COLORS[q]); patch.set_alpha(.82)
    ax.set_xscale("log")
    ax.set_xlabel("知产密度 = 知产总数 / 参保人数（对数轴）")
    ax.set_title("每位参保人员的知产产出：高企反而最高", loc="left", fontsize=17, fontweight="bold", pad=14)
    style_ax(ax, grid_axis="x")
    for i,q in enumerate(QUAL_ORDER, start=1):
        med = s.loc[(q,"知产密度"),"median"]
        ax.text(med, i+.34, f"中位数 {med:.3f}", ha="center", va="bottom", fontsize=9, color=COLORS[q], fontweight="bold")
    fig.text(.06,.01,"仅计算参保人数>0且知产字段完整的记录。总量与密度排序相反，说明规模是重要解释变量。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,1])
    save_fig(fig,"06_ip_density.png")


def plot_paidin(df, paid):
    fig, axes = plt.subplots(1,2,figsize=(15,6.0),gridspec_kw={"width_ratios":[1.25,1]})
    vals, labels = [], []
    for q in QUAL_ORDER:
        v = df.loc[df["qualification"]==q,"paid_in_rate"].dropna()
        vals.append(v.values); labels.append(f"{SHORT[q]}\n(n={len(v):,})")
    bp = axes[0].boxplot(vals, tick_labels=labels, patch_artist=True, widths=.5,
                         medianprops={"color":"white","linewidth":2},
                         flierprops={"marker":"o","markersize":2.2,"alpha":.25})
    for patch,q in zip(bp["boxes"],QUAL_ORDER):
        patch.set_facecolor(COLORS[q]); patch.set_alpha(.82)
    axes[0].set_ylim(0,1.05); axes[0].set_ylabel("实缴率")
    axes[0].set_title("实缴率分布", loc="left", fontsize=13, fontweight="bold")
    style_ax(axes[0])
    p = paid.set_index("qualification").loc[QUAL_ORDER]
    y = np.arange(len(QUAL_ORDER))
    bars = axes[1].barh(y,p["low_paid_share_pct"],color=[COLORS[q] for q in QUAL_ORDER],alpha=.88,height=.55)
    axes[1].set_yticks(y); axes[1].set_yticklabels([SHORT[q] for q in QUAL_ORDER]); axes[1].invert_yaxis()
    axes[1].set_xlabel("低实缴占比（%）"); axes[1].set_xlim(0,max(38,p["low_paid_share_pct"].max()*1.32))
    axes[1].set_title("低实缴（<30%）占比", loc="left", fontsize=13, fontweight="bold")
    style_ax(axes[1],grid_axis="x")
    for bar,v,n in zip(bars,p["low_paid_share_pct"],p["low_paid_n"]):
        axes[1].text(v,bar.get_y()+bar.get_height()/2,f"  {v:.1f}%  (n={int(n):,})",va="center",fontsize=9,fontweight="bold")
    fig.suptitle("实缴率张力：高企低实缴更集中，但缺失率也更高",x=.06,ha="left",fontsize=18,fontweight="bold")
    fig.text(.06,.01,"实缴率仅对注册资本>0且实缴资本非缺失的记录计算；低实缴占比的分母为可计算样本。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,.93])
    save_fig(fig,"07_paidin_compliance.png")


def plot_quality(quality):
    q = quality.set_index("qualification").loc[QUAL_ORDER]
    cols = [
        ("raw_duplicate_pct","原始重复率"),
        ("paid_missing_pct","实缴资本缺失率"),
        ("insured_missing_pct","参保人数缺失率"),
        ("reg_extreme_pct","注册资本>10亿占比"),
        ("credit_missing_pct","信用代码缺失率"),
    ]
    mat = q[[c for c,_ in cols]].values.astype(float)
    fig, ax = plt.subplots(figsize=(12.2,4.7))
    im = ax.imshow(mat,cmap="Reds",aspect="auto",vmin=0,vmax=max(45,mat.max()*1.05))
    ax.set_xticks(np.arange(len(cols))); ax.set_xticklabels([label for _,label in cols],rotation=25,ha="right")
    ax.set_yticks(np.arange(len(QUAL_ORDER))); ax.set_yticklabels([SHORT[q] for q in QUAL_ORDER])
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v=mat[i,j]
            ax.text(j,i,f"{v:.2f}%",ha="center",va="center",fontsize=9,color="white" if v>22 else TEXT,fontweight="bold")
    ax.set_title("数据质量热力图：高企与专精特新的重复、缺失问题更突出",loc="left",fontsize=16,fontweight="bold",pad=14)
    ax.tick_params(length=0)
    for s in ax.spines.values(): s.set_visible(False)
    cbar=fig.colorbar(im,ax=ax,fraction=.025,pad=.02); cbar.set_label("比例（%）")
    fig.text(.06,.01,"“原始重复率”基于去重前名单；“实缴资本缺失率”等基于清洗后样本。颜色越深表示质量问题越突出。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,1])
    save_fig(fig,"08_data_quality_heatmap.png")


def plot_ip_composition(comp):
    fig, ax = plt.subplots(figsize=(11.2,5.6))
    y=np.arange(len(QUAL_ORDER))[::-1]; h=.32
    p=comp.set_index("qualification").loc[QUAL_ORDER]
    ax.barh(y+h/2,p["patent_median"],height=h,color="#264653",label="专利数中位数",alpha=.92)
    ax.barh(y-h/2,p["copyright_median"],height=h,color="#E9C46A",label="著作权数中位数",alpha=.95)
    for yi,q in zip(y,QUAL_ORDER):
        ax.text(p.loc[q,"patent_median"],yi+h/2,f"  {p.loc[q,'patent_median']:.0f}",va="center",fontsize=9)
        ax.text(p.loc[q,"copyright_median"],yi-h/2,f"  {p.loc[q,'copyright_median']:.0f}",va="center",fontsize=9)
    ax.set_yticks(y); ax.set_yticklabels([SHORT[q] for q in QUAL_ORDER])
    ax.set_xlabel("件"); ax.set_title("知产结构：小巨人的专利数量优势最明显",loc="left",fontsize=17,fontweight="bold",pad=14)
    style_ax(ax,grid_axis="x"); ax.legend(frameon=False,ncol=2,loc="lower right")
    fig.text(.06,.01,"图中展示专利数和著作权数的中位数，不能直接相加还原知产总数中位数。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,1])
    save_fig(fig,"09_ip_composition.png")


def main():
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query("SELECT * FROM merged_clean", con)
        quality = build_quality(df, con)
        scale, ip, pool_counts, scale_dist, age_dist, ip_scale_ext, ratios, paid, comp = build_tables(df, con)
        overlap, cross, sets = build_overlap(df, con)
        metrics = build_metrics(df, quality, pool_counts, paid, overlap, sets)
    df.to_csv(PROCESSED_DIR / "merged_clean.csv", index=False, encoding="utf-8-sig")
    plot_overview(metrics)
    plot_funnel(metrics)
    plot_overlap(sets, metrics)
    plot_scale_gradient(scale)
    plot_structure(scale_dist, age_dist)
    plot_ip_by_scale(ip_scale_ext)
    plot_ip_density(df, ip)
    plot_paidin(df, paid)
    plot_quality(quality)
    plot_ip_composition(comp)
    print(json.dumps({
        "clean_rows": metrics["clean_rows"], "unique_codes": metrics["unique_codes"],
        "cross_unique": metrics["cross_unique"], "tables": len(list(TABLES_DIR.glob('*.csv'))),
        "figures": len(list(IMAGES_DIR.glob('*.png'))),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
