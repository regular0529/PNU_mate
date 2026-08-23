"""Smart Course Planner MVP — CLI.

Usage:
    python course_planner.py --course "자료구조" --syllabus syllabus.txt --reviews cap1.png cap2.png
    python course_planner.py --course "자료구조" --reviews cap1.png   # syllabus optional

Requires ANTHROPIC_API_KEY in the environment.
"""
import argparse
import base64
import mimetypes
import os
import sys

import anthropic

SYSTEM_PROMPT = (
    "너는 부산대학교 학생들을 위한 수강신청 컨설턴트야. "
    "제공된 교수계획서 텍스트와 에브리타임 강의평가 캡처 이미지를 분석해서 "
    "과제 비중, 팀 프로젝트 유무, 선수 과목, 학점 취득 난이도, 꿀팁/이슈를 정리하고 "
    "수강 여부에 대한 구체적인 조언을 한국어로 제공해."
)


def build_message_content(course: str, syllabus_text: str | None, review_images: list[str]) -> list[dict]:
    text = f"과목명: {course}\n\n"
    if syllabus_text:
        text += f"[교수계획서]\n{syllabus_text}\n\n"
    if review_images:
        text += "[에브리타임 강의평가 캡처 이미지 첨부됨]\n"
    content = [{"type": "text", "text": text}]
    for path in review_images:
        mime, _ = mimetypes.guess_type(path)
        with open(path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime or "image/png", "data": data},
        })
    return content


def analyze(course: str, syllabus_text: str | None, review_images: list[str]) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_message_content(course, syllabus_text, review_images)}],
    )
    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(description="Smart Course Planner MVP")
    parser.add_argument("--course", required=True, help="과목명")
    parser.add_argument("--syllabus", help="교수계획서 텍스트 파일 경로")
    parser.add_argument("--reviews", nargs="*", default=[], help="에브리타임 캡처 이미지 경로들")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY 환경변수를 설정하세요.")

    syllabus_text = None
    if args.syllabus:
        with open(args.syllabus, encoding="utf-8") as f:
            syllabus_text = f.read()

    print(analyze(args.course, syllabus_text, args.reviews))


if __name__ == "__main__":
    main()
