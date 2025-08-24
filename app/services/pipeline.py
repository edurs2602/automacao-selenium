from __future__ import annotations
import os
import json
import subprocess
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.utils.dates import Competencia
from app.database.models import DomFile
from app.crud import upsert_many
from app.services.upload import upload_for_competencia

DATA_ROOT = settings.DOWNLOAD_DIR

def _month_dir(comp: Competencia) -> Path:
    p = DATA_ROOT / comp.ym
    p.mkdir(parents=True, exist_ok=True)
    return p

def _uploads_json_path(comp: Competencia) -> Path:
    return _month_dir(comp) / "uploads.json"

def _to_items(pairs: list[tuple[Path, str]]) -> list[dict]:
    return [{"filename": p.name, "path": str(p), "url": u} for p, u in pairs if u]

def _run_scraper_for(comp: Competencia) -> None:
    env = os.environ.copy()
    env["TARGET_YEAR"]  = str(comp.year)
    env["TARGET_MONTH"] = f"{comp.month}"
    for mod in ("app.services.doc_scraper", "app.services.doc_scraper"):
        try:
            subprocess.run(
                ["python", "-m", mod],
                env=env,
                check=True,
                cwd=str(Path(__file__).resolve().parents[2])
            )
            return
        except Exception:
            continue
    raise RuntimeError("Não foi possível executar o scraper (módulo não encontrado).")


async def ensure_month_in_db(session: AsyncSession, comp: Competencia) -> tuple[str, int]:
    q = await session.execute(select(func.count(DomFile.id)).where(DomFile.competencia == comp.ym))
    count = int(q.scalar_one() or 0)
    if count > 0:
        return ("existing", count)

    _run_scraper_for(comp)

    pairs = upload_for_competencia(comp, download_root=DATA_ROOT)
    items = _to_items(pairs)

    inserted, skipped = await upsert_many(session, items)

    q2 = await session.execute(select(func.count(DomFile.id)).where(DomFile.competencia == comp.ym))
    total = int(q2.scalar_one() or 0)
    return ("created", total)


async def import_local_uploads_json(session: AsyncSession, comp: Competencia) -> tuple[int, int]:
    path = _uploads_json_path(comp)
    if not path.exists():
        raise FileNotFoundError(f"uploads.json não encontrado em {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return await upsert_many(session, payload)
