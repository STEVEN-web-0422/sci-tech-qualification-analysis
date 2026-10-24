# -*- coding: utf-8 -*-
"""Direction 1: stratified and propensity-score matched qualification-stack analysis."""
from pathlib import Path
import json
import os
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("ANALYSIS_DB", ROOT / "data" / "analysis.sqlite"))
TABLES = ROOT / "outputs" / "tables"
IMAGES = ROOT / "docs" / "images"
SEED = 20261017
RNG = np.random.default_rng(SEED)
CONTROL = "纯高企"
TREATMENTS = ["高企+专精特新", "高企+小巨人", "三重叠加"]
COHORT_ORDER = [CONTROL] + TREATMENTS
COLORS = {"纯高企": "#6B7280", "高企+专精特新": "#009E73", "高企+小巨人": "#D55E00", "三重叠加": "#7B2CBF"}
TEXT = "#1F2937"
MUTED = "#6B7280"
GRID = "#E5E7EB"
SCALE_ORDER = ["<50", "50-200", "200+"]

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"],
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#D1D5DB",
    "text.color": TEXT,
    "axes.labelcolor": TEXT,
    "xtick.color": TEXT,
    "ytick.color": TEXT,
    "font.size": 10,
})


def style_ax(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=.8, alpha=.8)
        ax.set_axisbelow(True)


def save_fig(fig, name):
    fig.savefig(IMAGES / name, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)




def load_data():
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query("SELECT * FROM high_tech_analysis", con)
    df["log_insured"] = np.log1p(df["insured_count"])
    df["log_reg_cap"] = np.log1p(df["registered_capital_wan"])
    return df


def cohort_summary(df):
    rows=[]
    for c in COHORT_ORDER:
        g=df[df["cohort"]==c]
        rows.append({
            "cohort": c, "n": len(g),
            "ip_total_median": g["ip_total"].median(),
            "patent_median": g["patent_count"].median(),
            "copyright_median": g["copyright_count"].median(),
            "ip_density_median": g["ip_density"].median(),
            "insured_median": g["insured_count"].median(),
            "reg_cap_median": g["registered_capital_wan"].median(),
            "age_median": g["enterprise_age"].median(),
        })
    out=pd.DataFrame(rows)
    out.to_csv(TABLES / "direction1_cohort_summary.csv", index=False, encoding="utf-8-sig")
    return out


def raw_stratified(df):
    rows=[]
    for c in COHORT_ORDER:
        for b in SCALE_ORDER:
            g=df[(df["cohort"]==c)&(df["scale_band"]==b)]
            rows.append({
                "cohort": c, "scale_band": b, "n": len(g),
                "ip_total_median": g["ip_total"].median(),
                "ip_total_q1": g["ip_total"].quantile(.25),
                "ip_total_q3": g["ip_total"].quantile(.75),
                "ip_density_median": g["ip_density"].median(),
                "sample_warning": "样本不足，结论谨慎" if len(g)<30 else "",
            })
    out=pd.DataFrame(rows)
    out.to_csv(TABLES / "direction1_raw_stratified.csv", index=False, encoding="utf-8-sig")
    return out

