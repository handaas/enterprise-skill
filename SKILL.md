---
name: enterprise-report
description: Use for generating a professional enterprise big-data report (企业大数据报告) from the HandaaS enterprise MCP — covering 工商信息、企业简介、企业标签、企业业务、控股股东、对外投资、分支机构、主要人员. Trigger when users ask for “企业大数据报告”, “企业工商报告”, “查一家公司的工商信息/股东/对外投资/分支机构/主要人员”, “企业尽调报告”, “企业画像”, or “生成企业分析报告”. Infer the canonical enterprise name (auto-fuzzy-completing a keyword), pick the right MCP tools, and produce HTML + Markdown + JSON reports automatically. MCP 服务名称触发词：企业信息洞察。
---

# 企业大数据报告

## 用户契约

把“企业大数据报告”作为面向用户的调用短语。`enterprise-report` 仅为内部包名。

当本 skill 处于激活状态：

1. 不要向用户索要 product_id、MCP 工具名、API 字段、内部参数或凭证信息；只接受企业名称或关键词。
2. 接受自然目标，例如“查一下某某公司的工商信息”“分析这家企业的股东和对外投资”“给我一份某某公司的企业画像报告”“尽调一下某某企业”。
3. 当用户只给关键词（如简称、品牌、人名）时，自动调用关键词模糊查询补全企业全称，再查询详情。
4. 优先使用 MCP 连接（`ENTERPRISE_MCP_URL` Remote MCP 或本地 `handaas-mcp-server/enterprise-mcp-server`）；不要让用户处理签名或凭证。
5. 同时产出 HTML（可分享交付）、Markdown（知识库 / wiki）、JSON（系统集成）三类产物；除非用户明确只要其中之一。
6. 报告正文必须是专业研究报告风格：只见企业事实与结构化数据，绝不出现“联网收集”“Skill 生成”、工具名、入参、product_id、内部字段或空表。
7. 绝不打印 `secret_id`、`secret_key`、签名、token 或原始签名请求。
8. 默认 dry-run；真实付费 / 凭证调用需用户明确要求且 MCP 连接配置完整。
9. 数据为空时明确说明数据范围 / 口径，不渲染空表、不臆造事实。


- MCP 返回的嵌套 JSON 字符串（如金额 `{"coinType":"人民币","value":430000000.0}`、地址 `{"city":"杭州市",...}`）必须解析为可读文本（如"4.30 亿 人民币"、"浙江省杭州市"），绝不在报告正文、表格或指标中输出原始 JSON 字符串。
- 报告所有章节标题、指标卡标签必须用中文；`core_analysis.sections` 的 `title` 字段必须中文，不可显示英文 key（如 `holders`、`investments`）。
- 指标值必须可读化：金额格式为"X 亿/万 + 币种"，地址拼接省市区，比率显示百分号。详见 `references/report-output.md` 的「数据格式约束」。

## 付费调用与分页预算（强制）

每次 MCP 业务调用和每一页明细请求都可能计费；希望得到 total / 页数计算**不是**全量拉取的授权。

1. **先计划再调用**：调用前先推导本次报告必需的结论、需要的数据维度、工具与参数方案、所需页数和最大调用预算。上游 total 未知时，第一个必要的明细页同时用于发现 total 与报告数据，绝不为此页重复付费。
2. **优先统计 / 概况接口**：当结论可由工商基础信息等概况接口回答时优先使用它们；仅在结论、图表、代表性记录或用户明确要求全量/计数时才拉取明细。只有在用户确实要求综合报告时才跑完整流水线，绝不因为工具存在就全部调用。
3. **预算内取数**：使用 schema 允许的合理最大 pageSize 获取所需行数，达到证据/样本目标即停止，且始终在显式预算内。额外翻页必须有缺失结论的正当理由，而不是“想填满所有章节”。不得用样本分布冒充全量结论。
4. **复用相同请求**：同一任务/报告内相同的工具+参数只调用一次（含首屏规划数据）；渲染只用本地已保存 JSON 重渲，不重跑 compose/MCP。禁止自动重试、重复拉取相同统计/明细、并行拉取相同数据。补充查询前先列出具体缺口并复用已返回记录。
5. **总数与完整性口径**：`total_pages` / `remaining_pages` 只是按请求 pageSize 的估算；短而未完的页在预算内要继续翻。仅当稳定有效的 total 与实扫条数一致才算完整采集；报错、提前空页、重复页、total 变化/缺失或数量溢出均视为不完整。因显式预算或样本目标提前停止的都是部分采集，绝不宣称全量数据。
6. **预算不足要说清缺口**：若预算不足以支撑某个关键结论，在申请扩大授权前先说明证据缺口与预计的额外调用数；不得静默降级结论，也不得擅自扩大计费范围。

