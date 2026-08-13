#!/usr/bin/env python3
"""Compose an enterprise big-data report by orchestrating the enterprise MCP.

This script calls the upstream enterprise-mcp-server tools in order and
assembles a structured JSON payload that the renderer turns into a
professional HTML / Markdown report. It supports ``--dry-run`` which returns a
well-formed skeleton from the bundled sample data WITHOUT contacting the MCP
(never triggers paid/credentialed API calls).

Workflow (real run):
  1. Resolve the canonical enterprise name (fuzzy search if only a keyword).
  2. Query base_info, holder, invest, branch, main_person in sequence.
  3. Build unified report JSON (metrics, caliber, core_analysis, records).
  4. Optionally render HTML + Markdown via render_report.

This file never prints secrets; MCP credentials live in the server's own .env.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from typing import Any, Dict, List, Mapping, Optional

from common import REPORT_BANNER, REPORT_TYPE, json_dumps, load_json_file, print_json
import mcp_client
from render_report import build_payload as render_build_payload  # noqa: F401  (kept for clarity)
from render_report import render_html, render_markdown, html_to_pdf

SAMPLE_PATH = pathlib.Path(__file__).resolve().parent.parent / "assets" / "report.example.json"

# Tool name constants for clarity.
T_FUZZY = "enterprise_get_keyword_search"
T_BASE = "enterprise_get_enterprise_base_info"
T_HOLDER = "enterprise_get_enterprise_holder_info"
T_INVEST = "enterprise_get_enterprise_invest_info"
T_BRANCH = "enterprise_get_enterprise_branch_info"
T_PERSON = "enterprise_get_enterprise_main_person_info"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _is_api_error(value: Any) -> bool:
    """Detect MCP API error responses (not empty data, but actual failures like 405)."""
    if value is None:
        return False
    if isinstance(value, str):
        return any(s in value for s in ("接口调用失败", "查询失败", "状态码：4", "状态码：5"))
    if isinstance(value, dict):
        for v in value.values():
            if isinstance(v, str) and any(s in v for s in ("接口调用失败", "查询失败", "状态码：4", "状态码：5")):
                return True
    return False

def _first_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if _is_api_error(value):
            return []
        # Some products return {total, resultList}
        for key in ("resultList", "list", "items", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    if value in (None, "", {}):
        return []
    return [value]


def _first_record(value: Any) -> Dict[str, Any]:
    records = _first_list(value)
    for record in records:
        if isinstance(record, dict):
            return record
    if isinstance(value, dict):
        return value
    return {}


def _text(value: Any, limit: int = 0) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    text = " ".join(text.split())
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_call(tool: str, arguments: Dict[str, Any]) -> Any:
    """Call an MCP tool; on failure return a structured error object."""
    try:
        return mcp_client.call_tool(tool, arguments)
    except Exception as exc:  # surfaced to report as data-source gap, not crash
        return {"_error": str(exc)}


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #

def resolve_enterprise_name(raw: str) -> Dict[str, Any]:
    """If raw is already a full name, return as-is; else fuzzy-search one."""
    raw = (raw or "").strip()
    if not raw:
        return {"keyword": "", "enterprise": "", "resolved": False, "reason": "关键词为空"}
    # Heuristic: if it looks like a full enterprise name (contains 公司/集团/院/厂 etc.), trust it.
    if any(suffix in raw for suffix in ("公司", "集团", "有限", "院", "厂", "中心", "事务所", "合作社", "合伙")):
        return {"keyword": raw, "enterprise": raw, "resolved": True, "reason": "视为企业全称"}
    fuzzy = _safe_call(T_FUZZY, {"matchKeyword": raw, "pageSize": 1})
    record = _first_record(fuzzy)
    name = str(record.get("name") or "").strip()
    if name:
        return {"keyword": raw, "enterprise": name, "resolved": True, "reason": "由关键词模糊查询补全", "fuzzy_total": _int(_safe_total(fuzzy))}
    return {"keyword": raw, "enterprise": raw, "resolved": False, "reason": "模糊查询未命中企业全称，按关键词直查"}


def _safe_total(payload: Any) -> Any:
    if isinstance(payload, dict):
        if _is_api_error(payload):
            return None
        return payload.get("total")
    return None


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #

def build_subject(raw: str, resolved: Mapping[str, Any], keyword_type: str) -> Dict[str, Any]:
    return {
        "enterprise": resolved.get("enterprise") or raw,
        "matchKeyword": resolved.get("enterprise") or raw,
        "keywordType": keyword_type,
        "match_raw": raw,
        "resolved": bool(resolved.get("resolved")),
        "resolve_reason": resolved.get("reason", ""),
    }


def build_metrics(base: Mapping[str, Any], holder: Any, invest: Any, branch: Any, person: Any) -> List[Dict[str, Any]]:
    metrics: List[Dict[str, Any]] = []
    info = base.get("base_info") if isinstance(base, dict) and isinstance(base.get("base_info"), dict) else (base if isinstance(base, dict) else {})
    metrics.append({"label": "注册资本", "value": _fmt_capital(info), "hint": "工商公示注册资本"})
    paid = _fmt_paid_capital(info)
    if paid != "-":
        metrics.append({"label": "实缴资本", "value": paid, "hint": "工商公示实缴资本"})
        ratio = _paid_ratio(info)
        if ratio is not None:
            metrics.append({"label": "资本实缴率", "value": f"{ratio * 100:.1f}%", "hint": "实缴资本/注册资本", "delta": "实缴" if ratio >= 0.5 else None})
    metrics.append({"label": "成立时间", "value": _text(info.get("foundTime") or info.get("esDate") or info.get("establishmentDate")) or "-", "hint": "工商公示"})
    metrics.append({"label": "经营状态", "value": _text(info.get("operStatus") or info.get("openStatus")) or "-", "hint": "存续/在业/注销等"})
    metrics.append({"label": "对外投资", "value": str(_safe_total(invest) or len(_first_list(invest))) + " 家", "hint": "对外投资企业数"})
    metrics.append({"label": "分支机构", "value": str(_safe_total(branch) or len(_first_list(branch))) + " 家", "hint": "分支机构数"})
    metrics.append({"label": "主要人员", "value": str(_safe_total(person) or len(_first_list(person))) + " 人", "hint": "工商公示主要人员"})
    metrics.append({"label": "股东数量", "value": _holder_count(holder), "hint": "工商公示股东"})
    return [m for m in metrics if m.get("value") not in ("", None, "-")]


def _capital_value(info: Mapping[str, Any], key: str = "regCapital") -> Optional[float]:
    """Extract a numeric capital amount (in 元) from {value, coinType} dict or legacy scalars."""
    raw = info.get(key)
    if isinstance(raw, dict):
        amount = raw.get("amount") if raw.get("amount") is not None else raw.get("value")
    else:
        amount = raw
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None
    if amount in (None, "", 0) or amount <= 0:
        return None
    return amount


def _capital_coin(info: Mapping[str, Any], key: str = "regCapital") -> str:
    raw = info.get(key)
    if isinstance(raw, dict):
        return _text(raw.get("coinType")) or ""
    return _text(info.get(f"{key}CoinType")) or ""


def _fmt_amount_cn(amount: Optional[float], coin: str = "") -> str:
    """Format a capital amount (in 元) as a readable Chinese unit string.

    The upstream API returns the registered/paid capital in 元 (yuan), e.g.
    2695267300 == 26.95 亿元. We render 亿/万 with thousands separators and
    never use scientific notation.
    """
    if amount is None or amount <= 0:
        return "-"
    text = f"{coin} " if coin else ""
    if amount >= 100_000_000:
        return f"{text}{amount / 100_000_000:,.4f} 亿元".strip()
    if amount >= 10_000:
        return f"{text}{amount / 10_000:,.2f} 万元".strip()
    return f"{text}{amount:,.0f} 元".strip()


def _fmt_capital(info: Mapping[str, Any]) -> str:
    amount = _capital_value(info, "regCapital")
    if amount is None:
        # legacy scalar fallback (already in 万)
        legacy = info.get("regCapitalValue") or info.get("regCapital")
        if legacy not in (None, "", 0):
            return f"{_text(legacy)} 万{_capital_coin(info) or ''}".strip()
        return "-"
    return _fmt_amount_cn(amount, _capital_coin(info))


def _fmt_paid_capital(info: Mapping[str, Any]) -> str:
    amount = _capital_value(info, "payAmountCount")
    if amount is None:
        return "-"
    return _fmt_amount_cn(amount, _capital_coin(info, "payAmountCount") or _capital_coin(info))


def _paid_ratio(info: Mapping[str, Any]) -> Optional[float]:
    """实缴/注册资本比率 (0-1). None if either missing/zero."""
    paid = _capital_value(info, "payAmountCount")
    reg = _capital_value(info, "regCapital")
    if not paid or not reg:
        return None
    return paid / reg


def _holder_count(holder: Any) -> str:
    if isinstance(holder, dict):
        lst = holder.get("holderList") or holder.get("stockHolderList") or []
        if isinstance(lst, list):
            return str(len(lst)) + " 个"
    return "-"


def build_caliber(subject: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "match_target": subject.get("enterprise") or subject.get("match_raw"),
        "match_type": f"企业全称精确匹配（keywordType={subject.get('keywordType', 'name')}）",
        "data_scope": "企业工商信息、简介、业务、企业标识标签、控股股东、对外投资、分支机构、主要人员",
        "products": [
            "工商基础信息", "企业简介", "企业业务", "企业标签",
            "控股股东信息", "对外投资信息", "分支机构信息", "主要人员信息",
        ],
        "limit": "数据来自工商公示及公开数据；少量字段可能存在更新延迟。",
    }


# --------------------------------------------------------------------------- #
# Tag / shareholder / branch / person extraction helpers
# --------------------------------------------------------------------------- #

TAG_LABELS = [
    ("isHighTechEnterprise", "高新技术企业"),
    ("isTopEnterprise", "头部企业"),
    ("hasStock", "上市公司"),
    ("isAnomaly", "经营异常"),
]


def _is_01(value: Any) -> bool:
    """True only when an explicit positive 0/1 flag equals 1."""
    try:
        return int(value) == 1
    except (TypeError, ValueError):
        return False


def build_identity_tags(tags: Any) -> Dict[str, Any]:
    """Return {标识名: 状态文本} for the 4 boolean identity flags.

    经营异常 is marked so the renderer can highlight it (bold red).
    """
    tags = tags if isinstance(tags, dict) else {}
    out: Dict[str, Any] = {}
    for key, label in TAG_LABELS:
        raw = tags.get(key)
        if raw is None:
            continue
        flag = _is_01(raw)
        out[label] = {
            "value": "是" if flag else "否",
            "flag": "anomaly" if (key == "isAnomaly" and flag) else ("yes" if flag else "no"),
        }
    return out


def _oper_status_text(value: Any) -> str:
    """operStatus may be {name, value} dict or a scalar."""
    if isinstance(value, dict):
        return _text(value.get("value") or value.get("name"))
    return _text(value)


def _position_text(value: Any) -> str:
    """position may be a list of roles; join with '、'."""
    if isinstance(value, list):
        return "、".join(_text(t) for t in value if t)
    return _text(value)


def _shareholder_charts(holder: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Aggregate stockHolderList into bar (top by ratio), donut (流通/限售), pie (机构/个人)."""
    out: Dict[str, List[Dict[str, Any]]] = {"shareholder_top": [], "shareholding_type": [], "shareholder_entity": []}
    if not isinstance(holder, dict):
        return out
    sh_list = holder.get("stockHolderList")
    if not isinstance(sh_list, list) or not sh_list:
        return out

    # 1) Top shareholders by shareHoldingRatio (bar)
    top = []
    for sh in sh_list:
        if not isinstance(sh, dict):
            continue
        name = _text(sh.get("name"))
        if not name:
            continue
        ratio = sh.get("shareHoldingRatio")
        try:
            ratio_f = float(ratio)
        except (TypeError, ValueError):
            ratio_f = 0.0
        top.append({"股东": name, "持股比例": round(ratio_f * 100, 2)})
    top.sort(key=lambda r: r["持股比例"], reverse=True)
    out["shareholder_top"] = top[:10]

    # 2) 流通/受限 donut from shareHoldingType (may be "流通A股" / "受限流通股" / "受限流通股,流通A股")
    type_counter: Dict[str, float] = {}
    for sh in sh_list:
        if not isinstance(sh, dict):
            continue
        sht = _text(sh.get("shareHoldingType"))
        if not sht:
            continue
        try:
            ratio_f = float(sh.get("shareHoldingRatio") or 0)
        except (TypeError, ValueError):
            ratio_f = 0.0
        weight = ratio_f if ratio_f > 0 else 1.0
        for token in sht.replace("，", ",").split(","):
            token = token.strip()
            if not token:
                continue
            bucket = "受限流通股" if "受限" in token else "流通股"
            type_counter[bucket] = type_counter.get(bucket, 0.0) + weight
    if type_counter:
        total = sum(type_counter.values()) or 1.0
        out["shareholding_type"] = [{"类型": k, "占比": round(v / total * 100, 1)} for k, v in type_counter.items()]

    # 3) 机构/个人 split from entityType (enterprise => 机构, else 自然人)
    ent_counter: Dict[str, float] = {}
    for sh in sh_list:
        if not isinstance(sh, dict):
            continue
        try:
            ratio_f = float(sh.get("shareHoldingRatio") or 0)
        except (TypeError, ValueError):
            ratio_f = 0.0
        weight = ratio_f if ratio_f > 0 else 1.0
        bucket = "机构股东" if sh.get("entityType") == "enterprise" else "自然人股东"
        ent_counter[bucket] = ent_counter.get(bucket, 0.0) + weight
    if ent_counter:
        total = sum(ent_counter.values()) or 1.0
        out["shareholder_entity"] = [{"类型": k, "占比": round(v / total * 100, 1)} for k, v in ent_counter.items()]
    return out


