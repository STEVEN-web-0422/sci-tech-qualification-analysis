# -*- coding: utf-8 -*-
"""Direction 2: nested qualification-stacking models, diagnostics and score artifact."""
from pathlib import Path
import json
import os
import sqlite3
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, roc_curve, precision_recall_curve
from sklearn.calibration import calibration_curve

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("ANALYSIS_DB", ROOT / "data" / "analysis.sqlite"))
TABLES = ROOT / "outputs" / "tables"
IMAGES = ROOT / "docs" / "images"
MODELS = ROOT / "outputs" / "models"
SEED = 20261017
TEXT = "#1F2937"
MUTED = "#6B7280"
GRID = "#E5E7EB"
COLORS = {"base": "#6B7280", "full": "#0072B2"}
TARGETS = {
    "any_stacking": "获得任一叠加资质",
    "small_giant": "获得科技小巨人",
    "specialized": "获得专精特新",
}

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
    df["scale_band"] = df["scale_band"].fillna("缺失").astype(str)
    df["log_insured"] = np.log1p(df["insured_count"])
    df["log_reg_cap"] = np.log1p(df["registered_capital_wan"])
    df["log_patent"] = np.log1p(df["patent_count"])
    df["log_copyright"] = np.log1p(df["copyright_count"])
    df["log_ip_density"] = np.log1p(df["ip_density"])
    return df


def feature_specs():
    base_num = ["log_insured", "log_reg_cap", "enterprise_age", "paid_in_rate"]
    ip_num = ["log_patent", "log_copyright", "log_ip_density"]
    cat = ["industry_group", "district_group", "type_group", "scale_band"]
    return base_num, ip_num, cat


def make_pipeline(num_cols, cat_cols, C=0.5):
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=20)),
    ])
    pre = ColumnTransformer([
        ("num", numeric, num_cols),
        ("cat", categorical, cat_cols),
    ])
    return Pipeline([
        ("pre", pre),
        ("model", LogisticRegression(C=C, max_iter=3000, solver="lbfgs", random_state=SEED)),
    ])


def bootstrap_auc(y, p, B=500):
    rng = np.random.default_rng(SEED)
    vals=[]
    n=len(y)
    for _ in range(B):
        idx=rng.integers(0,n,n)
        if len(np.unique(y[idx]))<2: continue
        vals.append(roc_auc_score(y[idx],p[idx]))
    return np.percentile(vals,[2.5,97.5]) if vals else [np.nan,np.nan]


def top_decile_metrics(y, p):
    k=max(1,int(len(y)*.1))
    order=np.argsort(-p)
    top=y[order[:k]]
    prevalence=y.mean()
    precision=top.mean()
    capture=top.sum()/max(1,y.sum())
    return precision*100, capture*100, precision/prevalence if prevalence else np.nan


def evaluate_oof(y, p):
    precision10, capture10, lift10 = top_decile_metrics(y,p)
    lo,hi=bootstrap_auc(y,p)
    return {
        "roc_auc": roc_auc_score(y,p), "auc_ci_low": lo, "auc_ci_high": hi,
        "pr_auc": average_precision_score(y,p), "brier": brier_score_loss(y,p),
        "top_decile_precision_pct": precision10,
        "top_decile_capture_pct": capture10,
        "top_decile_lift": lift10,
    }


def oof_predictions(df, target, num_cols, cat_cols):
    X=df[num_cols+cat_cols].copy(); y=df[target].astype(int).to_numpy()
    skf=StratifiedKFold(n_splits=5,shuffle=True,random_state=SEED)
    pred=np.zeros(len(y))
    for tr,te in skf.split(X,y):
        model=make_pipeline(num_cols,cat_cols)
        model.fit(X.iloc[tr],y[tr])
        pred[te]=model.predict_proba(X.iloc[te])[:,1]
    return y,pred

def bootstrap_delta(y, p_base, p_full, B=500):
    rng=np.random.default_rng(SEED)
    vals=[]; n=len(y)
    for _ in range(B):
        idx=rng.integers(0,n,n)
        if len(np.unique(y[idx]))<2: continue
        vals.append(roc_auc_score(y[idx],p_full[idx])-roc_auc_score(y[idx],p_base[idx]))
    return np.percentile(vals,[2.5,97.5]) if vals else [np.nan,np.nan]