本 skill 无客户端分页明细：base / holder / invest / branch / person 五个详情接口仅接受 `keyword`（企业全称）、单次调用，schema 不支持 pageIndex/pageSize，不得向其传分页参数或自行翻页；仅 `enterprise_get_keyword_search` 支持分页，且仅用于主体唯一确认（单次调用，pageSize=1），不做候选遍历。

## MCP 服务入口

- MCP 服务当前名称：企业信息洞察（连接仍使用原服务目录标识）。

- 上游 MCP 项目：`handaas-mcp-server/enterprise-mcp-server`（位于 `HANDAAS_MCP_SERVER_ROOT` 或本仓库同级目录）。
- Remote MCP：设置环境变量 `ENTERPRISE_MCP_URL`（streamable-http），可选 `ENTERPRISE_MCP_TOKEN`。
- 本地 MCP：设置 `HANDAAS_MCP_SERVER_ROOT` 指向 `handaas-mcp-server` 仓库根目录；该 server 自己的 `.env` 提供 `INTEGRATOR_ID` / `SECRET_ID` / `SECRET_KEY`。
- 首次真实查询前，运行 `scripts/mcp_client.py ping` 与 `scripts/mcp_client.py list-tools` 验证连通。

## 按需加载 references

- 不清楚该 MCP 有哪些工具、参数、返回字段、何时调用：`references/mcp-tools-reference.md`。
- 报告结构、章节、质量底线、渲染工作流：`references/report-output.md`。

## 意图路由

| 用户意图 | 内部工作流 |
| --- | --- |
| 查一家公司的全维度企业报告 | 调 6 个企业工具组装全量报告；`compose_report.py --enterprise ...` |
| 只要工商基础 / 股东 / 投资 / 分支 / 人员某一维度 | 仅调对应工具，按统一骨架组装该维度为主的核心分析 |
| 只给关键词（不是全称） | 先 `enterprise_get_keyword_search` 补全全称，再查详情 |
| 只要 JSON / 只要 HTML / 只要 Markdown | 用 `--output`（JSON）或 `--report-output`（HTML+MD），或用 `render_report.py` 重渲染 |
| 连接 / 工具不存在 / 传参错误 | `mcp_client.py ping` / `list-tools` 排查；报脱敏后的缺失项 |

## Golden path for 企业大数据报告

1. **解析企业全称**：若输入含“公司/集团/有限/院/厂/中心/事务所/合作社/合伙”等后缀视为全称；否则调 `enterprise_get_keyword_search` 取首个命中。
2. **调用企业工具**：依次调用 `enterprise_get_enterprise_base_info`（含工商/简介/业务/标签）、`enterprise_get_enterprise_holder_info`（股东）、`enterprise_get_enterprise_invest_info`（对外投资）、`enterprise_get_enterprise_branch_info`（分支机构）、`enterprise_get_enterprise_main_person_info`（主要人员）。所有详情接口入参为 `keyword`（企业全称）。
3. **组装统一报告**：按统一 JSON 骨架（subject / abstract / metrics / caliber / core_analysis / representative_records / insights / data_source）组装；核心分析按工商基础 / 简介 / 业务 / 标签 / 股东 / 对外投资 / 分支机构 / 主要人员分章节。
4. **渲染三件套**：`compose_report.py --enterprise ... --output ... --report-output ...` 直接产出 JSON + HTML + Markdown；或用 `render_report.py --input ... --output ...` 重渲染。
5. **返回路径**：返回 JSON、HTML、Markdown 文件路径，以及企业全称映射与数据口径。

- **渲染前置检查**：执行会产出含图表 HTML / PDF 的报告命令前，先验证 `node --version` 与本 skill 自带 `assets/vendor/echarts.min.js` 存在；内嵌静态 SVG 的生成需要 Node.js（推荐当前 LTS，无需 npm 包），缺失时报告生成明确报错。查看已生成的 HTML 与 Markdown 输出不需要 Node。

## AI 内容审校（正常生成已内置，离线复核可重放）

脚本只做确定性解析；以下语义核对由当前 AI 在渲染前完成，并把“原值 → 规范值 → 证据位置”写入审校记录。不得把未执行的审校写成已完成。

正常生成（`build_payload` / CLI 非 `--dry-run`）在组装阶段自动执行 `apply_content_review`，并把同次 `holderList` 原始数值作为 `source_evidence` 传入；`--dry-run` 与正常生成共用同一条组装/审校路径，只执行一次。下面的离线入口用于复核已有报告；重复调用会保留此前的 `content_review.corrections`，不会清空首次修正依据。

