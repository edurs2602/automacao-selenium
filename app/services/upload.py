from __future__ import annotations
import os
import json
import asyncio
from pathlib import Path
from typing import Iterable
import httpx
from app.config import settings
from app.utils.dates import Competencia, previous_month

UPLOAD_URL = os.getenv("UPLOAD_ENDPOINT", "https://0x0.st")


def _target_competencia() -> Competencia:
    y = os.getenv("TARGET_YEAR")
    m = os.getenv("TARGET_MONTH")
    if y and m:
        return Competencia(year=int(y), month=int(m))
    return previous_month()


def _month_dir(root: Path | None, comp: Competencia) -> Path:
    base = (root or settings.DOWNLOAD_DIR) / comp.ym
    base.mkdir(parents=True, exist_ok=True)
    return base


def _list_pdfs(dirpath: Path) -> list[Path]:
    return sorted([p for p in dirpath.glob("*.pdf") if p.is_file()])


def upload_for_competencia(comp: Competencia, download_root: Path | None = None) -> list[tuple[Path, str]]:
    month_dir = _month_dir(download_root, comp)
    pdfs = _list_pdfs(month_dir)
    if not pdfs:
        print(f"Nenhum PDF encontrado em {month_dir}")
        return []

    print(f"Enviando {len(pdfs)} arquivo(s) de {comp.ym} para {UPLOAD_URL}...")
    results = asyncio.run(_upload_many(pdfs))

    ok = [(p, u) for p, u in results if u]
    out_json = [{"filename": p.name, "path": str(p), "url": u} for p, u in ok]
    (month_dir / "uploads.json").write_text(json.dumps(out_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print("URLs públicas:")
    for _, url in ok:
        print(url)
    return ok


async def _upload_one(client: httpx.AsyncClient, path: Path, retries: int = 3) -> tuple[Path, str | None]:
    data = {"file": (path.name, path.read_bytes(), "application/pdf")}
    attempt = 0
    while True:
        try:
            resp = await client.post(UPLOAD_URL, files=data, timeout=60)
            text = resp.text.strip()
            if resp.status_code == 200 and text.startswith("http"):
                return path, text
            raise RuntimeError(f"bad response {resp.status_code}: {text[:200]}")
        except Exception:
            attempt += 1
            if attempt > retries:
                return path, None
            await asyncio.sleep(1.5 * attempt)


async def _upload_many(paths: Iterable[Path], concurrency: int = 4) -> list[tuple[Path, str | None]]:
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        async def _task(p: Path):
            async with sem:
                return await _upload_one(client, p)
        return await asyncio.gather(*(_task(p) for p in paths))


def upload_previous_month(download_root: Path | None = None) -> list[tuple[Path, str]]:
    comp = _target_competencia()
    month_dir = _month_dir(download_root, comp)
    pdfs = _list_pdfs(month_dir)
    if not pdfs:
        print(f"Nenhum PDF encontrado em {month_dir}")
        return []

    print(f"Enviando {len(pdfs)} arquivo(s) de {comp.ym} para {UPLOAD_URL}...")
    results = asyncio.run(_upload_many(pdfs))

    ok = [(p, u) for p, u in results if u]
    fail = [p for p, u in results if not u]

    out_json = [{"filename": p.name, "path": str(p), "url": u} for p, u in ok]
    (month_dir / "uploads.json").write_text(json.dumps(out_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print("URLs públicas:")
    for _, url in ok:
        print(url)

    if fail:
        print(f"Falharam {len(fail)} arquivo(s):")
        for p in fail:
            print(f"- {p.name}")

    return ok


if __name__ == "__main__":
    upload_previous_month()
