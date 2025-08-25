from __future__ import annotations
import asyncio
import logging
import os
import time
import re
from pathlib import Path
from typing import Iterable
import httpx
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
)
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.webdriver.support.ui import Select, WebDriverWait
from app.config import settings
from app.utils.dates import Competencia, previous_month

LOGGER = logging.getLogger("dom_scraper")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DEBUG = (os.getenv("DEBUG") or "").lower() in {"1", "true", "yes", "on"}
DEBUG_DIR = Path("data/debug")
if DEBUG:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

def _dbg(msg: str, *args) -> None:
    if DEBUG:
        print(f"[DEBUG] " + (msg % args if args else msg))

BASE_URL = "https://www.natal.rn.gov.br/dom"
PDF_RE = re.compile(r"/storage/app/media/DOM/.+/(dom_(\d{8})[^/]*\.pdf)$", re.IGNORECASE)
TOTAL_RE = re.compile(r"de\s+(\d+)\s+registros", re.I)
_DATE_IN_NAME = re.compile(r"dom_(\d{4})(\d{2})(\d{2})", re.IGNORECASE)


def _target_competencia() -> Competencia:
    y = os.getenv("TARGET_YEAR")
    m = os.getenv("TARGET_MONTH")
    if y and m:
        return Competencia(year=int(y), month=int(m))
    return previous_month()


def _build_driver() -> WebDriver:
    opts = ChromeOptions()
    if settings.CHROME_HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    if settings.SELENIUM_REMOTE_URL:
        _dbg("Usando remoto: %s", settings.SELENIUM_REMOTE_URL)
        return webdriver.Remote(command_executor=settings.SELENIUM_REMOTE_URL, options=opts)
    _dbg("Usando Chrome local via Selenium Manager")
    return webdriver.Chrome(options=opts)


def _first_row_href(driver: WebDriver) -> str:
    try:
        a = driver.find_element(By.CSS_SELECTOR, "#example tbody tr:first-child a[href$='.pdf']")
        return (a.get_attribute("href") or "").strip()
    except NoSuchElementException:
        return ""


def _active_page_number(driver: WebDriver) -> int | None:
    try:
        active_a = driver.find_element(By.CSS_SELECTOR, "#example_paginate li.active a.page-link")
        text = (active_a.text or "").strip()
        return int(text) if text.isdigit() else None
    except NoSuchElementException:
        return None


def _is_link_of_competencia(href: str, comp) -> bool:
    h = (href or "").lower()
    m = _DATE_IN_NAME.search(h)
    if m:
        y, mm, _dd = m.groups()
        try:
            return int(y) == int(comp.year) and int(mm) == int(comp.month)
        except Exception:
            return False
    ym = f"{int(comp.year):04d}{int(comp.month):02d}"
    return ym in h


def _safe_text(el) -> str:
    try:
        t = el.text
        if not t:
            t = el.get_attribute("textContent") or ""
        return t.strip()
    except StaleElementReferenceException:
        return ""


def _paginate_texts(driver) -> list[str]:
    texts: list[str] = []
    anchors = driver.find_elements(By.CSS_SELECTOR, "#example_paginate a.page-link, #example_paginate a")
    for a in anchors:
        txt = _safe_text(a)
        if txt:
            texts.append(txt)
    return texts


def _example_info_text(driver: WebDriver) -> str:
    try:
        return driver.find_element(By.ID, "example_info").text
    except NoSuchElementException:
        return ""


def _rows_count(driver: WebDriver) -> int:
    return len(driver.find_elements(By.CSS_SELECTOR, "#example tbody tr"))


def _dump_state(driver: WebDriver, label: str) -> None:
    if not os.getenv("DEBUG"):
        return
    try:
        outdir = settings.DOWNLOAD_DIR / "debug"
        outdir.mkdir(parents=True, exist_ok=True)

        (outdir / f"{label}.html").write_text(driver.page_source, encoding="utf-8")

        try:
            driver.save_screenshot(str(outdir / f"{label}.png"))
        except Exception:
            pass

        try:
            info = driver.execute_script(
                "const e=document.querySelector('#example_info');"
                "return e? e.textContent.trim() : '';"
            ) or ""
        except Exception:
            info = ""

        try:
            pages = driver.execute_script(
                "return Array.from(document.querySelectorAll('#example_paginate a'))"
                ".map(a => (a.textContent||'').trim()).filter(Boolean);"
            ) or []
        except Exception:
            pages = []

        (outdir / f"{label}.txt").write_text(
            f"DataTables info: {info or '<vazio>'}\n"
            f"Paginação: {', '.join(pages) if pages else '<vazia>'}\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def _submit_form_month_year(driver: WebDriver, comp: Competencia) -> None:
    driver.get(BASE_URL)
    wait = WebDriverWait(driver, 30)
    form = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'form[data-request="onTest"]')))
    Select(form.find_element(By.NAME, "mes")).select_by_value(f"{comp.month:02d}")
    Select(form.find_element(By.NAME, "ano")).select_by_value(str(comp.year))
    btn = form.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
    try:
        btn.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", btn)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#result")))
    wait.until(EC.presence_of_element_located((By.ID, "example")))
    _dump_state(driver, "após-submit")
    _set_datatables_length_100(driver)
    _dump_state(driver, "após-length-100")


