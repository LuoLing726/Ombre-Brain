"""
========================================
tools/breath/catalog.py — catalog 目录模式（省 token 的记忆总览）
========================================

用途：开新对话时先花极少的 token 看一眼「我都记得哪些事」，再用
breath_search(query=...) 精准拉取需要的记忆——代替把全部记忆一股脑塞进上下文。

关键行为：
- 只读元数据（bucket_mgr.list_all），0 次 LLM/embedding 调用
- 每桶一行：名称 | 域 | 重要度 | Footprint，按重要度降序
- 按类型分区（固化/动态/feel/plan/letter），区头带数量
- 可选 domain 过滤（OR）、tags 过滤（AND）和条数上限
- protected 桶保留在显式目录中，统一标记为「🛡️ [受保护记忆]」

不做什么（边界）：
- 不返回正文、不算权重分、不触发衰减/浮现逻辑——那些是其他分支的事
- 不做 token 截断：目录本身就是最省形态
========================================
"""

from .. import _runtime as rt
from ..plan.core import is_letter_bucket, letter_lock_state
from ombrebrain.storage.relation_store import relation_hint
from utils import parse_bool
from errors import safe_error_detail

# 类型 → (区头, 排序位)。未知类型归入动态区兜底。
_SECTIONS = [
    ("permanent", "固化"),
    ("dynamic", "动态"),
    ("feel", "feel"),
    ("plan", "plan"),
    ("letter", "letter"),
]


async def surface_catalog(
    domain_filter: list[str] | None = None,
    tag_filter: list[str] | None = None,
    max_results: int = 20,
) -> str:
    """返回全部记忆桶的紧凑目录。每桶一行：名称 | 域 | 重要度 | Footprint。"""
    try:
        buckets = await rt.bucket_mgr.list_all(include_archive=False)
    except Exception as e:
        return f"获取记忆目录失败: {safe_error_detail(e)}"

    if not buckets:
        return "记忆库为空。"

    try:
        footprint_snapshot = rt.bucket_mgr.footprint_snapshot()
    except Exception as exc:
        rt.logger.warning(f"Footprint snapshot unavailable / 足迹读取失败: {exc}")
        footprint_snapshot = None

    def _footprint(bucket: dict, meta: dict) -> str:
        if footprint_snapshot is None:
            return "👣 Footprint：暂时无法读取"
        return footprint_snapshot.summary(str(bucket.get("id") or ""), meta)

    grouped: dict[str, list[tuple[int, str]]] = {key: [] for key, _ in _SECTIONS}
    for b in buckets:
        meta = b.get("metadata", {})
        logical_letter = is_letter_bucket(b)
        letter_locked = (
            logical_letter and letter_lock_state(b, "ai")["locked"]
        )
        domains = (
            ["letter"]
            if letter_locked
            else [d for d in (meta.get("domain") or []) if d]
        )
        if domain_filter and not any(d in domain_filter for d in domains):
            continue
        bucket_tags = (
            {"__letter__"} if letter_locked else set(meta.get("tags") or [])
        )
        if tag_filter and not all(tag in bucket_tags for tag in tag_filter):
            continue
        try:
            imp = int(meta.get("importance") or 0)
        except (TypeError, ValueError):
            imp = 0
        name = "一封上锁的信" if letter_locked else meta.get("name") or b["id"]
        protected = parse_bool(meta.get("protected"), default=False)
        pin_mark = ""
        if not logical_letter:
            if protected:
                pin_mark = "🛡️ [受保护记忆] "
            elif parse_bool(meta.get("pinned"), default=False):
                pin_mark = "📌"
        anchor_mark = (
            "⚓ [anchor] "
            if parse_bool(meta.get("anchor"), default=False)
            else ""
        )
        line = (
            f"{pin_mark}{anchor_mark}{name} | {','.join(domains) or '未分类'} | {imp} "
            f"| {_footprint(b, meta)}"
        )
        if not letter_locked:
            hint = relation_hint(b)
            if hint:
                line += f" | {hint.replace(chr(10), ' | ')}"
        btype = meta.get("type")
        key = "letter" if logical_letter else btype if btype in grouped else "dynamic"
        grouped[key].append((imp, line))

    total = sum(len(v) for v in grouped.values())
    if total == 0:
        return "没有匹配过滤条件的记忆桶。"

    ranked: list[tuple[int, str, str]] = []
    for key, _label in _SECTIONS:
        ranked.extend((imp, line, key) for imp, line in grouped[key])
    ranked.sort(key=lambda item: item[0], reverse=True)
    limited: dict[str, list[tuple[int, str]]] = {key: [] for key, _ in _SECTIONS}
    for imp, line, key in ranked[:max_results]:
        limited[key].append((imp, line))
    grouped = limited
    total = sum(len(v) for v in grouped.values())

    parts = [
        f"=== 记忆目录（{total} 桶）===",
        "先看目录定位，再 breath_search(query=...) 精准拉取正文。",
    ]
    for key, label in _SECTIONS:
        rows = grouped[key]
        if not rows:
            continue
        rows.sort(key=lambda t: t[0], reverse=True)
        parts.append(f"--- {label}（{len(rows)}）---")
        parts.extend(line for _, line in rows)
    return "\n".join(parts)
