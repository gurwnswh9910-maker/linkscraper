# -*- coding: utf-8 -*-
"""Inspect one Threads page DOM around Coupang links."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import linkscraper


def parse_args():
    parser = argparse.ArgumentParser(description="Capture DOM diagnostics for one Threads URL.")
    parser.add_argument("url")
    parser.add_argument("--output-dir", default="output/dom_inspect")
    parser.add_argument("--driver-mode", choices=["selenium", "uc"], default="selenium")
    parser.add_argument("--page-load-strategy", choices=["normal", "eager", "none"], default="normal")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--wait-seconds", type=float, default=5.0)
    parser.add_argument("--scrolls", type=int, default=1)
    return parser.parse_args()


def capture(driver):
    return driver.execute_script(
        r"""
        const textOf = (el) => ((el && (el.innerText || el.textContent)) || '').trim();
        const cssPath = (el) => {
          const parts = [];
          for (let node = el; node && node.nodeType === 1 && parts.length < 8; node = node.parentElement) {
            let part = node.tagName.toLowerCase();
            const role = node.getAttribute('role');
            const aria = node.getAttribute('aria-label');
            if (role) part += `[role="${role}"]`;
            if (aria) part += `[aria-label="${aria.slice(0, 60)}"]`;
            parts.unshift(part);
          }
          return parts.join(' > ');
        };
        const anchors = Array.from(document.querySelectorAll('a')).map((a, index) => ({
          index,
          href: a.href || '',
          text: textOf(a).slice(0, 300),
          aria: (a.getAttribute('aria-label') || '').slice(0, 300),
          path: cssPath(a),
          outerHTML: a.outerHTML.slice(0, 800)
        }));
        const linkAnchors = anchors.filter(a =>
          /coupang\.com|l\.threads\.com/i.test(`${a.href} ${a.text} ${a.aria} ${a.outerHTML}`)
        );
        const contexts = linkAnchors.map((anchor) => {
          const a = document.querySelectorAll('a')[anchor.index];
          const chain = [];
          for (let node = a; node && node.nodeType === 1 && chain.length < 8; node = node.parentElement) {
            chain.push({
              tag: node.tagName.toLowerCase(),
              role: node.getAttribute('role') || '',
              aria: node.getAttribute('aria-label') || '',
              text: textOf(node).slice(0, 1200),
              html: node.outerHTML.slice(0, 1600),
              path: cssPath(node)
            });
          }
          return {anchor, chain};
        });
        return {
          url: location.href,
          title: document.title,
          readyState: document.readyState,
          bodyTextLength: textOf(document.body).length,
          bodyTextPreview: textOf(document.body).slice(0, 3000),
          anchorCount: anchors.length,
          roleCounts: Array.from(document.querySelectorAll('[role]')).reduce((acc, el) => {
            const role = el.getAttribute('role') || '';
            acc[role] = (acc[role] || 0) + 1;
            return acc;
          }, {}),
          anchors: anchors.slice(0, 200),
          linkAnchors,
          contexts
        };
        """
    )


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    driver = linkscraper.init_driver(
        headless=args.headless,
        driver_mode=args.driver_mode,
        page_load_strategy=args.page_load_strategy,
    )
    try:
        driver.get(args.url)
        linkscraper.wait_for_dom(driver, 2.0, expected_url=args.url)
        time.sleep(max(0.0, args.wait_seconds))
        for _ in range(max(0, args.scrolls)):
            linkscraper.scroll_once(driver)
            time.sleep(0.5)
        data = capture(driver)
        html = driver.page_source
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        if args.driver_mode == "uc":
            try:
                driver.quit = lambda *args, **kwargs: None
            except Exception:
                pass

    slug = args.url.rstrip("/").split("/")[-1]
    json_path = output_dir / f"{slug}.json"
    html_path = output_dir / f"{slug}.html"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(json_path),
                "html": str(html_path),
                "anchors": data["anchorCount"],
                "linkAnchors": len(data["linkAnchors"]),
                "readyState": data["readyState"],
                "bodyTextLength": data["bodyTextLength"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
