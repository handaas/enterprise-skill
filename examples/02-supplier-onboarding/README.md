# 供应商准入主体核验

- 用户需求：请生成宁德时代新能源科技股份有限公司的企业画像，重点看股东、分支机构和主要人员。
- 决策用途：验证供应商签约主体并识别组织复杂度。
- 本轮结果：**本轮检查通过**
- 实际工具调用：5；失败 0
- 章节覆盖率：91%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 报告标题与主体全称一致
- 股东、分支、人员章节应避免重复记录
- quality_report 覆盖率应与非空章节一致

## 本轮自动检查发现


## 使用局限

- 仅反映本次 HandaaS 数据产品返回范围与生成时点，不等同于官方证明。
- 空结果必须保留为空，不能解释为该事项客观不存在。
- 不包含本 skill 之外的诉讼、财务或履约风险结论。

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 enterprise-skill/scripts/compose_report.py --enterprise '宁德时代新能源科技股份有限公司' --output enterprise-skill/output/02-supplier-onboarding/report.json --report-output enterprise-skill/output/02-supplier-onboarding/report.html
```

## 逐场景业务复核

本轮正式真实产物已逐项复核；结论限于上游公开数据、本次分页样本及报告声明口径。

- **pass** 报告标题与主体全称一致：report.title 为“宁德时代新能源科技股份有限公司 企业大数据报告”，与 subject.enterprise 完全一致。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=宁德时代新能源科技股份有限公司，match_raw=宁德时代新能源科技股份有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=159; enterprise_get_enterprise_branch_info:data,rows=8,total=8; enterprise_get_enterprise_main_person_info:data,rows=15,total=15]；metrics=[注册资本=人民币 45.6361 亿元; 实缴资本=人民币 4.0000 亿元; 资本实缴率=8.8%; 成立时间=2011-12-16; 经营状态=营业; 对外投资=159 家; 分支机构=8 家; 主要人员=15 人; 股东数量=5 个]；sections=[enterprise_base=14, identity_tags=4, description=1, business=0, tags=1, shareholder_top=10, shareholding_type=2, shareholder_entity=2, holders=5, investments=50, branches=8, key_persons=15]；quality_report={"total_sections":11,"populated_sections":10,"empty_sections":1,"coverage_pct":91}。
- **pass** 股东、分支、人员章节应避免重复记录：holders 5 条、branches 8 条、key_persons 15 条均逐条 JSON 唯一；未发现重复展示记录。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=宁德时代新能源科技股份有限公司，match_raw=宁德时代新能源科技股份有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=159; enterprise_get_enterprise_branch_info:data,rows=8,total=8; enterprise_get_enterprise_main_person_info:data,rows=15,total=15]；metrics=[注册资本=人民币 45.6361 亿元; 实缴资本=人民币 4.0000 亿元; 资本实缴率=8.8%; 成立时间=2011-12-16; 经营状态=营业; 对外投资=159 家; 分支机构=8 家; 主要人员=15 人; 股东数量=5 个]；sections=[enterprise_base=14, identity_tags=4, description=1, business=0, tags=1, shareholder_top=10, shareholding_type=2, shareholder_entity=2, holders=5, investments=50, branches=8, key_persons=15]；quality_report={"total_sections":11,"populated_sections":10,"empty_sections":1,"coverage_pct":91}。
- **pass** quality_report 覆盖率应与非空章节一致：data_source.quality_report 为 total=11、populated=10、empty=1、coverage_pct=91；与 core_analysis.sections 的实质非空情况一致。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=宁德时代新能源科技股份有限公司，match_raw=宁德时代新能源科技股份有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=159; enterprise_get_enterprise_branch_info:data,rows=8,total=8; enterprise_get_enterprise_main_person_info:data,rows=15,total=15]；metrics=[注册资本=人民币 45.6361 亿元; 实缴资本=人民币 4.0000 亿元; 资本实缴率=8.8%; 成立时间=2011-12-16; 经营状态=营业; 对外投资=159 家; 分支机构=8 家; 主要人员=15 人; 股东数量=5 个]；sections=[enterprise_base=14, identity_tags=4, description=1, business=0, tags=1, shareholder_top=10, shareholding_type=2, shareholder_entity=2, holders=5, investments=50, branches=8, key_persons=15]；quality_report={"total_sections":11,"populated_sections":10,"empty_sections":1,"coverage_pct":91}。

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)