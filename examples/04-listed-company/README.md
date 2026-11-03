# 上市公司主体结构核查

- 用户需求：查看贵州茅台酒股份有限公司的股东、投资和分支机构结构。
- 决策用途：了解成熟企业的组织与投资版图。
- 本轮结果：**本轮检查通过**
- 实际工具调用：5；失败 0
- 章节覆盖率：91%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 股东和投资对象的名称与金额字段应可读
- 列表数量必须基于返回记录而非臆测总量
- 空字段使用缺失语义而非数字零

## 本轮自动检查发现


## 使用局限

- 仅反映本次 HandaaS 数据产品返回范围与生成时点，不等同于官方证明。
- 空结果必须保留为空，不能解释为该事项客观不存在。
- 本报告不提供证券估值或投资建议。

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 enterprise-skill/scripts/compose_report.py --enterprise '贵州茅台酒股份有限公司' --output enterprise-skill/output/04-listed-company/report.json --report-output enterprise-skill/output/04-listed-company/report.html
```

## 逐场景业务复核

本轮正式真实产物已逐项复核；结论限于上游公开数据、本次分页样本及报告声明口径。

- **pass** 股东和投资对象的名称与金额字段应可读：holders 和 investments 使用名称、金额/比例、状态及日期等可读字段；未展示原始嵌套对象。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=贵州茅台酒股份有限公司，match_raw=贵州茅台酒股份有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=15,total=15; enterprise_get_enterprise_branch_info:data,rows=3,total=3; enterprise_get_enterprise_main_person_info:data,rows=7,total=7]；metrics=[注册资本=人民币 12.5227 亿元; 实缴资本=人民币 12.5008 亿元; 资本实缴率=99.8%; 成立时间=1999-11-20; 经营状态=营业; 对外投资=15 家; 分支机构=3 家; 主要人员=7 人; 股东数量=2 个]；sections=[enterprise_base=13, identity_tags=3, description=1, business=0, tags=1, shareholder_top=10, shareholding_type=1, shareholder_entity=2, holders=2, investments=15, branches=3, key_persons=7]；quality_report={"total_sections":11,"populated_sections":10,"empty_sections":1,"coverage_pct":91}。
- **pass** 列表数量必须基于返回记录而非臆测总量：calls.json 对投资返回 row_count=15、reported_total=15；metrics“对外投资 15 家”，分支 3、人员 7 也与调用返回一致。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=贵州茅台酒股份有限公司，match_raw=贵州茅台酒股份有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=15,total=15; enterprise_get_enterprise_branch_info:data,rows=3,total=3; enterprise_get_enterprise_main_person_info:data,rows=7,total=7]；metrics=[注册资本=人民币 12.5227 亿元; 实缴资本=人民币 12.5008 亿元; 资本实缴率=99.8%; 成立时间=1999-11-20; 经营状态=营业; 对外投资=15 家; 分支机构=3 家; 主要人员=7 人; 股东数量=2 个]；sections=[enterprise_base=13, identity_tags=3, description=1, business=0, tags=1, shareholder_top=10, shareholding_type=1, shareholder_entity=2, holders=2, investments=15, branches=3, key_persons=7]；quality_report={"total_sections":11,"populated_sections":10,"empty_sections":1,"coverage_pct":91}。
- **pass** 空字段使用缺失语义而非数字零：记录中的缺失字段使用“-”或不生成指标，未把未知金额/日期替换为数值 0。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=贵州茅台酒股份有限公司，match_raw=贵州茅台酒股份有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=15,total=15; enterprise_get_enterprise_branch_info:data,rows=3,total=3; enterprise_get_enterprise_main_person_info:data,rows=7,total=7]；metrics=[注册资本=人民币 12.5227 亿元; 实缴资本=人民币 12.5008 亿元; 资本实缴率=99.8%; 成立时间=1999-11-20; 经营状态=营业; 对外投资=15 家; 分支机构=3 家; 主要人员=7 人; 股东数量=2 个]；sections=[enterprise_base=13, identity_tags=3, description=1, business=0, tags=1, shareholder_top=10, shareholding_type=1, shareholder_entity=2, holders=2, investments=15, branches=3, key_persons=7]；quality_report={"total_sections":11,"populated_sections":10,"empty_sections":1,"coverage_pct":91}。

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)