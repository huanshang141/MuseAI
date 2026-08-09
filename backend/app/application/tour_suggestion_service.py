"""Deterministic, visitor-friendly suggestion questions for the mini-program."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

SUGGESTION_MIN_LENGTH = 8
SUGGESTION_PREFERRED_MAX_LENGTH = 16
SUGGESTION_MAX_LENGTH = 18

SUGGESTION_META_FRAGMENTS = (
    "测试数据",
    "这是一条测试",
    "真实数据",
    "馆方数据",
    "数据接入",
    "上线后",
    "后续上线",
    "如何替换",
    "怎么替换",
    "导入数据",
    "上传数据",
)
SUGGESTION_JARGON_FRAGMENTS = (
    "层位",
    "形制",
    "证据链",
    "对应关系",
    "可核对",
    "剖面",
    "夯实",
    "烧结",
    "差序",
    "同心磨痕",
    "判断型",
    "合理推断",
    "直接观察",
    "现场信息",
)
SUGGESTION_GENERIC_COPY = {
    "这里有哪些可以直接观察的证据",
    "哪些结论仍需要保留不确定性",
    "最值得记录的观察点是什么",
    "我可以怎样整理这段参观笔记",
    "这些材料反映了怎样的史前生活",
    "它与更大的历史问题有什么联系",
    "可以从哪些材料和制作痕迹观察",
    "这些细节可能对应什么用途",
    "这个展厅的核心主题是什么",
    "这里最值得看什么",
    "这个展厅讲什么",
}
SUGGESTION_VAGUE_PATTERNS = (
    r"^(?:眼前|这里|这些|这个|这件|这座|它)",
    r"^(?:为什么|怎么|怎样|如何|哪些|有什么|有何)",
    r".*(?:怎样|怎么|如何)理解",
    r".*(?:值得|应该).*(?:看|观察|记录).*什么",
    r".*(?:还有|接下来).*(?:问|了解)什么",
)

DESCRIPTION_ANCHORS = (
    ("人面鱼纹", "人面鱼纹"),
    ("刻划符号", "陶器刻痕"),
    ("碳化谷粒", "烧焦的谷粒"),
    ("炭化木椽", "烧黑的木椽"),
    ("颜料残留", "颜料痕迹"),
    ("墓葬区", "墓区"),
    ("陶窑区", "陶窑区"),
    ("居住区", "住屋区"),
    ("使用痕迹", "磨损"),
    ("随葬品", "随葬品"),
    ("谷壳层", "谷壳"),
    ("草泥层", "草泥墙"),
    ("柱洞", "柱洞"),
    ("壕沟", "壕沟"),
    ("火膛", "火膛"),
    ("窑室", "窑室"),
    ("窑箅", "窑床"),
    ("穿孔", "小孔"),
    ("倒刺", "倒刺"),
    ("磨痕", "磨痕"),
    ("耳孔", "耳孔"),
    ("尖底", "尖底"),
    ("小口", "小口"),
    ("网纹", "网纹"),
    ("席纹", "席纹"),
    ("鱼纹", "鱼纹"),
    ("鹿纹", "鹿纹"),
    ("骨骼", "骨头"),
    ("火道", "火道"),
    ("灶台", "灶台"),
    ("窖穴", "窖穴"),
    ("榫卯", "木头接头"),
    ("陶片", "陶片"),
    ("纺轮", "纺轮"),
)

SUBJECT_NOISE_PREFIXES = (
    "西安半坡博物馆",
    "新石器时代",
    "仰韶文化",
    "半坡文化",
    "半坡遗址",
    "馆藏",
    "出土",
)
SUBJECT_NOISE_SUFFIXES = (
    "复制品",
    "修复件",
    "复原件",
    "展品",
    "标本",
    "藏品",
    "之谜",
    "集萃",
)
SUBJECT_OBJECT_ENDINGS = (
    "人面鱼纹彩陶盆",
    "小口尖底瓶",
    "彩陶盆",
    "尖底瓶",
    "陶罐",
    "陶钵",
    "陶壶",
    "陶盆",
    "陶瓶",
    "石斧",
    "石刀",
    "骨针",
    "骨锥",
    "骨铲",
    "纺轮",
    "网坠",
    "鱼钩",
    "陶窑",
    "房址",
    "墓葬",
    "壕沟",
    "灶址",
    "遗址",
    "雕塑",
    "模型",
    "陶片",
    "骨器",
    "石器",
    "陶器",
    "器物",
    "工具",
)
SUBJECT_MODIFIER_TERMS = (
    "人面鱼纹",
    "兽面纹",
    "彩绘",
    "高足",
    "小口",
    "尖底",
    "陶质",
    "石质",
    "骨质",
    "磨制",
    "穿孔",
)
SITE_SUBJECT_MARKERS = (
    "房址",
    "墓葬",
    "遗址",
    "号墓",
    "灰坑",
    "窖穴",
    "壕沟",
    "柱洞",
    "灶址",
)
DISPLAY_SUBJECT_MARKERS = (
    "雕塑",
    "模型",
    "分布图",
    "平面图",
    "复原图",
    "示意图",
)
FRAGMENT_SUBJECT_MARKERS = ("残片", "碎片", "陶片", "骨片")
TOOL_OR_ARTIFACT_MARKERS = (
    "盆",
    "瓶",
    "罐",
    "钵",
    "壶",
    "斧",
    "刀",
    "针",
    "锥",
    "铲",
    "纺轮",
    "网坠",
    "鱼钩",
    "骨器",
    "石器",
    "陶器",
    "器物",
    "工具",
)
SUBJECT_NAME_NOISE_FRAGMENTS = (
    "测试",
    "占位",
    "待替换",
    "待补充",
    "临时数据",
    "示例",
    "样例",
    "模拟",
    "虚拟",
    "示例名称",
    "维护用",
    "数据接入",
)
SUBJECT_ASCII_NOISE_LABELS = ("demo", "test")
SUBJECT_PLACEHOLDER_LABELS = (
    "临时数据",
    "测试数据",
    "示例名称",
    "数据接入",
    "待替换",
    "待补充",
    "维护用",
    "测试",
    "占位",
    "示例",
    "样例",
    "模拟",
    "虚拟",
    "demo",
    "test",
)
STRONG_DETAIL_ANCHORS = {
    "人面鱼纹",
    "陶器刻痕",
    "烧焦的谷粒",
    "烧黑的木椽",
    "颜料痕迹",
    "磨损",
    "随葬品",
    "草泥墙",
    "小孔",
    "倒刺",
    "磨痕",
    "尖底",
    "小口",
    "网纹",
    "席纹",
    "鱼纹",
    "鹿纹",
    "榫卯",
    "陶片",
}


def normalize_suggestion(value: object) -> str:
    question = re.sub(r"\s+", " ", str(value or "")).strip()
    if question.endswith("?"):
        question = f"{question[:-1]}？"
    return question


def suggestion_rejection_reason(value: object) -> str | None:
    question = normalize_suggestion(value)
    normalized = question.rstrip("？?。！! ")
    if len(question) < SUGGESTION_MIN_LENGTH:
        return f"must contain at least {SUGGESTION_MIN_LENGTH} characters"
    if len(question) > SUGGESTION_MAX_LENGTH:
        return f"exceeds {SUGGESTION_MAX_LENGTH} characters"
    if not question.endswith("？"):
        return "must end with a question mark"
    if any(fragment in question for fragment in SUGGESTION_META_FRAGMENTS):
        return "contains maintenance or test-data wording"
    if any(fragment in question for fragment in SUGGESTION_JARGON_FRAGMENTS):
        return "contains unexplained specialist wording"
    if normalized in SUGGESTION_GENERIC_COPY:
        return "is a generic placeholder"
    if any(re.search(pattern, normalized) for pattern in SUGGESTION_VAGUE_PATTERNS):
        return "does not name a concrete exhibit or feature"
    return None


def is_meaningful_suggestion(value: object) -> bool:
    return suggestion_rejection_reason(value) is None


def quality_suggestions(values: object, *, limit: int = 6) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    suggestions: list[str] = []
    seen: set[str] = set()
    for value in values:
        question = normalize_suggestion(value)
        if not is_meaningful_suggestion(question) or question in seen:
            continue
        seen.add(question)
        suggestions.append(question)
        if len(suggestions) >= limit:
            break
    return suggestions


def _strip_subject_noise(value: str) -> str:
    subject = value.strip(" ，、。:：—–-·/|｜")
    changed = True
    while changed and subject:
        changed = False
        for prefix in SUBJECT_NOISE_PREFIXES:
            if subject.startswith(prefix):
                subject = subject[len(prefix) :]
                changed = True
        for suffix in SUBJECT_NOISE_SUFFIXES:
            if subject.endswith(suffix):
                subject = subject[: -len(suffix)]
                changed = True
        subject = subject.strip(" ，、。:：—–-·/|｜")
    return subject


def _bounded_name_subject(value: str) -> str:
    subject = _strip_subject_noise(value)
    subject = re.sub(r"^(?:这个|那个|这些|眼前|这里)", "", subject)
    for fragment in (*SUGGESTION_META_FRAGMENTS, *SUGGESTION_JARGON_FRAGMENTS):
        subject = subject.replace(fragment, "")
    subject = _strip_subject_noise(subject)
    if 2 <= len(subject) <= 8:
        return subject

    for ending in SUBJECT_OBJECT_ENDINGS:
        position = subject.rfind(ending)
        if position < 0:
            continue
        remaining = subject[:position]
        modifiers: list[str] = []
        available = 8 - len(ending)
        while available > 0:
            matches = [term for term in SUBJECT_MODIFIER_TERMS if len(term) <= available and remaining.endswith(term)]
            if not matches:
                break
            term = max(matches, key=len)
            modifiers.insert(0, term)
            remaining = remaining[: -len(term)]
            available -= len(term)
        candidate = f"{''.join(modifiers)}{ending}"
        if 2 <= len(candidate) <= 8:
            return candidate

    candidate = subject[-8:].lstrip("的之与和及")
    if 2 <= len(candidate) <= 8:
        return candidate
    return ""


def _extract_special_subject(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    tomb_fragment = re.search(
        r"(\d{1,4}号墓).{0,10}?(残片|碎片|陶片|骨片)", normalized
    )
    if tomb_fragment:
        return f"{tomb_fragment.group(1)}{tomb_fragment.group(2)}"
    if re.search(r"出土.{0,4}?(残片|碎片|陶片|骨片)", normalized):
        fragment = re.search(r"(残片|碎片|陶片|骨片)", normalized)
        if fragment:
            return f"出土{fragment.group(1)}"
    inventory = re.search(
        r"(?:馆藏)?编号[:：]?([A-Za-z]{1,8}(?:[-_:][A-Za-z0-9]+)+)",
        normalized,
        flags=re.IGNORECASE,
    )
    if inventory and len(inventory.group(1)) <= 14:
        return inventory.group(1)
    return ""


def _strip_standardized_placeholder_labels(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip()
    labels = "|".join(
        re.escape(label)
        for label in sorted(SUBJECT_PLACEHOLDER_LABELS, key=len, reverse=True)
    )
    bracketed = re.compile(
        rf"^\s*(?:【\s*(?:{labels})\s*】|"
        rf"\[\s*(?:{labels})\s*\]|"
        rf"\(\s*(?:{labels})\s*\))\s*",
        flags=re.IGNORECASE,
    )
    delimited = re.compile(
        rf"^\s*(?:{labels})\s*(?:[:：/_|｜·—–-]+|\s+)\s*",
        flags=re.IGNORECASE,
    )
    while normalized:
        stripped = bracketed.sub("", normalized, count=1)
        if stripped == normalized:
            stripped = delimited.sub("", normalized, count=1)
        if stripped == normalized:
            break
        normalized = stripped.strip()
    return normalized


def _has_subject_name_noise(value: str | None) -> bool:
    normalized = _strip_standardized_placeholder_labels(value)
    # A leading bracketed dataset label is presentation metadata and may be
    # removed. Noise remaining in the actual name must never become a question.
    normalized = re.sub(
        r"^(?:(?:【[^】]{1,40}】)|(?:\[[^\]]{1,40}\])|(?:\([^)]{1,40}\)))+",
        "",
        normalized,
    ).lower()
    if any(fragment in normalized for fragment in SUBJECT_NAME_NOISE_FRAGMENTS):
        return True
    return any(
        re.search(rf"(?<![a-z0-9]){label}(?![a-z0-9])", normalized)
        for label in SUBJECT_ASCII_NOISE_LABELS
    )


def _clean_subject(value: str | None, category: str | None = None) -> str:
    original = re.sub(
        r"\s+",
        "",
        _strip_standardized_placeholder_labels(value),
    )
    if special_subject := _extract_special_subject(original):
        return special_subject
    without_brackets = re.sub(
        r"(?:【[^】]{1,40}】|\[[^\]]{1,40}\])",
        "",
        original,
    )
    original = without_brackets or original.replace("【", "").replace("】", "")
    original = re.sub(r"[（(].*?[）)]", "", original).strip(" ，、。")
    parts = [part for part in re.split(r"[、，,:：/|｜·—–-]+", original) if _strip_subject_noise(part)]
    ranked_parts = sorted(
        enumerate(parts),
        key=lambda item: (
            -int(any(ending in item[1] for ending in SUBJECT_OBJECT_ENDINGS)),
            -int(2 <= len(_strip_subject_noise(item[1])) <= 8),
            item[0],
        ),
    )
    for _, part in ranked_parts:
        if subject := _bounded_name_subject(part):
            return subject

    category_value = _strip_standardized_placeholder_labels(category)
    if _has_subject_name_noise(category):
        category_value = ""
    category_text = _bounded_name_subject(re.sub(r"\s+", "", category_value))
    if 2 <= len(category_text) <= 6:
        return category_text
    return ""


def _description_anchors(description: str | None, *, limit: int = 3) -> list[str]:
    text = str(description or "")
    matches = sorted(
        (text.find(source), order, plain) for order, (source, plain) in enumerate(DESCRIPTION_ANCHORS) if source in text
    )
    anchors: list[str] = []
    for _, _, plain in matches:
        if plain not in anchors:
            anchors.append(plain)
        if len(anchors) >= limit:
            break
    return anchors


def _ordered_short_candidates(candidates: Sequence[str]) -> list[str]:
    accepted = quality_suggestions(list(candidates), limit=len(candidates))
    preferred = [question for question in accepted if len(question) <= SUGGESTION_PREFERRED_MAX_LENGTH]
    longer = [question for question in accepted if question not in preferred]
    return [*preferred, *longer]


def _anchor_question(anchor: str) -> str:
    if "刻痕" in anchor:
        return f"{anchor}记了什么？"
    if anchor.endswith(("纹", "花纹")):
        return f"{anchor}画的是什么？"
    if any(marker in anchor for marker in ("痕", "磨损", "谷粒", "木椽", "骨头", "陶片", "谷壳")):
        return f"{anchor}是怎么留下的？"
    return f"{anchor}主要有什么用？"


def _subject_questions(subject: str) -> list[str]:
    if any(marker in subject for marker in FRAGMENT_SUBJECT_MARKERS):
        return [f"{subject}具体是什么？", f"{subject}保留了什么？"]
    if any(marker in subject for marker in DISPLAY_SUBJECT_MARKERS):
        return [f"{subject}展示了什么？", f"{subject}表现了什么？"]
    if any(marker in subject for marker in SITE_SUBJECT_MARKERS):
        return [f"{subject}发现了什么？", f"{subject}能看出什么？"]
    if subject == "陶窑" or subject.endswith("陶窑"):
        return [f"{subject}怎样烧陶器？", f"{subject}结构怎么看？"]
    if any(subject.endswith(marker) for marker in TOOL_OR_ARTIFACT_MARKERS):
        return [f"{subject}当时怎么用？", f"{subject}是怎么做的？"]
    if re.fullmatch(r"[A-Za-z0-9]+(?:[-_:][A-Za-z0-9]+)+", subject):
        return [f"{subject}是什么？"]
    return [f"{subject}具体是什么？", f"{subject}能看出什么？"]


def derive_exhibit_suggestions(
    name: str | None,
    description: str | None,
    category: str | None = None,
) -> list[str]:
    """Build two short questions solely from trusted exhibit fields."""
    if _has_subject_name_noise(name):
        return []
    subject = _clean_subject(name, category)
    anchor_limit = 3 if subject else len(DESCRIPTION_ANCHORS)
    anchors = _description_anchors(description, limit=anchor_limit)
    subject_from_anchor = False
    if not subject:
        anchors = [
            anchor for anchor in anchors if anchor in STRONG_DETAIL_ANCHORS
        ][:3]
    if not subject and anchors:
        subject = anchors[0]
        subject_from_anchor = True
    if not subject:
        return []

    if subject_from_anchor:
        candidates = [_anchor_question(anchor) for anchor in anchors]
    else:
        subject_questions = _subject_questions(subject)
        candidates = [subject_questions[0]]
        candidates.extend(
            _anchor_question(anchor)
            for anchor in anchors
            if anchor in STRONG_DETAIL_ANCHORS
        )
        candidates.extend(subject_questions[1:])
    return _ordered_short_candidates(candidates)[:2]
