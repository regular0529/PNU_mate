"""Board Watcher — 여러 부산대 게시판 새 글 감시 CLI.

Usage:
    python board_watcher.py
"""
import datetime
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from deadlines import get_upcoming

load_dotenv(Path(__file__).parent / ".env")

CATEGORY_KEYWORDS = {
    "장학금": ("장학금", "장학생"),
    "채용": ("채용", "인턴", "구인"),
    "공모전": ("공모전", "경진대회", "해커톤", "챌린지"),
}
DEADLINE_PATTERN = re.compile(r"~\s*\d{1,2}\s*/\s*\d{1,2}")
DEADLINE_DATE_PATTERN = re.compile(r"~\s*(\d{1,2})\s*/\s*(\d{1,2})")


def parse_title_deadline(title: str, today: datetime.date | None = None) -> datetime.date | None:
    """제목의 "(~M/D)" 패턴에서 마감일을 뽑아냄. 연도 미표기라 올해로 가정하고,
    250일 넘게 과거로 나오면 해넘이(작년말 공지→내년초 마감)로 보고 내년으로 보정."""
    today = today or datetime.date.today()
    m = DEADLINE_DATE_PATTERN.search(title)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    try:
        d = datetime.date(today.year, month, day)
    except ValueError:
        return None
    if (today - d).days > 250:
        try:
            d = datetime.date(today.year + 1, month, day)
        except ValueError:
            pass
    return d


def categorize_title(title: str, today: datetime.date | None = None) -> list[str]:
    today = today or datetime.date.today()
    tags = [tag for tag, keywords in CATEGORY_KEYWORDS.items() if any(k in title for k in keywords)]
    deadline = parse_title_deadline(title, today)
    if deadline is not None:
        tags.append("마감됨" if deadline < today else "마감임박")
    elif "마감" in title:
        tags.append("마감임박")
    return tags


STATE_FILE = Path(__file__).parent / "board_state.json"
DASHBOARD_FILE = Path(__file__).parent / "dashboard.html"
LOG_FILE = Path(__file__).parent / "board_watcher.log"
MANUAL_REPORTS_FILE = Path(__file__).parent / "manual_reports.json"


def load_manual_reports() -> list[dict]:
    if MANUAL_REPORTS_FILE.exists():
        return json.loads(MANUAL_REPORTS_FILE.read_text(encoding="utf-8"))
    return []


def add_manual_report(title: str, body: str) -> None:
    reports = load_manual_reports()
    reports.insert(0, {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": title,
        "body": body,
    })
    MANUAL_REPORTS_FILE.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")


def log(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode(sys.stdout.encoding or "ascii", errors="replace").decode(sys.stdout.encoding or "ascii"))
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# ("rss", url) 게시판은 RSS 2.0 피드로, ("html", url) 게시판은 페이지 파싱으로 확인.
# RSS가 HTML 파싱보다 구조 변경에 훨씬 덜 취약해서 있는 곳은 전부 RSS 사용.
# ponytail: URL이 완전히 바뀌면(사이트 개편) 여기서 수동 교체 필요 — 실패 시 ⚠ 에러로 알려주므로
# 놓치진 않음. URL 자동 재탐색은 오탐 위험이 커서 보류, 수동 교체가 반복적으로 귀찮아지면 추가.
BOARDS = {
    "산업공학과": ("rss", "https://ie.pusan.ac.kr/bbs/ie/182/rssList.do?row=50"),
    "교양교육원": ("rss", "https://culedu.pusan.ac.kr/bbs/culedu/1827/rssList.do?row=50"),
    "PICEE": ("rss", "https://picee.pusan.ac.kr/bbs/picee/9933/rssList.do?row=50"),
    "AI융합교육원": ("rss", "https://swedu.pusan.ac.kr/bbs/swedu/2265/rssList.do?row=50"),
    "부산대 공지사항": ("html", "https://www.pusan.ac.kr/kor/CMS/Board/Board.do?mCode=MN095"),
    "취업지원센터 공지": ("html", "https://job.pusan.ac.kr/ko/notice"),
}

# html 게시판 중 목록이 &page=N 페이지네이션을 지원하는 곳만 여러 페이지를 이어붙임 (게시판 이름 -> 추가로 더 가져올 페이지 수)
MULTI_PAGE_BOARDS = {"부산대 공지사항": 3}

