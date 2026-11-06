# 报告输出 — 企业大数据报告

本文件规定 `enterprise-report` skill 产出的报告结构、质量底线与渲染工作流。所有产物遵循 `AGENTS.md` 的统一 JSON 骨架与本 skill 的领域裁剪。

## 默认展示模式

- HTML：可分享 / 可交付的可视化报告；独立本地文件，内嵌 CSS，无调试 / 内部段落。
- Markdown：知识库 / wiki / PRD / 后续手工编辑。
- JSON：系统集成或二次处理。

`compose_report.py` 通过 `--report-output <path>` 同时产出 HTML + Markdown；`--output <path>` 产出 JSON。`render_report.py` 可基于已有 JSON 重渲染。

## 报告结构（7 章）

所有 HTML / Markdown 报告按以下顺序组织：

1. **报告摘要**：分析对象、数据覆盖范围、核心发现、关键指标卡。
2. **查询对象与口径**：企业全称、匹配方式（全称精确匹配 / 关键词模糊补全）、数据范围、产品、局限。
3. **数据总览**：注册资本、成立时间、经营状态、对外投资数、分支机构数、主要人员数、股东数等指标卡。
4. **核心分析**（企业专属子章节）：
   - 工商基础信息（KV：名称 / 统一社会信用代码 / 法定代表人 / 企业类型 / 行业 / 注册资本 / 成立日期 / 营业期限 / 登记机关 / 注册地址 / 经营范围 / 经营状态 / 联系电话 / 官网）。
   - 企业简介（文本）。
   - 企业业务（文本）。
   - 企业标签。
   - 股东信息（表：股东名称 / 类型 / 持股比例 / 认缴实缴）。
   - 对外投资（表：被投资企业 / 成立日期 / 投资比例 / 注册资本 / 经营状态 / 所属地区）。
   - 分支机构（表：分支机构 / 成立日期 / 负责人 / 经营状态 / 登记机关 / 地址）。
   - 主要人员（表：姓名 / 职位 / 持股比例 / 现任 / 曾任职企业数）。
5. **代表性记录**：关键明细 Top N（对外投资 + 分支机构）。
6. **特征与洞察**：结构化解读（对外投资布局 / 分支机构网络 / 股权结构 / 核心人员），每条含 `feature` / `evidence` / `interpretation`。
7. **数据口径与来源**：MCP server、数据产品、生成时间、是否 dry-run。

## 质量底线

- 报告脱离 Skill 上下文也可独立阅读；正文只见企业事实与结构化数据。
- 绝不出现“联网收集”“Skill 生成”、工具名、入参（如 `keyword=...`）、product_id、内部字段名、空表、调试信息。
- HTML 采用研究报告视觉风格：A4 风、灰色顶部条纹、蓝色报告横幅、左侧目录 / 范围侧栏、深蓝章节标题、深蓝表头、浅蓝斑马行、打印友好分页。
- 数据为空时明确说明数据范围 / 口径，不渲染空表、不臆造事实。
- 绝不打印 `secret_id` / `secret_key` / 签名 / token / 原始签名请求。
- 自动补全企业全称时，在报告口径中说明“由关键词模糊查询补全”。

### 数据格式约束（铁律）

以下约束适用于 compose_report.py 组装数据与 render_report.py 渲染输出的全过程：

1. **嵌套 JSON 字符串必须解析**：MCP 返回的某些字段（如 `regCapital`、`addressValue`、`subscriptionDetail`）可能是 JSON 字符串（例：`{"coinType":"人民币","value":430000000.0}`）。compose 层必须调用 `_unwrap_json_str()` / `_parse_reg_capital()` / `_flatten_addr()` 解析为可读文本（如"4.30 亿 人民币"、"浙江省杭州市滨江区..."）。绝不在报告正文、表格单元格或指标值中输出原始 JSON 字符串。

2. **section 标题必须用中文**：`core_analysis.sections` 数组中每个 section 的 `title` 字段必须使用中文（如"企业基本信息"、"对外投资"、"股东信息"）。`key` 字段用英文 snake_case 供程序索引，但 `title` 绝不可显示英文 key。即使缺少 sections 数组，渲染器回退逻辑也内置了 `_TITLE_MAP` 映射。

