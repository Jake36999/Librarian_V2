"""Headless Playwright A7 accessibility, viewport, theme, zoom, reduced-motion, and screenshot suite."""
from __future__ import annotations

import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

EVIDENCE_DIR = Path(r"D:\Librarian_V2\reports\2026-11-19-agent-review\evidence")
OUT_JSON = EVIDENCE_DIR / "a7_playwright_report.json"

LIB_URL = "http://127.0.0.1:65414/"
GEO_BUILD_URL = "http://127.0.0.1:64181/"

VIEWPORTS = [
    ("375x812", {"width": 375, "height": 812}),
    ("768x1024", {"width": 768, "height": 1024}),
    ("1280x900", {"width": 1280, "height": 900}),
    ("1440x1000", {"width": 1440, "height": 1000}),
    ("zoom200_720x500", {"width": 720, "height": 500}),
]


def redact(text: str) -> str:
    return re.sub(r"(geo_token|token)=[A-Za-z0-9._-]+", r"\1=<REDACTED_TOKEN>", text or "")


def audit_dom(page) -> dict:
    return page.evaluate(
        """() => {
            const docEl = document.documentElement;
            const horizOverflow = docEl.scrollWidth > window.innerWidth;
            const buttons = [...document.querySelectorAll('button, [role="button"], [role="tab"], a[href], select, input')];
            const unlabelled = [];
            const missingDisabledTitle = [];
            for (const el of buttons) {
                const st = getComputedStyle(el);
                if (st.display === 'none' || st.visibility === 'hidden') continue;
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) continue;
                const txt = (el.innerText || el.textContent || el.value || el.getAttribute('placeholder') || '').trim();
                const aria = (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || '').trim();
                const title = (el.getAttribute('title') || '').trim();
                if (!txt && !aria && !title) {
                    unlabelled.push({tag: el.tagName, cls: el.className, html: el.outerHTML.slice(0, 120)});
                }
                if ((el.disabled || el.getAttribute('aria-disabled') === 'true') && !title) {
                    missingDisabledTitle.push({tag: el.tagName, text: txt || aria, cls: el.className});
                }
            }
            const headerBtns = [...document.querySelectorAll('header a, header button, .topbar button, .topbar a, nav button, nav a')]
                .filter(b => getComputedStyle(b).display !== 'none' && b.getBoundingClientRect().height > 0);
            const rowYs = [...new Set(headerBtns.map(b => Math.round(b.getBoundingClientRect().top / 8) * 8))];
            const hScrollContainers = [...document.querySelectorAll('*')].filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 40 && el.scrollWidth > el.clientWidth + 4 && getComputedStyle(el).overflowX !== 'visible';
            }).map(el => ({
                tag: el.tagName,
                cls: String(el.className || '').slice(0, 60),
                scrollW: el.scrollWidth,
                clientW: el.clientWidth,
            })).slice(0, 8);
            const landmarks = {
                main: document.querySelectorAll('main, [role="main"]').length,
                nav: document.querySelectorAll('nav, [role="navigation"]').length,
                header: document.querySelectorAll('header, [role="banner"]').length,
                h1: [...document.querySelectorAll('h1')].map(h => h.innerText.trim()),
            };
            const clippedTexts = [];
            for (const el of document.querySelectorAll('button, [role="tab"], a')) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && el.scrollWidth > el.clientWidth + 3) {
                    clippedTexts.push({text: (el.innerText||'').trim(), scrollW: el.scrollWidth, clientW: el.clientWidth});
                }
            }
            return {
                innerWidth: window.innerWidth,
                scrollWidth: docEl.scrollWidth,
                horizOverflow,
                headerButtonRowsEstimate: rowYs.length,
                unlabelledControlsCount: unlabelled.length,
                unlabelledSample: unlabelled.slice(0, 8),
                missingDisabledTitleCount: missingDisabledTitle.length,
                missingDisabledTitle: missingDisabledTitle.slice(0, 12),
                hScrollContainers,
                clippedTexts: clippedTexts.slice(0, 10),
                landmarks,
            };
        }"""
    )


