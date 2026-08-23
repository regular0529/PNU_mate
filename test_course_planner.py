from course_planner import build_message_content


def test_text_only():
    content = build_message_content("자료구조", "과제 3회, 팀플 없음", [])
    assert len(content) == 1
    assert "자료구조" in content[0]["text"]
    assert "과제 3회" in content[0]["text"]


def test_no_syllabus():
    content = build_message_content("자료구조", None, [])
    assert "교수계획서" not in content[0]["text"]


if __name__ == "__main__":
    test_text_only()
    test_no_syllabus()
    print("ok")
