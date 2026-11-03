# 品牌合作主体识别

- 用户需求：请查询北京京东世纪贸易有限公司的企业基础和对外投资情况。
- 决策用途：在品牌合作前确认运营主体及关联投资线索。
- 本轮结果：**本轮检查通过**
- 实际工具调用：5；失败 0
- 章节覆盖率：64%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 工商主体与品牌名称不得混淆
- 对外投资章节应保留被投企业名称和可用比例/金额
- 摘要应由实际非空指标生成

## 本轮自动检查发现


## 使用局限

- 仅反映本次 HandaaS 数据产品返回范围与生成时点，不等同于官方证明。
- 空结果必须保留为空，不能解释为该事项客观不存在。
- 品牌归属与知识产权需另用商标等数据验证。

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 enterprise-skill/scripts/compose_report.py --enterprise '北京京东世纪贸易有限公司' --output enterprise-skill/output/06-brand-company/report.json --report-output enterprise-skill/output/06-brand-company/report.html
```

## 逐场景业务复核

本轮正式真实产物已逐项复核；结论限于上游公开数据、本次分页样本及报告声明口径。

- **pass** 工商主体与品牌名称不得混淆：subject、title 和 caliber.match_target 均为工商主体“北京京东世纪贸易有限公司”，未用“京东”替代法定主体。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=北京京东世纪贸易有限公司，match_raw=北京京东世纪贸易有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=190; enterprise_get_enterprise_branch_info:data,rows=11,total=11; enterprise_get_enterprise_main_person_info:data,rows=2,total=2]；metrics=[注册资本=美元 13.9799 亿元; 实缴资本=美元 13.9799 亿元; 资本实缴率=100.0%; 成立时间=2007-04-20; 经营状态=营业; 对外投资=190 家; 分支机构=11 家; 主要人员=2 人; 股东数量=1 个]；sections=[enterprise_base=13, identity_tags=1, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=11, key_persons=2]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。
- **pass** 对外投资章节应保留被投企业名称和可用比例/金额：investments 50 条均保留被投企业名称，关系字段展示投资比例；metrics 披露上游总量 190 家而非样本数。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=北京京东世纪贸易有限公司，match_raw=北京京东世纪贸易有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=190; enterprise_get_enterprise_branch_info:data,rows=11,total=11; enterprise_get_enterprise_main_person_info:data,rows=2,total=2]；metrics=[注册资本=美元 13.9799 亿元; 实缴资本=美元 13.9799 亿元; 资本实缴率=100.0%; 成立时间=2007-04-20; 经营状态=营业; 对外投资=190 家; 分支机构=11 家; 主要人员=2 人; 股东数量=1 个]；sections=[enterprise_base=13, identity_tags=1, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=11, key_persons=2]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。
- **pass** 摘要应由实际非空指标生成：summary 只引用非空资本、成立时间、经营状态和企业简介，并说明已给出实际返回的投资/分支/人员明细。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=北京京东世纪贸易有限公司，match_raw=北京京东世纪贸易有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=190; enterprise_get_enterprise_branch_info:data,rows=11,total=11; enterprise_get_enterprise_main_person_info:data,rows=2,total=2]；metrics=[注册资本=美元 13.9799 亿元; 实缴资本=美元 13.9799 亿元; 资本实缴率=100.0%; 成立时间=2007-04-20; 经营状态=营业; 对外投资=190 家; 分支机构=11 家; 主要人员=2 人; 股东数量=1 个]；sections=[enterprise_base=13, identity_tags=1, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=11, key_persons=2]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)