def _set_datatables_length_100(driver: WebDriver) -> None:
    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.ID, "example")))
    prev_first = _first_row_href(driver)
    length_select = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "select[name='example_length']")))
    current_value = (length_select.get_attribute("value") or "").strip()
    _dbg("[length] antes: value=%s, first=%s", current_value or "(vazio)", prev_first or "(vazio)")
    if current_value != "100":
        sel = Select(length_select)
        try:
            sel.select_by_value("100")
        except Exception:
            driver.execute_script(
                "arguments[0].value='100'; arguments[0].dispatchEvent(new Event('change'));",
                length_select,
            )
    _wait_processing_done(driver)
    wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "select[name='example_length']").get_attribute("value") == "100")
    wait.until(lambda d: _first_row_href(d) != prev_first or _rows_count(d) >= 1)
    _dbg("[length] depois: value=%s, first=%s",
         driver.find_element(By.CSS_SELECTOR, "select[name='example_length']").get_attribute("value"),
         _first_row_href(driver) or "(vazio)")


def _wait_processing_done(driver: WebDriver) -> None:
    try:
        processing = driver.find_element(By.ID, "example_processing")
    except NoSuchElementException:
        return
    WebDriverWait(driver, 15).until(EC.invisibility_of_element(processing))


def _has_next_page(driver: WebDriver) -> bool:
    if not driver.find_elements(By.ID, "example_paginate"):
        return False

    li_next = driver.find_elements(By.CSS_SELECTOR, "#example_paginate li.next")
    if li_next:
        classes = li_next[0].get_attribute("class") or ""
        has_link = bool(li_next[0].find_elements(By.TAG_NAME, "a"))
        return has_link and "disabled" not in classes

    for _ in range(3):
        try:
            for a in driver.find_elements(By.CSS_SELECTOR, "#example_paginate a"):
                label = ((a.text or a.get_attribute("textContent") or "")).strip().lower()
                if label in {"próximo", "proximo", "next", "»"}:
                    parent = a.find_element(By.XPATH, "./..")
                    classes = parent.get_attribute("class") or ""
                    return "disabled" not in classes
            return False
        except StaleElementReferenceException:
            time.sleep(0.2)
            continue
    return False


def _click_next_page(driver: WebDriver) -> bool:
    prev_first = _first_row_href(driver)
    prev_active = _active_page_number(driver)

    a = None
    li_next = driver.find_elements(By.CSS_SELECTOR, "#example_paginate li.next")
    if li_next and "disabled" not in (li_next[0].get_attribute("class") or ""):
        links = li_next[0].find_elements(By.TAG_NAME, "a")
        a = links[0] if links else None
    if a is None:
        for cand in driver.find_elements(By.CSS_SELECTOR, "#example_paginate a"):
            label = (cand.text or cand.get_attribute("textContent") or "").strip().lower()
            if label in {"próximo", "proximo", "next", "»"}:
                a = cand
                break
    if a is None:
        return False

    try:
        a.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", a)

    _wait_processing_done(driver)
    WebDriverWait(driver, 20).until(
        lambda d: _first_row_href(d) != prev_first or _active_page_number(d) != prev_active
    )
    return True


def _click_page_number(driver: WebDriver, page_num: int) -> bool:
    candidates = driver.find_elements(By.CSS_SELECTOR, "#example_paginate a.page-link")
    target = None
    for a in candidates:
        txt = (a.text or "").strip()
        if txt.isdigit() and int(txt) == page_num:
            target = a
            break
    if not target:
        return False
    prev_first = _first_row_href(driver)
    prev_active = _active_page_number(driver)
    try:
        target.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", target)
    _wait_processing_done(driver)
    WebDriverWait(driver, 20).until(
        lambda d: _active_page_number(d) == page_num
        or _first_row_href(d) != prev_first
        or _active_page_number(d) != prev_active
    )
    return True


