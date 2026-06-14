# -*- coding: utf-8 -*-
"""Collect visible Coupang links from existing Threads post URLs.

Run this from a fresh Windows PC after installing requirements.txt.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import threading
import json
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


COUPANG_URL_RE = re.compile(
    r"(?:https?://)?(?:link\.coupang\.com|www\.coupang\.com|coupang\.com)/[^\s\"'<>]+",
    re.IGNORECASE,
)
THREADS_URL_RE = re.compile(
    r"https?://(?:www\.)?threads\.(?:net|com)/@[^\s\"'<>]+/(?:post|t)/[^\s\"'<>]+",
    re.IGNORECASE,
)
RATE_LIMIT_RE = re.compile(
    r"\b429\b|too many requests|rate limit|" + "\uc694\uccad\uc774 \ub108\ubb34 \ub9ce",
    re.IGNORECASE,
)
_DRIVER_INIT_LOCK = threading.Lock()


def detect_chrome_major_version() -> int | None:
    versions = []
    try:
        import winreg

        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(root, r"Software\Google\Chrome\BLBeacon") as key:
                    versions.append(winreg.QueryValueEx(key, "version")[0])
            except OSError:
                pass
    except ImportError:
        pass

    for app_dir in (
        Path(r"C:\Program Files\Google\Chrome\Application"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application"),
    ):
        if not app_dir.exists():
            continue
        for child in app_dir.iterdir():
            if child.is_dir() and re.match(r"^\d+\.\d+\.\d+\.\d+$", child.name):
                versions.append(child.name)

    for version in versions:
        match = re.match(r"^(\d+)\.", safe_str(version))
        if match:
            return int(match.group(1))
    return None


def find_cached_chromedriver(chrome_major: int | None) -> str | None:
    cache_root = Path.home() / ".cache" / "selenium" / "chromedriver" / "win64"
    if not cache_root.exists():
        return None
    candidates = []
    for driver_path in cache_root.glob("*/chromedriver.exe"):
        version = driver_path.parent.name
        if chrome_major and not version.startswith(f"{chrome_major}."):
            continue
        candidates.append(driver_path)
    if not candidates:
        return None
    return str(sorted(candidates, key=lambda path: path.parent.name, reverse=True)[0])


def remove_profile_dir(path: str) -> None:
    for _ in range(5):
        shutil.rmtree(path, ignore_errors=True)
        if not Path(path).exists():
            return
        time.sleep(0.2)


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
        .replace("?", "...")
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


def init_driver(
    headless: bool = False,
    debugger_address: str | None = None,
    driver_mode: str = "selenium",
    page_load_strategy: str = "normal",
    user_data_dir: str | None = None,
):
    if driver_mode == "uc":
        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
    elif driver_mode == "selenium":
        options = Options()
    else:
        raise ValueError(f"unsupported driver_mode={driver_mode}")

    options.page_load_strategy = page_load_strategy
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--window-size=1280,1000")
    if headless:
        options.add_argument("--headless=new")
    if debugger_address:
        options.add_experimental_option("debuggerAddress", debugger_address)
    elif user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")

    with _DRIVER_INIT_LOCK:
        if driver_mode == "uc":
            chrome_major = detect_chrome_major_version()
            driver_kwargs = {"version_main": chrome_major} if chrome_major else {}
            cached_driver = find_cached_chromedriver(chrome_major)
            if cached_driver:
                driver_kwargs["driver_executable_path"] = cached_driver
            driver = uc.Chrome(options=options, **driver_kwargs)
        else:
            try:
                driver = webdriver.Chrome(options=options)
            except Exception:
                from webdriver_manager.chrome import ChromeDriverManager

                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_script_timeout(10)
    return driver


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


def read_page_state(driver, expected_url: str | None = None) -> dict:
    expected_path = urllib.parse.urlparse(expected_url or "").path
    expected_handle = ""
    path_parts = [part for part in expected_path.split("/") if part]
    if path_parts and path_parts[0].startswith("@"):
        expected_handle = path_parts[0].lstrip("@")
    try:
        state = driver.execute_script(
            """
            const body = document.body;
            const text = body ? ((body.innerText || body.textContent || '').trim()) : '';
            const anchors = Array.from(document.querySelectorAll('a'));
            return {
              currentUrl: location.href || '',
              readyState: document.readyState || '',
              hasDom: !!(document.documentElement || document.body),
              bodyTextLength: text.length,
              anchorCount: anchors.length,
              roleLinkCount: document.querySelectorAll('a[role="link"]').length,
              hasCoupangCandidate: /coupang\\.com|link\\.coupang\\.com|l\\.threads\\.com/i.test(
                text + ' ' + anchors.map(a => `${a.href || ''} ${a.innerText || a.textContent || ''}`).join(' ')
              )
            };
            """
        ) or {}
    except Exception:
        state = {}
    current_url = safe_str(state.get("currentUrl"))
    current_path = urllib.parse.urlparse(current_url).path
    state["isTargetPage"] = bool(current_url and current_url != "about:blank" and (not expected_path or current_path == expected_path))
    body_len = int(state.get("bodyTextLength") or 0)
    anchor_count = int(state.get("anchorCount") or 0)
    try:
        body_text = driver.execute_script(
            "return document.body ? ((document.body.innerText || document.body.textContent || '').trim()) : ''"
        ) or ""
    except Exception:
        body_text = ""
    state["hasExpectedHandle"] = bool(expected_handle and expected_handle in body_text)
    state["hasRenderedThreadsContent"] = bool(
        state.get("hasCoupangCandidate")
        or (state["hasExpectedHandle"] and anchor_count >= 3 and 0 < body_len < 100000)
    )
    return state


def read_anchor_records(driver) -> list[dict]:
    return driver.execute_script(
        """
        const textOf = (el) => ((el && (el.innerText || el.textContent)) || '').trim();
        const bestContext = (el) => {
          for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
            const text = textOf(node);
            if (text.length >= 40 && text.length <= 1800) {
              return text;
            }
          }
          return textOf(el);
        };
        return Array.from(document.querySelectorAll('a')).map(a => ({
          href: a.href || '',
          text: a.innerText || a.textContent || '',
          aria: a.getAttribute('aria-label') || '',
          context: bestContext(a)
        }));
        """
    ) or []


def collect_coupang_link_records(driver) -> list[dict]:
    records = []
    try:
        anchors = read_anchor_records(driver)
    except Exception:
        anchors = []

    for anchor in anchors:
        for field in ("href", "aria", "text"):
            candidate = normalize_coupang_url(anchor.get(field))
            if candidate:
                records.append(
                    {
                        "url": candidate,
                        "source_href": safe_str(anchor.get("href")),
                        "anchor_text": safe_str(anchor.get("text")),
                        "context_text": safe_str(anchor.get("context")),
                    }
                )
                break

    try:
        page_source = unescape_url_text((driver.page_source or "").replace("&amp;", "&"))
    except Exception:
        page_source = ""
    source_contexts = extract_source_contexts(page_source)
    for candidate, context_text in source_contexts.items():
        records.append({"url": candidate, "source_href": "", "anchor_text": "", "context_text": context_text})
    for value in re.findall(r"https://l\.threads\.com/\?u=[^\s\"'<>]+", page_source):
        candidate = normalize_coupang_url(value)
        if candidate:
            records.append(
                {
                    "url": candidate,
                    "source_href": value,
                    "anchor_text": "",
                    "context_text": source_contexts.get(candidate, ""),
                }
            )

    deduped = {}
    for record in records:
        url = record["url"]
        if url not in deduped or (record.get("context_text") and not deduped[url].get("context_text")):
            deduped[url] = record
    return list(deduped.values())


def extract_source_contexts(page_source: str) -> dict[str, str]:
    contexts = {}
    for match in re.finditer(r'"caption"\s*:\s*\{\s*"text"\s*:\s*"((?:\\.|[^"\\])*)"', page_source):
        try:
            text = json.loads(f'"{match.group(1)}"')
        except Exception:
            continue
        for url in unique_coupang_urls([text]):
            contexts.setdefault(url, text)
    return contexts


def scroll_once(driver) -> None:
    driver.execute_script(
        """
        window.scrollBy(0, Math.max(window.innerHeight || 900, 900));
        """
    )


def is_rate_limited(driver) -> bool:
    values = []
    for script in (
        "return document.title || ''",
        "return document.body ? document.body.innerText : ''",
    ):
        try:
            values.append(driver.execute_script(script) or "")
        except Exception:
            pass
    try:
        values.append(driver.page_source[:8000] or "")
    except Exception:
        pass
    return bool(RATE_LIMIT_RE.search("\n".join(values)))


def wait_for_dom(driver, timeout_seconds: float, expected_url: str | None = None) -> bool:
    deadline = time.time() + max(0.0, timeout_seconds)
    while True:
        state = read_page_state(driver, expected_url=expected_url)
        if state.get("hasDom") and state.get("isTargetPage"):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.1)


def wait_for_threads_render(driver, timeout_seconds: float, expected_url: str | None = None) -> dict:
    deadline = time.time() + max(0.0, timeout_seconds)
    last_state = {}
    while True:
        last_state = read_page_state(driver, expected_url=expected_url)
        if last_state.get("hasRenderedThreadsContent"):
            return last_state
        if time.time() >= deadline:
            return last_state
        time.sleep(0.05)


def collect_visible_coupang_links(driver, wait_seconds: float = 0.0, scroll_if_empty: bool = True) -> list[dict]:
    deadline = time.time() + max(0.0, wait_seconds)
    did_scroll = False
    last = []
    while True:
        try:
            last = collect_coupang_link_records(driver)
        except Exception:
            last = []
        if not last and scroll_if_empty and not did_scroll:
            try:
                scroll_once(driver)
            except Exception:
                pass
            did_scroll = True
            continue
        has_context = any(safe_str(record.get("context_text")) for record in last)
        if (last and has_context) or time.time() >= deadline:
            return last
        time.sleep(0.05)


def make_result_rows(
    source_index: int,
    worker_id: int,
    url: str,
    started: str,
    links: list[dict],
    status: str,
    error: str,
) -> tuple[dict, list[dict]]:
    link_urls = [link["url"] for link in links]
    row = {
        "source_index": source_index,
        "worker_id": worker_id,
        "source_url": url,
        "scraped_at": started,
        "link_count": len(link_urls),
        "coupang_link_1": link_urls[0] if link_urls else "",
        "coupang_links_json": json.dumps(link_urls, ensure_ascii=False),
        "coupang_contexts_json": json.dumps(
            [
                {
                    "url": link["url"],
                    "anchor_text": link.get("anchor_text", ""),
                    "context_text": link.get("context_text", ""),
                }
                for link in links
            ],
            ensure_ascii=False,
        ),
        "status": status,
        "error": error,
    }
    long_rows = []
    for link_index, link in enumerate(links, start=1):
        row[f"coupang_link_{link_index}"] = link["url"]
        long_rows.append(
            {
                "source_index": source_index,
                "worker_id": worker_id,
                "source_url": url,
                "scraped_at": started,
                "link_index": link_index,
                "coupang_url": link["url"],
                "source_href": link.get("source_href", ""),
                "anchor_text": link.get("anchor_text", ""),
                "context_text": link.get("context_text", ""),
            }
        )
    return row, long_rows


def scrape_url_worker(
    worker_id: int,
    task_queue: Queue,
    *,
    total_count: int,
    headless: bool,
    debugger_address: str | None,
    wait_seconds: float,
    sleep_seconds: float,
    dom_timeout_seconds: float,
    render_timeout_seconds: float,
    driver_mode: str,
    page_load_strategy: str,
):
    rows = []
    long_rows = []
    profile_dir = tempfile.mkdtemp(prefix=f"linkscraper-worker-{worker_id}-")
    driver = None
    try:
        driver = init_driver(
            headless=headless,
            debugger_address=debugger_address,
            driver_mode=driver_mode,
            page_load_strategy=page_load_strategy,
            user_data_dir=profile_dir,
        )
    except Exception as exc:
        error = f"driver_init_error: {type(exc).__name__}: {exc}"
        print(f"[worker {worker_id}] {error}; worker stopped", flush=True)
        remove_profile_dir(profile_dir)
        return rows, long_rows

    try:
        while True:
            try:
                source_index, url = task_queue.get_nowait()
            except Empty:
                break
            started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"[worker {worker_id} #{source_index}/{total_count}] open {url}",
                flush=True,
            )
            links = []
            error = ""
            status = "completed"
            stop_worker = False
            try:
                driver.get(url)
                dom_ready = wait_for_dom(driver, dom_timeout_seconds, expected_url=url)
                if not dom_ready:
                    status = "dom_not_ready"
                    error = "target page DOM was not ready before timeout"
                    row, url_long_rows = make_result_rows(source_index, worker_id, url, started, [], status, error)
                    rows.append(row)
                    long_rows.extend(url_long_rows)
                    if sleep_seconds:
                        time.sleep(sleep_seconds)
                    task_queue.task_done()
                    continue
                render_state = wait_for_threads_render(driver, render_timeout_seconds, expected_url=url)
                if not render_state.get("hasRenderedThreadsContent"):
                    status = "content_not_ready"
                    error = (
                        "threads content was not rendered before timeout "
                        f"(readyState={render_state.get('readyState', '')}, "
                        f"anchors={render_state.get('anchorCount', 0)}, "
                        f"bodyTextLength={render_state.get('bodyTextLength', 0)})"
                    )
                    row, url_long_rows = make_result_rows(source_index, worker_id, url, started, [], status, error)
                    rows.append(row)
                    long_rows.extend(url_long_rows)
                    if sleep_seconds:
                        time.sleep(sleep_seconds)
                    task_queue.task_done()
                    continue
                dismiss_soft_popups(driver)
                if is_rate_limited(driver):
                    status = "rate_limited"
                    error = "HTTP 429 detected; stopping this worker"
                    stop_worker = True
                else:
                    links = collect_visible_coupang_links(
                        driver,
                        wait_seconds=wait_seconds,
                        scroll_if_empty=True,
                    )
                    if is_rate_limited(driver):
                        links = []
                        status = "rate_limited"
                        error = "HTTP 429 detected; stopping this worker"
                        stop_worker = True
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                status = "error"

            row, url_long_rows = make_result_rows(source_index, worker_id, url, started, links, status, error)
            rows.append(row)
            long_rows.extend(url_long_rows)

            if stop_worker:
                print(f"[worker {worker_id}] HTTP 429 at #{source_index}; worker stopped", flush=True)
                task_queue.task_done()
                break

            if sleep_seconds:
                time.sleep(sleep_seconds)
            task_queue.task_done()
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        if driver_mode == "uc":
            try:
                driver.quit = lambda *args, **kwargs: None
            except Exception:
                pass
        remove_profile_dir(profile_dir)
    return rows, long_rows


def scrape_urls(
    urls: list[str],
    *,
    headless: bool,
    debugger_address: str | None,
    wait_seconds: float,
    sleep_seconds: float,
    dom_timeout_seconds: float,
    render_timeout_seconds: float,
    workers: int,
    driver_mode: str,
    page_load_strategy: str,
    limit: int | None,
):
    selected_urls = urls[:limit] if limit else urls
    indexed_urls = list(enumerate(selected_urls, start=1))
    if debugger_address and workers > 1:
        raise ValueError("--debugger-address cannot be shared across parallel workers")

    worker_count = max(1, min(workers, len(indexed_urls)))
    task_queue = Queue()
    for item in indexed_urls:
        task_queue.put(item)

    rows = []
    long_rows = []

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                scrape_url_worker,
                worker_id,
                task_queue,
                total_count=len(indexed_urls),
                headless=headless,
                debugger_address=debugger_address if worker_count == 1 else None,
                wait_seconds=wait_seconds,
                sleep_seconds=sleep_seconds,
                dom_timeout_seconds=dom_timeout_seconds,
                render_timeout_seconds=render_timeout_seconds,
                driver_mode=driver_mode,
                page_load_strategy=page_load_strategy,
            )
            for worker_id in range(1, worker_count + 1)
        ]
        for future in as_completed(futures):
            worker_rows, worker_long_rows = future.result()
            rows.extend(worker_rows)
            long_rows.extend(worker_long_rows)

    while True:
        try:
            source_index, url = task_queue.get_nowait()
        except Empty:
            break
        row, _ = make_result_rows(
            source_index,
            0,
            url,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            [],
            "not_processed_no_active_worker",
            "no active workers remained to process this URL",
        )
        rows.append(row)
        task_queue.task_done()

    rows.sort(key=lambda row: row["source_index"])
    long_rows.sort(key=lambda row: (row["source_index"], row["link_index"]))
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
    parser.add_argument("--wait-seconds", type=float, default=0.5)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument(
        "--dom-timeout-seconds",
        "--page-shell-timeout-seconds",
        type=float,
        default=0.5,
        help="max fail-safe seconds to wait only until document DOM exists",
    )
    parser.add_argument(
        "--render-timeout-seconds",
        type=float,
        default=0.5,
        help="max event-driven seconds to wait until Threads anchors/content render",
    )
    parser.add_argument("--workers", type=int, default=15, help="parallel Chrome workers")
    parser.add_argument("--driver-mode", choices=["uc", "selenium"], default="uc")
    parser.add_argument("--page-load-strategy", choices=["normal", "eager", "none"], default="none")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--debugger-address", help="optional existing Chrome debugger address; workers must be 1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    urls = read_input_urls(input_path, url_column=args.url_column)
    if not urls:
        raise SystemExit("No Threads post URLs found in input.")
    selected_count = min(len(urls), args.limit) if args.limit else len(urls)
    print(
        " ".join(
            [
                f"input_urls={len(urls)}",
                f"selected={selected_count}",
                f"workers={args.workers}",
                f"driver={args.driver_mode}",
                f"page_load_strategy={args.page_load_strategy}",
                f"dom_timeout_seconds={args.dom_timeout_seconds}",
                f"render_timeout_seconds={args.render_timeout_seconds}",
                f"wait_seconds={args.wait_seconds}",
                f"sleep_seconds={args.sleep_seconds}",
                f"output={output_path}",
            ]
        ),
        flush=True,
    )
    rows, long_rows = scrape_urls(
        urls,
        headless=args.headless,
        debugger_address=args.debugger_address,
        wait_seconds=args.wait_seconds,
        sleep_seconds=args.sleep_seconds,
        dom_timeout_seconds=args.dom_timeout_seconds,
        render_timeout_seconds=args.render_timeout_seconds,
        workers=args.workers,
        driver_mode=args.driver_mode,
        page_load_strategy=args.page_load_strategy,
        limit=args.limit,
    )
    write_output(output_path, rows, long_rows)
    print(f"done rows={len(rows)} links={len(long_rows)} output={output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
