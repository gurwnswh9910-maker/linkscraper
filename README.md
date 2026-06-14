# linkscraper

Threads 게시글 URL 목록에서 DOM에 보이는 쿠팡 링크만 수집하는 독립 실행 도구입니다.

## 목적

- 이미 확보한 Threads 게시글 URL을 방문합니다.
- 로그인 없이 공개 DOM에 보이는 `link.coupang.com` / `coupang.com` 링크를 찾습니다.
- 결과를 Excel 또는 CSV로 저장합니다.
- MSS 대신 실제 클릭/링크 성과를 추적하기 위한 후보 데이터를 만듭니다.

## 빈 Windows PC에서 시작

PowerShell을 열고 다음을 확인합니다.

```powershell
python --version
py --version
git --version
where chrome
```

도구가 없고 `winget`이 가능하면 설치합니다.

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
winget install --id Google.Chrome -e
```

리포를 받고 의존성을 설치합니다.

```powershell
git clone https://github.com/gurwnswh9910-maker/linkscraper.git
cd linkscraper
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

PowerShell이 venv 실행을 막으면 같은 창에서만 정책을 풉니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 포함된 3계정 URL 입력 복원

리포에는 2026-06-14 기준 3계정 URL 1,814개가 압축 텍스트 조각으로 들어 있습니다.

```powershell
python scripts\unpack_input.py
```

복원 파일:

```text
input\three_account_threads_urls_20260614.csv
```

계정별 URL 수:

| account | URLs | handle |
|---|---:|---|
| arch_dotori | 644 | arch_dotori |
| sehee | 603 | _seheehx_ |
| coco_x_pas | 567 | coco_x_pas |

## 실행

먼저 3개만 smoke test 합니다.

```powershell
python linkscraper.py --input input\three_account_threads_urls_20260614.csv --output output\smoke_links.xlsx --url-column thread_url --limit 3
```

문제가 없으면 전체 실행합니다.

```powershell
python linkscraper.py --input input\three_account_threads_urls_20260614.csv --output output\coupang_links.xlsx --url-column thread_url
```

결과 workbook:

- `summary`: Threads 게시글 1개당 1행
- `links_long`: 추출된 쿠팡 링크 1개당 1행

## 멈출 조건

다음이 보이면 바로 중단하고 기록합니다.

- CAPTCHA
- HTTP 429
- Threads 계정 경고
- 반복 access denied
- 브라우저가 URL마다 빈 화면만 반환

로그인 자동화나 계정 세션 조작은 이 리포의 범위가 아닙니다.

## 주요 파일

- `linkscraper.py`: 링크 전용 수집 CLI
- `requirements.txt`: PC방 설치용 최소 의존성
- `input/three_account_threads_urls_20260614.csv.gz.b64.part*`: 3계정 URL CSV 압축 조각
- `scripts/unpack_input.py`: 압축 입력 복원
- `docs/PC_BANG_HANDOFF.md`: 무맥락 인수인계 절차
