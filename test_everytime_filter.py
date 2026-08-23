from everytime_filter import build_message_content


def test_text_only_when_no_images():
    content = build_message_content([])
    assert len(content) == 1
    assert content[0]["type"] == "text"


if __name__ == "__main__":
    test_text_only_when_no_images()
    print("ok")
