# 工程合同相对方核验

- 用户需求：核验中国建筑第八工程局有限公司的主体、分支和主要人员，供合同审查。
- 决策用途：确认合同相对方身份并发现需进一步核验的分支关系。
- 本轮结果：**本轮检查通过**
- 实际工具调用：5；失败 0
- 章节覆盖率：64%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 企业全称与分支机构名称应清楚区分
- 主要人员只展示上游返回范围
- 报告中不得暴露 MCP 参数或凭证

## 本轮自动检查发现


## 使用局限

- 仅反映本次 HandaaS 数据产品返回范围与生成时点，不等同于官方证明。
- 空结果必须保留为空，不能解释为该事项客观不存在。
- 不能据此确认具体分支机构的签约授权。

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 enterprise-skill/scripts/compose_report.py --enterprise '中国建筑第八工程局有限公司' --output enterprise-skill/output/05-contract-counterparty/report.json --report-output enterprise-skill/output/05-contract-counterparty/report.html
```

## 逐场景业务复核

本轮正式真实产物已逐项复核；结论限于上游公开数据、本次分页样本及报告声明口径。

- **pass** 企业全称与分支机构名称应清楚区分：subject.enterprise 为“中国建筑第八工程局有限公司”；branches 中名称均作为“分支机构”单列，未与主体混写。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=中国建筑第八工程局有限公司，match_raw=中国建筑第八工程局有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=278; enterprise_get_enterprise_branch_info:data,rows=40,total=40; enterprise_get_enterprise_main_person_info:data,rows=8,total=8]；metrics=[注册资本=人民币 152.1800 亿元; 实缴资本=人民币 152.1800 亿元; 资本实缴率=100.0%; 成立时间=1998-09-29; 经营状态=营业; 对外投资=278 家; 分支机构=40 家; 主要人员=8 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=40, key_persons=8]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。
- **pass** 主要人员只展示上游返回范围：主要人员工具 row_count/reported_total=8/8，core_analysis.key_persons 与 metrics 均为 8 人。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=中国建筑第八工程局有限公司，match_raw=中国建筑第八工程局有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=278; enterprise_get_enterprise_branch_info:data,rows=40,total=40; enterprise_get_enterprise_main_person_info:data,rows=8,total=8]；metrics=[注册资本=人民币 152.1800 亿元; 实缴资本=人民币 152.1800 亿元; 资本实缴率=100.0%; 成立时间=1998-09-29; 经营状态=营业; 对外投资=278 家; 分支机构=40 家; 主要人员=8 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=40, key_persons=8]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。
- **pass** 报告中不得暴露 MCP 参数或凭证：report.json/report.md/report.html 未出现 secret、signature、token、authorization、密钥或签名内容；仅呈现业务数据。 本轮实际产物：technical_status=passed，successful_data_calls=5，subject.enterprise=中国建筑第八工程局有限公司，match_raw=中国建筑第八工程局有限公司，resolved=True；calls=[enterprise_get_enterprise_base_info:data,rows=None,total=None; enterprise_get_enterprise_holder_info:data,rows=None,total=None; enterprise_get_enterprise_invest_info:data,rows=50,total=278; enterprise_get_enterprise_branch_info:data,rows=40,total=40; enterprise_get_enterprise_main_person_info:data,rows=8,total=8]；metrics=[注册资本=人民币 152.1800 亿元; 实缴资本=人民币 152.1800 亿元; 资本实缴率=100.0%; 成立时间=1998-09-29; 经营状态=营业; 对外投资=278 家; 分支机构=40 家; 主要人员=8 人; 股东数量=1 个]；sections=[enterprise_base=14, identity_tags=2, description=1, business=0, tags=1, shareholder_top=0, shareholding_type=0, shareholder_entity=0, holders=1, investments=50, branches=40, key_persons=8]；quality_report={"total_sections":11,"populated_sections":7,"empty_sections":4,"coverage_pct":64}。

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)