def build_core_analysis(base: Mapping[str, Any], holder: Any, invest: Any, branch: Any, person: Any) -> Dict[str, Any]:
    info = base.get("base_info") if isinstance(base, dict) and isinstance(base.get("base_info"), dict) else (base if isinstance(base, dict) else {})
    desc = base.get("desc") if isinstance(base, dict) else ""
    if isinstance(desc, dict):  # desc may be {desc: "..."}
        desc = desc.get("desc") or ""
    business = base.get("business_info") if isinstance(base, dict) else ""
    if isinstance(business, dict):
        business = business.get("business") or business.get("business_info") or ""
    tags = base.get("tag") if isinstance(base, dict) else ""

    paid_capital = _fmt_paid_capital(info)
    former_names = info.get("formerNames")
    former_names_text = ""
    if isinstance(former_names, list) and former_names:
        former_names_text = "、".join(_text(t) for t in former_names if t)
    elif isinstance(former_names, str) and former_names.strip():
        former_names_text = former_names.strip()

    base_fields = [
        {"字段": "企业名称", "内容": _text(info.get("name")) or "-"},
        {"字段": "曾用名", "内容": former_names_text or "-"},
        {"字段": "统一社会信用代码", "内容": _text(info.get("socialCreditCode") or info.get("unifiedSocialCreditCode")) or "-"},
        {"字段": "法定代表人", "内容": _text(info.get("legalRepresentative") or info.get("legalPerson")) or "-"},
        {"字段": "企业类型", "内容": _text(info.get("enterpriseType") or info.get("companyType")) or "-"},
        {"字段": "行业", "内容": _flatten_industry(info.get("industry")) or "-"},
        {"字段": "注册资本", "内容": _fmt_capital(info) if _fmt_capital(info) != "-" else "-"},
        {"字段": "实缴资本", "内容": paid_capital if paid_capital != "-" else "-"},
        {"字段": "成立日期", "内容": _text(info.get("foundTime") or info.get("esDate")) or "-"},
        {"字段": "营业期限", "内容": _flatten_term(info.get("businessTerm") or info.get("operatingPeriod")) or "-"},
        {"字段": "登记机关", "内容": _text(info.get("registrationAuthority") or info.get("regInstitute")) or "-"},
        {"字段": "注册地址", "内容": _text(info.get("address") or info.get("regAddr") or info.get("regLocation")) or "-"},
        {"字段": "经营范围", "内容": _text(info.get("businessScope") or info.get("business") or info.get("operateScope")) or "-"},
        {"字段": "经营状态", "内容": _oper_status_text(info.get("operStatus") or info.get("openStatus")) or "-"},
        {"字段": "联系电话", "内容": _text(info.get("phoneNumber") or info.get("contactPhone")) or "-"},
        {"字段": "企业官网", "内容": _text(info.get("homepage") or info.get("website")) or "-"},
    ]

    identity_tags = build_identity_tags(tags)

    holder_rows = []
    if isinstance(holder, dict):
        raw_holders = holder.get("holderList") or holder.get("stockHolderList") or []
        for h in _first_list(raw_holders):
            if not isinstance(h, dict):
                continue
            holder_rows.append({
                "股东名称": _text(h.get("name")) or "-",
                "股东类型": _text(h.get("holderType") or h.get("investType") or h.get("entityType")) or "-",
                "持股比例": _format_ratio(h.get("ratio") or h.get("shareHoldingRatio") or h.get("subscribedRatio") or h.get("investRatio")),
                "认缴/实缴": _format_amount(h.get("subscriptionDetail") or h.get("payAmount") or h.get("subscribedAmount")),
            })

    invest_rows = []
    for inv in _first_list(invest):
        if not isinstance(inv, dict):
            continue
        invest_rows.append({
            "被投资企业": _text(inv.get("name")) or "-",
            "成立日期": _text(inv.get("foundTime")) or "-",
            "投资比例": _format_ratio(inv.get("ratio")),
            "注册资本": _parse_reg_capital(inv.get("regCapital")),
            "经营状态": _oper_status_text(inv.get("operStatus")) or "-",
            "所属地区": _flatten_addr(inv.get("addressValue") or inv.get("regAddr")),
        })

    branch_rows = []
    for br in _first_list(branch):
        if not isinstance(br, dict):
            continue
        branch_rows.append({
            "分支机构": _text(br.get("name")) or "-",
            "成立日期": _text(br.get("foundTime")) or "-",
            "负责人": _text(br.get("legalRepresentative")) or "-",
            "经营状态": _oper_status_text(br.get("operStatus")) or "-",
            "登记机关": _text(br.get("registrationAuthority")) or "-",
            "地址": _flatten_addr(br.get("addressValue") or br.get("address")) or "-",
        })

    person_rows = []
    for p in _first_list(person):
        if not isinstance(p, dict):
            continue
        person_rows.append({
            "姓名": _text(p.get("name")) or "-",
            "职位": _position_text(p.get("position")) or "-",
            "持股比例": _format_ratio(p.get("ratio")),
            "现任职企业数": _text(p.get("relatedEnterpriseCurrentNum")) or "-",
            "曾任职企业数": _text(p.get("relatedEnterpriseHistoryNum")) or "-",
        })

    sh_charts = _shareholder_charts(holder)

    return {
        "sections": [
            {"key": "enterprise_base", "title": "企业基本信息", "kind": "kv", "columns": [("字段", "字段"), ("内容", "内容")]},
            {"key": "identity_tags", "title": "身份标签", "kind": "tags"},
            {"key": "description", "title": "企业简介", "kind": "text"},
            {"key": "business", "title": "经营范围", "kind": "text"},
            {"key": "shareholder_top", "title": "股东持股排行", "kind": "bar", "chart": {"name": "股东", "value": "持股比例", "orient": "h"}, "columns": [("股东", "股东"), ("持股比例", "持股比例")]},
            {"key": "shareholding_type", "title": "股东类型分布", "kind": "donut", "chart": {"name": "类型", "value": "数量"}, "columns": [("类型", "类型"), ("数量", "数量")]},
            {"key": "shareholder_entity", "title": "股东性质分布", "kind": "donut", "chart": {"name": "性质", "value": "数量"}, "columns": [("性质", "性质"), ("数量", "数量")]},
            {"key": "holders", "title": "股东信息", "kind": "table", "columns": [("股东名称", "股东名称"), ("股东类型", "股东类型"), ("持股比例", "持股比例"), ("认缴/实缴", "认缴/实缴")]},
            {"key": "investments", "title": "对外投资", "kind": "table", "columns": [("被投资企业", "被投资企业"), ("成立日期", "成立日期"), ("投资比例", "投资比例"), ("注册资本", "注册资本"), ("经营状态", "经营状态"), ("所属地区", "所属地区")]},
            {"key": "branches", "title": "分支机构", "kind": "table", "columns": [("分支机构", "分支机构"), ("成立日期", "成立日期"), ("负责人", "负责人"), ("经营状态", "经营状态"), ("登记机关", "登记机关"), ("地址", "地址")]},
            {"key": "key_persons", "title": "主要人员", "kind": "table", "columns": [("姓名", "姓名"), ("职位", "职位"), ("持股比例", "持股比例"), ("现任职企业数", "现任职企业数"), ("曾任职企业数", "曾任职企业数")]},
        ],
        "enterprise_base": [row for row in base_fields if row["内容"] != "-"],
        "identity_tags": identity_tags,
        "description": _text(desc, limit=600),
        "business": _text(business, limit=600),
        "tags": _join_tags(tags),
        "shareholder_top": sh_charts["shareholder_top"],
        "shareholding_type": sh_charts["shareholding_type"],
        "shareholder_entity": sh_charts["shareholder_entity"],
        "holders": holder_rows,
        "investments": invest_rows,
        "branches": branch_rows,
        "key_persons": person_rows,
    }


