"""Everytime Filter — 에브리타임 캡처를 붙여넣으면 값진 글만 골라주는 CLI.

에브리타임은 로그인이 필요한 폐쇄형 커뮤니티라 자동 스크래핑은 하지 않는다.
사용자가 직접 화면을 캡처해서 붙여넣는 방식.

우선적으로 캡처하면 좋은 게시판 (신호 밀도 순):
  1. 동아리·학회 — 학술동아리/학회 모집 공고가 몰려있음
  2. 자격증/고시 게시판군 (CPA, CTA, 공무원, 노무사, 관세사, 공기업 등) — 스터디원 모집
  3. 정보게시판 — 공모전/모임 모집 (잡다한 글과 섞여있어 필터링 필요)
  4. 홍보게시판 — 연구참여자/기자단/멘토링 모집
  5. 학과 게시판 — 가끔 경진대회/학술 정보

Usage:
    python everytime_filter.py --images cap1.png cap2.png

Requires ANTHROPIC_API_KEY in the environment.
"""
import argparse
import base64
import mimetypes
import os
import sys

import anthropic

SYSTEM_PROMPT = (
    "너는 부산대학교 학생을 위한 정보 큐레이터야. 에브리타임(대학 커뮤니티) 게시판 캡처 이미지를 보고, "
    "학업/진로에 실질적으로 도움되는 정보만 골라내. "
    "포함할 것: 공모전, 자격증/고시 스터디·캠스터디 모집, 학술동아리·학회 모집, 학술대회·경진대회, "
    "연구참여자 모집, 인턴/채용, 장학금 등 커리어·학업에 도움되는 활동. "
    "제외할 것: 자극적인 트렌드/드립/욕설/개인 신세한탄/연애·잡담/취미 동아리(마술, 종이접기 등) 같은 "
    "학업·진로와 무관한 글. "
    "결과는 '[분류] 제목 — 한 줄 요약' 형식으로 목록만 한국어로 출력해. 값진 글이 없으면 "
    "'값진 정보 없음'이라고만 답해."
)


def build_message_content(images: list[str]) -> list[dict]:
    content = [{"type": "text", "text": "아래 에브리타임 게시판 캡처에서 값진 정보만 골라줘."}]
    for path in images:
        mime, _ = mimetypes.guess_type(path)
        with open(path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime or "image/png", "data": data},
        })
    return content


def filter_posts(images: list[str]) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_message_content(images)}],
    )
    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(description="Everytime Filter")
    parser.add_argument("--images", nargs="+", required=True, help="에브리타임 캡처 이미지 경로들")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY 환경변수를 설정하세요.")

    print(filter_posts(args.images))


if __name__ == "__main__":
    main()
