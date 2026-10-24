# 资质叠加潜力评分指南

## 1. 评分定位

本评分用于高企-like 候选企业的参考排序，不是高新认定概率，也不是小巨人/专精特新行政认定概率。

训练集：29,323 家已获高企资质企业。由于缺少非高企和申请失败样本，无法建立高新认定概率模型。

## 2. 输入

将真实候选企业整理为 CSV，参考 `examples/candidate_template.csv`：

| 字段 | 必填 | 说明 |
|---|---|---|
| credit_code | 否 | 企业标识，可用于回填结果 |
| insured_count | 建议 | 参保人数；缺失时模型使用中位数和缺失指示 |
| registered_capital_wan | 建议 | 注册资本，万元 |
| paid_in_capital_wan | 否 | 实缴资本，万元；可用于计算实缴率 |
| paid_in_rate | 否 | 实缴率；缺失时可由实缴/注册资本计算 |
| establishment_date | 否 | 成立日期 YYYY-MM-DD；用于计算企业年龄 |
| enterprise_age | 建议 | 企业年龄；缺失时可由成立日期计算 |
| patent_count | 建议 | 专利数 |
| copyright_count | 建议 | 著作权数 |
| ip_density | 否 | 知产密度；缺失时可由知产总数/参保人数计算 |
| industry_category | 建议 | 国标行业门类 |
| district | 建议 | 所在区县 |
| enterprise_type | 建议 | 企业（机构）类型 |
| scale_band | 否 | 规模分档；缺失时按参保人数自动生成 |

## 3. 运行

```bash
python analysis/05_score_enterprise.py \
  --input examples/candidate_template.csv \
  --output outputs/scored_candidates.csv
```

## 4. 输出字段

- `p_any_stacking`：任一叠加参考条件概率
- `score_any_stacking`：0–100 参考百分位潜力分
- `band_any_stacking`：低 / 中 / 高
- `p_small_giant` / `score_small_giant` / `band_small_giant`
- `p_specialized` / `score_specialized` / `band_specialized`

评分带：

- `<50`：低潜力
- `50–80`：中潜力
- `>=80`：高潜力

## 5. 使用限制

- 仅用于高企-like 企业。
- 不用于自动认定、对外承诺或合规判断。
- 输入数据缺失时模型会插补，但缺失越多，解释越弱。
- 对外使用时必须同时说明“参考条件概率 / 非认定概率”。