1. **主体与名称**：`subject.enterprise`、标题、工商基础信息、统一社会信用代码必须指向同一主体；曾用名只作历史名称，不拼成当前主体。输入含“集团”但无“公司/有限”等法定后缀时，不得仅凭后缀判定全称，需在口径中标注“按输入名称查询，未做候选核验”。
2. **股东两套口径**：工商登记股东表（`holderList`，含认缴/实缴）与证券持有人排行（`stockHolderList`，含持股比例）不可相加或互相替换；同一股东比例差异 ≥0.5 个百分点时保留两套原值并提示核验。“其他股东/其他无限售条件股东”是汇总行，不计入股东人数。
3. **金额与比例**：认缴/实缴金额的上游单位是元或币种基础单位，不得再追加“万”；注册资本按亿/万缩放时保留币种。持股比例保留上游有效数字，`0` 是真实值、`-` 是缺失；百分数字符串（如 `1.00%`）是源端权威值，不得因“唯一股东/法人独资”改成 `100%`；`ratio=1.0` 的分数/百分数歧义必须标记待核实。派生实缴率标注“约”并保留 2 位小数。
4. **状态与时效**：对外投资、分支机构数量是上游 `total`，可能含注销、吊销记录；必须同时给出本次返回行中的非存续数量，不能把“54 家”读成 54 家当前存续。企业简介是上游原文，可能含历史年份和宣传口径，引用时标明“上游简介摘录”，不把旧营收/排名当当前事实。
5. **标识与结论**：`0/1` 标签只按明确值转“是/否”；空值或无法识别的文本记为“未提供”，不得默认“否”。洞察只描述返回字段，不据标签推断创新能力、市场地位或异常原因。

离线修订已有报告（不调用 MCP、不覆盖 `examples/` 原件）：

```python
import json
from compose_report import apply_content_review

report = json.load(open("examples/01-investment-dd/report.json", encoding="utf-8"))
evidence = json.load(open("examples/01-investment-dd/calls.json", encoding="utf-8"))
revised = apply_content_review(report, evidence)   # 纯函数，返回修正后的完整 payload
json.dump(revised, open("output/content-quality-review/01-investment-dd/report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
```

`source_evidence` 接受同案 `calls.json`（list，或含 `calls`/`numeric_evidence` 的 dict）。只有金额数值与 `holderList[i].subscriptionDetail.amount`/`payAmount.value` 完全一致时才重排单位；没有证据则保留原值并写入 `review_flags`。比例字符串不改写；未解决的金额/比例单位会在正文生成“待核验事项”表，并在股东表 note 标注，不能只藏在 JSON 元数据里。其余修正是汇总行计数、股东口径标题、行业重复层级、实缴率展示与状态提示，均记录在 `data_source.content_review.corrections`。

## 脚本速查

```bash
# 校验连接配置（脱敏）
python scripts/validate_config.py --allow-placeholders

# 连通性自测
python scripts/mcp_client.py ping
python scripts/mcp_client.py list-tools

# 干跑（不调真实 API，用样例数据组装报告骨架）
python scripts/compose_report.py \
  --enterprise "深圳市汇川技术股份有限公司" \
  --dry-run \
  --output output/enterprise.json \
  --report-output output/enterprise.html

# 真实查询 + 渲染（需 MCP 连接就绪）
python scripts/compose_report.py \
  --enterprise "深圳市汇川技术股份有限公司" \
  --output output/enterprise.json \
  --report-output output/enterprise.html

# 只给关键词（自动模糊补全）
python scripts/compose_report.py --enterprise "汇川技术" --report-output output/huichuan.html

# 手动调单个工具
python scripts/mcp_client.py call-tool \
  --tool enterprise_get_enterprise_base_info \
  --arguments-json '{"keyword": "深圳市汇川技术股份有限公司"}'

# 重渲染已有 JSON
python scripts/render_report.py --input output/enterprise.json --output output/enterprise.html
python scripts/render_report.py --input output/enterprise.json --output output/enterprise.md
```

## 输出字段

- `subject`：企业全称、匹配关键词、主体类型、是否自动补全。
- `abstract` / `summary`：封面摘要与详细摘要。
- `executive_summary`：3-5 条核心发现要点。
- `metrics`：注册资本、成立时间、经营状态、对外投资数、分支机构数、主要人员数、股东数等指标卡。
- `caliber`：匹配对象、匹配方式、数据范围、产品、局限。
- `core_analysis`：工商基础（KV）、企业简介（文本）、企业业务（文本）、企业标签、股东、对外投资、分支机构、主要人员（表格）。
- `representative_records`：代表性记录（对外投资 + 分支机构 Top N）。
- `insights`：结构化特征与解读（投资布局 / 分支网络 / 股权结构 / 核心人员）。
- `data_source`：MCP server、数据产品、生成时间、是否 dry-run。

若 API 调用失败，明确报出缺失的配置 / 缺失的工具 / MCP 错误 / 参数校验错误 / 上游网络错误，给出 dry-run 命令或配置步骤，绝不暴露密钥。
