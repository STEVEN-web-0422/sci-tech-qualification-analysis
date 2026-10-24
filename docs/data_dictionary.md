# 数据字典

## 核心标识

| 字段 | 定义 |
|---|---|
| `qualification` | 资质类别 |
| `credit_code` | 标准化统一社会信用代码 |
| `cross_pool` | 是否跨多个资质池 |
| `cohort` | 高企内部资质组合 |
| `any_stacking` | 是否有任一额外资质 |

## 规模、资本、年龄

| 字段 | 定义 |
|---|---|
| `insured_count` | 参保人数 |
| `registered_capital_wan` | 注册资本（万元） |
| `paid_in_capital_wan` | 实缴资本（万元） |
| `enterprise_age` | 分析日减成立日期，年 |
| `scale_band` | `<50` / `50-200` / `200+` / `缺失` |

## 知产与实缴

| 字段 | 定义 |
|---|---|
| `patent_count` | 专利数 |
| `copyright_count` | 著作权数 |
| `ip_total` | 专利数 + 著作权数 |
| `ip_density` | 知产总数 / 参保人数 |
| `paid_in_rate` | 实缴资本 / 注册资本 |

## 模型特征

| 字段 | 用途 |
|---|---|
| `log_insured` | log1p 参保人数 |
| `log_reg_cap` | log1p 注册资本 |
| `log_patent` | log1p 专利数 |
| `log_copyright` | log1p 著作权数 |
| `log_ip_density` | log1p 知产密度 |
| `industry_group` | 高频行业 + 其他 |
| `district_group` | 高频区县 + 其他 |
| `type_group` | 高频企业类型 + 其他 |

## 评分输出

| 字段 | 定义 |
|---|---|
| `p_any_stacking` | 任一叠加的参考条件概率 |
| `score_any_stacking` | 参考样本内的 0–100 百分位分 |
| `band_any_stacking` | 低 / 中 / 高 |
| `p_small_giant` | 小巨人参考条件概率 |
| `p_specialized` | 专精特新参考条件概率 |
| `scope_note` | 适用范围说明 |

## 缺失策略

- 数值变量：中位数插补 + 缺失指示。
- 分类变量：众数插补 + 低频合并。
- 0 与 NULL 不混同：0 是观测值，NULL 是缺失或无法计算。
