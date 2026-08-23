"""4B vs 9B 로컬 모델 속도 벤치마크 (board_watcher 요약 작업과 동일한 프롬프트 사용)."""
import time
import requests

SYSTEM_PROMPT = (
    "너는 부산대학교 산업공학과 학생을 위한 비서야. 여러 게시판에 새로 올라온 공지 제목들을 보고, "
    "이 학생에게 실제로 중요할 만한 것 위주로 한국어로 짧게 요약해. "
    "장학금/마감일/채용/공모전처럼 놓치면 아까운 것을 우선하고, 각 항목은 '[분류] 핵심내용 — 왜 중요한지' 형식으로 "
    "한 줄씩, 최대 5줄로 정리해. 중요한 게 없으면 '오늘은 특별히 중요한 새 글 없음'이라고만 답해."
)

SAMPLE_POSTS = "\n".join([
    "[산업공학과] 2026 넥스트 블록체인 교육 3회차 교육생 모집",
    "[교양교육원] 2026-2학기 수강정정 대비 영어 기초학력 진단평가 안내(신청: 8/10~8/21)",
    "[부산대 공지사항] 2026년 2학기 국가장학금 2차 신청기간 안내",
    "[취업지원센터] 일자리첫걸음보장센터 2026학년도 공공기관 직무탐방 프로그램 참가자 모집",
    "[AI융합교육원] 2026-2학기 현장실습학기제 인턴십 참여학생 모집(채용연계형)",
])


def bench(model: str) -> dict:
    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": SAMPLE_POSTS,
        "stream": False,
    }
    start = time.time()
    resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=600)
    wall = time.time() - start
    data = resp.json()
    eval_count = data.get("eval_count", 0)
    eval_duration_s = data.get("eval_duration", 0) / 1e9
    tok_per_sec = eval_count / eval_duration_s if eval_duration_s else 0
    return {
        "model": model,
        "wall_seconds": round(wall, 1),
        "output_tokens": eval_count,
        "tokens_per_sec": round(tok_per_sec, 2),
        "response": data.get("response", ""),
    }


if __name__ == "__main__":
    for m in ["qwen3.5:4b", "qwen3.5:9b"]:
        print(f"\n=== {m} 측정 중 ===")
        result = bench(m)
        print(f"전체 소요시간: {result['wall_seconds']}초")
        print(f"출력 토큰수: {result['output_tokens']}")
        print(f"토큰/초: {result['tokens_per_sec']}")
        print(f"응답:\n{result['response']}")
        requests.post("http://localhost:11434/api/generate", json={"model": m, "keep_alive": 0})
