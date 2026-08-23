import datetime

import board_watcher
from board_watcher import (
    build_deadlines_html,
    build_manual_reports_html,
    build_notification_text,
    categorize_title,
    chunk_message,
    extract_posts,
    extract_rss_posts,
    extract_rss_previews,
    generate_dashboard_html,
)

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>RSS 게시판 2.0</title>
<item>
<title><![CDATA[ 공지 A ]]></title>
<link>/bbs/ie/182/1453306/artclView.do?layout=unknown</link>
<pubDate>2026-08-03 09:42:35.593</pubDate>
</item>
<item>
<title><![CDATA[ 공지 B ]]></title>
<link>/bbs/ie/182/1453089/artclView.do?layout=unknown</link>
<pubDate>2026-07-30 16:37:56.207</pubDate>
</item>
</channel>
</rss>"""

ARTCL_HTML = """
<table><tr><td><a href="/bbs/ie/182/1453306/artclView.do">공지 A</a></td></tr>
<tr><td><a href="/bbs/ie/182/1453089/artclView.do">공지 B</a></td></tr></table>
"""

JOB_NOTICE_HTML = """
<table><tr><td><a href="/ko/notice/notice/view/204166?p=1">CEP 집단상담 모집</a></td></tr></table>
"""

BOARD_DO_HTML = """
<table><tr><td><a href="?mCode=MN095&mode=view&mgr_seq=3&board_seq=1510419">국가장학금 안내</a></td></tr></table>
"""

NO_MATCH_HTML = "<html><body><nav><a href='/menu'>메뉴</a></nav></body></html>"


def test_artcl_pattern():
    posts = extract_posts(ARTCL_HTML, "https://ie.pusan.ac.kr/ie/5850/subview.do")
    assert len(posts) == 2
    assert posts[0][0] == "공지 A"
    assert posts[0][1] == "https://ie.pusan.ac.kr/bbs/ie/182/1453306/artclView.do"


def test_board_do_pattern():
    posts = extract_posts(BOARD_DO_HTML, "https://www.pusan.ac.kr/kor/CMS/Board/Board.do")
    assert len(posts) == 1
    assert posts[0][0] == "국가장학금 안내"
    assert "board_seq=1510419" in posts[0][1]


def test_job_notice_pattern():
    posts = extract_posts(JOB_NOTICE_HTML, "https://job.pusan.ac.kr/ko/notice")
    assert len(posts) == 1
    assert posts[0][0] == "CEP 집단상담 모집"
    assert posts[0][1] == "https://job.pusan.ac.kr/ko/notice/notice/view/204166?p=1"


def test_no_match_returns_empty():
    assert extract_posts(NO_MATCH_HTML, "https://example.com") == []


def test_rss_previews_extracted_and_truncated():
    xml = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title><![CDATA[ 공지 A ]]></title><link>/bbs/1/artclView.do</link>
<description><![CDATA[ 이것은 아주 긴 설명입니다. """ + ("내용 " * 60) + """ ]]></description></item>
<item><title><![CDATA[ 공지 B ]]></title><link>/bbs/2/artclView.do</link><description><![CDATA[  ]]></description></item>
</channel></rss>"""
    previews = extract_rss_previews(xml, "https://ie.pusan.ac.kr/", max_len=50)
    assert "https://ie.pusan.ac.kr/bbs/1/artclView.do" in previews
    assert len(previews["https://ie.pusan.ac.kr/bbs/1/artclView.do"]) <= 51
    assert "https://ie.pusan.ac.kr/bbs/2/artclView.do" not in previews  # empty description skipped


def test_rss_parsing():
    posts = extract_rss_posts(RSS_XML, "https://ie.pusan.ac.kr/")
    assert len(posts) == 2
    assert posts[0][0] == "공지 A"
    assert posts[0][1] == "https://ie.pusan.ac.kr/bbs/ie/182/1453306/artclView.do?layout=unknown"


def test_notification_text_includes_new_posts_only():
    results = {
        "산업공학과": {"new": [("공지 A", "https://x/1")]},
        "PICEE": {"new": []},
        "취업지원센터 공지": {"error": "접속 실패"},
    }
    text = build_notification_text(results)
    assert "공지 A" in text
    assert "https://x/1" in text
    assert "접속 실패" not in text