def make_design(sample):
    num = sample[["log_insured", "log_reg_cap", "enterprise_age"]].copy()
    num["insured_missing"] = sample["insured_count"].isna().astype(int)
    num["reg_cap_missing"] = sample["registered_capital_wan"].isna().astype(int)
    for col in ["log_insured", "log_reg_cap", "enterprise_age"]:
        num[col] = num[col].fillna(num[col].median())
    dummies = pd.get_dummies(
        sample[["industry_group", "district_group", "type_group"]].astype(str),
        drop_first=False, dtype=float,
    )
    X = pd.concat([num.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
    return X


def smd_numeric(t, c):
    t = pd.to_numeric(t, errors="coerce").dropna()
    c = pd.to_numeric(c, errors="coerce").dropna()
    if len(t) < 2 or len(c) < 2:
        return np.nan
    pooled = np.sqrt((t.var(ddof=1) + c.var(ddof=1)) / 2)
    return 0.0 if pooled == 0 else abs(t.mean() - c.mean()) / pooled


def smd_categorical(t, c):
    cats = sorted(set(t.dropna().astype(str)) | set(c.dropna().astype(str)))
    values = []
    for cat in cats:
        pt = (t.astype(str) == cat).mean()
        pc = (c.astype(str) == cat).mean()
        denom = np.sqrt((pt * (1-pt) + pc * (1-pc)) / 2)
        if denom > 0:
            values.append(abs(pt-pc) / denom)
    return max(values) if values else np.nan


def balance_table(treat, control):
    specs = [
        ("参保人数（log）", "log_insured", "numeric"),
        ("注册资本（log）", "log_reg_cap", "numeric"),
        ("企业年龄", "enterprise_age", "numeric"),
        ("行业门类", "industry_group", "categorical"),
        ("区县", "district_group", "categorical"),
        ("企业类型", "type_group", "categorical"),
        ("年龄分档", "enterprise_age_band", "categorical"),
        ("资本四分位", "cap_quartile", "categorical"),
    ]
    rows = []
    for label, col, typ in specs:
        fn = smd_numeric if typ == "numeric" else smd_categorical
        rows.append({"variable": label, "type": typ, "smd": fn(treat[col], control[col])})
    return pd.DataFrame(rows)


def propensity_match(df, treatment):
    sample = df[df["cohort"].isin([CONTROL, treatment])].copy().reset_index(drop=True)
    for col in ["enterprise_age", "log_insured", "log_reg_cap"]:
        sample[col] = sample[col].fillna(sample[col].median())
    X = make_design(sample)
    y = (sample["cohort"] == treatment).astype(int).values
    model = Pipeline([
        ("scale", StandardScaler(with_mean=False)),
        ("logit", LogisticRegression(C=1.0, max_iter=3000, solver="lbfgs", random_state=SEED)),
    ])
    model.fit(X, y)
    ps = model.predict_proba(X)[:, 1]
    eps = 1e-6
    sample["ps"] = np.clip(ps, eps, 1-eps)
    sample["logit_ps"] = np.log(sample["ps"]/(1-sample["ps"]))
    t_idx = sample.index[sample["cohort"] == treatment].to_numpy()
    c_idx = sample.index[sample["cohort"] == CONTROL].to_numpy()
    # Coarsened exact cells balance industry, district, size band, legal type,
    # age band and capital quartile exactly. Within each cell, nearest matching
    # uses the propensity score plus the remaining continuous covariates.
    caliper = 5.0
    match_features = ["logit_ps", "enterprise_age", "log_insured", "log_reg_cap"]
    sample["match_key"] = (
        sample["scale_band"].astype(str) + "|" +
        sample["industry_group"].astype(str) + "|" +
        sample["district_group"].astype(str) + "|" +
        sample["type_group"].astype(str) + "|" +
        sample["enterprise_age_band"].astype(str) + "|" +
        sample["cap_quartile"].astype(str)
    )
    used = set()
    pairs = []
    treated_all = sample[sample["cohort"] == treatment]
    for key, tg in treated_all.groupby("match_key"):
        cg = sample[(sample["cohort"] == CONTROL) & (sample["match_key"] == key)]
        if cg.empty:
            continue
        scaler = StandardScaler().fit(cg[match_features])
        ctrl_scaled = scaler.transform(cg[match_features])
        knn = NearestNeighbors(n_neighbors=min(100, len(cg))).fit(ctrl_scaled)
        for ti in tg.index[np.argsort(-tg["logit_ps"].values)]:
            dist, inds = knn.kneighbors(scaler.transform(sample.loc[[ti], match_features]))
            for d, pos in zip(dist[0], inds[0]):
                ci = cg.index[pos]
                if ci not in used and d <= caliper:
                    used.add(ci)
                    pairs.append((ti, ci))
                    break
    pair_df = pd.DataFrame(pairs, columns=["treated_idx", "control_idx"])
    pair_df["pair_id"] = np.arange(1, len(pair_df)+1)
    treated = sample.loc[pair_df["treated_idx"]].copy()
    control = sample.loc[pair_df["control_idx"]].copy()
    treated["pair_id"] = pair_df["pair_id"].values
    control["pair_id"] = pair_df["pair_id"].values
    treated["role"] = "treated"
    control["role"] = "control"
    matched = pd.concat([treated, control], ignore_index=True)
    bal_after = balance_table(treated, control).set_index("variable")
    treat_all = sample[sample["cohort"] == treatment]
    ctrl_all = sample[sample["cohort"] == CONTROL]
    bal_before = balance_table(treat_all, ctrl_all).set_index("variable")["smd"]
    bal = bal_after.reset_index()
    bal["smd_before"] = bal["variable"].map(bal_before)
    bal["smd_after"] = bal["smd"]
    bal["cohort"] = treatment
    summary = {
        "cohort": treatment,
        "treated_available": len(treat_all),
        "control_available": len(ctrl_all),
        "matched_pairs": len(pair_df),
        "match_rate_pct": 100*len(pair_df)/len(treat_all),
        "caliper_composite": caliper,
        "max_smd_before": float(bal["smd_before"].max()),
        "max_smd_after": float(bal["smd_after"].max()),
    }
    return treated, control, matched, bal, summary

def paired_effect(treated, control, metric, treatment, scale_band="全部", B=2000):
    left = treated[["pair_id", metric, "scale_band"]].rename(columns={metric:"t"}).set_index("pair_id")
    right = control[["pair_id", metric]].rename(columns={metric:"c"}).set_index("pair_id")
    dat = left.join(right, how="inner")
    if scale_band != "全部":
        dat = dat[dat["scale_band"] == scale_band]
    dat = dat[["t","c"]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(dat) < 5:
        return None
    t = dat["t"].to_numpy(float); c = dat["c"].to_numpy(float)
    mt, mc = np.median(t), np.median(c)
    diff = mt - mc
    ratio = mt / mc if mc != 0 else np.nan
    rng = np.random.default_rng(SEED + len(dat))
    bdiff, bratio = [], []
    n = len(dat)
    for _ in range(B):
        idx = rng.integers(0, n, n)
        bt, bc = np.median(t[idx]), np.median(c[idx])
        bdiff.append(bt-bc)
        bratio.append(bt/bc if bc != 0 else np.nan)
    return {
        "contrast": treatment, "scale_band": scale_band, "metric": metric,
        "n_pairs": n,
        "treated_median": mt, "control_median": mc,
        "median_diff": diff,
        "diff_ci_low": np.percentile(bdiff, 2.5), "diff_ci_high": np.percentile(bdiff, 97.5),
        "median_ratio": ratio,
        "ratio_ci_low": np.nanpercentile(bratio, 2.5), "ratio_ci_high": np.nanpercentile(bratio, 97.5),
        "pct_diff": 100*(ratio-1) if pd.notna(ratio) else np.nan,
        "pct_ci_low": 100*(np.nanpercentile(bratio, 2.5)-1),
        "pct_ci_high": 100*(np.nanpercentile(bratio, 97.5)-1),
        "sample_warning": "样本不足，结论谨慎" if n < 30 else "",
    }

def plot_raw_stratified(raw):
    fig, ax = plt.subplots(figsize=(13.5,6.4))
    x = np.arange(4); width=.19
    bands = ["<50","50-200","200+","缺失"]
    for i,c in enumerate(COHORT_ORDER):
        vals=[]
        for b in bands:
            tmp=raw[(raw["cohort"]==c)&(raw["scale_band"]==b)]
            vals.append(np.nan if tmp.empty else tmp.iloc[0]["ip_total_median"])
        bars=ax.bar(x+(i-1.5)*width, vals, width, label=c, color=COLORS[c], alpha=.9)
        for bar,v in zip(bars,vals):
            if pd.notna(v): ax.text(bar.get_x()+bar.get_width()/2,v+2,f"{v:.0f}",ha="center",va="bottom",fontsize=7.5)
    ax.set_xticks(x); ax.set_xticklabels(bands); ax.set_ylabel("知产总数中位数（件）")
    ax.set_title("方向 1：不同资质组合在规模档内的知产总量中位数", loc="left", fontsize=16, fontweight="bold", pad=14)
    style_ax(ax); ax.legend(frameon=False,ncol=2,loc="upper left")
    fig.text(.06,.01,"“缺失”规模档样本较少；正式比较以 <50、50-200、200+ 三档为主。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,1])
    save_fig(fig,"direction1_raw_stratified.png")


def plot_balance(balance):
    fig, axes = plt.subplots(1,3,figsize=(15.5,5.3),sharey=True)
    order=["参保人数（log）","注册资本（log）","企业年龄","行业门类","区县","企业类型","年龄分档","资本四分位"]
    for ax,c in zip(axes,TREATMENTS):
        b=balance[balance["cohort"]==c].set_index("variable").loc[order]
        y=np.arange(len(order))
        ax.scatter(b["smd_before"],y,s=55,facecolors="white",edgecolors=MUTED,label="匹配前",zorder=3)
        ax.scatter(b["smd_after"],y,s=55,color=COLORS[c],label="匹配后",zorder=4)
        for yi,(a,z) in enumerate(zip(b["smd_before"],b["smd_after"])):
            ax.plot([a,z],[yi,yi],color="#D1D5DB",lw=1.5,zorder=1)
        ax.axvline(.1,color="#B00020",ls="--",lw=1,label="0.1 参考线")
        ax.set_yticks(y); ax.set_yticklabels(order); ax.invert_yaxis()
        ax.set_xlabel("标准化均值差 SMD"); ax.set_title(c,fontsize=12,fontweight="bold")
        style_ax(ax,grid_axis="x")
    axes[0].legend(frameon=False,loc="lower right",fontsize=8)
    fig.suptitle("方向 1：倾向得分匹配前后的协变量平衡",x=.06,ha="left",fontsize=17,fontweight="bold")
    fig.text(.06,.01,"分类变量展示各类别 SMD 的最大绝对值；SMD<0.1 通常视为可接受的平衡水平。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,.92])
    save_fig(fig,"direction1_balance.png")


def plot_forest(effects):
    fig, axes = plt.subplots(1,2,figsize=(13.5,5.4))
    specs=[("ip_total","知产总数"),("ip_density","知产密度")]
    for ax,(metric,label) in zip(axes,specs):
        d=effects[(effects["metric"]==metric)&(effects["scale_band"]=="全部")].set_index("contrast").loc[TREATMENTS]
        y=np.arange(len(TREATMENTS))
        for yi,c in zip(y,TREATMENTS):
            r=d.loc[c]
            ax.errorbar(r["pct_diff"],yi,xerr=[[r["pct_diff"]-r["pct_ci_low"]],[r["pct_ci_high"]-r["pct_diff"]]],
                        fmt="o",color=COLORS[c],capsize=4,markersize=7,lw=2)
            ax.text(r["pct_ci_high"]+5,yi,f"{r['pct_diff']:+.1f}%",va="center",fontsize=9,color=COLORS[c],fontweight="bold")
        ax.axvline(0,color=MUTED,lw=1)
        ax.set_yticks(y); ax.set_yticklabels(TREATMENTS); ax.invert_yaxis()
        ax.set_xlabel(f"{label}中位数相对纯高企的变化（%）")
        ax.set_title(label,fontsize=13,fontweight="bold")
        style_ax(ax,grid_axis="x")
    fig.suptitle("方向 1：匹配后资质叠加的相对知产差异（Bootstrap 95% CI）",x=.06,ha="left",fontsize=17,fontweight="bold")
    fig.text(.06,.01,"横轴为处理组中位数相对纯高企中位数的百分比变化；区间跨 0 表示描述性差异不稳健。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,.92])
    save_fig(fig,"direction1_forest.png")


def plot_scale_forest(by_scale):
    fig, axes = plt.subplots(1,2,figsize=(14.5,6.2))
    specs=[("ip_total","知产总数"),("ip_density","知产密度")]
    labels=[]; rows=[]
    for c in TREATMENTS:
        for b in SCALE_ORDER:
            labels.append(f"{c}\n{b}")
            rows.append((c,b))
    for ax,(metric,label) in zip(axes,specs):
        d=by_scale[by_scale["metric"]==metric].set_index(["contrast","scale_band"])
        y=np.arange(len(rows))
        for yi,(c,b) in zip(y,rows):
            if (c,b) not in d.index:
                continue
            r=d.loc[(c,b)]
            ax.errorbar(r["pct_diff"],yi,xerr=[[r["pct_diff"]-r["pct_ci_low"]],[r["pct_ci_high"]-r["pct_diff"]]],
                        fmt="o",color=COLORS[c],capsize=3,markersize=6,lw=1.8)
        ax.axvline(0,color=MUTED,lw=1)
        ax.set_yticks(y); ax.set_yticklabels(labels,fontsize=7.8); ax.invert_yaxis()
        ax.set_xlabel(f"{label}中位数变化（%）"); ax.set_title(label,fontsize=13,fontweight="bold")
        style_ax(ax,grid_axis="x")
    fig.suptitle("方向 1：按规模档拆分的匹配后效应",x=.06,ha="left",fontsize=17,fontweight="bold")
    fig.text(.06,.01,"每一行先按资质组合、再按参保人数档拆分；小样本格子需谨慎解读。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.05,1,.92])
    save_fig(fig,"direction1_scale_forest.png")

def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)
    df = load_data()
    cohort_summary(df)
    raw = raw_stratified(df)
    all_balance = []
    summaries = []
    overall_effects = []
    scale_effects = []
    for treatment in TREATMENTS:
        treated, control, matched, bal, summary = propensity_match(df, treatment)
        all_balance.append(bal)
        summaries.append(summary)
        for metric in ["ip_total", "patent_count", "copyright_count", "ip_density"]:
            eff = paired_effect(treated, control, metric, treatment, "全部")
            if eff: overall_effects.append(eff)
            for band in SCALE_ORDER:
                se = paired_effect(treated, control, metric, treatment, band)
                if se: scale_effects.append(se)
    balance = pd.concat(all_balance, ignore_index=True)
    match_summary = pd.DataFrame(summaries)
    effects = pd.DataFrame(overall_effects)
    effects_by_scale = pd.DataFrame(scale_effects)
    balance.to_csv(TABLES / "direction1_balance.csv", index=False, encoding="utf-8-sig")
    match_summary.to_csv(TABLES / "direction1_match_summary.csv", index=False, encoding="utf-8-sig")
    effects.to_csv(TABLES / "direction1_effects.csv", index=False, encoding="utf-8-sig")
    effects_by_scale.to_csv(TABLES / "direction1_effects_by_scale.csv", index=False, encoding="utf-8-sig")
    plot_raw_stratified(raw)
    plot_balance(balance)
    plot_forest(effects)
    plot_scale_forest(effects_by_scale)
    metrics = {
        "n_high_tech": int(len(df)),
        "cohort_counts": {c: int((df["cohort"]==c).sum()) for c in COHORT_ORDER},
        "matches": match_summary.to_dict(orient="records"),
        "overall_effects": effects[effects["metric"].isin(["ip_total","ip_density"])].to_dict(orient="records"),
    }
    (ROOT / "outputs" / "direction1_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cohort_counts": metrics["cohort_counts"], "matches": match_summary[["cohort","matched_pairs","match_rate_pct","max_smd_after"]].to_dict(orient="records")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
