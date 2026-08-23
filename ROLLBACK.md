# 롤백 가이드

## 예약 작업(스케줄러) 제거

매일 06:00/18:00 자동 실행되는 Windows 작업 스케줄러 항목을 완전히 삭제하려면 PowerShell에서:

```powershell
Unregister-ScheduledTask -TaskName "PNU_BoardWatcher" -Confirm:$false
```

등록됐는지/삭제됐는지 확인:

```powershell
Get-ScheduledTask -TaskName "PNU_BoardWatcher"
```
(결과 없으면 정상 삭제된 것)

## 생성된 파일들 (지워도 안전, 전부 이 프로젝트 폴더 안에만 있음)

- `run_board_watcher.ps1` — 스케줄러가 실행하는 래퍼 스크립트
- `board_watcher.log` — 실행 기록 로그
- `board_watcher.py`, `dashboard.html`, `board_state.json` — 게시판 감시 본체/결과물

```powershell
Remove-Item "C:\Dev\PNU_mate\run_board_watcher.ps1"
Remove-Item "C:\Dev\PNU_mate\board_watcher.log"
```

## 요약

- 시스템 레지스트리, 드라이버, 다른 프로그램에는 전혀 영향 없음
- 스케줄러 항목은 이 컴퓨터의 "내 계정" 범위에서만 동작하는 일반 예약 작업 (관리자 권한/시스템 전역 변경 아님)
- 삭제해도 컴퓨터에 아무 흔적 안 남음 — 언제든 위 명령 한 줄로 완전 원상복구 가능
