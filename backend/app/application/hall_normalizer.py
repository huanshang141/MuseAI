"""Shared hall identity normalization.

Known Banpo aliases map to their canonical slugs. Generic admin/import paths may
preserve another well-formed slug for audit, while mini-program API boundaries
must additionally require membership in ``CANONICAL_HALL_SLUGS``.
"""

import re

CANONICAL_HALLS: dict[str, str] = {
    "basic-exhibition-hall": "基本陈列展厅",
    "site-protection-hall": "遗址保护大厅",
    "temporary-hall-1": "临展厅一",
    "temporary-hall-2": "临展厅二",
    "banpo-girl-sculpture": "半坡姑娘雕塑",
    "prehistoric-workshop": "史前工坊",
    "education-center": "教研中心",
    "peony-garden": "牡丹园",
    "kiln-hall": "陶窑展厅",
}

CANONICAL_HALL_ORDER = [
    "basic-exhibition-hall",
    "site-protection-hall",
    "kiln-hall",
    "prehistoric-workshop",
    "banpo-girl-sculpture",
    "education-center",
    "peony-garden",
    "temporary-hall-1",
    "temporary-hall-2",
]

TEMPORARY_HALL_SLUGS = frozenset({"temporary-hall-1", "temporary-hall-2"})


def temporary_hall_description(
    base_description: str | None = None,
    exhibit_names: list[str] | None = None,
    *,
    exhibit_count: int | None = None,
) -> str:
    """Build the shared temporary-hall copy from currently active exhibits."""
    base = str(base_description or "").strip()
    names: list[str] = []
    seen: set[str] = set()
    for raw_name in exhibit_names or []:
        name = str(raw_name or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    count = max(int(exhibit_count or 0), len(names))
    if count <= 0:
        status = "当前暂无已发布展品信息。"
        return f"{base} {status}".strip()

    summary = f"当前已发布 {count} 件展品。"
    if names:
        summary += f" 当前展品包括：{'、'.join(names[:3])}。"
    return f"{base} {summary}".strip()

CANONICAL_HALL_SLUGS = frozenset(CANONICAL_HALLS)

HALL_ALIASES: dict[str, str] = {
    **{slug: slug for slug in CANONICAL_HALLS},
    "基本陈列展厅": "basic-exhibition-hall",
    "遗址保护大厅": "site-protection-hall",
    "临展厅一": "temporary-hall-1",
    "临展厅二": "temporary-hall-2",
    "半坡姑娘雕塑": "banpo-girl-sculpture",
    "史前工坊": "prehistoric-workshop",
    "教研中心": "education-center",
    "牡丹园": "peony-garden",
    "陶窑展厅": "kiln-hall",
}


def normalize_hall(value: str | None) -> str | None:
    """Return a canonical alias or preserve a well-formed imported slug."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    known = HALL_ALIASES.get(raw)
    if known:
        return known
    lowered = raw.lower()
    if len(lowered) <= 100 and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", lowered):
        return lowered
    return None


def normalize_halls(values: list[str] | None) -> list[str]:
    """Normalize a list while preserving order and removing duplicates."""
    if not values:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        slug = normalize_hall(item)
        if slug and slug not in seen:
            seen.add(slug)
            result.append(slug)
    return result


def is_canonical_hall(value: str | None) -> bool:
    slug = normalize_hall(value)
    return bool(slug and slug in CANONICAL_HALL_SLUGS)


def is_temporary_hall(value: str | None) -> bool:
    slug = normalize_hall(value)
    return bool(slug and slug in TEMPORARY_HALL_SLUGS)


def hall_display_name(value: str | None) -> str:
    slug = normalize_hall(value)
    if not slug:
        return ""
    return CANONICAL_HALLS.get(slug, str(value))
