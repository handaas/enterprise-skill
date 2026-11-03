# 大客户 KYB 建档

- 用户需求：为腾讯科技（深圳）有限公司建立工商客户档案，输出结构化报告。
- 决策用途：支撑客户主数据建档和合同主体复核。
- 本轮结果：**本轮检查通过**
- 实际工具调用：5；失败 0
- 章节覆盖率：64%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 企业名称、经营状态、成立时间等字段应按源数据展示
- 业务、标签与简介不得被拼接成未经证实的结论
- JSON、HTML、Markdown 的核心指标应一致

## 本轮自动检查发现


## 使用局限

- 仅反映本次 HandaaS 数据产品返回范围与生成时点，不等同于官方证明。
- 空结果必须保留为空，不能解释为该事项客观不存在。
- 不能替代证照原件或工商登记机关实时核验。

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 enterprise-skill/scripts/compose_report.py --enterprise '腾讯科技（深圳）有限公司' --output enterprise-skill/output/03-customer-kyb/report.json --report-output enterprise-skill/output/03-customer-kyb/report.html
```

## 逐场景业务复核

本轮正式真实产物已逐项复核；结论限于上游公开数据、本次分页样本及报告声明口径。

- **pass** 企业名称、经营状态、成立时间等字段应按源数据展示：metrics 明示注册/实缴资本、成立时间 2000-02-24、经营状态“营业”，subject 为腾讯科技（深圳）有限公司。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=腾讯科技（深圳）有限公司，match_raw=腾讯科技（深圳）有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=17,total=17; enterprise_get_enterprise_branch_info:data,rows=5,total=5; enterprise_get_enterprise_main_person_info:data,rows=5,total=5]；metrics=[注册资本=美元 200.00 万元; 实缴资本=美元 200.00 万元; 资本实缴率=100.0%; 成立时间=2000-02-24; 经营状态=营业; 对外投资=17 家; 分支机构=5 家; 主要人员=5 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=17, branches=5, key_persons=5]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。
- **pass** 业务、标签与简介不得被拼接成未经证实的结论：摘要以“企业简介”标注上游简介并截断展示；insights 对数量含义均附核验边界，未把业务、标签拼接成确定性结论。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=腾讯科技（深圳）有限公司，match_raw=腾讯科技（深圳）有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=17,total=17; enterprise_get_enterprise_branch_info:data,rows=5,total=5; enterprise_get_enterprise_main_person_info:data,rows=5,total=5]；metrics=[注册资本=美元 200.00 万元; 实缴资本=美元 200.00 万元; 资本实缴率=100.0%; 成立时间=2000-02-24; 经营状态=营业; 对外投资=17 家; 分支机构=5 家; 主要人员=5 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=17, branches=5, key_persons=5]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。
- **pass** JSON、HTML、Markdown 的核心指标应一致：report.json 的资本、日期、经营状态和数量指标均可在 report.md 与 report.html 中检索到；result.checks.independent_rerender=true。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=腾讯科技（深圳）有限公司，match_raw=腾讯科技（深圳）有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=17,total=17; enterprise_get_enterprise_branch_info:data,rows=5,total=5; enterprise_get_enterprise_main_person_info:data,rows=5,total=5]；metrics=[注册资本=美元 200.00 万元; 实缴资本=美元 200.00 万元; 资本实缴率=100.0%; 成立时间=2000-02-24; 经营状态=营业; 对外投资=17 家; 分支机构=5 家; 主要人员=5 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=17, branches=5, key_persons=5]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)