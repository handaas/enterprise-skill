# enterprise-skill：已验收示例

本目录只展示 **6 个完全通过的真实正向场景**（最低要求4例）。

每例均为真实、非空、非缓存调用；技术检查、独立业务检查和离线浏览器检查全部通过。不把空数据、报错处理或仅生成页面计作通过。历史验收记录保留在本地 test-records/；本目录的 HTML/Markdown 由原 JSON 重渲染，不代表重新查询或重新验收。

| 场景 | 真实使用需求 | 报告 |
|---|---|---|
| [投资前企业主体核验](01-investment-dd/README.md) | 请核验华为技术有限公司的工商主体、股东、对外投资、分支机构和主要人员，供投资初筛。 | [HTML](01-investment-dd/report.html) / [MD](01-investment-dd/report.md) / [JSON](01-investment-dd/report.json) |
| [供应商准入主体核验](02-supplier-onboarding/README.md) | 请生成宁德时代新能源科技股份有限公司的企业画像，重点看股东、分支机构和主要人员。 | [HTML](02-supplier-onboarding/report.html) / [MD](02-supplier-onboarding/report.md) / [JSON](02-supplier-onboarding/report.json) |
| [大客户 KYB 建档](03-customer-kyb/README.md) | 为腾讯科技（深圳）有限公司建立工商客户档案，输出结构化报告。 | [HTML](03-customer-kyb/report.html) / [MD](03-customer-kyb/report.md) / [JSON](03-customer-kyb/report.json) |
| [上市公司主体结构核查](04-listed-company/README.md) | 查看贵州茅台酒股份有限公司的股东、投资和分支机构结构。 | [HTML](04-listed-company/report.html) / [MD](04-listed-company/report.md) / [JSON](04-listed-company/report.json) |
| [工程合同相对方核验](05-contract-counterparty/README.md) | 核验中国建筑第八工程局有限公司的主体、分支和主要人员，供合同审查。 | [HTML](05-contract-counterparty/report.html) / [MD](05-contract-counterparty/report.md) / [JSON](05-contract-counterparty/report.json) |
| [品牌合作主体识别](06-brand-company/README.md) | 请查询北京京东世纪贸易有限公司的企业基础和对外投资情况。 | [HTML](06-brand-company/report.html) / [MD](06-brand-company/report.md) / [JSON](06-brand-company/report.json) |

- [逐例验收结果](results.json) · [业务复核](review.json) · [证据摘要](evidence-index.json)
- 完整测试记录仅存于本地 test-records/live-replaced-20261027/（仅本地审计用，不随本目录发布），不属于可展示示例。
- 当前数据与结论限于原查询时点及公开样本；覆盖率不代表准确率或低风险。