def tab_order_check(page, count: int = 8) -> list[dict]:
    out = []
    for _ in range(count):
        page.keyboard.press("Tab")
        info = page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el) return null;
                const st = getComputedStyle(el);
                return {
                    tag: el.tagName,
                    role: el.getAttribute('role'),
                    text: (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim().slice(0, 50),
                    outlineStyle: st.outlineStyle,
                    outlineWidth: st.outlineWidth,
                    boxShadow: st.boxShadow !== 'none',
                };
            }"""
        )
        out.append(info)
    return out


def reduced_motion_check(page) -> list[dict]:
    return page.evaluate(
        """() => {
            const nonZero = [];
            for (const el of [...document.querySelectorAll('button, a, div, nav, aside, canvas')].slice(0, 140)) {
                const st = getComputedStyle(el);
                const td = parseFloat(st.transitionDuration || '0');
                const ad = parseFloat(st.animationDuration || '0');
                if (td > 0.01 || ad > 0.01) {
                    nonZero.push({tag: el.tagName, cls: String(el.className||'').slice(0, 40), transitionDuration: st.transitionDuration, animationDuration: st.animationDuration});
                }
            }
            return nonZero.slice(0, 10);
        }"""
    )


def nav_click(page, label: str) -> None:
    loc = page.locator(f"header >> text={label}").first
    if loc.count() == 0:
        loc = page.get_by_text(label, exact=True).locator("visible=true").first
    loc.click(timeout=5000)


def main() -> None:
    report: dict = {"librarian": {}, "geo_build": {}, "geo_accept02": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")

        # ---- 1. LIBRARIAN V2 (:65414) in DARK scheme ----
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
        page = ctx.new_page()
        page.set_default_timeout(15000)
        lib_errors = []
        page.on("pageerror", lambda e: lib_errors.append(str(e)))
        page.goto(LIB_URL, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2500)

        report["librarian"]["nav_element_tags"] = page.evaluate(
            """() => ['Chat','Staging','Search','Settings','Models'].map(t => {
                const el = [...document.querySelectorAll('a,button,[role="tab"],span')].find(x => (x.innerText||'').trim() === t && x.getBoundingClientRect().height > 0);
                return {label: t, tag: el ? el.tagName : null, role: el ? el.getAttribute('role') : null};
            })"""
        )

        report["librarian"]["viewports"] = {}
        for label, vp in VIEWPORTS:
            page.set_viewport_size(vp)
            page.wait_for_timeout(450)
            report["librarian"]["viewports"][label] = audit_dom(page)
            if label == "375x812":
                page.screenshot(path=str(EVIDENCE_DIR / "librarian-mobile-dark-375.png"))
            elif label == "1440x1000":
                page.screenshot(path=str(EVIDENCE_DIR / "librarian-chat-dark-1440.png"))

        # Staging & Search screenshots at 1440x1000
        page.set_viewport_size({"width": 1440, "height": 1000})
        nav_click(page, "Staging")
        page.wait_for_timeout(900)
        page.screenshot(path=str(EVIDENCE_DIR / "librarian-staging-dark-1440.png"))

        nav_click(page, "Search")
        page.wait_for_timeout(600)
        search_inp = page.locator("input[placeholder*='Search' i] >> visible=true").first
        if search_inp.count() == 0:
            search_inp = page.locator("input:not([type='checkbox']):not([type='radio']) >> visible=true").first
        search_inp.fill("route")
        page.locator("button:has-text('Search') >> visible=true").last.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(EVIDENCE_DIR / "librarian-search-thin-bug-1440.png"))
        report["librarian"]["search_audit_1440"] = audit_dom(page)

        # Keyboard Tab focus check
        nav_click(page, "Chat")
        page.wait_for_timeout(400)
        report["librarian"]["tab_focus"] = tab_order_check(page, 8)

        # Escape key checks on popovers/modals
        esc_results = {}
        for name, rx in [
            ("Sessions menu", r"Sessions"),
            ("Checkpoints menu", r"Checkpoints"),
            ("Attach menu", r"Attach"),
            ("Settings modal", r"^Settings$"),
        ]:
            try:
                loc = page.get_by_role("button", name=re.compile(rx)).locator("visible=true").first
                loc.click(timeout=3000)
                page.wait_for_timeout(350)
                before_text = page.locator("body").inner_text()
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                after_text = page.locator("body").inner_text()
                esc_results[name] = {"changed_after_escape": before_text != after_text}
                if before_text == after_text:
                    try:
                        loc.click(timeout=1000)
                    except Exception:
                        pass
            except Exception as ex:
                esc_results[name] = {"error": str(ex)[:150]}
        report["librarian"]["escape_key"] = esc_results

        # Open ACCEPT-02 Geo via Geo-Grapher link
        try:
            with ctx.expect_page(timeout=8000) as new_pg_info:
                page.get_by_role("button", name=re.compile(r"Geo-Grapher")).locator("visible=true").first.click()
            geo_acc = new_pg_info.value
            geo_acc.wait_for_load_state("domcontentloaded", timeout=15000)
            geo_acc.wait_for_timeout(2500)
            geo_acc.set_viewport_size({"width": 1440, "height": 1000})
            geo_acc.screenshot(path=str(EVIDENCE_DIR / "geo-accept02-paper-only-1440.png"))
            report["geo_accept02"]["audit_1440"] = audit_dom(geo_acc)
            report["geo_accept02"]["url_redacted"] = redact(geo_acc.url)
            geo_acc.close()
        except Exception as ex:
            report["geo_accept02"]["error"] = redact(str(ex))

        report["librarian"]["page_errors"] = lib_errors
        ctx.close()

        # Light theme via OS prefers-color-scheme on Librarian
        lctx = browser.new_context(viewport={"width": 1440, "height": 1000}, color_scheme="light")
        lpage = lctx.new_page()
        lpage.goto(LIB_URL, wait_until="domcontentloaded", timeout=20000)
        lpage.wait_for_timeout(1800)
        lpage.screenshot(path=str(EVIDENCE_DIR / "librarian-light-chat-1440.png"))
        report["librarian"]["light_bg"] = lpage.evaluate("() => getComputedStyle(document.body).backgroundColor")
        lctx.close()

        # Reduced motion context for Librarian
        rm_ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, color_scheme="dark", reduced_motion="reduce")
        rm_page = rm_ctx.new_page()
        rm_page.goto(LIB_URL, wait_until="domcontentloaded", timeout=20000)
        rm_page.wait_for_timeout(1500)
        report["librarian"]["reduced_motion_nonzero"] = reduced_motion_check(rm_page)
        rm_ctx.close()

        # ---- 2. GEO-GRAPHER (:64181 disposable with ingested multi-part graphs) ----
        gctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        gpage = gctx.new_page()
        gpage.set_default_timeout(15000)
        geo_errors = []
        gpage.on("pageerror", lambda e: geo_errors.append(str(e)))
        gpage.goto(GEO_BUILD_URL, wait_until="domcontentloaded", timeout=20000)
        gpage.wait_for_timeout(2500)

        try:
            sel = gpage.get_by_label("Active graph")
            opts = sel.locator("option").all_inner_texts()
            report["geo_build"]["available_graphs"] = opts
            if "app_repo" in opts:
                sel.select_option(label="app_repo")
                gpage.wait_for_timeout(1200)
        except Exception as ex:
            report["geo_build"]["select_err"] = str(ex)[:120]

        report["geo_build"]["viewports"] = {}
        for label, vp in VIEWPORTS:
            gpage.set_viewport_size(vp)
            gpage.wait_for_timeout(500)
            report["geo_build"]["viewports"][label] = audit_dom(gpage)
            if label == "375x812":
                gpage.screenshot(path=str(EVIDENCE_DIR / "geo-mobile-375.png"))
            elif label == "768x1024":
                gpage.screenshot(path=str(EVIDENCE_DIR / "geo-tablet-768.png"))
            elif label == "1440x1000":
                gpage.screenshot(path=str(EVIDENCE_DIR / "geo-build-operator-dark-1440.png"))

        gpage.set_viewport_size({"width": 1440, "height": 1000})
        report["geo_build"]["tab_focus"] = tab_order_check(gpage, 10)

        # Escape key checks in Geo
        geo_esc = {}
        for label, finder in [
            ("Legend", lambda: gpage.get_by_role("button", name="Legend").locator("visible=true").first),
            ("Scope & filters", lambda: gpage.get_by_role("button", name=re.compile(r"Scope & filters")).locator("visible=true").first),
            ("Configure rules", lambda: gpage.locator("button:has-text('Configure rules') >> visible=true").first),
            ("Settings", lambda: gpage.locator("button[aria-label*='Settings' i], button[title*='Settings' i]").locator("visible=true").first),
        ]:
            try:
                btn = finder()
                btn.click(timeout=2500)
                gpage.wait_for_timeout(300)
                before_txt = gpage.locator("body").inner_text()
                gpage.keyboard.press("Escape")
                gpage.wait_for_timeout(250)
                after_txt = gpage.locator("body").inner_text()
                geo_esc[label] = {"text_changed_on_escape": before_txt != after_txt}
                if before_txt == after_txt:
                    try:
                        btn.click(timeout=1000)
                    except Exception:
                        pass
            except Exception as ex:
                geo_esc[label] = {"error": str(ex)[:150]}
        report["geo_build"]["escape_key"] = geo_esc

        # Light theme check on Geo -> screenshot -> restore Dark
        try:
            gpage.locator("button[aria-label*='Settings' i], button[title*='Settings' i]").locator("visible=true").first.click()
            gpage.wait_for_timeout(300)
            gpage.get_by_role("button", name="Light").locator("visible=true").first.click()
            gpage.wait_for_timeout(500)
            gpage.screenshot(path=str(EVIDENCE_DIR / "geo-light-theme-1440.png"))
            report["geo_build"]["light_theme_bg"] = gpage.evaluate("() => getComputedStyle(document.body).backgroundColor")
            gpage.get_by_role("button", name="Dark").locator("visible=true").first.click()
            gpage.wait_for_timeout(300)
            gpage.locator("button[aria-label*='Settings' i], button[title*='Settings' i]").locator("visible=true").first.click()
        except Exception as ex:
            report["geo_build"]["light_theme_error"] = str(ex)[:150]

        report["geo_build"]["page_errors"] = geo_errors
        gctx.close()

        grm = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
        gp2 = grm.new_page()
        gp2.goto(GEO_BUILD_URL, wait_until="domcontentloaded", timeout=20000)
        gp2.wait_for_timeout(1500)
        report["geo_build"]["reduced_motion_nonzero"] = reduced_motion_check(gp2)
        grm.close()

        browser.close()

    OUT_JSON.write_text(redact(json.dumps(report, indent=2)), encoding="utf-8")
    print(f"Saved {OUT_JSON}")


if __name__ == "__main__":
    main()
