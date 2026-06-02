#!/usr/bin/env python3
"""Clear test data and import real exhibits via frontend admin exhibit API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
DEFAULT_REFERENCE_FILE = "docs/reference/展品.md"


@dataclass(frozen=True)
class HallSpec:
    slug: str
    name: str
    floor: int
    description: str
    display_order: int


HALL_SPECS: dict[str, HallSpec] = {
    "civilization": HallSpec(
        slug="basic-exhibition-hall",
        name="基本陈列展厅",
        floor=1,
        description="以半坡遗址相关考古发现与研究成果为主线，系统展示半坡文化的生活形态、生产方式与社会结构。",
        display_order=10,
    ),
    "pottery": HallSpec(
        slug="basic-exhibition-hall",
        name="基本陈列展厅",
        floor=1,
        description="以半坡遗址相关考古发现与研究成果为主线，系统展示半坡文化的生活形态、生产方式与社会结构。",
        display_order=20,
    ),
    "archaeology": HallSpec(
        slug="site-protection-hall",
        name="遗址保护大厅",
        floor=1,
        description="强调边保护边展示，呈现墓葬、地面圆形房屋、烧制作坊、灶具灶台等关键遗存。",
        display_order=30,
    ),
    "kiln": HallSpec(
        slug="kiln-hall",
        name="陶窑展厅",
        floor=1,
        description="以陶器如何被制作出来为核心叙事，展示半坡时期制陶与烧制工艺。",
        display_order=40,
    ),
    "temporary_1": HallSpec(
        slug="temporary-hall-1",
        name="临展厅一",
        floor=1,
        description="承载策划性的短期或阶段性展览，具体主题和展品视当期安排而定。",
        display_order=90,
    ),
    "temporary_2": HallSpec(
        slug="temporary-hall-2",
        name="临展厅二",
        floor=1,
        description="与临展厅一共同负责轮换展出，具体内容需由馆方按当期展览更新。",
        display_order=100,
    ),
    "banpo_girl": HallSpec(
        slug="banpo-girl-sculpture",
        name="半坡姑娘雕塑",
        floor=1,
        description="以半坡姑娘为代表性形象进行艺术化再现，是观众合影点与文化符号。",
        display_order=60,
    ),
    "workshop": HallSpec(
        slug="prehistoric-workshop",
        name="史前工坊",
        floor=1,
        description="以工坊形式让观众参与史前生活相关体验，把考古知识转化为可参与的学习过程。",
        display_order=50,
    ),
    "education": HallSpec(
        slug="education-center",
        name="教研中心",
        floor=1,
        description="面向青少年和公众教育活动，组织课堂、研学和主题研究型活动。",
        display_order=80,
    ),
    "peony": HallSpec(
        slug="peony-garden",
        name="牡丹园",
        floor=1,
        description="以牡丹为核心的园林景观区域，兼具观赏与休闲功能。",
        display_order=85,
    ),
}

SECTION_MARKERS = {
    "《文明曙光里的火种》": "civilization",
    "《陶器上的灵与肉》": "pottery",
}

META_PREFIXES = (
    "前言",
    "结语",
    "请您继续",
    "（注：",
)

META_CONTAINS = (
    "展陈提示",
    "参观动线",
    "手工与生产工具分布",
    "建筑周期与修葺证据",
    "社会组织与群体行为的物质证据",
    "环境利用与农业证据",
)


def _http_request(
    base_url: str,
    method: str,
    path: str,
    token: str | None = None,
    payload: dict | None = None,
    query: dict | None = None,
) -> tuple[int, dict]:
    url = base_url.rstrip("/") + path
    if query:
        encoded_query = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        url = f"{url}?{encoded_query}"

    body = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url=url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            return response.status, json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(error_body) if error_body else {}
        except json.JSONDecodeError:
            parsed = {"detail": error_body}
        return exc.code, parsed


def login(base_url: str, email: str, password: str) -> str:
    status, body = _http_request(
        base_url,
        "POST",
        "/auth/login",
        payload={"email": email, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"登录失败 ({status}): {body}")
    token = body.get("access_token")
    if not token:
        raise RuntimeError("登录响应缺少 access_token")
    return token


def fetch_all(base_url: str, token: str, path: str, key: str, query: dict | None = None) -> list[dict]:
    query = dict(query or {})
    if "limit" not in query:
        query["limit"] = 100
    if "skip" not in query:
        query["skip"] = 0

    all_items: list[dict] = []
    while True:
        status, body = _http_request(base_url, "GET", path, token=token, query=query)
        if status != 200:
            raise RuntimeError(f"查询 {path} 失败 ({status}): {body}")

        data = body.get(key)
        if isinstance(data, list):
            page_items = data
        elif isinstance(body, list):
            page_items = body
        else:
            page_items = []

        all_items.extend(page_items)

        limit = int(query["limit"])
        if len(page_items) < limit:
            break
        query["skip"] = int(query["skip"]) + limit

    return all_items


def delete_all_exhibits(base_url: str, token: str) -> int:
    exhibits = fetch_all(base_url, token, "/admin/exhibits", "exhibits", query={"skip": 0, "limit": 100})
    deleted = 0
    for exhibit in exhibits:
        exhibit_id = exhibit["id"]
        status, _ = _http_request(base_url, "DELETE", f"/admin/exhibits/{exhibit_id}", token=token)
        if status in (200, 204):
            deleted += 1
    return deleted


def delete_all_documents(base_url: str, token: str) -> int:
    documents = fetch_all(base_url, token, "/admin/documents", "documents", query={"skip": 0, "limit": 100})
    deleted = 0
    for document in documents:
        doc_id = document["id"]
        status, _ = _http_request(base_url, "DELETE", f"/admin/documents/{doc_id}", token=token)
        if status in (200, 204):
            deleted += 1
    return deleted


def delete_all_halls(base_url: str, token: str) -> int:
    halls = fetch_all(base_url, token, "/admin/halls", "halls", query={"include_inactive": "true"})
    deleted = 0
    for hall in halls:
        slug = hall["slug"]
        status, _ = _http_request(base_url, "DELETE", f"/admin/halls/{slug}", token=token)
        if status in (200, 204):
            deleted += 1
    return deleted


def ensure_halls(base_url: str, token: str) -> None:
    seen_slugs: set[str] = set()
    for spec in HALL_SPECS.values():
        if spec.slug in seen_slugs:
            continue
        seen_slugs.add(spec.slug)
        payload = {
            "slug": spec.slug,
            "name": spec.name,
            "description": spec.description,
            "floor": spec.floor,
            "estimated_duration_minutes": 35,
            "display_order": spec.display_order,
            "is_active": True,
        }
        status, body = _http_request(base_url, "POST", "/admin/halls", token=token, payload=payload)
        if status not in (200, 201, 409):
            raise RuntimeError(f"创建展厅失败 {spec.slug} ({status}): {body}")


def normalize_heading(text: str) -> str:
    return text.strip().rstrip("\u3000").rstrip()


def is_heading(line: str) -> bool:
    if not line:
        return False
    if line.startswith("- "):
        return False
    if len(line) > 36:
        return False
    return True


def is_meta_heading(heading: str) -> bool:
    if heading.startswith(META_PREFIXES):
        return True
    if heading.startswith("《"):
        return True
    return any(item in heading for item in META_CONTAINS)


def classify_category(name: str) -> str:
    if any(k in name for k in ("墓", "葬", "瓮棺")):
        return "葬制遗迹"
    if any(k in name for k in ("陶", "彩陶", "石砚", "纹", "雕塑", "符号")):
        return "陶器与艺术"
    if any(k in name for k in ("房屋", "柱洞", "窖", "围沟", "窑", "灶", "小沟", "居所")):
        return "聚落遗迹"
    if any(k in name for k in ("农耕", "渔猎", "饲养", "工具", "饮食", "编织", "纺织")):
        return "生产生活"
    if any(k in name for k in ("半坡人", "生态环境")):
        return "社会与环境"
    return "综合陈列"


def classify_importance(name: str) -> int:
    key_items = {
        "人面网纹彩陶盆",
        "鹿纹彩陶盆",
        "小女孩墓（个别富葬实例）",
        "陶窑（横穴窑结构与窑温证据）",
    }
    if name in key_items:
        return 5
    if "之谜" in name or "彩陶" in name:
        return 4
    return 3


def parse_reference(reference_path: Path) -> list[dict]:
    if not reference_path.exists():
        raise FileNotFoundError(f"找不到参考文件: {reference_path}")

    lines = [normalize_heading(line) for line in reference_path.read_text(encoding="utf-8").splitlines()]

    section = "civilization"
    exhibits: list[dict] = []
    idx = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        marker_line = line.replace("----", "——")
        for marker, section_name in SECTION_MARKERS.items():
            if marker in marker_line:
                section = section_name
                break

        if line == "堆积层剖面与分层遗存":
            section = "archaeology"

        if line and is_heading(line):
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if next_line and not next_line.startswith("- ") and len(next_line) > 36:
                heading = line
                paragraph_lines: list[str] = []
                j = i + 1
                while j < len(lines) and lines[j]:
                    paragraph_lines.append(lines[j])
                    j += 1

                if not is_meta_heading(heading):
                    hall_spec = HALL_SPECS["kiln"] if "陶窑" in heading else HALL_SPECS[section]
                    exhibits.append(
                        {
                            "name": heading,
                            "description": "\n".join(paragraph_lines),
                            "location_x": 80 + (idx % 6) * 120,
                            "location_y": 100 + ((idx // 6) % 8) * 85,
                            "floor": hall_spec.floor,
                            "hall": hall_spec.slug,
                            "category": classify_category(heading),
                            "era": "新石器时代·仰韶文化",
                            "importance": classify_importance(heading),
                            "estimated_visit_time": 6 if section != "archaeology" else 8,
                            "document_id": None,
                        }
                    )
                    idx += 1

                i = j
                continue

        i += 1

    if not exhibits:
        raise RuntimeError("未从参考文件中解析出可导入展品")

    return exhibits


def import_exhibits(base_url: str, token: str, exhibits: list[dict]) -> tuple[int, int]:
    success = 0
    failed = 0
    for exhibit in exhibits:
        status, body = _http_request(base_url, "POST", "/admin/exhibits", token=token, payload=exhibit)
        if status in (200, 201):
            success += 1
        else:
            failed += 1
            print(f"[WARN] 导入失败: {exhibit['name']} ({status}) {body}")
    return success, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清空旧数据并导入 docs/reference/展品.md 中的真实展品")
    parser.add_argument("--base-url", default=os.getenv("MUSEAI_API_BASE", DEFAULT_BASE_URL), help="后端 API 根路径")
    parser.add_argument("--email", default=os.getenv("MUSEAI_ADMIN_EMAIL", "test@test.com"), help="管理员邮箱")
    parser.add_argument(
        "--password",
        default=os.getenv("MUSEAI_ADMIN_PASSWORD", "AdminPass123!"),
        help="管理员密码",
    )
    parser.add_argument(
        "--reference",
        default=DEFAULT_REFERENCE_FILE,
        help="真实展品参考文档路径",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    exhibits_to_import = parse_reference(Path(args.reference))

    token = login(args.base_url, args.email, args.password)

    deleted_exhibits = delete_all_exhibits(args.base_url, token)
    deleted_documents = delete_all_documents(args.base_url, token)
    deleted_halls = delete_all_halls(args.base_url, token)

    ensure_halls(args.base_url, token)

    success, failed = import_exhibits(args.base_url, token, exhibits_to_import)

    print("\n=== 导入结果 ===")
    print(f"已删除展品: {deleted_exhibits}")
    print(f"已删除文档: {deleted_documents}")
    print(f"已删除展厅: {deleted_halls}")
    print(f"计划导入展品: {len(exhibits_to_import)}")
    print(f"导入成功: {success}")
    print(f"导入失败: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