def _collect_current_page_pdf_links(driver: WebDriver, comp) -> list[str]:
    try:
        urls: list[str] = driver.execute_script("""
            return Array.from(
                document.querySelectorAll('#example tbody a[href$=".pdf"]')
            ).map(a => a.href || '').filter(Boolean);
        """)
    except Exception:
        anchors = driver.find_elements(By.CSS_SELECTOR, "#example tbody a[href$='.pdf']")
        urls = []
        for a in anchors:
            try:
                href = (a.get_attribute("href") or "").strip()
                if href:
                    urls.append(href)
            except Exception:
                pass

    urls = [u for u in urls if _is_link_of_competencia(u, comp)]
    return urls


def _log_total_info(driver: WebDriver) -> None:
    try:
        info = driver.find_element(By.ID, "example_info").text
        m = TOTAL_RE.search(info)
        if m:
            LOGGER.info("Total reportado pelo DataTables: %s registros", m.group(1))
        else:
            LOGGER.info("Info DataTables: %s", info)
    except NoSuchElementException:
        pass


def _collect_all_pages_pdf_links(driver: WebDriver, comp: Competencia) -> list[str]:
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.ID, "example")))
    wait.until(EC.presence_of_element_located((By.ID, "example_paginate")))
    all_urls: list[str] = []
    current = _active_page_number(driver) or 1
    LOGGER.info("Página inicial do DataTables: %s", current)
    _dump_state(driver, f"antes-coleta-p{current}")
    urls = _collect_current_page_pdf_links(driver, comp)
    LOGGER.info("Página %s: %s PDFs (após filtro)", current, len(urls))
    all_urls.extend(urls)
    page_num = current + 1
    while True:
        clicked = _click_page_number(driver, page_num)
        if not clicked:
            break
        _dump_state(driver, f"após-click-{page_num}")
        urls = _collect_current_page_pdf_links(driver, comp)
        LOGGER.info("Página %s: %s PDFs (após filtro)", page_num, len(urls))
        all_urls.extend(urls)
        page_num += 1
    safety = 0
    while _has_next_page(driver):
        if safety > 500:
            LOGGER.warning("Parando por segurança (muitas páginas).")
            break
        if not _click_next_page(driver):
            break
        safety += 1
        active = _active_page_number(driver)
        _dump_state(driver, f"após-next-{active or safety}")
        urls = _collect_current_page_pdf_links(driver, comp)
        LOGGER.info("Página (next) %s: %s PDFs (após filtro)", active or "?", len(urls))
        all_urls.extend(urls)
    dedup = _dedup(all_urls)
    LOGGER.info("Total acumulado (dedup): %s", len(dedup))
    return dedup


def _dedup(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

async def _download_one(client: httpx.AsyncClient, url: str, out_dir: Path) -> Path | None:
    m = PDF_RE.search(url)
    if not m:
        return None
    filename = m.group(1)
    dest = out_dir / filename
    if dest.exists():
        LOGGER.info("Já existe: %s", dest.name)
        return dest
    try:
        resp = await client.get(url, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        LOGGER.warning("Falha ao baixar %s: %s", url, e)
        return None
    dest.write_bytes(resp.content)
    LOGGER.info("Baixado: %s", dest.name)
    return dest

async def _download_all(urls: Iterable[str], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        results = await asyncio.gather(*[_download_one(client, u, out_dir) for u in urls])
    return [p for p in results if p is not None]


def scrape_previous_month(download_root: Path | None = None) -> list[Path]:
    comp = _target_competencia()
    out_dir = (download_root or settings.DOWNLOAD_DIR) / comp.ym
    LOGGER.info("Competência alvo: %s", comp.ym)
    driver = _build_driver()
    try:
        _submit_form_month_year(driver, comp)
        urls = _collect_all_pages_pdf_links(driver, comp)
        if not urls:
            LOGGER.error("Nenhum PDF do mês %s encontrado.", comp.ym)
            return []
        LOGGER.info("Encontrados %d PDFs do mês %s", len(urls), comp.ym)
        return asyncio.run(_download_all(urls, out_dir))
    finally:
        driver.quit()

if __name__ == "__main__":
    saved = scrape_previous_month()
    print(f"Arquivos salvos: {len(saved)}")
    for p in saved:
        print(f"- {p}")
