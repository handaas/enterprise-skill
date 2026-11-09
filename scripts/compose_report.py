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
import copy
import datetime as dt
import json
import pathlib
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from common import REPORT_BANNER, REPORT_TYPE, json_dumps, load_json_file, print_json
import mcp_client
from render_report import build_payload as render_build_payload  # noqa: F401  (kept for clarity)
from semantic_review import prepare_draft
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




def _is_empty_signal(value: Any) -> bool:
    """Recognize documented no-data text without classifying it as an API failure."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(text) and any(token in text for token in (
        "查询数据为空", "暂无数据", "未查询到", "未检索到", "查询结果为空",
    ))

def _is_api_error(value: Any) -> bool:
    """Recognize failures without treating a documented empty result as an error."""
    if value is None:
        return False
    if isinstance(value, str):
        text = value.strip()
        if any(s in text for s in ("查询数据为空", "暂无数据", "未查询到", "未检索到")):
            return False
        return any(s in text for s in (
            "接口调用失败", "查询失败", "Error executing tool", "validation error",
            "状态码：4", "状态码：5", "密钥错误", "签名错误", "未配置",
        ))
    if not isinstance(value, dict):
        return False
    if value.get("isError") is True or value.get("success") is False:
        return True
    if value.get("_error") or value.get("error") or value.get("error_message"):
        return True
    if "code" in value and value.get("code") not in (None, 0, 200, "0", "200", "SUCCESS", "success"):
        return True
    if set(value) == {"text"} and value.get("text"):
        return not any(s in str(value["text"]) for s in ("查询数据为空", "暂无数据", "未查询到", "未检索到"))
    return any(_is_api_error(v) for v in value.values() if isinstance(v, (dict, str)))


def _first_list(value: Any) -> List[Any]:
    if _is_api_error(value):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("resultList", "list", "items", "records", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def _first_record(value: Any) -> Dict[str, Any]:
    for record in _first_list(value):
        if isinstance(record, dict) and _has_evidence(record):
            return record
    if isinstance(value, dict) and not _is_api_error(value) and _has_evidence(value):
        return value
    return {}


def _has_evidence(value: Any) -> bool:
    if value is None or value in ("", "-") or _is_empty_signal(value):
        return False
    if _is_api_error(value):
        return False
    if isinstance(value, dict):
        return any(_has_evidence(v) for k, v in value.items() if k not in {"sections", "_raw"})
    if isinstance(value, list):
        return any(_has_evidence(v) for v in value)
    return True


def _text(value: Any, limit: int = 0) -> str:
    if value is None or _is_empty_signal(value):
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
    total = _int(_safe_total(fuzzy))
    name = str(record.get("name") or "").strip()
    if name and total == 1:
        return {"keyword": raw, "enterprise": name, "resolved": True, "reason": "模糊查询唯一候选补全", "fuzzy_total": total, "record": record}
    if name and total and total > 1:
        return {"keyword": raw, "enterprise": raw, "resolved": False, "reason": f"模糊查询返回 {total} 个候选，未静默采用首条", "fuzzy_total": total}
    return {"keyword": raw, "enterprise": raw, "resolved": False, "reason": "模糊查询未命中唯一企业全称，按原始关键词查询"}


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
        "fuzzy_total": resolved.get("fuzzy_total"),
        "requires_confirmation": bool((resolved.get("fuzzy_total") or 0) > 1),
    }


def build_metrics(base: Mapping[str, Any], holder: Any, invest: Any, branch: Any, person: Any) -> List[Dict[str, Any]]:
    metrics: List[Dict[str, Any]] = []
    nested_info = base.get("base_info")
    info: Mapping[str, Any] = nested_info if isinstance(nested_info, dict) else base
    metrics.append({"label": "注册资本", "value": _fmt_capital(info), "hint": "工商公示注册资本"})
    paid = _fmt_paid_capital(info)
    if paid != "-":
        metrics.append({"label": "实缴资本", "value": paid, "hint": "工商公示实缴资本"})
        ratio = _paid_ratio(info)
        if ratio is not None:
            metrics.append({"label": "资本实缴率", "value": f"约 {ratio * 100:.2f}%", "hint": "按返回的实缴资本/注册资本计算，保留 2 位小数；非上游原始比例", "delta": "实缴" if ratio >= Decimal("0.5") else None})
    metrics.append({"label": "成立时间", "value": _text(info.get("foundTime") or info.get("esDate") or info.get("establishmentDate")) or "-", "hint": "工商公示"})
    metrics.append({"label": "经营状态", "value": _text(info.get("operStatus") or info.get("openStatus")) or "-", "hint": "存续/在业/注销等"})
    for label, payload, unit, hint in (
        ("对外投资", invest, "家", "对外投资企业数"),
        ("分支机构", branch, "家", "分支机构数"),
        ("主要人员", person, "人", "工商公示主要人员"),
    ):
        count = _known_count(payload)
        if count is not None:
            metrics.append({"label": label, "value": f"{count} {unit}", "hint": hint})
    # Total counts include 注销/吊销 records. Surface that in the hint rather
    # than letting "对外投资 54 家" read as 54 currently active companies.
    for label, payload, row_key in (("对外投资", invest, "operStatus"), ("分支机构", branch, "operStatus")):
        rows = _first_list(payload)
        if not rows:
            continue
        counts = _status_counts(rows, row_key)
        clause = _status_clause(counts)
        if clause:
            for metric in metrics:
                if metric.get("label") == label:
                    metric["hint"] = f"{metric.get('hint', '')}；本次返回行中 {clause}（非全量）"
                    break
    metrics.append({"label": "股东数量", "value": _holder_count(holder), "hint": "工商公示股东；汇总行不计入股东数"})
    return [m for m in metrics if m.get("value") not in ("", None, "-")]


def _capital_value(info: Mapping[str, Any], key: str = "regCapital") -> Optional[float]:
    """Extract a numeric capital amount (in 元) from {value, coinType} dict or legacy scalars."""
    raw = info.get(key)
    if isinstance(raw, dict):
        amount = raw.get("amount") if raw.get("amount") is not None else raw.get("value")
    else:
        amount = raw
    if amount is None:
        return None
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


def _paid_ratio(info: Mapping[str, Any]) -> Optional[Decimal]:
    """实缴/注册资本比率 (0-1). None if either missing/zero."""
    paid = _capital_value(info, "payAmountCount")
    reg = _capital_value(info, "regCapital")
    if not paid or not reg:
        return None
    return Decimal(str(paid)) / Decimal(str(reg))


def _status_bucket(value: Any) -> str:
    text = _text(value)
    if not text or text == "-":
        return "状态未返回"
    if "注销" in text:
        return "注销"
    if "吊销" in text or "撤销" in text:
        return "吊销/撤销"
    if "迁出" in text:
        return "迁出"
    if "停业" in text or "清算" in text:
        return "停业/清算"
    if any(token in text for token in ("存续", "在营", "开业", "正常", "营业")):
        return "存续/在营"
    return "其他状态"


def _status_counts(rows: Sequence[Mapping[str, Any]], key: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        bucket = _status_bucket(row.get(key))
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _status_clause(counts: Mapping[str, int]) -> str:
    parts = [f"{name} {count}" for name, count in counts.items() if name != "存续/在营"]
    return "、".join(parts)


def _first_present(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    """Return the first present (not None/empty-string) value, preserving real 0."""
    for key in keys:
        if key in mapping and mapping.get(key) not in (None, ""):
            return mapping.get(key)
    return None


def _holder_count(holder: Any) -> str:
    if isinstance(holder, dict) and not _is_api_error(holder):
        for key in ("holderList", "stockHolderList"):
            if key in holder and isinstance(holder[key], list):
                rows = [r for r in holder[key] if isinstance(r, dict)]
                named = [r for r in rows if _text(r.get("name")) and "其他" not in _text(r.get("name"))]
                aggregate = len(rows) - len(named)
                if aggregate:
                    return f"{len(named)} 个（另有 {aggregate} 条汇总行，未计入）"
                return str(len(named)) + " 个"
    return "-"


def _known_count(payload: Any) -> Optional[int]:
    if _is_api_error(payload):
        return None
    total = _int(_safe_total(payload))
    if total is not None:
        return total
    if isinstance(payload, list):
        return len(payload)
    rows = _first_list(payload)
    return len(rows) if rows else None


def _match_type_text(subject: Mapping[str, Any]) -> str:
    reason = str(subject.get("resolve_reason") or "")
    total = subject.get("fuzzy_total")
    if subject.get("requires_confirmation"):
        return f"多候选待确认（模糊查询返回 {total if total is not None else '多个'} 个候选，未静默采用首条）"
    if "模糊" in reason or "候选" in reason:
        return f"关键词模糊查询后唯一匹配（keywordType={subject.get('keywordType', 'name')}）"
    if "全称" in reason or "视为" in reason:
        return f"按输入名称直接查询（keywordType={subject.get('keywordType', 'name')}；未做候选核验）"
    return f"企业主体匹配（keywordType={subject.get('keywordType', 'name')}）"


def build_caliber(subject: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "match_target": subject.get("enterprise") or subject.get("match_raw"),
        "match_type": _match_type_text(subject),
        "data_scope": "企业工商信息、简介、业务、企业标识标签、控股股东、对外投资、分支机构、主要人员",
        "products": [
            "工商基础信息", "企业简介", "企业业务", "企业标签",
            "控股股东信息", "对外投资信息", "分支机构信息", "主要人员信息",
        ],
        "limit": "数据来自工商公示及公开数据；少量字段可能存在更新延迟。对外投资/分支机构数量为上游 total，可能包含注销、吊销等非存续记录；明细为本次返回样本，不代表全量。",
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


def _flag_state(value: Any) -> Optional[bool]:
    """Return True/False only for explicit upstream flags; None means unknown.

    Accepts 1/0, "1"/"0", true/false, 是/否. Empty strings and arbitrary text
    are unknown, not "否".
    """
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "1.0", "true", "yes", "y", "是"}:
        return True
    if text in {"0", "0.0", "false", "no", "n", "否"}:
        return False
    return None


def build_identity_tags(tags: Any) -> Dict[str, Any]:
    """Return {标识名: 状态文本} for the 4 boolean identity flags.

    经营异常 is marked so the renderer can highlight it (bold red). Unknown or
    empty flags are surfaced as 未提供 instead of being silently converted to 否.
    """
    tags = tags if isinstance(tags, dict) else {}
    out: Dict[str, Any] = {}
    for key, label in TAG_LABELS:
        raw = tags.get(key)
        if raw is None:
            continue
        flag = _flag_state(raw)
        if flag is None:
            out[label] = {"value": "未提供", "flag": "unknown"}
            continue
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
    """Aggregate stockHolderList into bar (top by ratio), donut (流通/限售), pie (机构/个人).

    Rows without a usable ratio are excluded from percentage charts instead of
    being assigned weight 1.0, which would fabricate an equal-share distribution.
    A missing entityType is labelled 未标注 rather than guessed as 自然人.
    """
    out: Dict[str, List[Dict[str, Any]]] = {"shareholder_top": [], "shareholding_type": [], "shareholder_entity": []}
    if not isinstance(holder, dict):
        return out
    sh_list = holder.get("stockHolderList")
    if not isinstance(sh_list, list) or not sh_list:
        return out

    # 1) Top shareholders by shareHoldingRatio (bar)
    top: List[Dict[str, Any]] = []
    for sh in sh_list:
        if not isinstance(sh, dict):
            continue
        name = _text(sh.get("name"))
        if not name:
            continue
        ratio = sh.get("shareHoldingRatio")
        pct = source_ratio_percent(ratio)
        if pct is None:
            continue
        top.append({"股东": name, "持股比例": format_source_ratio(ratio),
                    "持股比例数值": float(pct)})
    top.sort(key=lambda r: r["持股比例数值"], reverse=True)
    out["shareholder_top"] = top[:10]

    # 2) 流通/受限 donut from shareHoldingType (may be "流通A股" / "受限流通股" / "受限流通股,流通A股")
    type_counter: Dict[str, float] = {}
    for sh in sh_list:
        if not isinstance(sh, dict):
            continue
        sht = _text(sh.get("shareHoldingType"))
        if not sht:
            continue
        pct = source_ratio_percent(sh.get("shareHoldingRatio"))
        if pct is None or pct <= 0:
            continue
        weight = float(pct)
        for token in sht.replace("，", ",").split(","):
            token = token.strip()
            if not token:
                continue
            bucket = "受限流通股" if "受限" in token else "流通股"
            type_counter[bucket] = type_counter.get(bucket, 0.0) + weight
    if type_counter:
        total = sum(type_counter.values()) or 1.0
        out["shareholding_type"] = [{"类型": k, "占比": round(v / total * 100, 1)} for k, v in type_counter.items()]

    # 3) 机构/个人 split from entityType (enterprise => 机构, blank => 未标注)
    ent_counter: Dict[str, float] = {}
    for sh in sh_list:
        if not isinstance(sh, dict):
            continue
        pct = source_ratio_percent(sh.get("shareHoldingRatio"))
        if pct is None or pct <= 0:
            continue
        raw_type = _text(sh.get("entityType"))
        if raw_type == "enterprise":
            bucket = "机构股东"
        elif raw_type:
            bucket = "自然人股东"
        else:
            bucket = "股东性质未标注"
        ent_counter[bucket] = ent_counter.get(bucket, 0.0) + float(pct)
    if ent_counter:
        total = sum(ent_counter.values()) or 1.0
        out["shareholder_entity"] = [{"类型": k, "占比": round(v / total * 100, 1)} for k, v in ent_counter.items()]
    return out


def build_core_analysis(base: Mapping[str, Any], holder: Any, invest: Any, branch: Any, person: Any) -> Dict[str, Any]:
    nested_info = base.get("base_info")
    info: Mapping[str, Any] = nested_info if isinstance(nested_info, dict) else base
    desc = base.get("desc")
    if isinstance(desc, dict):  # desc may be {desc: "..."}
        desc = desc.get("desc") or ""
    business = base.get("business_info")
    if isinstance(business, dict):
        business = business.get("business") or business.get("business_info") or ""
    tags = base.get("tag")

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
    identity_tag_labels = [f"{name}：{item.get('value', '未提供')}" for name, item in identity_tags.items() if isinstance(item, dict)]

    holder_rows = []
    if isinstance(holder, dict):
        raw_holders = holder.get("holderList") or holder.get("stockHolderList") or []
        for h in _first_list(raw_holders):
            if not isinstance(h, dict):
                continue
            subscribed = _format_amount(h.get("subscriptionDetail") or h.get("subscribedAmount"))
            paid = _format_amount(h.get("payAmount"))
            if subscribed != "-" and paid != "-":
                capital = f"认缴 {subscribed}；实缴 {paid}"
            elif subscribed != "-":
                capital = f"认缴 {subscribed}；实缴未返回"
            elif paid != "-":
                capital = f"实缴 {paid}；认缴未返回"
            else:
                capital = "-"
            holder_rows.append({
                "股东名称": _text(h.get("name")) or "-",
                "股东类型": _text(h.get("holderType") or h.get("investType") or h.get("entityType")) or "-",
                "持股比例": _format_ratio(_first_present(h, ("ratio", "shareHoldingRatio", "subscribedRatio", "investRatio"))),
                "认缴/实缴": capital,
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
            {"key": "identity_tag_labels", "title": "身份标签", "kind": "tags", "note": "仅为上游标识；未提供不等于否"},
            {"key": "description", "title": "企业简介", "kind": "text"},
            {"key": "shareholder_top", "title": "股东持股排行（证券持有人口径）", "kind": "bar", "note": "按 stockHolderList 持股比例排序；与工商登记股东表口径可能不同", "chart": {"name": "股东", "value": "持股比例数值", "orient": "h"}, "columns": [("股东", "股东"), ("持股比例", "持股比例")]},
            {"key": "shareholding_type", "title": "股东类型分布", "kind": "donut", "chart": {"name": "类型", "value": "数量"}, "columns": [("类型", "类型"), ("数量", "数量")]},
            {"key": "shareholder_entity", "title": "股东性质分布", "kind": "donut", "note": "仅统计有持股比例的记录；entityType 缺失记为未标注", "chart": {"name": "性质", "value": "数量"}, "columns": [("性质", "性质"), ("数量", "数量")]},
            {"key": "holders", "title": "股东信息（工商登记口径）", "kind": "table", "note": "holderList 口径；“其他股东”等汇总行不等同于单个股东", "columns": [("股东名称", "股东名称"), ("股东类型", "股东类型"), ("持股比例", "持股比例"), ("认缴/实缴", "认缴/实缴")]},
            {"key": "investments", "title": "对外投资", "kind": "table", "columns": [("被投资企业", "被投资企业"), ("成立日期", "成立日期"), ("投资比例", "投资比例"), ("注册资本", "注册资本"), ("经营状态", "经营状态"), ("所属地区", "所属地区")]},
            {"key": "branches", "title": "分支机构", "kind": "table", "columns": [("分支机构", "分支机构"), ("成立日期", "成立日期"), ("负责人", "负责人"), ("经营状态", "经营状态"), ("登记机关", "登记机关"), ("地址", "地址")]},
            {"key": "key_persons", "title": "主要人员", "kind": "table", "columns": [("姓名", "姓名"), ("职位", "职位"), ("持股比例", "持股比例"), ("现任职企业数", "现任职企业数"), ("曾任职企业数", "曾任职企业数")]},
        ],
        "enterprise_base": [row for row in base_fields if row["内容"] != "-"],
        "identity_tags": identity_tags,
        "identity_tag_labels": identity_tag_labels,
        "description": _text(desc, limit=600),
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
        cleaned: List[str] = []
        for part in parts:
            text = _text(part)
            if text and (not cleaned or cleaned[-1] != text):
                cleaned.append(text)
        joined = " / ".join(cleaned)
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
    if raw is None or raw in ("", 0, "0"):
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


def source_ratio_percent(value: Any) -> Optional[Decimal]:
    """Return a percentage as Decimal without rounding; None when unavailable.

    Accepts a 0-1 fraction, an already-percent number, a '12.3456%' string,
    or a dict. Zero is a real value; only missing/invalid input returns None.
    """
    if isinstance(value, dict):
        value = value.get("value", value.get("ratio", value.get("percent")))
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text or text in {"-", "—"}:
        return None
    had_percent = "%" in text
    if had_percent:
        text = text.replace("%", "").strip()
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    # A literal percent string is already in percentage points; never rescale
    # "1.00%" to 100. Numeric fractions (0.01) are scaled to 1.
    if not had_percent and number != 0 and abs(number) <= 1:
        number *= 100
    return number


def format_source_ratio(value: Any) -> str:
    """Render an upstream ratio without rounding, zero-padding, or unit guessing.

    A percent string such as '12.3400%' is returned verbatim. Numeric 0-1
    fractions keep their original significant digits (0.123456 -> 12.3456%).
    Zero renders as '0%'; missing or invalid values render as '-'.
    """
    if isinstance(value, dict):
        value = value.get("value", value.get("ratio", value.get("percent")))
    if value is None:
        return "-"
    text = str(value).strip()
    if not text or text in {"-", "—"}:
        return "-"
    if "%" in text:
        return text
    number = source_ratio_percent(value)
    if number is None:
        return text
    return f"{format(number.normalize(), 'f')}%"


def _format_ratio(value: Any) -> str:
    """Preserve the upstream ratio exactly; never round or zero-pad."""
    return format_source_ratio(value)


def _format_amount(value: Any) -> str:
    """Format a subscription/paid amount whose upstream unit is the base unit.

    ``subscriptionDetail.amount`` / ``payAmount.value`` are returned in 元 (or
    the named coin's base unit), not in 万. The previous code appended "万"
    unconditionally, turning 15,218,000,000 元 into "15218000000.0 万元".
    Scalars without a currency wrapper are preserved verbatim because their
    unit cannot be proven from the payload.
    """
    value = _unwrap_json_str(value)
    if isinstance(value, dict):
        amount = value.get("amount") if value.get("amount") is not None else value.get("value")
        coin = _text(value.get("coinType")) or ""
        if amount in (None, "", 0, "0"):
            return "-"
        try:
            return _fmt_amount_cn(float(amount), coin) or "-"
        except (TypeError, ValueError):
            return f"{_text(amount)}{(' ' + coin) if coin else ''}".strip()
    if value in (None, "", 0, "0"):
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


def build_insights(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
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
            "interpretation": "该数量只描述工商数据中的投资主体数；扩张、多元化或活跃度需结合投资时间、金额和经营状态核验。",
        })
    if branch_n and branch_n.isdigit() and int(branch_n) > 0:
        insights.append({
            "feature": "分支机构网络",
            "evidence": f"工商公示分支机构 {branch_n} 家。",
            "interpretation": "该数量只描述工商公示分支机构；实际区域经营范围和活跃程度需结合地址及经营状态核验。",
        })
    if holder_n and holder_n.isdigit() and int(holder_n) > 0:
        insights.append({
            "feature": "股权结构",
            "evidence": f"工商公示股东 {holder_n} 个。",
            "interpretation": "股东数量本身不能判断控制权或治理稳定性；需结合持股比例、表决权和协议安排核验。",
        })
    # 关联主体状态：只统计本次返回行，避免把注销/吊销记录当作存续主体。
    for label, rows, status_key in (
        ("对外投资", core.get("investments") or [], "经营状态"),
        ("分支机构", core.get("branches") or [], "经营状态"),
    ):
        if not isinstance(rows, list) or not rows:
            continue
        counts = _status_counts(rows, status_key)
        non_active = {k: v for k, v in counts.items() if k not in ("存续/在营",)}
        if non_active:
            detail = "、".join(f"{k} {v} 条" for k, v in non_active.items())
            insights.append({
                "feature": f"{label}主体状态（本次返回行）",
                "evidence": f"本次返回 {len(rows)} 条{label}记录，其中{detail}。",
                "interpretation": "该统计仅覆盖本次返回行，不是上游 total 的全量分布；注销、吊销等记录不能被当作当前存续主体，也不能反推企业整体经营质量。",
            })
    # 同一股东在两套口径下比例不一致时显式提示，不替用户选择“正确值”。
    sh_top = core.get("shareholder_top") or []
    holder_rows = core.get("holders") or []
    if sh_top and holder_rows:
        def _norm_name(name: Any) -> str:
            text = re.sub(r"[（(][^）)]*[）)]", "", str(name or ""))
            return re.sub(r"[\s集团]", "", text)
        holder_map = {_norm_name(r.get("股东名称")): r.get("持股比例") for r in holder_rows if isinstance(r, dict)}
        conflicts = []
        for row in sh_top:
            if not isinstance(row, dict):
                continue
            name = _norm_name(row.get("股东"))
            other = holder_map.get(name)
            if not other:
                continue
            a = source_ratio_percent(row.get("持股比例"))
            b = source_ratio_percent(other)
            if a is not None and b is not None and abs(a - b) >= Decimal("0.5"):
                conflicts.append(f"“{row.get('股东')}”证券持有人口径 {format_source_ratio(row.get('持股比例'))}，工商登记口径 {format_source_ratio(other)}")
        if conflicts:
            insights.append({
                "feature": "股东比例口径差异",
                "evidence": "；".join(conflicts) + "。",
                "interpretation": "两套股东数据来源与统计口径不同（如工商认缴登记与证券持有人名册），不能相加或相互替换；控制权判断应以股东名册、章程和公示记录交叉核验。",
            })
    # 资本实缴率洞察
    paid_ratio_str = metric_map.get("资本实缴率")
    if paid_ratio_str:
        insights.append({
            "feature": "资本实缴情况",
            "evidence": f"注册资本 {metric_map.get('注册资本', '-')}，实缴资本 {metric_map.get('实缴资本', '-')}，资本实缴率 {paid_ratio_str}。",
            "interpretation": "该比例仅按返回的实缴资本与注册资本计算，不能单独证明企业偿付能力、股东履约能力或未来出资风险。",
        })
    # 股东集中度（基于 shareHoldingRatio）
    sh_top = core.get("shareholder_top") or []
    if sh_top:
        try:
            cr3 = sum(float(r.get("持股比例数值") or 0) for r in sh_top[:3])
            top_name = sh_top[0].get("股东", "-")
            insights.append({
                "feature": "股东集中度",
                "evidence": f"第一大股东“{top_name}”持股 {sh_top[0].get('持股比例', '-')}，前三大股东合计约 {cr3:.2f}%（CR3）。",
                "interpretation": "CR3 只描述返回股东的持股集中度，不能单独判断控制权、决策效率或治理质量。",
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
        insights.append({
            "feature": "企业资质与风险标识",
            "evidence": "；".join(ev_parts) + "。",
            "interpretation": "以上仅为上游返回标识，不能据此推断创新能力、市场地位、融资能力或异常原因；需核验对应认定和公示记录。",
        })
    if person_n and person_n.isdigit() and int(person_n) > 0:
        insights.append({
            "feature": "核心人员",
            "evidence": f"工商公示主要人员 {person_n} 人。",
            "interpretation": "人数只描述工商公示名单规模；团队能力与关联风险需结合人员履历和任职关系核验。",
        })
    if not insights:
        insights.append({
            "feature": "数据完整性",
            "evidence": "部分维度未返回有效数据。",
            "interpretation": "建议核对匹配关键词是否为企业全称，或检查 MCP 连接与上游数据产品覆盖范围。",
        })
    return insights


def build_abstract(subject: Mapping[str, Any], core: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]]) -> str:
    name = subject.get("enterprise") or subject.get("match_raw") or "目标企业"
    if subject.get("requires_confirmation"):
        return f"原始关键词“{subject.get('match_raw') or name}”返回多个候选主体，待人工确认；本报告未调用主体详情，也不形成企业结论。"
    if not metrics and not any(_has_evidence(v) for k, v in core.items() if k != "sections"):
        return f"本次未获得“{name}”的可用工商证据，核心维度覆盖率为 0；不得据此判断企业状态、规模或关联关系。"
    parts = [f"本报告以“{name}”为分析对象，基于工商公示及公开数据，系统呈现企业基础信息、股权结构、对外投资、分支机构与主要人员等核心维度。"]
    if metrics:
        kv = "、".join(f"{m['label']} {m['value']}" for m in metrics[:5])
        parts.append(f"关键指标包括：{kv}。")
    sections = core.get("sections") if isinstance(core, dict) else []
    if isinstance(sections, list) and sections:
        populated = sum(1 for s in sections if isinstance(s, dict) and _has_evidence(core.get(s.get("key"))))
        parts.append(f"本次核心维度有数据 {populated}/{len(sections)} 个；未覆盖维度不作推断。")
    desc = core.get("description") or ""
    if desc:
        parts.append("上游企业简介摘录（可能含历史年份与宣传表述，非本报告结论）：" + (desc[:120] + ("…" if len(desc) > 120 else "")))
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

def _assemble(
    subject: Mapping[str, Any],
    core: Mapping[str, Any],
    metrics: Sequence[Mapping[str, Any]],
    *,
    dry_run: bool,
    source_evidence: Optional[Any] = None,
) -> Dict[str, Any]:
    abstract = build_abstract(subject, core, metrics)
    records = build_records(core)
    insights = build_insights(subject, core, metrics)
    # Quality gate: count populated core-analysis sections.
    ca = core if isinstance(core, dict) else {}
    secs = ca.get("sections", [])
    if secs:
        total_secs = len(secs)
        populated = sum(1 for s in secs if isinstance(s, dict) and _has_evidence(ca.get(s.get("key"))))
    else:
        total_secs = max(1, len([k for k in ca if k != "sections"]))
        populated = sum(1 for k in ca if k != "sections" and _has_evidence(ca.get(k)))
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
    report = {
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
    return apply_content_review(report, source_evidence=source_evidence)


def _holder_numeric_evidence(holder: Any) -> Dict[str, Any]:
    """Collect same-case holder numeric fields for content review.

    Paths mirror the raw tool result (``holderList[i].field``); values are
    copied verbatim so a correction can cite the returned number. Nothing is
    derived, converted, or defaulted here.
    """
    if not isinstance(holder, dict) or _is_api_error(holder):
        return {}
    evidence: Dict[str, Any] = {}
    for list_key in ("holderList", "stockHolderList"):
        rows = holder.get(list_key)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            for field_key in ("subscriptionDetail", "payAmount"):
                value = row.get(field_key)
                if isinstance(value, dict):
                    for amount_key in ("amount", "value"):
                        if value.get(amount_key) not in (None, ""):
                            evidence[f"{list_key}[{index}].{field_key}.{amount_key}"] = value[amount_key]
                elif value not in (None, ""):
                    evidence[f"{list_key}[{index}].{field_key}"] = value
            if row.get("ratio") not in (None, ""):
                evidence[f"{list_key}[{index}].ratio"] = row["ratio"]
    return {"numeric_evidence": evidence} if evidence else {}


def build_payload(raw: str, keyword_type: str) -> Dict[str, Any]:
    resolved = resolve_enterprise_name(raw)
    if (resolved.get("fuzzy_total") or 0) > 1:
        subject = build_subject(raw, resolved, keyword_type)
        core = build_core_analysis({}, {}, {}, {}, {})
        return _assemble(subject, core, [], dry_run=False)
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
    return _assemble(
        subject, core, metrics,
        dry_run=False,
        source_evidence=_holder_numeric_evidence(holder),
    )


def _parse_amount_text(text: Any) -> Optional[float]:
    """Parse a composed amount such as '人民币 411.4113 亿元' or
    '人民币 2,380.00 万元' back to base units, keeping the currency unit.

    ``_fmt_amount_cn`` writes thousands separators, so the numeric part must
    accept grouped digits; the previous pattern did not, matching only
    '380.00' inside '2,380.00 万元'.
    """
    raw = str(text or "").strip()
    match = re.search(r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(亿|万)?\s*元", raw)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    unit = match.group(2)
    if unit == "亿":
        value *= 100_000_000
    elif unit == "万":
        value *= 10_000
    return value


def _numeric_evidence_index(source_evidence: Any) -> Dict[str, Any]:
    """Build {json_path: number} from a same-case calls.json or explicit map."""
    index: Dict[str, Any] = {}
    if not source_evidence:
        return index
    if isinstance(source_evidence, dict) and isinstance(source_evidence.get("numeric_evidence"), dict):
        index.update({str(k): v for k, v in source_evidence["numeric_evidence"].items()})
    calls = source_evidence
    if isinstance(source_evidence, dict) and isinstance(source_evidence.get("calls"), list):
        calls = source_evidence["calls"]
    if isinstance(calls, list):
        for call in calls:
            if not isinstance(call, dict):
                continue
            for item in call.get("numeric_evidence") or []:
                if isinstance(item, dict) and item.get("path") is not None:
                    index[str(item["path"])] = item.get("value")
    if isinstance(source_evidence, dict):
        for key, value in source_evidence.items():
            if key in {"calls", "numeric_evidence"}:
                continue
            if isinstance(value, (int, float, str)) and not isinstance(value, bool):
                index.setdefault(str(key), value)
    return index


def _holder_evidence(index: Mapping[str, Any], row_index: int, keys: Sequence[str]) -> Tuple[Optional[str], Any]:
    for container in ("holderList", "stockHolderList"):
        for key in keys:
            path = f"{container}[{row_index}].{key}"
            if path in index:
                return path, index[path]
    return None, None


def _refresh_quality_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Refresh section-fill metrics after offline review changed sections.

    ``0`` is a populated value; None/""/[]/{} and documented empty sentinels are
    empty. coverage_pct is section fill only, never an accuracy claim.
    """
    core = report.get("core_analysis") or {}
    sections = core.get("sections")
    if isinstance(sections, list) and sections:
        total = len(sections)
        populated = sum(1 for s in sections if isinstance(s, dict) and _has_evidence(core.get(s.get("key"))))
    else:
        keys = [k for k in core if k != "sections"]
        total = max(1, len(keys))
        populated = sum(1 for k in keys if _has_evidence(core.get(k)))
    source = report.setdefault("data_source", {})
    source["quality_report"] = {
        "total_sections": total,
        "populated_sections": populated,
        "empty_sections": total - populated,
        "coverage_pct": round(populated / max(1, total) * 100),
        "metric": "section_fill_rate",
        "note": "章节填充率，仅表示有返回内容的 section 占比，不是内容准确率",
    }
    return report


def _merge_review_records(previous: Any, current: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Keep earlier review records when the same report is processed again."""
    merged: List[Dict[str, Any]] = []
    seen = set()
    for item in list(previous or []) + list(current or []):
        if not isinstance(item, Mapping):
            continue
        row = dict(item)
        key = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def apply_content_review(report: Mapping[str, Any], source_evidence: Optional[Any] = None) -> Dict[str, Any]:
    """Rebuild enterprise narrative from fields already present in a report.

    Pure/offline: no MCP call, no new facts. Optional ``source_evidence`` is the
    same case's numeric evidence: a ``calls.json`` (list, or dict with
    ``calls``/``numeric_evidence``) or an explicit ``{"numeric_evidence": {...}}``
    map built from the raw holder response. It is required before any
    amount/ratio is reinterpreted. Without matching numeric evidence the
    original value is retained and a review flag is added.

    Fixed only when grounded: holder capital strings whose numeric part exactly
    matches ``holderList[i].subscriptionDetail.amount``/``payAmount.value`` and
    whose documented unit is the coin base unit; holder counts; dual-caliber
    labels/conflicts; status wording. A literal percent string is never changed.
    """
    out = copy.deepcopy(dict(report))
    corrections: List[Dict[str, Any]] = []
    subject = out.get("subject") or {}
    core = out.get("core_analysis") or {}
    metrics = [dict(m) for m in (out.get("metrics") or []) if isinstance(m, dict)]
    previous_review = (out.get("data_source") or {}).get("content_review") or {}
    # A no-evidence repeat must not downgrade a review that already cited the
    # same case's raw numeric evidence.
    allow_no_evidence_flags = not (
        previous_review.get("source_evidence_supplied") and not source_evidence
    )

    base_rows = core.get("enterprise_base") or []

    # 1) Holder amount unit. Only rewrite when same-case calls.json numeric
    # evidence proves the underlying amount, and the field's documented unit is
    # the coin base unit (subscriptionDetail.amount / payAmount.value). Never
    # infer from magnitude alone.
    holders = core.get("holders") or []
    evidence_index = _numeric_evidence_index(source_evidence)
    review_flags: List[Dict[str, Any]] = []
    for row_index, row in enumerate(holders):
        if not isinstance(row, dict):
            continue
        original = str(row.get("认缴/实缴") or "")
        match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*万\s*(.*)$", original)
        if not match:
            continue
        amount = Decimal(match.group(1))
        coin = match.group(2).strip()
        path, evidence_value = _holder_evidence(
            evidence_index, row_index,
            ("subscriptionDetail.amount", "subscriptionDetail.value", "payAmount.value", "payAmount.amount"),
        )
        if path is not None and evidence_value is not None:
            try:
                if Decimal(str(evidence_value)) == amount:
                    corrected = _fmt_amount_cn(float(amount), coin)
                    if corrected and corrected != "-":
                        row["认缴/实缴"] = corrected
                        corrections.append({
                            "field": f"core_analysis.holders[{row_index}].认缴/实缴",
                            "before": original,
                            "after": corrected,
                            "evidence": f"{path}={evidence_value}；该字段单位为元/币种基础单位",
                            "reason": "旧格式把基础单位金额错误追加“万”；数值与同案 calls.json numeric_evidence 完全一致",
                        })
                        continue
            except (InvalidOperation, ValueError):
                pass
        if allow_no_evidence_flags:
            review_flags.append({
                "field": f"core_analysis.holders[{row_index}].认缴/实缴",
                "value": original,
                "issue": (
                    "金额单位待核实：同案数值证据未匹配到该行金额，保留原值，不按数量级推断"
                    if source_evidence else
                    "金额单位待核实：未找到同案 calls.json 数值证据，保留原值，不按数量级推断"
                ),
            })

    # 2) Ratio unit. A literal percent string is source-authoritative. Source
    # numeric ratio=1.0 is ambiguous between 100% (fraction) and 1% (percent);
    # without an explicit unit, keep the original and flag it for verification.
    for row_index, row in enumerate(holders):
        if not isinstance(row, dict):
            continue
        original = str(row.get("持股比例") or "")
        if not original or original in {"-", "—"}:
            continue
        path, evidence_value = _holder_evidence(evidence_index, row_index, ("ratio", "shareHoldingRatio", "subscribedRatio", "investRatio"))
        try:
            shown = source_ratio_percent(original)
            source_value = Decimal(str(evidence_value)) if evidence_value is not None else None
        except (InvalidOperation, ValueError):
            shown, source_value = None, None
        if source_value is not None and shown is not None:
            as_fraction = abs(source_value * 100 - shown) < Decimal("0.01")
            as_percent = abs(source_value - shown) < Decimal("0.01")
            if not as_fraction and not as_percent:
                review_flags.append({
                    "field": f"core_analysis.holders[{row_index}].持股比例",
                    "value": original,
                    "issue": f"上游 {path}={evidence_value} 与展示值 {original} 的单位关系无法确定；保留原值待核验",
                })
            elif abs(source_value) == Decimal("1") and abs(shown) == Decimal("1"):
                review_flags.append({
                    "field": f"core_analysis.holders[{row_index}].持股比例",
                    "value": original,
                    "issue": f"上游 {path}={evidence_value}，原展示 {original}；按分数口径应为 100%，按百分数口径应为 1%，单位未确定；保留原值待核验",
                })
        elif source_value is None and allow_no_evidence_flags:
            review_flags.append({
                "field": f"core_analysis.holders[{row_index}].持股比例",
                "value": original,
                "issue": "未找到同案 ratio 数值证据；保留原值，不按企业类型或股东人数推断",
            })

    # 3) Holder count from named rows, keeping aggregate rows visible.
    for metric in metrics:
        if metric.get("label") != "股东数量":
            continue
        named = [r for r in holders if isinstance(r, dict) and r.get("股东名称") and "其他" not in str(r.get("股东名称"))]
        aggregate = len(holders) - len(named)
        before = metric.get("value")
        metric["value"] = f"{len(named)} 个" + (f"（另有 {aggregate} 条汇总行，未计入）" if aggregate else "")
        metric["hint"] = "工商公示股东；汇总行不计入股东数"
        if metric["value"] != before:
            corrections.append({
                "field": "metrics[股东数量]",
                "before": before,
                "after": metric["value"],
                "reason": "“其他股东/其他无限售条件股东”是汇总行，不是单个股东",
            })

    # 4) Recompute the displayed paid-in ratio from the two displayed amount
    # metrics; mark it approximate because the display values are rounded.
    metric_map = {m.get("label"): m for m in metrics}
    reg_metric = metric_map.get("注册资本")
    paid_metric = metric_map.get("实缴资本")
    ratio_metric = metric_map.get("资本实缴率")
    if reg_metric and paid_metric and ratio_metric:
        reg = _parse_amount_text(reg_metric.get("value"))
        paid = _parse_amount_text(paid_metric.get("value"))
        if reg and paid:
            ratio = paid / reg
            before = ratio_metric.get("value")
            ratio_metric["value"] = f"约 {ratio * 100:.2f}%"
            ratio_metric["hint"] = "按返回的实缴资本/注册资本计算，保留 2 位小数；非上游原始比例"
            if ratio_metric["value"] != before:
                corrections.append({
                    "field": "metrics[资本实缴率]",
                    "before": before,
                    "after": ratio_metric["value"],
                    "reason": "原值按 1 位小数展示且未标“约”；按报告中的两个金额重算并保留 2 位",
                })

    # 5) Metric hints: disclose non-active related-party records in the returned rows.
    for label, rows in (("对外投资", core.get("investments") or []), ("分支机构", core.get("branches") or [])):
        if not isinstance(rows, list) or not rows:
            continue
        counts = _status_counts(rows, "经营状态")
        clause = _status_clause(counts)
        if not clause:
            continue
        for metric in metrics:
            if metric.get("label") == label:
                before = metric.get("hint", "")
                if clause in str(before):
                    break
                metric["hint"] = f"{before}；本次返回行中 {clause}（非全量）"
                corrections.append({
                    "field": f"metrics[{label}].hint",
                    "before": before,
                    "after": metric["hint"],
                    "reason": "total 计数包含注销/吊销记录，需避免误读为当前存续主体",
                })
                break

    # 5) Caliber labels and section titles (no recalculation).
    out["caliber"] = build_caliber(subject)
    tags = core.get("identity_tags") or {}
    if isinstance(tags, dict) and tags:
        core["identity_tag_labels"] = [
            f"{name}：{item.get('value', '未提供')}"
            for name, item in tags.items() if isinstance(item, dict)
        ]
    for section in core.get("sections") or []:
        if not isinstance(section, dict):
            continue
        if section.get("key") == "identity_tags":
            section["key"] = "identity_tag_labels"
            section["note"] = "仅为上游标识；未提供不等于否"
            corrections.append({
                "field": "core_analysis.sections[identity_tags]",
                "before": "结构化 dict 直接进入标签列表，显示 value/flag 内部字段",
                "after": "改为“名称：是/否/未提供”的可读标签",
                "reason": "标签正文不应暴露内部字段名；未提供状态单独保留",
            })
        if section.get("key") == "business":
            core["sections"] = [s for s in core["sections"] if s.get("key") != "business"]
            corrections.append({
                "field": "core_analysis.sections[business]",
                "before": "经营范围章节与工商基础信息重复",
                "after": "移除重复章节，经营范围保留在基础信息",
                "reason": "同一字段两处展示且正文为空，降低可读性",
            })
            break
    title_updates = {
        "holders": ("股东信息", "股东信息（工商登记口径）"),
        "shareholder_top": ("股东持股排行", "股东持股排行（证券持有人口径）"),
    }
    for section in core.get("sections") or []:
        if not isinstance(section, dict):
            continue
        old, new = title_updates.get(section.get("key"), (None, None))
        if old and section.get("title") == old:
            section["title"] = new
            corrections.append({
                "field": f"core_analysis.sections[{section.get('key')}].title",
                "before": old,
                "after": new,
                "reason": "同一企业存在工商登记股东与证券持有人两套口径，需在标题中说明",
            })

    # 5.1) Surface unresolved units/ratios in the report body, not only metadata.
    if previous_review.get("source_evidence_supplied") and not source_evidence:
        review_flags = _merge_review_records(previous_review.get("review_flags"), review_flags)
    if review_flags:
        def _review_field_label(field: Any) -> str:
            text = str(field or "-")
            match = re.match(r"core_analysis\.holders\[(\d+)\]\.(.+)", text)
            if match:
                return f"股东信息第 {int(match.group(1)) + 1} 行·{match.group(2)}"
            return text.replace("core_analysis.", "").replace("metrics[", "指标[").replace("].", "·")
        core["review_flags"] = [
            {"字段": _review_field_label(item.get("field")), "原值": item.get("value", "-"), "问题": item.get("issue", "-")}
            for item in review_flags
        ]
        core["sections"] = [s for s in (core.get("sections") or []) if isinstance(s, dict) and s.get("key") != "review_flags"]
        core["sections"].append({
            "key": "review_flags",
            "title": "待核验事项",
            "kind": "table",
            "note": "以下值保留原展示，不按企业类型、股东人数或数值大小推断单位；核实上游单位后再改写事实。",
            "columns": [("字段", "字段"), ("原值", "原值"), ("问题", "问题")],
        })
        for section in core["sections"]:
            if section.get("key") == "holders":
                note = str(section.get("note") or "")
                if "单位待核验" not in note:
                    section["note"] = (note + "；" if note else "") + "金额/比例存在单位待核验项，见“待核验事项”；未核实前不得把展示值当作既定事实"
    else:
        core.pop("review_flags", None)
        core["sections"] = [s for s in (core.get("sections") or []) if isinstance(s, dict) and s.get("key") != "review_flags"]

    # 6) Rebuild narrative from corrected fields.
    out["metrics"] = metrics
    for row in base_rows:
        if isinstance(row, dict) and row.get("字段") == "行业":
            before = str(row.get("内容") or "")
            parts = [p.strip() for p in before.split("/") if p.strip()]
            deduped: List[str] = []
            for part in parts:
                if not deduped or deduped[-1] != part:
                    deduped.append(part)
            after = " / ".join(deduped)
            if after and after != before:
                row["内容"] = after
                corrections.append({
                    "field": "core_analysis.enterprise_base[行业]",
                    "before": before,
                    "after": after,
                    "reason": "上游行业层级重复（如第三、第四级同名），仅去除相邻重复，不改写行业名称",
                })
    insights = build_insights(subject, core, metrics)
    out["insights"] = insights
    out["executive_summary"] = [item["interpretation"] for item in insights][:5] or [build_abstract(subject, core, metrics)[:120]]
    abstract = build_abstract(subject, core, metrics)
    if review_flags:
        abstract += f"报告另有 {len(review_flags)} 项金额/比例单位待核验，已在“待核验事项”列明；核实前不把相关展示值作为既定事实。"
    out["abstract"] = abstract
    out["summary"] = abstract
    out.setdefault("data_source", {})["content_review"] = {
        "mode": "offline_report_fields_only",
        "source_evidence_supplied": bool(source_evidence),
        "reviewed_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "corrections": _merge_review_records(previous_review.get("corrections"), corrections),
        "review_flags": review_flags,
        "not_changed": [
            "未重新查询 MCP；未新增企业、金额、日期或案件事实",
            "上游缺失（-）与未提供字段保持原样，不补 0、不猜单位",
            "未提供同案数值证据时，金额/比例原值不改，只写入 review_flags",
            "百分数字符串视为源端权威值；ratio=1.0 的分数/百分数歧义保留待核验",
        ],
    }
    return _refresh_quality_report(out)


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

    payload = prepare_draft(payload)

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
