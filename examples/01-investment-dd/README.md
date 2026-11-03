# 投资前企业主体核验

- 用户需求：请核验华为技术有限公司的工商主体、股东、对外投资、分支机构和主要人员，供投资初筛。
- 决策用途：识别主体结构和投资关系，为后续人工尽调确定重点。
- 本轮结果：**本轮检查通过**
- 实际工具调用：5；失败 0
- 章节覆盖率：64%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 主体名称与工商基础信息应可识别
- 股东与对外投资应分章节呈现且不混为一类
- 分支机构和主要人员只统计实际返回记录
- 金额、地址和日期应可读而非原始 JSON

## 本轮自动检查发现


## 使用局限

- 仅反映本次 HandaaS 数据产品返回范围与生成时点，不等同于官方证明。
- 空结果必须保留为空，不能解释为该事项客观不存在。
- 不能仅凭股东或投资列表判断实际控制权。

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 enterprise-skill/scripts/compose_report.py --enterprise '华为技术有限公司' --output enterprise-skill/output/01-investment-dd/report.json --report-output enterprise-skill/output/01-investment-dd/report.html
```

## 逐场景业务复核

本轮正式真实产物已逐项复核；结论限于上游公开数据、本次分页样本及报告声明口径。

- **pass** 主体名称与工商基础信息应可识别：report.subject.enterprise、title 与基础信息均为“华为技术有限公司”，metrics 展示成立时间 1987-09-15、经营状态“营业”等主体信息。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=华为技术有限公司，match_raw=华为技术有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=54; enterprise_get_enterprise_branch_info:data,rows=27,total=27; enterprise_get_enterprise_main_person_info:data,rows=32,total=32]；metrics=[注册资本=人民币 411.4113 亿元; 实缴资本=人民币 410.4113 亿元; 资本实缴率=99.8%; 成立时间=1987-09-15; 经营状态=营业; 对外投资=54 家; 分支机构=27 家; 主要人员=32 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=27, key_persons=32]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。
- **pass** 股东与对外投资应分章节呈现且不混为一类：core_analysis.holders 为 1 条，investments 为 50 条且各自在“股东信息”“对外投资”章节；未把两类关系合并。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=华为技术有限公司，match_raw=华为技术有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=54; enterprise_get_enterprise_branch_info:data,rows=27,total=27; enterprise_get_enterprise_main_person_info:data,rows=32,total=32]；metrics=[注册资本=人民币 411.4113 亿元; 实缴资本=人民币 410.4113 亿元; 资本实缴率=99.8%; 成立时间=1987-09-15; 经营状态=营业; 对外投资=54 家; 分支机构=27 家; 主要人员=32 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=27, key_persons=32]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。
- **pass** 分支机构和主要人员只统计实际返回记录：calls.json 显示分支工具 row_count/reported_total=27/27、人员工具=32/32；报告 branches=27、key_persons=32。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=华为技术有限公司，match_raw=华为技术有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=54; enterprise_get_enterprise_branch_info:data,rows=27,total=27; enterprise_get_enterprise_main_person_info:data,rows=32,total=32]；metrics=[注册资本=人民币 411.4113 亿元; 实缴资本=人民币 410.4113 亿元; 资本实缴率=99.8%; 成立时间=1987-09-15; 经营状态=营业; 对外投资=54 家; 分支机构=27 家; 主要人员=32 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=27, key_persons=32]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。
- **pass** 金额、地址和日期应可读而非原始 JSON：报告 metrics/enterprise_base 将资本格式化为“人民币 411.4113 亿元”，并展示地址和 ISO 日期；无原始 JSON 串。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=华为技术有限公司，match_raw=华为技术有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=54; enterprise_get_enterprise_branch_info:data,rows=27,total=27; enterprise_get_enterprise_main_person_info:data,rows=32,total=32]；metrics=[注册资本=人民币 411.4113 亿元; 实缴资本=人民币 410.4113 亿元; 资本实缴率=99.8%; 成立时间=1987-09-15; 经营状态=营业; 对外投资=54 家; 分支机构=27 家; 主要人员=32 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=27, key_persons=32]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)
[页面截图](browser.png)