def _join_tags(tags: Any) -> str:
    if isinstance(tags, dict):
        # businessTags is a list under tag; surface it as the descriptive tag set
        biz = tags.get("businessTags")
        if isinstance(biz, list) and biz:
            return "、".join(_text(t) for t in biz if t)
        # fall through to other useful scalar tag fields
        for key in ("financingSeries", "operStatus", "enterpriseScaleAlgValue"):
            val = tags.get(key)
            if val:
                return _text(val)
        return ""
    if isinstance(tags, list):
        return "、".join(_text(t) for t in tags if t)
    return _text(tags, limit=200)


def _flatten_industry(value: Any) -> str:
    """industry may be a nested dict {firstIndustry, secondIndustry, thirdIndustry, ...}."""
    if isinstance(value, dict):
        parts = [value.get("firstIndustry"), value.get("secondIndustry"), value.get("thirdIndustry"), value.get("fourthIndustry")]
        joined = " / ".join(_text(p) for p in parts if p)
        return joined or _text(value.get("originName") or value.get("name"))
    return _text(value)


def _flatten_term(value: Any) -> str:
    if isinstance(value, dict):
        mn = value.get("min")
        mx = value.get("max")
        long_term = value.get("longTerm") or value.get("isLongTerm")
        if long_term:
            return f"{_text(mn) or '—'} 至 长期"
        if mn and mx:
            return f"{_text(mn)} 至 {_text(mx)}"
        return _text(mn or mx)
    return _text(value)


