"""Shared hall normalization for tour APIs.

Known Banpo aliases map to their canonical slugs. Well-formed imported slugs
are preserved so future museum datasets can add halls without code changes;
API boundaries remain responsible for checking that a slug exists and is active.
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

HALL_CONTRACT: list[dict] = [
    {
        "slug": "basic-exhibition-hall",
        "name": CANONICAL_HALLS["basic-exhibition-hall"],
        "description": None,
        "floor": 1,
        "estimated_duration_minutes": 25,
        "display_order": 10,
        "is_active": True,
    },
    {
        "slug": "site-protection-hall",
        "name": CANONICAL_HALLS["site-protection-hall"],
        "description": None,
        "floor": 1,
        "estimated_duration_minutes": 25,
        "display_order": 20,
        "is_active": True,
    },
    {
        "slug": "kiln-hall",
        "name": CANONICAL_HALLS["kiln-hall"],
        "description": None,
        "floor": 1,
        "estimated_duration_minutes": 18,
        "display_order": 30,
        "is_active": True,
    },
    {
        "slug": "prehistoric-workshop",
        "name": CANONICAL_HALLS["prehistoric-workshop"],
        "description": None,
        "floor": 2,
        "estimated_duration_minutes": 20,
        "display_order": 40,
        "is_active": True,
    },
    {
        "slug": "banpo-girl-sculpture",
        "name": CANONICAL_HALLS["banpo-girl-sculpture"],
        "description": None,
        "floor": 1,
        "estimated_duration_minutes": 8,
        "display_order": 50,
        "is_active": True,
    },
    {
        "slug": "education-center",
        "name": CANONICAL_HALLS["education-center"],
        "description": None,
        "floor": 2,
        "estimated_duration_minutes": 18,
        "display_order": 60,
        "is_active": True,
    },
    {
        "slug": "peony-garden",
        "name": CANONICAL_HALLS["peony-garden"],
        "description": None,
        "floor": 3,
        "estimated_duration_minutes": 10,
        "display_order": 70,
        "is_active": True,
    },
    {
        "slug": "temporary-hall-1",
        "name": CANONICAL_HALLS["temporary-hall-1"],
        "description": None,
        "floor": 3,
        "estimated_duration_minutes": 15,
        "display_order": 90,
        "is_active": True,
    },
    {
        "slug": "temporary-hall-2",
        "name": CANONICAL_HALLS["temporary-hall-2"],
        "description": None,
        "floor": 3,
        "estimated_duration_minutes": 15,
        "display_order": 100,
        "is_active": True,
    },
]

CANONICAL_HALL_SLUGS = set(CANONICAL_HALLS)

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


def canonical_hall_contract() -> list[dict]:
    return [dict(item) for item in HALL_CONTRACT]


def hall_display_name(value: str | None) -> str:
    slug = normalize_hall(value)
    if not slug:
        return ""
    return CANONICAL_HALLS.get(slug, str(value))
