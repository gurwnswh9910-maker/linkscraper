# PC방 작업 인수인계

이 문서는 아무 맥락이 없는 Windows PC에서 linkscraper를 바로 실행하기 위한 절차입니다.

## 1. 확인

PowerShell에서 확인합니다.

```powershell
python --version
py --version
git --version
where chrome
```

없으면 `winget`으로 설치합니다.

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
winget install --id Google.Chrome -e
```

## 2. 리포 받기

```powershell
git clone https://github.com/gurwnswh9910-maker/linkscraper.git
cd linkscraper
```

리포가 private으로 바뀌어 clone이 막히면 GitHub 로그인부터 해결합니다.

## 3. Python 환경

```powershell
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. 입력 복원

```powershell
python scripts\unpack_input.py
```

복원 결과는 `input\three_account_threads_urls_20260614.csv`입니다.

## 5. Smoke Test

```powershell
python linkscraper.py --input input\three_account_threads_urls_20260614.csv --output output\smoke_links.xlsx --url-column thread_url --limit 3
```

브라우저가 뜨고 Threads 게시글 3개를 방문해야 합니다. CAPTCHA, 429, 계정 경고가 보이면 중단합니다.

## 6. 전체 실행

```powershell
python linkscraper.py --input input\three_account_threads_urls_20260614.csv --output output\coupang_links.xlsx --url-column thread_url
```

기본 출력은 URL마다 한 줄입니다. 너무 빠르게 도는 느낌이면 `--sleep-seconds 2`를 추가합니다.

## 7. 결과 확인

```powershell
python - <<'PY'
import pandas as pd
p = 'output/coupang_links.xlsx'
summary = pd.read_excel(p, sheet_name='summary')
links = pd.read_excel(p, sheet_name='links_long')
print({'posts': len(summary), 'posts_with_links': int((summary['link_count'] > 0).sum()), 'links': len(links)})
PY
```

보고할 것:

- 입력 URL 수
- 완료 URL 수
- 쿠팡 링크가 발견된 URL 수
- 추출 링크 수
- 중단한 URL과 이유
- CAPTCHA/429 여부
