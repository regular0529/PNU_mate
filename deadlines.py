"""부산대학교 2026학년도 주요 일정 데이터 (수동 리서치 결과, 날짜순 정렬 제공)."""
import datetime

# (날짜, 분류, 라벨) — 날짜는 기간의 시작일 기준으로 정렬
DEADLINES: list[tuple[datetime.date, str, str]] = [
    (datetime.date(2025, 11, 20), "장학금", "국가장학금 1학기 1차 신청 (~12.26)"),
    (datetime.date(2026, 1, 30), "학사", "정보처리기사 1회 필기 (~3.3)"),
    (datetime.date(2026, 2, 3), "등록금", "신입생 등록금 납부 (~2.5 16:00)"),
    (datetime.date(2026, 2, 3), "장학금", "국가장학금 1학기 2차 신청 (~3.17)"),
    (datetime.date(2026, 2, 19), "등록금", "1학기 재학생 본등록 (~2.24)"),
    (datetime.date(2026, 2, 20), "졸업", "전기 학위수여식"),
    (datetime.date(2026, 3, 3), "학사", "1학기 개강"),
    (datetime.date(2026, 3, 3), "등록금", "1학기 추가등록 (~3.5)"),
    (datetime.date(2026, 3, 3), "학사", "1학기 수강정정 1차 (~3.9)"),
    (datetime.date(2026, 3, 17), "학사", "1학기 수강정정 2차 (~3.18)"),
    (datetime.date(2026, 3, 24), "등록금", "1학기 최종등록 (~3.26)"),
    (datetime.date(2026, 4, 18), "학사", "정보처리기사 1회 실기 (~5.6)"),
    (datetime.date(2026, 4, 20), "학사", "1학기 중간고사 (~4.25)"),
    (datetime.date(2026, 5, 9), "학사", "정보처리기사 2회 필기 (~5.29)"),
    (datetime.date(2026, 5, 12), "학사", "여름 계절/도약 수강신청 (~5.14)"),
    (datetime.date(2026, 5, 22), "장학금", "국가장학금 2학기 1차 신청 (~6.22)"),
    (datetime.date(2026, 6, 16), "학사", "1학기 기말고사 (~6.22)"),
    (datetime.date(2026, 6, 23), "학사", "1학기 종강 / 하기휴가 시작"),
    (datetime.date(2026, 7, 18), "학사", "정보처리기사 2회 실기 (~8.5)"),
    (datetime.date(2026, 8, 7), "학사", "정보처리기사 3회 필기 (~9.1)"),
    (datetime.date(2026, 8, 8), "자격증", "ADsP 50회 시험"),
    (datetime.date(2026, 8, 10), "학사", "2학기 수강신청 1차 (~8.12)"),
    (datetime.date(2026, 8, 12), "장학금", "국가장학금 2학기 2차 신청 (~9.9)"),
    (datetime.date(2026, 8, 18), "학사", "2학기 수강신청 2차 (~8.19)"),
    (datetime.date(2026, 8, 21), "졸업", "후기 학위수여식"),
    (datetime.date(2026, 8, 24), "등록금", "2학기 재학생 본등록 (~8.27)"),
    (datetime.date(2026, 9, 1), "학사", "2학기 개강"),
    (datetime.date(2026, 9, 1), "등록금", "2학기 추가등록 (~9.3)"),
    (datetime.date(2026, 9, 1), "학사", "2학기 수강정정 1차 (~9.7)"),
    (datetime.date(2026, 9, 7), "입시", "2027학년도 수시 원서접수 (~9.11)"),
    (datetime.date(2026, 9, 15), "학사", "2학기 수강정정 2차 (~9.16)"),
    (datetime.date(2026, 9, 21), "등록금", "2학기 최종등록 (~9.23)"),
    (datetime.date(2026, 10, 19), "학사", "2학기 중간고사 (~10.24)"),
    (datetime.date(2026, 10, 24), "학사", "정보처리기사 3회 실기 (~11.13)"),
    (datetime.date(2026, 10, 31), "자격증", "ADsP 51회 시험"),
    (datetime.date(2026, 11, 13), "학사", "겨울 계절/도약 수강신청 (~11.17)"),
    (datetime.date(2026, 11, 14), "자격증", "SQLD 63회 시험"),
    (datetime.date(2026, 11, 28), "자격증", "빅데이터분석기사 실기 13회 시험"),
    (datetime.date(2026, 12, 15), "학사", "2학기 기말고사 (~12.21)"),
    (datetime.date(2026, 12, 18), "입시", "2027학년도 수시 합격자 발표 마감"),
    (datetime.date(2026, 12, 22), "학사", "2학기 종강 / 동기휴가 시작"),
    (datetime.date(2026, 12, 24), "학사", "겨울 계절수업 (~1.21)"),
    (datetime.date(2027, 1, 4), "입시", "2027학년도 정시 원서접수 (~1.7)"),
    (datetime.date(2027, 1, 22), "학사", "겨울 도약수업 (~2.19)"),
]


def get_upcoming(today: datetime.date | None = None, within_days: int = 90) -> list[tuple[datetime.date, str, str]]:
    today = today or datetime.date.today()
    cutoff = today + datetime.timedelta(days=within_days)
    return sorted(d for d in DEADLINES if today <= d[0] <= cutoff)
