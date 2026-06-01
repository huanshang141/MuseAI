"""Shared hall normalization for tour APIs.

Frontend displays Chinese names, but API/session/event/report contracts should
prefer stable backend slugs. Keep aliases here so old local storage and older
event rows remain readable.
"""

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

HALL_ALIASES: dict[str, str] = {
    **{slug: slug for slug in CANONICAL_HALLS},
    "basic": "basic-exhibition-hall",
    "site": "site-protection-hall",
    "temp1": "temporary-hall-1",
    "temp2": "temporary-hall-2",
    "banpoGirl": "banpo-girl-sculpture",
    "workshop": "prehistoric-workshop",
    "education": "education-center",
    "peony": "peony-garden",
    "kiln": "kiln-hall",
    "基本陈列展厅": "basic-exhibition-hall",
    "遗址保护大厅": "site-protection-hall",
    "临展厅一": "temporary-hall-1",
    "临展厅二": "temporary-hall-2",
    "半坡姑娘雕塑": "banpo-girl-sculpture",
    "史前工坊": "prehistoric-workshop",
    "教研中心": "education-center",
    "牡丹园": "peony-garden",
    "陶窑展厅": "kiln-hall",
    "relic-hall": "basic-exhibition-hall",
    "pottery-spirit-hall": "basic-exhibition-hall",
    "civilization-spark-hall": "basic-exhibition-hall",
    "site-hall": "site-protection-hall",
    "site-archaeology-hall": "site-protection-hall",
    "出土文物陈列区": "basic-exhibition-hall",
    "半坡聚落复原区": "site-protection-hall",
    "专题文化展区": "basic-exhibition-hall",
}


def normalize_hall(value: str | None) -> str | None:
    """Return canonical slug for known halls; preserve unknown values."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return HALL_ALIASES.get(raw, raw)


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


def hall_display_name(value: str | None) -> str:
    slug = normalize_hall(value)
    if not slug:
        return ""
    return CANONICAL_HALLS.get(slug, str(value))