def test_notification_text_empty_when_no_new_posts():
    results = {"산업공학과": {"new": []}, "PICEE": {"error": "실패"}}
    assert build_notification_text(results) == ""


def test_dashboard_html_renders_summary():
    results = {"산업공학과": {"new": [], "posts": []}}
    out = generate_dashboard_html(results, summary="[장학금] 국가장학금 2차 마감 임박")
    assert "국가장학금 2차 마감 임박" in out
    out_no_summary = generate_dashboard_html(results)
    assert "오늘의 요약" not in out_no_summary


def test_deadlines_html_empty_when_no_items():
    assert build_deadlines_html([]) == ""


def test_deadlines_html_renders_dday_and_category():
    today = datetime.date.today()
    deadlines = [(today + datetime.timedelta(days=3), "장학금", "국가장학금 2차 신청")]
    out = build_deadlines_html(deadlines)
    assert "국가장학금 2차 신청" in out
    assert "장학금" in out
    assert "D-3" in out


def test_dashboard_html_includes_deadlines_panel():
    results = {"산업공학과": {"new": [], "posts": []}}
    today = datetime.date.today()
    deadlines = [(today, "학사", "개강")]
    out = generate_dashboard_html(results, deadlines=deadlines)
    assert "다가오는 일정" in out
    assert "D-DAY" in out


def test_dashboard_html_marks_new_and_errors():
    results = {
        "산업공학과": {"new": [("공지 A", "https://x/1")], "posts": [("공지 A", "https://x/1"), ("공지 B", "https://x/2")]},
        "취업지원센터 공지": {"error": "접속 실패"},
    }
    out = generate_dashboard_html(results)
    assert "공지 A" in out and "공지 B" in out
    assert "NEW" in out
    assert "접속 실패" in out


def test_categorize_title_matches_keywords():
    assert "장학금" in categorize_title("2026년 국가장학금 2차 신청 안내")
    assert "채용" in categorize_title("[삼성전기] 신입 채용 콘서트")
    assert "공모전" in categorize_title("AI 아이디어 공모전 개최")
    assert categorize_title("일반 공지사항입니다") == []


def test_categorize_title_detects_deadline():
    fixed_today = datetime.date(2026, 8, 1)
    assert "마감임박" in categorize_title("설명회 개최 안내(~8/7 13:59)", fixed_today)
    assert "마감임박" in categorize_title("모집 마감 임박", fixed_today)


def test_categorize_title_marks_past_deadline_as_expired():
    fixed_today = datetime.date(2026, 8, 21)
    assert "마감됨" in categorize_title("설명회 개최 안내(~8/7 13:59)", fixed_today)
    assert "마감임박" not in categorize_title("설명회 개최 안내(~8/7 13:59)", fixed_today)


def test_dashboard_html_renders_tags_and_filter_ui():
    results = {"산업공학과": {"new": [], "posts": [("국가장학금 2차 신청", "https://x/1")]}}
    out = generate_dashboard_html(results)
    assert 'id="search"' in out
    assert "tag-장학금" in out


def test_dashboard_html_renders_star_color_and_favorites_controls():
    results = {"산업공학과": {"new": [], "posts": [("공지 A", "https://x/1")], "previews": {"https://x/1": "미리보기 내용"}}}
    out = generate_dashboard_html(results)
    assert 'class="star-btn"' in out
    assert 'class="hl-color"' in out
    assert 'id="favBtn"' in out
    assert 'data-preview="미리보기 내용"' in out


def test_dashboard_html_no_preview_attr_when_missing():
    results = {"산업공학과": {"new": [], "posts": [("공지 A", "https://x/1")], "previews": {}}}
    out = generate_dashboard_html(results)
    assert 'data-preview="' not in out


def test_chunk_message_keeps_short_text_as_one_chunk():
    text = "entry one\n\nentry two"
    assert chunk_message(text, max_len=1000) == [text]


def test_chunk_message_splits_long_text_without_breaking_entries():
    entries = [f"[게시판] 제목 {i}\nhttps://x/{i}" for i in range(200)]
    text = "\n\n".join(entries)
    chunks = chunk_message(text, max_len=500)
    assert len(chunks) > 1
    assert all(len(c) <= 500 or c.count("\n\n") == 0 for c in chunks)
    # 모든 항목이 어딘가에는 그대로 살아있어야 함(잘리지 않음)
    rejoined = "\n\n".join(chunks)
    for entry in entries:
        assert entry in rejoined