3. **指标值可读化**：所有 `metrics` 的 `value` 字段必须格式化为人类可读形式：
   - 金额：`10995210218.0` → `109.95 亿 人民币`（≥1 亿用亿，≥1 万用万）
     - 金额文本可能含千分位（如 `人民币 2,380.00 万元`）；离线复算比率时必须先按千分位解析再换算亿/万，不得只读取逗号后的尾段。实缴为 0 或缺失时不生成“资本实缴率”。
   - 地址：嵌套 dict → 省+市+区拼接 或取 `value` 字段
   - 比率：`0.8858` → `88.58%`
   - 日期：保持 `yyyy-MM-dd` 格式
   - "-" 表示字段缺失（MCP 未返回）；`0` 表示真实为零

4. **企业画像指标提取**：有 fuzzy_search 的 skill 可从返回的候选记录中提取 `regCapitalValue` / `foundTime` / `operStatus` / `enterpriseType` / `legalRepresentative` 追加为指标卡；若主体未唯一确认，不得把候选记录画像当作目标企业事实。

5. **分布派生指标**：本 skill 由 `_shareholder_charts()` 生成股东排行/类型/性质分布，由 `build_insights()` 生成 CR3 等解读。指标与洞察必须来自 `metrics` 和 `core_analysis` 已返回字段；数量、样本范围与统计口径在名称或 hint 中写清，不从洞察句子正则抓数字补 KPI。

## 工作流

```bash
# 1. 干跑（不调真实 API，用样例数据组装报告骨架）
python scripts/compose_report.py \
  --enterprise "深圳市汇川技术股份有限公司" \
  --dry-run \
  --output output/enterprise.json \
  --report-output output/enterprise.html

# 2. 真实查询 + 渲染（需 MCP 连接就绪）
python scripts/compose_report.py \
  --enterprise "深圳市汇川技术股份有限公司" \
  --output output/enterprise.json \
  --report-output output/enterprise.html

# 3. 关键词自动补全
python scripts/compose_report.py --enterprise "汇川技术" --report-output output/huichuan.html

# 4. 重渲染已有 JSON
python scripts/render_report.py --input output/enterprise.json --output output/enterprise.html
python scripts/render_report.py --input output/enterprise.json --output output/enterprise.md
```

返回：JSON 路径、HTML 路径、Markdown 路径，以及企业全称映射与数据口径摘要。

## AI 内容审校清单（企业）

| 检查项 | 原值示例 | 允许的规范动作 | 证据位置 |
| --- | --- | --- | --- |
| 认缴/实缴单位 | `41141131820.0 万人民币` | 按元重排为 `人民币 411.4113 亿元`，保留币种 | `holderList[].subscriptionDetail/payAmount` |
| 唯一股东比例 | `1.00%`（法人独资） | 保留 `1.00%`；`ratio=1.0` 的分数/百分数歧义写入待核验，不改成 100% | `holderList[].ratio` + 同案 calls.json |
| 股东人数 | `5 个` 含“其他股东” | 计为 `4 个（另有 1 条汇总行）` | `holderList` 名称 |
| 两套股东口径 | 工商 `61.76%` / 证券 `54.50%` | 分别标注口径并提示冲突，不合并 | `holderList` vs `stockHolderList` |
| 关联主体状态 | `对外投资 54 家` | 补“返回行中注销 9 家（非全量）” | `investments[].经营状态` |
| 简介时效 | 2021 年营收/旧榜单 | 标为“上游简介摘录（可能含历史信息）” | `base.desc` |
| 行业层级 | `研究和试验发展 / 研究和试验发展` | 仅去相邻重复，不改名称 | `base_info.industry` |
| 待核验项展示 | `review_flags` 仅在 JSON | 正文生成“待核验事项”表，股东表加“单位待核验”note，摘要提示数量 | `core_analysis.review_flags` + sections |
| 标签 0/1 | 空串/无法识别 | 记“未提供”，不写“否” | `tag.*` |

离线修订入口：`compose_report.py::apply_content_review(report, source_evidence=None)`。正常生成（`build_payload` / CLI 非 `--dry-run`）已在组装阶段自动执行同一审校，并传入同次 `holderList` 原始数值；`--dry-run` 共用该路径且只执行一次。`source_evidence` 传同案 `calls.json`；金额/比例只有与 `numeric_evidence` 路径数值一致时才改，否则保留原值并写 `review_flags`。不查 MCP；修正项写入 `data_source.content_review.corrections`，重复处理会保留既有修正记录，原文与冻结证据文件不变。
