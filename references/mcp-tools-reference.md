# MCP 工具参考 — enterprise-mcp-server

本 skill 连接的 MCP server：`handaas-mcp-server/enterprise-mcp-server`（“HANDAAS企业大数据服务”）。

> **重要**：企业详情类工具（base / holder / invest / branch / person）入参为 `keyword`（**企业全称**）；
> 仅 `enterprise_get_keyword_search` 用 `matchKeyword`（关键词，含企业名 / 人名 / 品牌 / 产品 / 岗位）。当用户只给关键词时，必须先调关键词模糊查询补全全称。

## 通用约定

- 主体类型枚举（详情接口本身不传，但概念适用）：`name`（企业名称）/ `nameId`（企业 id）/ `regNumber`（注册号）/ `socialCreditCode`（统一社会信用代码）。
- 分页：`pageIndex` 从 1 开始；`pageSize` 单页最多 50。
- 所有工具返回 `dict`（list 类含 `total` + `resultList`，detail 类返回对象）。

---

## 工具清单

### 1. `enterprise_get_keyword_search` — 关键词模糊查询企业

用途：根据企业名称 / 人名 / 品牌 / 产品 / 岗位等关键词模糊查询企业列表，用于补全企业全称。**所有详情接口的前置步骤**（当无全称时）。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 匹配关键词 |
| `pageIndex` | int | 否 | 分页开始位置 |
| `pageSize` | int | 否 | 单页最多 50 |

返回：`total` + 企业列表（`name`、`nameId`、`regCapitalValue`、`foundTime`、`operStatus`、`address`、`legalRepresentative`、`enterpriseType`、`catchReason` 命中原因等）。

product_id：`675cea1f0e009a9ea37edaa1`。

---

### 2. `enterprise_get_enterprise_base_info` — 企业基础信息（工商 + 简介 + 业务 + 标签）

用途：识别“这家公司是做什么的”。返回工商信息、企业简介、企业业务、企业标签。**报告核心章节的数据源**。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 是 | 企业全称（无全称则先调 fuzzy_search） |

返回：
- `base_info`：企业工商信息（名称、统一社会信用代码、法定代表人、企业类型、行业、注册资本、成立日期、营业期限、登记机关、注册地址、经营范围、经营状态、联系电话、官网等）。
- `desc`：企业简介（文本）。
- `business_info`：企业业务（文本）。
- `tag`：企业标签（list 或文本）。

> 该工具内部聚合 4 个上游产品：`66dbccbec7a7e3460f5e613f`（工商基础）、`6682b0b370f56cb7d77701e0`（简介）、`66e55613ae988a28c6db9259`（业务）、`669e531ce1fd7bff82321d8d`（标签）。

---

### 3. `enterprise_get_enterprise_holder_info` — 控股股东信息

用途：查询企业控股股东。来源：工商公示 + 全量数据分析。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 是 | 企业全称 |

返回：
- `holderList`（工商公示股东）：`entityType` 主体类型、`holderType` 股东类型、`name` 股东名称、`nameId` 企业 id、`humanId` 人员 id、`payAmount` 实缴金额、`ratio` 持股比例、`subscriptionDetail` 认缴信息。
- `stockHolderList`（最新公示股东，来自上市信息）。

---

### 4. `enterprise_get_enterprise_invest_info` — 对外投资信息

用途：查询企业对外投资。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 是 | 企业全称 |

返回（list）：`addressValue` 被投资公司所属地区、`business` 经营范围、`foundTime` 成立日期、`isListed` 上市状态、`legalRepresentative` 法定代表人、`name` 对外投资企业名、`operStatus` 经营状态、`ratio` 占股比例、`regCapital` 注册资本、`scCode` 统一信用编码、`subscriptionAmount` 投资金额信息。

---

### 5. `enterprise_get_enterprise_branch_info` — 分支机构信息

用途：查询企业分支机构（来源：工商公示）。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 是 | 企业全称 |

返回（list）：`addressValue` 地址、`foundTime` 成立时间、`legalRepresentative` 法定代表人、`name` 机构名称、`operStatus` 经营状态、`orgCode` 组织机构代码、`registrationAuthority` 登记机关、`socialCreditCode` 统一社会信用代码。

---

### 6. `enterprise_get_enterprise_main_person_info` — 主要人员信息

用途：查询企业主要人员（来源：工商公示）。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 是 | 企业全称 |

返回（list）：`name` 成员名称、`position` 职位、`ratio` 持股比例、`relatedEnterpriseCurrentNum` 现任职企业数、`relatedEnterpriseHistoryNum` 曾任职企业数。

---

## 推荐调用顺序（报告编排）

1. （若仅有关键词）`enterprise_get_keyword_search` → 取 `name` 作为全称。
2. `enterprise_get_enterprise_base_info` → 工商 / 简介 / 业务 / 标签。
3. `enterprise_get_enterprise_holder_info` → 股东。
4. `enterprise_get_enterprise_invest_info` → 对外投资。
5. `enterprise_get_enterprise_branch_info` → 分支机构。
6. `enterprise_get_enterprise_main_person_info` → 主要人员。

> 单次报告通常调用 5-6 个工具；全部详情接口入参均为企业全称 `keyword`。
