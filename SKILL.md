---
name: enterprise-report
description: Use for generating a professional enterprise big-data report (企业大数据报告) from the HandaaS enterprise MCP — covering 工商信息、企业简介、企业标签、企业业务、控股股东、对外投资、分支机构、主要人员. Trigger when users ask for “企业大数据报告”, “企业工商报告”, “查一家公司的工商信息/股东/对外投资/分支机构/主要人员”, “企业尽调报告”, “企业画像”, or “生成企业分析报告”. Infer the canonical enterprise name (auto-fuzzy-completing a keyword), pick the right MCP tools, and produce HTML + Markdown + JSON reports automatically.
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

## MCP 服务入口

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
