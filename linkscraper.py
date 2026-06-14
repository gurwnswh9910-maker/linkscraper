# -*- coding: utf-8 -*-
"""Collect visible Coupang links from existing Threads post URLs.

Run this from a fresh Windows PC after installing requirements.txt.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait


COUPANG_URL_RE = re.compile(
    r"(?:https?://)?(?:link\.coupang\.com|www\.coupang\.com|coupang\.com)/[^\s\"'<>]+",
    re.IGNORECASE,
)
THREADS_URL_RE = re.compile(
    r"https?://(?:www\.)?threads\.(?:net|com)/@[^\s\"'<>]+/(?:post|t)/[^\s\"'<>]+",
    re.IGNORECASE,
)


def safe_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def unescape_url_text(value) -> str:
    text = safe_str(value)
    text = (
        text.replace("\\/", "/")
        .replace("\\u0026", "&")
        .replace("\\u003d", "=")
        .replace("\\u003D", "=")
        .replace("\\u003f", "?")
        .replace("\\u003F", "?")
        .replace("\\u2026", "...")
    )
    text = re.sub(r"\\u0025", "%", text, flags=re.IGNORECASE)
    for _ in range(2):
        decoded = urllib.parse.unquote(text)
        if decoded == text:
            break
        text = decoded
    return text


def normalize_coupang_url(raw_url) -> str:
    raw_value = unescape_url_text(raw_url).strip().strip("()[]{}<>\"'")
    if not raw_value:
        return ""
    if "..." in raw_value and "l.threads.com" not in raw_value:
        return ""
    if "l.threads.com" in raw_value:
        raw_value = raw_value.replace("&amp;", "&")
        parsed = urllib.parse.urlparse(raw_value)
        raw_value = unescape_url_text(urllib.parse.parse_qs(parsed.query).get("u", [""])[0])

    match = re.search(r"(?:https?://)?link\.coupang\.com/a/[A-Za-z0-9]+", raw_value)
    if not match:
        match = COUPANG_URL_RE.search(raw_value)
    if not match:
        return ""
    url = match.group(0).strip().strip("()[]{}<>\"'")
    if "..." in url:
        return ""
    if url.startswith(("www.coupang.com", "link.coupang.com", "coupang.com")):
        url = "https://" + url
    return url if "coupang.com" in url else ""


def unique_coupang_urls(values) -> list[str]:
    urls = []
    for value in values or []:
        candidate = normalize_coupang_url(value)
        if candidate:
            urls.append(candidate)
    return list(dict.fromkeys(urls))


def normalize_threads_url(value) -> str:
    text = safe_str(value)
    match = THREADS_URL_RE.search(text)
    if match:
        text = match.group(0)
    return text.split("?")[0].replace("threads.net", "threads.com")


def read_input_urls(path: Path, url_column: str | None = None) -> list[str]:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path, engine="openpyxl")
        if url_column and url_column in df.columns:
            column = url_column
        else:
            column = next(
                (
                    col
                    for col in df.columns
                    if "url" in str(col).lower()
                    or "link" in str(col).lower()
                    or "링크" in str(col)
                    or "threads" in str(col).lower()
                ),
                df.columns[0],
            )
        values = df[column].tolist()
    elif suffix == ".csv":
        df = pd.read_csv(path)
        if url_column and url_column in df.columns:
            column = url_column
        else:
            column = next(
                (
                    col
                    for col in df.columns
                    if "url" in str(col).lower()
                    or "link" in str(col).lower()
                    or "링크" in str(col)
                    or "threads" in str(col).lower()
                ),
                df.columns[0],
            )
        values = df[column].tolist()
    else:
        values = path.read_text(encoding="utf-8-sig").splitlines()

    urls = []
    for value in values:
        url = normalize_threads_url(value)
        if url.startswith("http") and "/post/" in url and url not in urls:
            urls.append(url)
    return urls


def init_driver(headless: bool = False, debugger_address: str | None = None):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--window-size=1280,1000")
    if headless:
        options.add_argument("--headless=new")
    if debugger_address:
        options.add_experimental_option("debuggerAddress", debugger_address)

    try:
        return webdriver.Chrome(options=options)
    except Exception:
        from webdriver_manager.chrome import ChromeDriverManager

        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def dismiss_soft_popups(driver) -> None:
    try:
        driver.execute_script(
            """
            const labels = ['나중에', '닫기', 'Close', 'Not now', 'Continue'];
            for (const el of Array.from(document.querySelectorAll('div[role="button"], button, span'))) {
              const text = ((el.innerText || el.textContent || '') + '').trim();
              if (labels.includes(text)) {
                const button = el.closest('div[role="button"], button') || el;
                try { button.click(); } catch (e) {}
              }
            }
            """
        )
    except Exception:
        pass


def collect_visible_coupang_links(driver, wait_seconds: float = 4.0) -> list[str]:
    deadline = time.time() + max(0.0, wait_seconds)
    last = []
    while True:
        values = []
        try:
            anchors = driver.execute_script(
                """
                return Array.from(document.querySelectorAll('a')).map(a => ({
                  href: a.href || '',
                  text: a.innerText || a.textContent || '',
                  aria: a.getAttribute('aria-label') || ''
                }));
                """
            ) or []
            for anchor in anchors:
                values.extend([anchor.get("href"), anchor.get("text"), anchor.get("aria")])
            body_text = driver.execute_script("return document.body ? document.body.innerText : ''") or ""
            page_source = unescape_url_text((driver.page_source or "").replace("&amp;", "&"))
            values.append(body_text)
            values.extend(re.findall(r"https://l\.threads\.com/\?u=[^\s\"'<>]+", page_source))
            values.append(page_source)
            last = unique_coupang_urls(values)
        except Exception:
            last = []
        if last or time.time() >= deadline:
            return last
        time.sleep(0.5)


def scrape_urls(
    urls: list[str],
    *,
    headless: bool,
    debugger_address: str | None,
    wait_seconds: float,
    sleep_seconds: float,
    limit: int | None,
):
    selected_urls = urls[:limit] if limit else urls
    rows = []
    long_rows = []
    driver = init_driver(headless=headless, debugger_address=debugger_address)
    try:
        for index, url in enumerate(selected_urls, start=1):
            started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{index}/{len(selected_urls)}] open {url}", flush=True)
            links = []
            error = ""
            try:
                driver.get(url)
                WebDriverWait(driver, max(3, int(wait_seconds))).until(
                    lambda d: d.execute_script("return document.readyState") in {"interactive", "complete"}
                )
                time.sleep(1.0)
                dismiss_soft_popups(driver)
                links = collect_visible_coupang_links(driver, wait_seconds=wait_seconds)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"

            row = {
                "source_url": url,
                "scraped_at": started,
                "link_count": len(links),
                "coupang_link_1": links[0] if links else "",
                "coupang_links_json": json.dumps(links, ensure_ascii=False),
                "status": "completed" if not error else "error",
                "error": error,
            }
            for link_index, link in enumerate(links, start=1):
                row[f"coupang_link_{link_index}"] = link
                long_rows.append(
                    {"source_url": url, "scraped_at": started, "link_index": link_index, "coupang_url": link}
                )
            rows.append(row)
            if sleep_seconds:
                time.sleep(sleep_seconds)
    finally:
        driver.quit()
    return rows, long_rows


def write_output(path: Path, rows: list[dict], long_rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
        long_path = path.with_name(path.stem + "_long.csv")
        pd.DataFrame(long_rows).to_csv(long_path, index=False, encoding="utf-8-sig")
        return

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="summary")
        pd.DataFrame(long_rows).to_excel(writer, index=False, sheet_name="links_long")


def parse_args():
    parser = argparse.ArgumentParser(description="Collect visible Coupang links from Threads post URLs.")
    parser.add_argument("--input", required=True, help="txt/csv/xlsx file containing Threads post URLs")
    parser.add_argument("--output", required=True, help="output .xlsx or .csv path")
    parser.add_argument("--url-column", help="optional URL column name for Excel/CSV input")
    parser.add_argument("--limit", type=int, help="optional max URLs for smoke runs")
    parser.add_argument("--wait-seconds", type=float, default=4.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.7)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--debugger-address", help="optional existing Chrome debugger address, e.g. 127.0.0.1:9222")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    urls = read_input_urls(input_path, url_column=args.url_column)
    if not urls:
        raise SystemExit("No Threads post URLs found in input.")
    print(f"input_urls={len(urls)} output={output_path}", flush=True)
    rows, long_rows = scrape_urls(
        urls,
        headless=args.headless,
        debugger_address=args.debugger_address,
        wait_seconds=args.wait_seconds,
        sleep_seconds=args.sleep_seconds,
        limit=args.limit,
    )
    write_output(output_path, rows, long_rows)
    print(f"done rows={len(rows)} links={len(long_rows)} output={output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
