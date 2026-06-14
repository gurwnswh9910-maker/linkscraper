# PC방 병렬 스크래퍼 실행 기록 - 2026-06-14

이 문서는 PC방처럼 새 Windows 환경에서 바로 재현할 수 있도록, 이번 코드 변경점과 실제 엑셀 산출물 기준 실행 결과를 남긴 기록이다.

## 산출물

- 최신 실행 엑셀: `output/coupang_links_queue_rerun.xlsx`
- 입력: `input/three_account_threads_urls_20260614.csv`
- 입력 URL 수: 1,814
- 추출된 쿠팡 링크 행 수: 1,089
- 쿠팡 링크가 1개 이상 발견된 게시글 수: 1,063
- 댓글/본문 문맥이 채워진 링크 행 수: 1,085

최신 실행 엑셀은 요청에 따라 Git에 함께 포함한다. 다만 `output/`은 기본적으로 계속 ignore 상태로 두어 smoke/debug 중간 산출물이 실수로 같이 올라가지 않게 한다.

## 실행 명령

```powershell
.\.venv\Scripts\python.exe linkscraper.py `
  --input input\three_account_threads_urls_20260614.csv `
  --output output\coupang_links_queue_rerun.xlsx `
  --url-column thread_url `
  --headless
```

이번 실행은 기본값으로 `--workers 15`, `--driver-mode uc`, `--page-load-strategy none`, `--sleep-seconds 0`, `--dom-timeout-seconds 0.5`, `--render-timeout-seconds 0.5`, `--wait-seconds 0.5`가 적용됐다.

## 실행 결과

| status | rows |
|---|---:|
| completed | 1,473 |
| content_not_ready | 281 |
| dom_not_ready | 59 |
| rate_limited | 1 |

- `skipped_after_429`: 0
- `not_processed_no_active_worker`: 0
- 429 발생 URL: `https://www.threads.com/@_seheehx_/post/DXsvFPdj8g3`
- 429 발생 위치: `source_index=1532`, `worker_id=10`

429가 발생한 워커만 종료했고, 나머지 워커는 큐에 남은 URL을 계속 처리했다. 따라서 이전 chunk 방식처럼 해당 워커 뒤쪽 URL이 통째로 스킵되는 현상은 없다.

## 코드 변경점

- 기본 실행을 PC방용 빠른 설정으로 변경했다.
  - `--workers` 기본값을 15로 설정했다.
  - `--driver-mode` 기본값을 `uc`로 설정했다.
  - `--page-load-strategy` 기본값을 `none`으로 설정했다.
  - 고정 대기보다 DOM/Threads 렌더 상태를 짧게 확인하는 방식으로 바꿨다.
- 로그인된 Chrome 프로필을 쓰지 않도록 워커별 임시 Chrome 프로필을 생성한다.
- `undetected-chromedriver`를 지원하고, 이미 캐시된 ChromeDriver가 있으면 재사용한다.
- Selenium 드라이버 생성은 락으로 보호해 병렬 초기화 충돌을 줄였다.
- URL 처리 방식을 worker chunk 분배에서 shared queue 방식으로 바꿨다.
  - 각 워커가 큐에서 URL을 하나씩 가져간다.
  - 한 워커가 429를 만나면 그 워커만 종료한다.
  - 남은 URL은 살아 있는 다른 워커가 계속 가져간다.
- 빈 화면을 곧바로 "없음"으로 처리하지 않도록 DOM과 Threads 렌더 신호를 분리해서 확인한다.
- 링크가 없을 때는 한 번 스크롤한 뒤 다시 추출한다.
- Threads의 `l.threads.com/?u=...` 리다이렉트 링크에서 실제 Coupang URL을 복원한다.
- SSR JSON의 `caption.text`와 앵커 주변 DOM에서 댓글/본문 문맥을 추출한다.
- 엑셀 출력에 추적 필드를 추가했다.
  - `summary`: `source_index`, `worker_id`, `coupang_contexts_json`
  - `links_long`: `source_index`, `worker_id`, `source_href`, `anchor_text`, `context_text`

## 재실행 체크

1. 새 PC에서 `python scripts\unpack_input.py`로 입력 CSV를 복원한다.
2. `pip install -r requirements.txt`로 Selenium, pandas, undetected-chromedriver를 설치한다.
3. smoke test는 `--limit 3`으로 먼저 실행한다.
4. 전체 실행은 위 실행 명령을 사용한다.
5. 429가 보이면 해당 워커만 멈추는 것이 정상 정책이다. 다른 워커가 계속 진행해야 한다.
