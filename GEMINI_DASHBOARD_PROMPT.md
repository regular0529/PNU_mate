# Gemini에게 줄 프롬프트 — board_watcher.py 대시보드 HTML/CSS 재생성

아래 내용을 통째로 복사해서 Gemini 새 채팅에 붙여넣으세요.

---

## 프롬프트 시작

너는 Python 함수 하나를 작성하는 시니어 프론트엔드 개발자야. 아래 스펙대로 `generate_dashboard_html` 함수의 **전체 코드**만 작성해줘. 설명 없이 Python 코드 블록 하나로만 줘.

### 함수 시그니처

```python
def generate_dashboard_html(results: dict[str, dict], summary: str | None = None) -> str:
    ...
```

### 입력 데이터 형태 (`results`)

키는 게시판 이름(한국어 문자열), 값은 둘 중 하나:

```python
# 정상 확인된 게시판
{
    "new": [("새 글 제목", "https://example.com/post/1"), ...],   # 이번에 새로 올라온 글만
    "posts": [("글 제목", "https://example.com/post/1"), ...],     # 최근 글 전체(최신순, new 포함)
}

# 확인 실패한 게시판
{
    "error": "접속 실패 사유 문자열"
}
```

예시:

```python
results = {
    "산업공학과": {
        "new": [("2026 K-ICT WEEK in BUSAN", "https://ie.pusan.ac.kr/bbs/ie/182/1455160/artclView.do")],
        "posts": [
            ("2026 K-ICT WEEK in BUSAN", "https://ie.pusan.ac.kr/bbs/ie/182/1455160/artclView.do"),
            ("2026 블록체인 밋업데이 19차시 교육생 모집", "https://ie.pusan.ac.kr/bbs/ie/182/1455111/artclView.do"),
        ],
    },
    "취업지원센터 공지": {
        "error": "https://job.pusan.ac.kr/ko/notice 접속 실패 (3회 재시도): timeout"
    },
}
summary = "1. [마감임박] CPA 설명회 — 경영학과 주최, 8/7까지 신청\n2. [장학금] 국가장학금 2차 신청 시작"
```

### 디자인 컨셉 — "부산 버스/지하철 전광판(split-flap display)"

이 대시보드는 부산대학교 여러 게시판(공지사항)을 감시하는 개인용 모니터링 도구야. **"전광판에 새 소식이 뜬다"**는 은유로 디자인해줘:

- **다크 배경**, 앰버/호박색(#ffb020 근처) 텍스트를 메인 포인트 컬러로 사용 (LED 전광판 느낌)
- **모노스페이스 폰트**를 헤더/카운트/타임스탬프 등 "데이터성" 텍스트에 사용 (`ui-monospace, "Cascadia Code", Consolas, monospace`)
- 본문 텍스트(게시글 제목)는 한글이 잘 보이는 시스템 폰트 사용 (`"Malgun Gothic", "Apple SD Gothic Neo", system-ui, sans-serif`)
- 새 글에는 작은 점등 표시(dot) + "NEW" 배지, 오래된 글은 점이 꺼진 느낌(회색)
- 상단에 "PNU BOARD WATCH" 브랜드 헤더 + 살짝 깜빡이는 LIVE 점(●) + 마지막 확인 시각
- 상단 헤더에 통계 3개를 숫자로 크게 표시: 새 글 총 개수 / 정상 게시판 수 / 오류 게시판 수 (모노스페이스, tabular-nums)
- `summary`가 있으면 헤더 바로 아래에 앰버색 테두리의 강조 박스로 표시 (라벨: "오늘의 요약"), 없으면 그 박스 자체를 렌더링하지 않음
- 게시판별로 카드(패널) 그리드. 에러난 게시판은 빨간 테두리 + "ERR" 배지 + 에러 메시지만 표시
- 카드 안 게시글 리스트는 최근 20개까지만 표시
- 전체적으로 미니멀하고 정보 밀도 높게, 장식 과함 금지

### 필수 기술 요구사항 (반드시 지켜야 테스트 통과함)

1. **완전히 self-contained**: 외부 CDN/폰트/이미지 요청 없이 인라인 `<style>`만 사용. 인터넷 연결 없이 파일 열어도 정상 렌더링돼야 함.
2. **HTML 이스케이프 필수**: 게시글 제목이나 게시판 이름에 `<script>` 같은 태그가 들어와도 그대로 렌더링되면 안 됨. Python 표준 라이브러리 `html.escape()`를 모든 사용자 제공 문자열(제목, URL, 게시판 이름, 에러 메시지, summary)에 적용해줘.
3. 새 글 배지에는 **정확히 "NEW"라는 대문자 텍스트**가 HTML 어딘가에 그대로 나와야 함 (테스트가 이 문자열을 찾음).
4. `summary` 파라미터가 `None`이거나 빈 문자열이면, 렌더링된 HTML에 **"오늘의 요약"이라는 문자열이 아예 나오면 안 됨** (테스트가 이걸 확인함).
5. `results[name]["error"]`가 있으면 그 에러 메시지 텍스트가 HTML에 그대로 (이스케이프된 채로) 포함돼야 함.
6. 반응형: 카드 그리드는 `grid-template-columns: repeat(auto-fill, minmax(300px, 1fr))` 같은 방식으로 화면 크기에 따라 자동 배치.
7. `prefers-reduced-motion: reduce` 미디어쿼리로 애니메이션(점멸 등) 끄는 것도 챙겨줘.
8. Python 3.10+ 문법 사용 가능 (`str | None` 등).
9. 함수 안에서 `import`가 필요하면 (`html`, `datetime` 등) 함수 최상단에 로컬 import로 넣어줘 — 파일 최상단 import는 이미 있다고 가정하지 말고, 혹시 몰라 필요한 import는 함수 안에 넣어서 이 함수만 복붙해도 동작하게 해줘.

### 참고: 기존 CSS 토큰 (이 톤을 유지해줘, 그대로 복붙 안 해도 됨 — 컨셉 참고용)

```css
--bg: #0a0c10;
--panel: #12161c;
--panel-border: #232a33;
--amber: #ffb020;
--amber-dim: #7a5417;
--text: #d8dee6;
--text-dim: #6b7684;
--red: #ff5a5f;
--red-dim: #4a2326;
```

### 출력 형식

Python 코드 블록 하나로, `generate_dashboard_html` 함수 전체만. 설명 문장 없이.

## 프롬프트 끝

---

## 받은 코드 적용 방법 (Claude가 처리)

1. Gemini 응답을 복사해서 여기 이 대화에 붙여넣거나, `C:\Dev\PNU_mate\gemini_output.py` 파일로 저장해서 알려주세요.
2. Claude가 코드를 검토(이스케이프 누락, 테스트 통과 여부 등)하고 `board_watcher.py`의 기존 `generate_dashboard_html` 함수를 교체합니다.
3. `python test_board_watcher.py`로 테스트 통과 확인 후 실제 대시보드를 열어서 시각적으로도 확인합니다.