def _unwrap_json_str(val: Any) -> Any:
    """If val is a JSON string (e.g. '{"coinType":"人民币","value":430000000.0}'), parse and return the dict; otherwise return val unchanged."""
    if isinstance(val, str):
        stripped = val.strip()
        if len(stripped) > 1 and stripped[0] in "{[" and stripped[-1] in "}]":
            try:
                return json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                pass
    return val


def _flatten_addr(value: Any) -> str:
    value = _unwrap_json_str(value)          # MCP may return a JSON string
    if isinstance(value, dict):
        joined = _text(value.get("value"))
        if joined and joined != "-":
            return joined
        parts = [value.get("province"), value.get("city"), value.get("district")]
        return "".join(_text(p) for p in parts if p) or "-"
    return _text(value) or "-"


def _parse_reg_capital(val: Any) -> str:
    """Parse regCapital: may be scalar, dict, or JSON string '{"coinType":"人民币","value":430000000.0}'."""
    val = _unwrap_json_str(val)
    if isinstance(val, dict):
        raw = val.get("value")
        coin = _text(val.get("coinType")) or ""
    else:
        raw = val
        coin = ""
    if raw in (None, "", 0, "0"):
        return "-"
    try:
        v = float(raw)
        if v >= 1e8:
            s = f"{v / 1e8:.2f} 亿"
        elif v >= 1e4:
            s = f"{v / 1e4:.2f} 万"
        else:
            s = f"{v:.0f}"
        return f"{s} {coin}".strip() if coin else s
    except (TypeError, ValueError):
        return _text(raw) or "-"