# (게시판 플랫폼별 상세보기 링크 패턴, 순서대로 시도해서 먼저 매치되는 걸 사용)
LINK_PATTERNS = [
    re.compile(r"artclView\.do"),
    re.compile(r"mode=view.*board_seq="),
    re.compile(r"/notice/notice/view/\d+"),
]


def fetch_html(url: str, retries: int = 3, timeout: int = 10) -> str:
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_error = e
            time.sleep(1)
    raise ConnectionError(f"{url} 접속 실패 ({retries}회 재시도): {last_error}")


def extract_posts(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    for pattern in LINK_PATTERNS:
        links = [a for a in soup.find_all("a", href=True) if pattern.search(a["href"])]
        if links:
            posts = []
            seen_urls = set()
            for a in links:
                title = a.get_text(strip=True)
                url = urljoin(base_url, a["href"])
                if title and url not in seen_urls:
                    posts.append((title, url))
                    seen_urls.add(url)
            return posts
    return []


def extract_rss_posts(xml_text: str, base_url: str) -> list[tuple[str, str]]:
    root = ET.fromstring(xml_text)
    posts = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title and link:
            posts.append((title, urljoin(base_url, link)))
    return posts


def extract_rss_previews(xml_text: str, base_url: str, max_len: int = 160) -> dict[str, str]:
    root = ET.fromstring(xml_text)
    previews = {}
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        desc = " ".join((item.findtext("description") or "").split())
        if link and desc:
            url = urljoin(base_url, link)
            previews[url] = desc if len(desc) <= max_len else desc[:max_len].rstrip() + "…"
    return previews


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def check_boards(boards: dict[str, tuple[str, str]] = BOARDS) -> dict[str, dict]:
    state = load_state()
    results = {}
    for name, (kind, url) in boards.items():
        try:
            body = fetch_html(url)
            posts = extract_rss_posts(body, url) if kind == "rss" else extract_posts(body, url)
            if kind == "html" and name in MULTI_PAGE_BOARDS:
                seen_urls = {p[1] for p in posts}
                sep = "&" if "?" in url else "?"
                for page_no in range(2, MULTI_PAGE_BOARDS[name] + 1):
                    try:
                        more_body = fetch_html(f"{url}{sep}page={page_no}")
                    except ConnectionError as e:
                        log(f"⚠ [{name}] {page_no}페이지 추가 로드 실패 (1페이지 결과는 유지): {e}")
                        break
                    for post in extract_posts(more_body, url):
                        if post[1] not in seen_urls:
                            posts.append(post)
                            seen_urls.add(post[1])
        except (ConnectionError, ET.ParseError) as e:
            results[name] = {"error": str(e)}
            continue
        if not posts:
            results[name] = {"error": "글 목록을 찾지 못함 (사이트 구조가 바뀌었을 수 있음, 수동 확인 필요)"}
            continue
        seen = set(state.get(name, []))
        new_posts = [p for p in posts if p[1] not in seen]
        previews = extract_rss_previews(body, url) if kind == "rss" else {}
        results[name] = {"new": new_posts, "posts": posts, "previews": previews}
        state[name] = [p[1] for p in posts]
    save_state(state)
    return results


def build_notification_text(results: dict[str, dict]) -> str:
    lines = []
    for name, result in results.items():
        if result.get("new"):
            for title, url in result["new"]:
                lines.append(f"[{name}] {title}\n{url}")
    return "\n\n".join(lines)


def build_deadlines_html(deadlines: list[tuple]) -> str:
    if not deadlines:
        return ""
    today = datetime.date.today()

    def d_text_of(d):
        n = (d - today).days
        return "D-DAY" if n == 0 else f"D-{n}"

    nearest_d, nearest_cat, nearest_label = deadlines[0]
    rest = deadlines[1:]

    rest_rows = "".join(
        f'<li><span class="deadline-date font-mono">{d.strftime("%m/%d")}</span>'
        f'<span class="pill cat-{html.escape(category)}">{html.escape(category)}</span>'
        f'<span class="deadline-label">{html.escape(label)}</span>'
        f'<span class="deadline-dday font-mono">{d_text_of(d)}</span></li>'
        for d, category, label in rest
    )

    return f"""
<section class="hero">
  <div class="hero-seal" aria-hidden="true"><span>PNU<br>공지</span></div>
  <div class="hero-head">
    <span class="hero-eyebrow">다가오는 일정 · {len(deadlines)}건</span>
  </div>
  <div class="hero-next">
    <span class="hero-dday font-mono">{d_text_of(nearest_d)}</span>
    <div class="hero-next-info">
      <div class="hero-next-row">
        <span class="pill cat-{html.escape(nearest_cat)}">{html.escape(nearest_cat)}</span>
        <span class="hero-next-label">{html.escape(nearest_label)}</span>
      </div>
      <span class="hero-next-date font-mono">{nearest_d.strftime("%Y.%m.%d")}</span>
    </div>
  </div>
  {f'<ul class="hero-list">{rest_rows}</ul>' if rest_rows else ""}
</section>"""


def build_manual_reports_html(reports: list[dict]) -> str:
    if not reports:
        return ""
    cards = "".join(
        f"""
<div class="report-card">
  <div class="report-head"><span class="report-date font-mono">{html.escape(r["date"])}</span><span class="report-title">{html.escape(r["title"])}</span></div>
  <div class="report-body">{html.escape(r["body"])}</div>
</div>"""
        for r in reports
    )
    return f"""
<section class="panel panel-reports">
  <header class="panel-head"><h2>수동 리포트</h2><span class="pill">{len(reports)}건</span></header>
  {cards}
</section>"""


def generate_dashboard_html(
    results: dict[str, dict],
    summary: str | None = None,
    deadlines: list[tuple] | None = None,
    manual_reports: list[dict] | None = None,
) -> str:
    if deadlines is None:
        deadlines = get_upcoming()
    if manual_reports is None:
        manual_reports = load_manual_reports()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_new = sum(len(r["new"]) for r in results.values() if "new" in r)
    ok_count = sum(1 for r in results.values() if "new" in r)
    error_count = sum(1 for r in results.values() if "error" in r)

    panels = []
    for name, result in results.items():
        board_title = html.escape(name)
        if "error" in result:
            panels.append(f"""
<section class="panel panel-error" draggable="true" data-board="{board_title}">
  <header class="panel-head"><span class="drag-handle" aria-hidden="true">⠿</span><h2>{board_title}</h2><span class="pill pill-error">ERR</span></header>
  <p class="error-msg">⚠ {html.escape(result["error"])}</p>
</section>""")
            continue

        new_urls = {url for _, url in result["new"]}
        previews = result.get("previews", {})
        rows = []
        for post_title, url in result["posts"][:20]:
            is_new = url in new_urls
            badge = '<span class="new">NEW</span>' if is_new else ""
            tags = categorize_title(post_title)
            is_expired = "마감됨" in tags
            tag_pills = "".join(f'<span class="tag tag-{t}">{t}</span>' for t in tags)
            preview = previews.get(url, "")
            preview_attr = f' data-preview="{html.escape(preview)}"' if preview else ""
            deadline = parse_title_deadline(post_title)
            deadline_attr = f' data-deadline="{deadline.isoformat()}"' if deadline else ""
            url_esc = html.escape(url)
            row_class = " ".join(c for c in ["is-new" if is_new else "", "is-expired" if is_expired else ""] if c)
            rows.append(
                f'<li class="{row_class}" data-tags="{",".join(tags)}" data-board="{board_title}" '
                f'data-search="{html.escape(post_title.lower())}" data-url="{url_esc}"{preview_attr}{deadline_attr}>'
                f'<button type="button" class="star-btn" data-url="{url_esc}" aria-label="즐겨찾기">☆</button>'
                f'<button type="button" class="apply-btn" data-url="{url_esc}" aria-label="신청완료 표시">✓</button>'
                f'<input type="color" class="hl-color" data-url="{url_esc}" value="#fbbf24" aria-label="강조 색상">'
                f'{tag_pills}'
                f'<a href="{url_esc}" target="_blank" rel="noopener">{html.escape(post_title)}</a>{badge}</li>'
            )
        new_count = len(result["new"])
        count_pill = f'<span class="pill pill-new">새 글 {new_count}</span>' if new_count else f'<span class="pill">{len(result["posts"])}건</span>'
        panels.append(f"""
<section class="panel" draggable="true" data-board="{board_title}">
  <header class="panel-head"><span class="drag-handle" aria-hidden="true">⠿</span><h2>{board_title}</h2>{count_pill}</header>
  <ul>{"".join(rows)}</ul>
</section>""")

    deadlines_html = build_deadlines_html(deadlines)

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PNU Board Watch</title>
<style>
:root {{
  --bg: #f7f9fc;
  --panel: #ffffff;
  --panel-2: #eef3f8;
  --panel-border: #dbe4ec;
  --brand: #005baa;
  --brand-dim: #b8d4ec;
  --brand-soft: rgba(0,91,170,0.06);
  --text: #17212b;
  --text-dim: #5b6b7c;
  --text-faint: #94a3b3;
  --red: #dc2626;
  --red-dim: #fecaca;
  --green: #00A651;
  --star: #f59e0b;
  --blue: #0891b2;
  --purple: #9333ea;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
  padding: clamp(1rem, 2.5vw, 2.5rem);
}}
a {{ color: inherit; }}
:focus-visible {{ outline: 2px solid var(--brand); outline-offset: 2px; }}
.font-mono {{ font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace; }}
header.top {{
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 1.25rem;
  padding-bottom: 0.9rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--panel-border);
}}
.brand {{
  font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace;
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--brand);
  display: flex;
  align-items: center;
  gap: 0.55rem;
}}
.brand .unit {{
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #fff;
  background: var(--brand);
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
}}
.live-dot {{
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--brand);
  animation: pulse 2s ease-in-out infinite;
}}
.timestamp {{ color: var(--text-faint); font-size: 0.8rem; }}
.stats {{ display: flex; gap: 1.25rem; margin-left: auto; }}
.stat {{ text-align: right; }}
.stat .num {{
  font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace;
  font-variant-numeric: tabular-nums;
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-dim);
  display: block;
  line-height: 1;
}}
.stat-new .num {{ color: var(--brand); }}
.stat-error .num {{ color: var(--red); }}
.stat .label {{ color: var(--text-faint); font-size: 0.65rem; letter-spacing: 0.05em; }}