def plot_performance(perf):
    fig, axes = plt.subplots(1,2,figsize=(14,5.2))
    targets=list(TARGETS.keys()); x=np.arange(len(targets)); width=.34
    for ax,metric,label in [(axes[0],"roc_auc","ROC-AUC"),(axes[1],"pr_auc","PR-AUC")]:
        for i,model in enumerate(["base","full"]):
            vals=[float(perf[(perf.target==t)&(perf.model==model)][metric].iloc[0]) for t in targets]
            bars=ax.bar(x+(i-.5)*width,vals,width,label={"base":"基础特征","full":"基础+知产"}[model],color=COLORS[model],alpha=.9)
            for bar,v in zip(bars,vals): ax.text(bar.get_x()+bar.get_width()/2,v+.01,f"{v:.3f}",ha="center",va="bottom",fontsize=8)
        ax.set_xticks(x); ax.set_xticklabels([TARGETS[t] for t in targets],fontsize=9)
        ax.set_ylim(.5,1.02); ax.set_ylabel(label); ax.set_title(label,loc="left",fontsize=13,fontweight="bold")
        style_ax(ax); ax.legend(frameon=False,loc="lower right")
    fig.suptitle("方向 2：基础特征与增加知产特征后的模型表现",x=.06,ha="left",fontsize=17,fontweight="bold")
    fig.text(.06,.01,"5 折分层交叉验证的折外预测；AUC/PR-AUC 不依赖分类阈值。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,.92]); save_fig(fig,"direction2_model_performance.png")


def plot_roc_pr(y,p_base,p_full):
    fig,axes=plt.subplots(1,2,figsize=(13,5.2))
    for p,label,color in [(p_base,"基础特征",COLORS["base"]),(p_full,"基础+知产",COLORS["full"])]:
        fpr,tpr,_=roc_curve(y,p); axes[0].plot(fpr,tpr,label=f"{label} AUC={roc_auc_score(y,p):.3f}",color=color,lw=2)
        pr,rc,_=precision_recall_curve(y,p); axes[1].plot(rc,pr,label=f"{label} AP={average_precision_score(y,p):.3f}",color=color,lw=2)
    axes[0].plot([0,1],[0,1],ls="--",color="#D1D5DB"); axes[0].set_xlabel("假阳性率"); axes[0].set_ylabel("真阳性率")
    axes[0].set_title("ROC 曲线：任一资质叠加",loc="left",fontsize=13,fontweight="bold"); axes[0].legend(frameon=False)
    axes[1].set_xlabel("召回率"); axes[1].set_ylabel("精确率")
    axes[1].set_title("PR 曲线：任一资质叠加",loc="left",fontsize=13,fontweight="bold"); axes[1].legend(frameon=False)
    for ax in axes: style_ax(ax)
    fig.suptitle("方向 2：折外预测的判别能力",x=.06,ha="left",fontsize=17,fontweight="bold")
    fig.tight_layout(rect=[0,0,1,.93]); save_fig(fig,"direction2_roc_pr.png")


def plot_calibration(y,p):
    frac,mean=calibration_curve(y,p,n_bins=10,strategy="quantile")
    fig,ax=plt.subplots(figsize=(7.6,6))
    ax.plot([0,1],[0,1],ls="--",color="#D1D5DB",label="完美校准")
    ax.plot(mean,frac,marker="o",color=COLORS["full"],lw=2,label="基础+知产")
    ax.set_xlabel("预测概率"); ax.set_ylabel("实际正例率")
    ax.set_title("方向 2：任一资质叠加模型的校准曲线",loc="left",fontsize=15,fontweight="bold")
    style_ax(ax); ax.legend(frameon=False)
    fig.text(.06,.01,f"Brier score={brier_score_loss(y,p):.4f}；曲线越接近对角线，概率校准越好。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,1]); save_fig(fig,"direction2_calibration.png")


def fit_coefficients(df,target,num_cols,cat_cols):
    X=df[num_cols+cat_cols]; y=df[target].astype(int)
    model=make_pipeline(num_cols,cat_cols).fit(X,y)
    pre=model.named_steps["pre"]
    names=pre.get_feature_names_out()
    coef=model.named_steps["model"].coef_[0]
    out=pd.DataFrame({"feature":names,"coef":coef})
    out["abs_coef"]=out["coef"].abs(); out["odds_ratio"]=np.exp(out["coef"])
    out=out.sort_values("abs_coef",ascending=False).head(20)
    return model,out


def plot_coefficients(coef):
    d=coef.head(15).iloc[::-1]
    fig,ax=plt.subplots(figsize=(10.5,6.5))
    colors=["#B00020" if v>0 else "#0072B2" for v in d["coef"]]
    ax.barh(d["feature"],d["coef"],color=colors,alpha=.85)
    ax.axvline(0,color=MUTED,lw=1); ax.set_xlabel("标准化 Logistic 系数")
    ax.set_title("方向 2：任一资质叠加模型的主要系数",loc="left",fontsize=15,fontweight="bold")
    style_ax(ax,grid_axis="x")
    fig.text(.06,.01,"系数为正表示与资质叠加正相关；仅为条件关联，不是因果效应。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,1]); save_fig(fig,"direction2_coefficients.png")


def group_importance(df,target,num_cols,cat_cols):
    X=df[num_cols+cat_cols]; y=df[target].astype(int)
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,stratify=y,random_state=SEED)
    model=make_pipeline(num_cols,cat_cols).fit(Xtr,ytr)
    base=roc_auc_score(yte,model.predict_proba(Xte)[:,1])
    groups={
        "规模":["log_insured","scale_band"], "注册资本":["log_reg_cap"], "企业年龄":["enterprise_age"],
        "实缴率":["paid_in_rate"], "专利":["log_patent"], "著作权":["log_copyright"],
        "知产密度":["log_ip_density"], "行业":["industry_group"], "区县":["district_group"], "企业类型":["type_group"],
    }
    rng=np.random.default_rng(SEED); rows=[]
    for label,cols in groups.items():
        drops=[]
        for _ in range(10):
            tmp=Xte.copy()
            for col in cols:
                tmp[col]=rng.permutation(tmp[col].values)
            drops.append(base-roc_auc_score(yte,model.predict_proba(tmp)[:,1]))
        rows.append({"group":label,"auc_drop_mean":np.mean(drops),"auc_drop_std":np.std(drops)})
    return pd.DataFrame(rows).sort_values("auc_drop_mean",ascending=False)


def plot_importance(imp):
    d=imp.iloc[::-1]
    fig,ax=plt.subplots(figsize=(9.6,5.8))
    ax.barh(d["group"],d["auc_drop_mean"],xerr=d["auc_drop_std"],color="#0072B2",alpha=.85,capsize=3)
    ax.set_xlabel("打乱该组特征后 ROC-AUC 的平均下降")
    ax.set_title("方向 2：特征组对资质叠加识别的贡献",loc="left",fontsize=15,fontweight="bold")
    style_ax(ax,grid_axis="x")
    fig.text(.06,.01,"基于 20% 留出集和 10 次随机置换；下降越大表示该组特征越重要。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,1]); save_fig(fig,"direction2_feature_importance.png")

def plot_score_deciles(dec):
    fig,ax=plt.subplots(figsize=(9.8,5.3))
    x=dec["decile"].astype(int)
    ax.bar(x,dec["positive_rate_pct"],color="#0072B2",alpha=.85,label="实际正例率")
    ax.plot(x,dec["mean_predicted_pct"],color="#D55E00",marker="o",lw=2,label="平均预测概率")
    ax.set_xlabel("预测得分十分位（1=最低，10=最高）"); ax.set_ylabel("比例（%）")
    ax.set_title("方向 2：任一资质叠加模型的十分位校准",loc="left",fontsize=15,fontweight="bold")
    style_ax(ax); ax.legend(frameon=False)
    fig.text(.06,.01,"高分位组的实际正例率应同步上升；若明显偏离，说明概率校准需要进一步调整。",fontsize=8.5,color=MUTED)
    fig.tight_layout(rect=[0,.04,1,1]); save_fig(fig,"direction2_score_deciles.png")


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    df=load_data()
    base_num,ip_num,cat=feature_specs()
    base_cols=base_num+cat; full_cols=base_num+ip_num+cat
    perf_rows=[]; comp_rows=[]; oof_store={}
    for target,label in TARGETS.items():
        y,pb=oof_predictions(df,target,base_num,cat)
        _,pf=oof_predictions(df,target,base_num+ip_num,cat)
        oof_store[target]=(y,pf,pb)
        for model_name,p in [("base",pb),("full",pf)]:
            rec={"target":target,"target_label":label,"model":model_name,"n":len(y),"positives":int(y.sum()),"prevalence_pct":100*y.mean()}
            rec.update(evaluate_oof(y,p)); perf_rows.append(rec)
        dlo,dhi=bootstrap_delta(y,pb,pf)
        comp_rows.append({"target":target,"target_label":label,"base_auc":roc_auc_score(y,pb),"full_auc":roc_auc_score(y,pf),
                          "delta_auc":roc_auc_score(y,pf)-roc_auc_score(y,pb),"delta_ci_low":dlo,"delta_ci_high":dhi})
    perf=pd.DataFrame(perf_rows); comp=pd.DataFrame(comp_rows)
    perf.to_csv(TABLES/"direction2_model_performance.csv",index=False,encoding="utf-8-sig")
    comp.to_csv(TABLES/"direction2_model_comparison.csv",index=False,encoding="utf-8-sig")
    y,pf,pb=oof_store["any_stacking"]
    plot_performance(perf); plot_roc_pr(y,pb,pf); plot_calibration(y,pf)
    _, coef = fit_coefficients(df, "any_stacking", base_num + ip_num, cat)
    coef.to_csv(TABLES/"direction2_coefficients.csv",index=False,encoding="utf-8-sig")
    plot_coefficients(coef)
    imp=group_importance(df,"any_stacking",base_num+ip_num,cat)
    imp.to_csv(TABLES/"direction2_feature_group_importance.csv",index=False,encoding="utf-8-sig")
    plot_importance(imp)
    dec=pd.DataFrame({"y":y,"p":pf})
    dec["decile"]=pd.qcut(dec["p"],10,labels=False,duplicates="drop")+1
    deciles=dec.groupby("decile").agg(n=("y","size"),mean_predicted=("p","mean"),positive_rate=("y","mean")).reset_index()
    deciles["mean_predicted_pct"]=100*deciles["mean_predicted"]; deciles["positive_rate_pct"]=100*deciles["positive_rate"]
    deciles.to_csv(TABLES/"direction2_score_deciles.csv",index=False,encoding="utf-8-sig")
    plot_score_deciles(deciles)
    with sqlite3.connect(DB_PATH) as con:
        top_maps = {
            "industry_group": pd.read_sql_query("SELECT category FROM dim_industry_group WHERE rn <= 8 ORDER BY rn", con)["category"].tolist(),
            "district_group": pd.read_sql_query("SELECT category FROM dim_district_group WHERE rn <= 8 ORDER BY rn", con)["category"].tolist(),
            "type_group": pd.read_sql_query("SELECT category FROM dim_type_group WHERE rn <= 6 ORDER BY rn", con)["category"].tolist(),
        }
    meta={"analysis_date":"2026-10-17","scope":"high_tech_cohort_only","top_categories":top_maps,
          "warning":"The score is a reference-conditional stacking-potential score among observed high-tech firms, not a probability of high-tech certification or a causal effect.",
          "targets":{}}
    for target,label in TARGETS.items():
        X=df[full_cols]; yt=df[target].astype(int)
        model=make_pipeline(base_num+ip_num,cat).fit(X,yt)
        joblib.dump(model,MODELS/f"direction2_{target}.joblib")
        yt_oof,pf_oof,_=oof_store[target]
        meta["targets"][target]={"label":label,"prevalence":float(yt.mean()),"reference_quantiles":{str(q):float(np.percentile(pf_oof,q)) for q in [1,5,10,25,50,75,90,95,99]}}
    (MODELS/"score_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    metrics={"n_high_tech":int(len(df)),"performance":perf.to_dict(orient="records"),"comparison":comp.to_dict(orient="records"),
             "importance":imp.to_dict(orient="records")}
    (ROOT/"outputs"/"direction2_metrics.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8")
    print(comp.to_string(index=False))
    print("\nTop feature groups:\n",imp.head(5).to_string(index=False))


if __name__=="__main__":
    main()
