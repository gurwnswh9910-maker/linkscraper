# PC방 미검출 751개 UC 재수집 기록 - 2026-06-14

이 문서는 `main` 브랜치의 `input/incomplete_threads_urls_751_20260614.xlsx` 기준 재수집 결과를 남긴 기록이다.

## 입력

- 원본 워크북: `input/incomplete_threads_urls_751_20260614.xlsx`
- 사용 시트: `incomplete_urls_751`
- 재수집 URL 수: 751
- 사유: `no_coupang_link_detected_in_previous_linkscraper_run`

계정별 입력 수:

| account | URLs |
|---|---:|
| `_seheehx_` | 210 |
| `arch_dotori` | 240 |
| `coco_x_pas` | 301 |

## 실행 정책

- 드라이버: `--driver-mode uc`
- Chrome 프로필: 워커별 임시 `--user-data-dir`
- 기존 사용자 Chrome 프로필/로그인 세션/`--debugger-address`: 사용하지 않음
- ChromeDriver: Chrome `148.0.7778` 계열에 맞춰 `148.0.7778.178` 캐시 사용

## 실행 순서

1차 전체 실행:

```powershell
python linkscraper.py `
  --input input\incomplete_threads_urls_751_20260614.csv `
  --output output\incomplete_751_uc_rerun_20260614.xlsx `
  --url-column thread_url `
  --workers 15 `
  --driver-mode uc `
  --dom-timeout-seconds 2 `
  --render-timeout-seconds 2 `
  --wait-seconds 1 `
  --headless
```

2차 미완료 18개 재실행:

```powershell
python linkscraper.py `
  --input input\incomplete_751_pending_pass2_20260614.csv `
  --output output\incomplete_751_uc_rerun_pass2_20260614.xlsx `
  --url-column thread_url `
  --workers 5 `
  --driver-mode uc `
  --dom-timeout-seconds 8 `
  --render-timeout-seconds 8 `
  --wait-seconds 4 `
  --sleep-seconds 0.2 `
  --headless
```

3차 미완료 4개 단일 워커 재실행:

```powershell
python linkscraper.py `
  --input input\incomplete_751_pending_pass3_20260614.csv `
  --output output\incomplete_751_uc_rerun_pass3_20260614.xlsx `
  --url-column thread_url `
  --workers 1 `
  --driver-mode uc `
  --page-load-strategy eager `
  --dom-timeout-seconds 20 `
  --render-timeout-seconds 12 `
  --wait-seconds 6 `
  --sleep-seconds 1 `
  --headless
```

## 최종 산출물

- 최종 병합 엑셀: `output/incomplete_751_uc_final_20260614.xlsx`
- `summary`: URL별 최종 선택 결과
- `links_long`: 추출된 쿠팡 링크 단위 결과
- `remaining_unprocessed`: 3회 재시도 후에도 target DOM 미도달 URL
- `run_summary`, `status_counts`, `account_counts`: 검수 요약

## 최종 결과

| metric | value |
|---|---:|
| 입력 URL | 751 |
| 완료 URL | 748 |
| 남은 미처리 URL | 3 |
| 쿠팡 링크 발견 게시글 | 660 |
| 추출 쿠팡 링크 행 | 673 |

계정별 결과:

| account | URLs | completed | posts_with_links | links |
|---|---:|---:|---:|---:|
| `_seheehx_` | 210 | 208 | 181 | 189 |
| `arch_dotori` | 240 | 239 | 207 | 208 |
| `coco_x_pas` | 301 | 301 | 272 | 276 |

남은 미처리 URL:

| priority | account | URL | status |
|---:|---|---|---|
| 53 | `_seheehx_` | `https://www.threads.com/@_seheehx_/post/DXLZ_-mAPRv` | `dom_not_ready` |
| 87 | `_seheehx_` | `https://www.threads.com/@_seheehx_/post/DXbDcn_lJRE` | `dom_not_ready` |
| 719 | `arch_dotori` | `https://www.threads.com/@arch_dotori/post/DYiXz0OjTpA` | `dom_not_ready` |

실행 중 CAPTCHA, HTTP 429, 계정 경고, 반복 access denied는 감지되지 않았다.