/* 히어로: 가장 임박한 일정 — 대학 공문서의 관인(직인) + 전광판 숫자를 결합 */
.hero {{
  position: relative;
  border: 1.5px solid var(--brand);
  background: linear-gradient(180deg, var(--brand-soft), transparent 60%);
  border-radius: 4px;
  padding: 1.2rem 5.5rem 1rem 1.4rem;
  margin: 0.3rem 0 1.5rem;
  box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}}
.hero-seal {{
  position: absolute;
  top: 1.1rem; right: 1.4rem;
  width: 3.6rem; height: 3.6rem;
  border: 2px solid var(--brand);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transform: rotate(-8deg);
  opacity: 0.85;
}}
.hero-seal span {{
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: var(--brand);
  text-align: center;
  line-height: 1.15;
  font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace;
}}
@media (max-width: 560px) {{ .hero {{ padding-right: 1.4rem; }} .hero-seal {{ display: none; }} }}
.hero-eyebrow {{
  font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace;
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  color: var(--brand);
  font-weight: 700;
}}
.hero-eyebrow::before {{ content: "공지 · "; color: var(--text-faint); font-weight: 400; }}
.hero-next {{
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.5rem;
  flex-wrap: wrap;
}}
.hero-dday {{
  font-size: clamp(2rem, 6vw, 2.75rem);
  font-weight: 700;
  color: var(--brand);
  line-height: 1;
  position: relative;
}}
.hero-dday::after {{
  content: "";
  position: absolute;
  left: -0.4rem; right: -0.4rem; top: 50%;
  border-top: 1px solid rgba(0,91,170,0.2);
}}
.hero-next-info {{ display: flex; flex-direction: column; gap: 0.35rem; }}
.hero-next-row {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }}
.hero-next-label {{ font-size: 1.05rem; font-weight: 600; }}
.hero-next-date {{ font-size: 0.75rem; color: var(--text-faint); }}
.hero-list {{
  list-style: none; margin: 0.75rem 0 0; padding-top: 0.6rem;
  border-top: 1px solid var(--panel-border);
  display: flex; flex-direction: column;
}}
.hero-list li {{
  display: flex; align-items: baseline; gap: 0.6rem;
  padding: 0.35rem 0; font-size: 0.85rem; color: var(--text-dim);
}}
.deadline-date {{ flex: none; color: var(--text-faint); font-size: 0.78rem; }}
.deadline-label {{ flex: 1; color: var(--text); }}
.deadline-dday {{ flex: none; color: var(--text-faint); font-size: 0.75rem; }}