def _format_ratio(value: Any) -> str:
    """ratio may be 0.8858 (fraction) or '88.58%' or a dict."""
    if isinstance(value, dict):
        value = value.get("value") or value.get("ratio")
    if value in (None, "", []):
        return "-"
    try:
        f = float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return _text(value)
    if f == 0:
        return "-"
    if f < 1 and f > 0 and "." not in str(value) and "%" not in str(value):
        return f"{f * 100:.2f}%"
    if "%" in str(value) or f >= 1:
        return f"{f:.2f}%"
    return f"{f * 100:.2f}%"


def _format_amount(value: Any) -> str:
    """subscriptionDetail / payAmount may be {amount, coinType, date} or scalar or JSON string."""
    value = _unwrap_json_str(value)
    if isinstance(value, dict):
        amount = value.get("amount") if value.get("amount") is not None else value.get("value")
        coin = value.get("coinType") or ""
        if amount in (None, "", 0):
            return "-"
        return f"{_text(amount)} 万{coin}".strip()
    if value in (None, "", 0):
        return "-"
    return _text(value)


def build_records(core: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Pick representative records (top investments) for the records chapter."""
    invests = core.get("investments") or []
    records = []
    for inv in invests[:10]:
        records.append({
            "类型": "对外投资",
            "名称": inv.get("被投资企业") or "-",
            "关系/比例": f"投资比例 {inv.get('投资比例', '-')}",
            "状态": inv.get("经营状态") or "-",
            "日期": inv.get("成立日期") or "-",
        })
    for br in (core.get("branches") or [])[:5]:
        records.append({
            "类型": "分支机构",
            "名称": br.get("分支机构") or "-",
            "关系/比例": "分支机构",
            "状态": br.get("经营状态") or "-",
            "日期": br.get("成立日期") or "-",
        })
    return records


def build_insights(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []
    metric_map = {m["label"]: str(m["value"]) for m in metrics}
    holder_n = (metric_map.get("股东数量") or "0").split()[0]
    invest_n = (metric_map.get("对外投资") or "0").split()[0]
    branch_n = (metric_map.get("分支机构") or "0").split()[0]
    person_n = (metric_map.get("主要人员") or "0").split()[0]

    if invest_n and invest_n.isdigit() and int(invest_n) > 0:
        insights.append({
            "feature": "对外投资布局",
            "evidence": f"企业对外投资 {invest_n} 家。",
            "interpretation": "对外投资数量反映该主体的对外扩张与多元化程度，结合投资地区与经营状态可判断其投资活跃度与版图范围。",
        })
    if branch_n and branch_n.isdigit() and int(branch_n) > 0:
        insights.append({
            "feature": "分支机构网络",
            "evidence": f"工商公示分支机构 {branch_n} 家。",
            "interpretation": "分支机构分布通常对应业务在地化部署，反映区域覆盖广度与连锁/网络化经营特征。",
        })
    if holder_n and holder_n.isdigit() and int(holder_n) > 0:
        insights.append({
            "feature": "股权结构",
            "evidence": f"工商公示股东 {holder_n} 个。",
            "interpretation": "股东类型与持股比例集中度决定企业控制权稳定性与治理结构；具体明细见核心分析章节。",
        })
    # 资本实缴率洞察
    paid_ratio_str = metric_map.get("资本实缴率")
    if paid_ratio_str:
        try:
            ratio_v = float(paid_ratio_str.replace("%", "")) / 100
            if ratio_v >= 0.7:
                lvl = "实缴充分，出资能力与股东承诺兑现度高"
            elif ratio_v >= 0.3:
                lvl = "实缴部分到位，需关注剩余认缴额的实缴进度"
            else:
                lvl = "实缴比例偏低，需关注出资到位风险"
            insights.append({
                "feature": "资本实缴情况",
                "evidence": f"注册资本 {metric_map.get('注册资本', '-')}，实缴资本 {metric_map.get('实缴资本', '-')}，资本实缴率 {paid_ratio_str}。",
                "interpretation": f"资本实缴率反映股东实际出资到位程度；当前{lvl}。",
            })
        except (TypeError, ValueError):
            pass
    # 股东集中度（基于 shareHoldingRatio）
    sh_top = core.get("shareholder_top") or []
    if sh_top:
        try:
            total_ratio = sum(float(r.get("持股比例", 0) or 0) for r in sh_top)
            cr3 = sum(float(r.get("持股比例", 0) or 0) for r in sh_top[:3])
            top_name = sh_top[0].get("股东", "-")
            insights.append({
                "feature": "股东集中度",
                "evidence": f"第一大股东“{top_name}”持股约 {sh_top[0].get('持股比例', 0)}%，前三大股东合计约 {cr3:.2f}%（CR3）。",
                "interpretation": "股权集中度高通常意味着控制权清晰、决策效率高，但也伴随大股东依赖；分散则治理更均衡，但需关注控制权稳定性。",
            })
        except (TypeError, ValueError):
            pass
    # 企业标识洞察（高新技术企业/经营异常等）
    id_tags = core.get("identity_tags") or {}
    positive = [k for k, v in id_tags.items() if isinstance(v, dict) and v.get("flag") not in ("anomaly",) and v.get("value") == "是"]
    anomaly = [k for k, v in id_tags.items() if isinstance(v, dict) and v.get("flag") == "anomaly"]
    if positive or anomaly:
        ev_parts = []
        if positive:
            ev_parts.append("具备“" + "、".join(positive) + "”标识")
        if anomaly:
            ev_parts.append("存在“" + "、".join(anomaly) + "”记录")
        interp_parts = []
        if "高新技术企业" in positive:
            interp_parts.append("具备高新技术企业资质，通常享受研发税收优惠并体现较强的技术创新能力")
        if "上市公司" in positive:
            interp_parts.append("为上市主体，信息披露较透明、融资渠道通畅")
        if "头部企业" in positive:
            interp_parts.append("被识别为行业头部企业，市场地位领先")
        if anomaly:
            interp_parts.append("经营异常需重点关注，建议核查是否已申请移出异常名录")
        insights.append({
            "feature": "企业资质与风险标识",
            "evidence": "；".join(ev_parts) + "。",
            "interpretation": "；".join(interp_parts) + "。",
        })
    if person_n and person_n.isdigit() and int(person_n) > 0:
        insights.append({
            "feature": "核心人员",
            "evidence": f"工商公示主要人员 {person_n} 人。",
            "interpretation": "主要人员的任职企业数与历史履历可用于评估管理团队资源与潜在关联风险。",
        })
    if not insights:
        insights.append({
            "feature": "数据完整性",
            "evidence": "部分维度未返回有效数据。",
            "interpretation": "建议核对匹配关键词是否为企业全称，或检查 MCP 连接与上游数据产品覆盖范围。",
        })
    return insights


def build_abstract(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: List[Mapping[str, Any]]) -> str:
    name = subject.get("enterprise") or subject.get("match_raw") or "目标企业"
    parts = [f"本报告以“{name}”为分析对象，基于工商公示及公开数据，系统呈现企业基础信息、股权结构、对外投资、分支机构与主要人员等核心维度。"]
    if metrics:
        kv = "、".join(f"{m['label']} {m['value']}" for m in metrics[:5])
        parts.append(f"关键指标包括：{kv}。")
    desc = core.get("description") or ""
    if desc:
        parts.append("企业简介：" + (desc[:120] + ("…" if len(desc) > 120 else "")))
    parts.append("报告同时给出对外投资、分支机构与核心人员的结构化明细，便于进一步尽调、关联分析与决策参考。")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Dry-run sample
# --------------------------------------------------------------------------- #

def build_dry_run_payload(raw: str, keyword_type: str) -> Dict[str, Any]:
    try:
        sample = load_json_file(SAMPLE_PATH)
    except Exception:
        sample = {}
    sample = sample if isinstance(sample, dict) else {}
    subject = sample.get("subject") or {"enterprise": raw, "matchKeyword": raw, "keywordType": keyword_type, "match_raw": raw}
    subject = {**subject, "match_raw": raw, "keywordType": keyword_type}
    core = sample.get("core_analysis") or {}
    metrics = sample.get("metrics") or []
    return _assemble(subject, core, metrics, dry_run=True)


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _assemble(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: List[Mapping[str, Any]], *, dry_run: bool) -> Dict[str, Any]:
    abstract = build_abstract(subject, core, metrics)
    records = build_records(core)
    insights = build_insights(subject, core, metrics)
    # Quality gate: count populated core-analysis sections.
    ca = core if isinstance(core, dict) else {}
    secs = ca.get("sections", [])
    if secs:
        total_secs = len(secs)
        populated = sum(1 for s in secs if isinstance(s, dict) and ca.get(s.get("key")) not in (None, "", [], {}))
    else:
        total_secs = max(1, len([k for k in ca if k != "sections"]))
        populated = sum(1 for k in ca if k != "sections" and ca.get(k) not in (None, "", [], {}))
    quality_report = {
        "total_sections": total_secs,
        "populated_sections": populated,
        "empty_sections": total_secs - populated,
        "coverage_pct": round(populated / max(1, total_secs) * 100),
    }
    if populated == 0:
        import sys
        print("⚠️ 质量门禁警告: 所有核心分析维度均无数据", file=sys.stderr)
    title = f"{subject.get('enterprise') or '目标企业'} 企业大数据报告"
    return {
        "report_type": REPORT_TYPE,
        "title": title,
        "banner": REPORT_BANNER,
        "subject": dict(subject),
        "abstract": abstract,
        "summary": abstract,
        "executive_summary": [item["interpretation"] for item in insights][:5] or [abstract[:120]],
        "metrics": list(metrics),
        "caliber": build_caliber(subject),
        "core_analysis": dict(core),
        "representative_records": records,
        "insights": insights,
        "data_source": {
            "mcp_server": "enterprise-mcp-server",
            "products": [
                {"name": "工商基础信息", "product_id": "66dbccbec7a7e3460f5e613f"},
                {"name": "企业简介/股东/投资/分支/人员", "product_id": "见 references/mcp-tools-reference.md"},
            ],
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "dry_run": dry_run,
            "quality_report": quality_report,
        },
    }


def build_payload(raw: str, keyword_type: str) -> Dict[str, Any]:
    resolved = resolve_enterprise_name(raw)
    enterprise = resolved["enterprise"]
    # All enterprise detail tools take the full name as `keyword`.
    base = _safe_call(T_BASE, {"keyword": enterprise})
    holder = _safe_call(T_HOLDER, {"keyword": enterprise})
    invest = _safe_call(T_INVEST, {"keyword": enterprise})
    branch = _safe_call(T_BRANCH, {"keyword": enterprise})
    person = _safe_call(T_PERSON, {"keyword": enterprise})

    subject = build_subject(raw, resolved, keyword_type)
    core = build_core_analysis(base, holder, invest, branch, person)
    metrics = build_metrics(base, holder, invest, branch, person)
    return _assemble(subject, core, metrics, dry_run=False)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Compose an enterprise big-data report via the enterprise MCP.")
    parser.add_argument("--enterprise", required=True, help="企业全称或关键词（关键词将自动模糊补全）")
    parser.add_argument("--keyword-type", default="name", help="主体类型：name/nameId/regNumber/socialCreditCode")
    parser.add_argument("--dry-run", action="store_true", help="不调用真实 MCP，使用样例数据组装报告骨架")
    parser.add_argument("--output", help="输出 JSON 路径；省略则打印到 stdout")
    parser.add_argument("--report-output", help="同时输出 HTML 报告（.html）与 Markdown 报告（.md）；按扩展名自动判断")
    parser.add_argument("--pdf-output", help="额外输出 PDF 报告（.pdf）；需要 Playwright + Chromium")
    args = parser.parse_args()

    if args.dry_run:
        payload = build_dry_run_payload(args.enterprise, args.keyword_type)
    else:
        payload = build_payload(args.enterprise, args.keyword_type)

    if args.output:
        out = pathlib.Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_dumps(payload, pretty=True), encoding="utf-8")
        print_json({"ok": True, "json": str(out), "dry_run": args.dry_run})
    else:
        print_json(payload)

    if args.report_output:
        base_out = pathlib.Path(args.report_output).expanduser()
        base_out.parent.mkdir(parents=True, exist_ok=True)
        html_path = base_out.with_suffix(".html") if base_out.suffix.lower() not in (".html", ".htm") else base_out
        md_path = html_path.with_suffix(".md")
        html_path.write_text(render_html(payload), encoding="utf-8")
        md_path.write_text(render_markdown(payload), encoding="utf-8")
        if args.pdf_output:
            pdf_path = pathlib.Path(args.pdf_output).expanduser()
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            html_to_pdf(render_html(payload), str(pdf_path))
        print_json({"ok": True, "html": str(html_path), "markdown": str(md_path), "pdf": str(pdf_path) if args.pdf_output else None, "dry_run": args.dry_run})


if __name__ == "__main__":
    main()