def test_manual_reports_html_empty_when_none():
    assert build_manual_reports_html([]) == ""


def test_manual_reports_html_renders_and_escapes():
    reports = [{"date": "2026-08-21 15:00", "title": "<script>x</script>", "body": "내용 여러줄\n둘째줄"}]
    out = build_manual_reports_html(reports)
    assert "2026-08-21 15:00" in out
    assert "<script>x</script>" not in out
    assert "둘째줄" in out


def test_dashboard_html_includes_manual_reports_section():
    results = {"산업공학과": {"new": [], "posts": []}}
    reports = [{"date": "2026-08-21", "title": "에브리타임 확인", "body": "내용"}]
    out = generate_dashboard_html(results, manual_reports=reports)
    assert "수동 리포트" in out
    assert "에브리타임 확인" in out


def test_dashboard_html_renders_apply_button_and_tracker_panel():
    results = {"산업공학과": {"new": [], "posts": [("국가장학금 신청(~9/9)", "https://x/1")], "previews": {}}}
    out = generate_dashboard_html(results)
    assert 'class="apply-btn"' in out
    assert 'id="appliedPanel"' in out
    assert 'id="appliedList"' in out
    assert 'data-deadline="' in out


def test_check_boards_keeps_page1_when_extra_page_fails():
    page1_html = '<table><tr><td><a href="?mode=view&board_seq=1">글1</a></td></tr></table>'

    def fake_fetch_html(url, *args, **kwargs):
        if "page=" in url:
            raise ConnectionError("simulated network blip on page 2")
        return page1_html

    orig_fetch = board_watcher.fetch_html
    orig_load_state = board_watcher.load_state
    orig_save_state = board_watcher.save_state
    orig_multi_page = board_watcher.MULTI_PAGE_BOARDS
    board_watcher.fetch_html = fake_fetch_html
    board_watcher.load_state = lambda: {}
    board_watcher.save_state = lambda state: None
    board_watcher.MULTI_PAGE_BOARDS = {"테스트게시판": 3}
    try:
        results = board_watcher.check_boards({"테스트게시판": ("html", "https://example.com/board")})
    finally:
        board_watcher.fetch_html = orig_fetch
        board_watcher.load_state = orig_load_state
        board_watcher.save_state = orig_save_state
        board_watcher.MULTI_PAGE_BOARDS = orig_multi_page

    assert "error" not in results["테스트게시판"]
    assert len(results["테스트게시판"]["posts"]) == 1
    assert results["테스트게시판"]["posts"][0][0] == "글1"


def test_dashboard_html_escapes_titles():
    results = {"X": {"new": [], "posts": [("<script>alert(1)</script>", "https://x/1")]}}
    out = generate_dashboard_html(results)
    assert "<script>alert" not in out


if __name__ == "__main__":
    test_artcl_pattern()
    test_board_do_pattern()
    test_no_match_returns_empty()
    test_rss_parsing()
    test_notification_text_includes_new_posts_only()
    test_notification_text_empty_when_no_new_posts()
    test_dashboard_html_renders_summary()
    test_deadlines_html_empty_when_no_items()
    test_deadlines_html_renders_dday_and_category()
    test_dashboard_html_includes_deadlines_panel()
    test_rss_previews_extracted_and_truncated()
    test_dashboard_html_renders_star_color_and_favorites_controls()
    test_dashboard_html_no_preview_attr_when_missing()
    test_chunk_message_keeps_short_text_as_one_chunk()
    test_chunk_message_splits_long_text_without_breaking_entries()
    test_manual_reports_html_empty_when_none()
    test_manual_reports_html_renders_and_escapes()
    test_dashboard_html_includes_manual_reports_section()
    test_categorize_title_matches_keywords()
    test_categorize_title_detects_deadline()
    test_categorize_title_marks_past_deadline_as_expired()
    test_dashboard_html_renders_tags_and_filter_ui()
    test_dashboard_html_marks_new_and_errors()
    test_dashboard_html_escapes_titles()
    test_check_boards_keeps_page1_when_extra_page_fails()
    test_dashboard_html_renders_apply_button_and_tracker_panel()
    print("ok")