.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}}
.panel {{
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 1rem;
  box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}}
.panel.dragging {{ opacity: 0.4; }}
.panel-error {{ border-color: var(--red-dim); }}
.panel-head {{
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--panel-border);
}}
.drag-handle {{
  flex: none;
  cursor: grab;
  color: var(--text-faint);
  font-size: 0.9rem;
  line-height: 1;
}}
.drag-handle:active {{ cursor: grabbing; }}
.panel-head h2 {{
  flex: 1;
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--text);
}}
.pill {{
  font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace;
  font-size: 0.68rem;
  color: var(--text-dim);
  background: rgba(0,0,0,0.045);
  border-radius: 3px;
  padding: 0.1rem 0.4rem;
  flex: none;
}}
.pill-error {{ color: var(--red); background: rgba(255,90,95,0.1); }}
.pill-new {{ color: var(--brand); background: var(--brand-soft); font-weight: 700; }}
.pill.cat-장학금 {{ color: var(--green); background: rgba(0,166,81,0.1); }}
.pill.cat-채용 {{ color: var(--blue); background: rgba(8,145,178,0.1); }}
.pill.cat-공모전 {{ color: var(--purple); background: rgba(147,51,234,0.1); }}
.pill.cat-학사 {{ color: var(--text-dim); }}
.pill.cat-등록금, .pill.cat-졸업, .pill.cat-입시 {{ color: var(--text-dim); }}
.error-msg {{ color: var(--red); font-size: 0.85rem; margin: 0; }}
.panel ul {{ list-style: none; margin: 0; padding: 0; }}
.panel li {{
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.35rem 0.5rem;
  padding: 0.55rem 0.6rem 0.55rem 0.6rem;
  margin: 0 -0.6rem;
  border-top: 1px solid var(--panel-border);
  border-left: 3px solid transparent;
  border-radius: 4px;
  font-size: 0.92rem;
  line-height: 1.4;
}}
.panel li.hidden {{ display: none; }}
.panel li:first-child {{ border-top: none; }}
.panel li.is-new {{
  border-left-color: var(--brand);
  background: var(--brand-soft);
}}
.tag {{
  flex: none;
  font-size: 0.68rem;
  padding: 0.08rem 0.45rem;
  border-radius: 999px;
  font-weight: 600;
  border: 1px solid currentColor;
}}
.tag-장학금 {{ color: var(--green); }}
.tag-채용 {{ color: var(--blue); }}
.tag-공모전 {{ color: var(--purple); }}
.tag-마감임박 {{ color: var(--red); }}
.tag-마감됨 {{ color: var(--text-faint); }}
.panel li.is-expired {{ opacity: 0.55; }}
.panel li.is-expired a {{ text-decoration: line-through; }}
.panel a {{
  color: var(--text-dim);
  text-decoration: none;
  flex: 1 1 200px;
  min-width: 0;
}}
.is-new a {{ color: var(--text); font-weight: 700; }}
.panel a:visited {{ color: var(--text-faint); }}
.panel a:hover {{ color: var(--brand); text-decoration: underline; }}
.new {{
  flex: none;
  font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace;
  font-size: 0.65rem;
  color: #fff;
  background: var(--brand);
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-weight: 700;
  letter-spacing: 0.03em;
}}
@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}
@media (prefers-reduced-motion: reduce) {{ .live-dot {{ animation: none; }} }}
.summary {{
  border: 1px solid var(--brand-dim);
  background: var(--brand-soft);
  border-radius: 8px;
  padding: 0.9rem 1rem;
  margin-bottom: 1.25rem;
  font-size: 0.9rem;
  line-height: 1.6;
  white-space: pre-line;
}}
.summary .summary-label {{
  font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace;
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  color: var(--brand);
  display: block;
  margin-bottom: 0.4rem;
}}
.filter-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: center;
  margin-bottom: 1.1rem;
}}
#search {{
  background: var(--panel);
  border: 1px solid var(--panel-border);
  color: var(--text);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  min-width: 200px;
  flex: 1 1 200px;
}}
#search::placeholder {{ color: var(--text-faint); }}
.filter-tags {{ display: flex; flex-wrap: wrap; gap: 0.4rem; }}
.filter-btn {{
  background: var(--panel);
  border: 1px solid var(--panel-border);
  color: var(--text-dim);
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font-size: 0.8rem;
  cursor: pointer;
}}
.filter-btn:hover {{ color: var(--text); }}
.filter-btn.active {{ background: var(--brand); color: #fff; border-color: var(--brand); font-weight: 600; }}
.panel-reports {{ grid-column: 1 / -1; margin-bottom: 1rem; }}
.report-card {{ padding: 0.7rem 0; border-top: 1px solid var(--panel-border); }}
.report-card:first-of-type {{ border-top: none; }}
.report-head {{ display: flex; align-items: baseline; gap: 0.6rem; margin-bottom: 0.3rem; }}
.report-date {{ color: var(--text-faint); font-size: 0.75rem; flex: none; }}
.report-title {{ font-weight: 700; font-size: 0.92rem; }}
.report-body {{ color: var(--text-dim); font-size: 0.88rem; line-height: 1.6; white-space: pre-line; }}
.star-btn {{
  flex: none;
  background: none;
  border: none;
  color: var(--text-faint);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.1rem;
}}
.star-btn:hover {{ color: var(--star); }}
.star-btn.starred {{ color: var(--star); }}
.apply-btn {{
  flex: none;
  background: none;
  border: 1px solid var(--panel-border);
  border-radius: 4px;
  color: var(--text-faint);
  font-size: 0.7rem;
  line-height: 1;
  width: 18px; height: 18px;
  cursor: pointer;
}}
.apply-btn:hover {{ border-color: var(--green); color: var(--green); }}
.apply-btn.applied {{ background: var(--green); border-color: var(--green); color: #fff; }}
.panel-applied .applied-empty {{ color: var(--text-faint); font-size: 0.85rem; margin: 0; }}
.panel-applied ul {{ list-style: none; margin: 0; padding: 0; }}
.panel-applied li {{
  display: flex; align-items: baseline; gap: 0.6rem;
  padding: 0.4rem 0; border-top: 1px solid var(--panel-border); font-size: 0.88rem;
}}
.panel-applied li:first-child {{ border-top: none; }}
.applied-dday {{ flex: none; color: var(--brand); font-family: ui-monospace, "Cascadia Code", "SFMono-Regular", Consolas, monospace; font-size: 0.8rem; }}
.applied-board {{ flex: none; color: var(--text-faint); font-size: 0.75rem; }}
.applied-title {{ flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.hl-color {{
  flex: none;
  width: 16px; height: 16px;
  padding: 0;
  border: 1px solid var(--panel-border);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  opacity: 0.45;
}}
.hl-color:hover {{ opacity: 1; }}
.panel li.is-highlighted {{
  background: var(--hl-bg, transparent);
  border-left-color: var(--hl-color, var(--star));
  border-radius: 4px;
}}
.preview-tip {{
  position: fixed;
  z-index: 20;
  max-width: 320px;
  background: var(--panel-2);
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  padding: 0.6rem 0.75rem;
  font-size: 0.82rem;
  line-height: 1.5;
  color: var(--text-dim);
  box-shadow: 0 8px 24px rgba(16,24,40,0.12);
  pointer-events: none;
  display: none;
}}
.preview-tip.visible {{ display: block; }}
</style></head>
<body>
<header class="top">
  <div class="brand"><span class="live-dot"></span>PNU MATE<span class="unit">WATCH</span></div>
  <span class="timestamp">마지막 확인 {now}</span>
  <div class="stats">
    <div class="stat stat-new"><span class="num">{total_new}</span><span class="label">새 글</span></div>
    <div class="stat"><span class="num">{ok_count}</span><span class="label">정상</span></div>
    <div class="stat stat-error"><span class="num">{error_count}</span><span class="label">오류</span></div>
  </div>
</header>
{deadlines_html}
{f'<div class="summary"><span class="summary-label">오늘의 요약</span>{html.escape(summary)}</div>' if summary else ""}
<div class="filter-bar">
  <input type="text" id="search" placeholder="제목 검색..." autocomplete="off">
  <div class="filter-tags" id="filterTags">
    <button class="filter-btn active" data-tag="">전체</button>
    <button class="filter-btn" data-tag="장학금">장학금</button>
    <button class="filter-btn" data-tag="채용">채용</button>
    <button class="filter-btn" data-tag="공모전">공모전</button>
    <button class="filter-btn" data-tag="마감임박">마감임박</button>
    <button class="filter-btn" id="favBtn" data-fav="1">☆ 즐겨찾기만</button>
  </div>
</div>
{build_manual_reports_html(manual_reports)}
<section class="panel panel-applied" id="appliedPanel">
  <header class="panel-head"><h2>내 신청 현황</h2><span class="pill" id="appliedCount">0건</span></header>
  <p class="applied-empty" id="appliedEmpty">아직 "신청완료" 표시한 글이 없습니다 — 게시글의 ✓ 버튼을 눌러 추가하세요.</p>
  <ul id="appliedList"></ul>
</section>
<div class="grid">{"".join(panels)}</div>
<div class="preview-tip" id="previewTip"></div>
<script>
(function() {{
  var STORAGE_KEY = 'pnuMateStarred';
  var search = document.getElementById('search');
  var buttons = document.querySelectorAll('.filter-tags .filter-btn:not(#favBtn)');
  var favBtn = document.getElementById('favBtn');
  var tip = document.getElementById('previewTip');
  var activeTag = '';
  var favOnly = false;

  function loadState() {{
    try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}'); }} catch (e) {{ return {{}}; }}
  }}
  function saveState(state) {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }}

  var state = loadState();

  function applyRowStyle(li) {{
    var url = li.dataset.url;
    var entry = state[url];
    var starBtn = li.querySelector('.star-btn');
    var applyBtn = li.querySelector('.apply-btn');
    var colorInput = li.querySelector('.hl-color');
    var starred = !!(entry && entry.starred);
    var applied = !!(entry && entry.applied);
    var color = (entry && entry.color) || null;
    if (starBtn) {{
      starBtn.textContent = starred ? '★' : '☆';
      starBtn.classList.toggle('starred', starred);
    }}
    if (applyBtn) applyBtn.classList.toggle('applied', applied);
    if (color && colorInput) colorInput.value = color;
    li.classList.toggle('is-highlighted', !!color);
    if (color) {{
      li.style.setProperty('--hl-color', color);
      li.style.setProperty('--hl-bg', color + '1a');
    }}
  }}

  function renderAppliedList() {{
    var listEl = document.getElementById('appliedList');
    var emptyEl = document.getElementById('appliedEmpty');
    var countEl = document.getElementById('appliedCount');
    var items = [];
    document.querySelectorAll('.panel li[data-url]').forEach(function(li) {{
      var entry = state[li.dataset.url];
      if (!entry || !entry.applied) return;
      var link = li.querySelector('a');
      items.push({{
        url: li.dataset.url,
        title: link ? link.textContent : li.dataset.url,
        deadline: li.dataset.deadline || null,
        board: li.dataset.board || '',
      }});
    }});
    items.sort(function(a, b) {{
      if (!a.deadline) return 1;
      if (!b.deadline) return -1;
      return a.deadline.localeCompare(b.deadline);
    }});
    countEl.textContent = items.length + '건';
    emptyEl.style.display = items.length ? 'none' : '';
    listEl.innerHTML = items.map(function(it) {{
      var today = new Date().toISOString().slice(0, 10);
      var dday = '';
      if (it.deadline) {{
        var diff = Math.round((new Date(it.deadline) - new Date(today)) / 86400000);
        dday = diff === 0 ? 'D-DAY' : (diff > 0 ? ('D-' + diff) : ('D+' + (-diff)));
      }}
      return '<li>' +
        '<span class="applied-dday">' + dday + '</span>' +
        '<span class="applied-board">' + it.board + '</span>' +
        '<a class="applied-title" href="' + it.url + '" target="_blank" rel="noopener">' + it.title + '</a>' +
        '</li>';
    }}).join('');
  }}

  document.querySelectorAll('.panel li[data-url]').forEach(applyRowStyle);
  renderAppliedList();

  document.querySelectorAll('.star-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      var url = btn.dataset.url;
      state[url] = state[url] || {{}};
      state[url].starred = !state[url].starred;
      saveState(state);
      applyRowStyle(btn.closest('li'));
      apply();
    }});
  }});

  document.querySelectorAll('.apply-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      var url = btn.dataset.url;
      state[url] = state[url] || {{}};
      state[url].applied = !state[url].applied;
      saveState(state);
      applyRowStyle(btn.closest('li'));
      renderAppliedList();
    }});
  }});

  document.querySelectorAll('.hl-color').forEach(function(input) {{
    input.addEventListener('input', function() {{
      var url = input.dataset.url;
      state[url] = state[url] || {{}};
      state[url].color = input.value;
      saveState(state);
      applyRowStyle(input.closest('li'));
    }});
  }});

  function apply() {{
    var q = search.value.trim().toLowerCase();
    document.querySelectorAll('.panel li[data-search]').forEach(function(li) {{
      var matchesText = !q || li.dataset.search.includes(q);
      var matchesTag = !activeTag || (li.dataset.tags || '').split(',').includes(activeTag);
      var entry = state[li.dataset.url];
      var matchesFav = !favOnly || (entry && entry.starred);
      li.classList.toggle('hidden', !(matchesText && matchesTag && matchesFav));
    }});
  }}

  search.addEventListener('input', apply);
  buttons.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      buttons.forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      activeTag = btn.dataset.tag;
      apply();
    }});
  }});
  favBtn.addEventListener('click', function() {{
    favOnly = !favOnly;
    favBtn.classList.toggle('active', favOnly);
    apply();
  }});

  document.querySelectorAll('.panel li[data-preview]').forEach(function(li) {{
    var link = li.querySelector('a');
    if (!link) return;
    link.addEventListener('mouseenter', function() {{
      tip.textContent = li.dataset.preview;
      tip.classList.add('visible');
    }});
    link.addEventListener('mousemove', function(e) {{
      var x = Math.min(e.clientX + 16, window.innerWidth - 336);
      var y = Math.min(e.clientY + 16, window.innerHeight - 100);
      tip.style.left = x + 'px';
      tip.style.top = y + 'px';
    }});
    link.addEventListener('mouseleave', function() {{ tip.classList.remove('visible'); }});
  }});

  // 게시판 순서 드래그 앤 드롭 (브라우저에 저장, 이 파일이 새로 생성돼도 유지됨)
  var ORDER_KEY = 'pnuMateBoardOrder';
  var grid = document.querySelector('.grid');
  var dragged = null;

  function applySavedOrder() {{
    var saved;
    try {{ saved = JSON.parse(localStorage.getItem(ORDER_KEY) || '[]'); }} catch (e) {{ saved = []; }}
    var byName = {{}};
    Array.from(grid.children).forEach(function(p) {{ byName[p.dataset.board] = p; }});
    saved.forEach(function(name) {{ if (byName[name]) grid.appendChild(byName[name]); }});
  }}

  function saveOrder() {{
    var order = Array.from(grid.children).map(function(p) {{ return p.dataset.board; }});
    localStorage.setItem(ORDER_KEY, JSON.stringify(order));
  }}

  applySavedOrder();

  Array.from(grid.children).forEach(function(panel) {{
    panel.addEventListener('dragstart', function() {{ dragged = panel; panel.classList.add('dragging'); }});
    panel.addEventListener('dragend', function() {{ panel.classList.remove('dragging'); saveOrder(); }});
    panel.addEventListener('dragover', function(e) {{ e.preventDefault(); }});
    panel.addEventListener('drop', function(e) {{
      e.preventDefault();
      if (dragged && dragged !== panel) grid.insertBefore(dragged, panel);
    }});
  }});
}})();
</script>
</body></html>"""


TELEGRAM_MAX_LEN = 4000  # 텔레그램 실제 한도는 4096자, 여유를 좀 둠


def chunk_message(text: str, max_len: int = TELEGRAM_MAX_LEN) -> list[str]:
    """항목(빈 줄로 구분) 단위를 안 끊고 max_len 이하 덩어리로 나눔."""
    entries = text.split("\n\n")
    chunks = []
    current = ""
    for entry in entries:
        candidate = f"{current}\n\n{entry}" if current else entry
        if len(candidate) > max_len and current:
            chunks.append(current)
            current = entry
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def send_telegram(bot_token: str, chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for chunk in chunk_message(message):
        resp = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=10)
        if not resp.ok:
            log(f"⚠ 텔레그램 발송 실패: {resp.status_code} {resp.text}")


def main():
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    log(f"\n=== {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    results = check_boards()
    for name, result in results.items():
        if "error" in result:
            log(f"⚠ [{name}] {result['error']}")
        elif result["new"]:
            log(f"📌 [{name}] 새 글 {len(result['new'])}건")
            for title, url in result["new"]:
                log(f"  - {title}\n    {url}")
        else:
            log(f"[{name}] 새 글 없음")

    DASHBOARD_FILE.write_text(generate_dashboard_html(results), encoding="utf-8")
    log(f"대시보드: {DASHBOARD_FILE}")

    notification_text = build_notification_text(results)
    if notification_text:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if bot_token and chat_id:
            send_telegram(bot_token, chat_id, notification_text)
        else:
            log("(TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 환경변수가 없어 폰 알림은 건너뜀)")


if __name__ == "__main__":
    main()
