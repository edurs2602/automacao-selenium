from __future__ import annotations
import os, re
from datetime import date
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DomFile

FILENAME_RE = re.compile(r"dom_(\d{8})", re.I)

def _infer_meta(filename: str) -> tuple[str, date | None]:
    m = FILENAME_RE.search(filename)
    if not m:
        return ("0000-00", None)
    ymd = m.group(1)
    y = int(ymd[0:4]); mth = int(ymd[4:6]); d = int(ymd[6:8])
    try:
        pub = date(y, mth, d)
    except ValueError:
        pub = None
    return (f"{y:04d}-{mth:02d}", pub)

async def upsert_many(session: AsyncSession, items: Iterable[dict]) -> tuple[int, int]:
    inserted = skipped = 0
    for it in items:
        fn = it["filename"]; local_path = it.get("path"); url = it["url"]
        comp, pub = _infer_meta(fn)
        size = None
        if local_path and os.path.exists(local_path):
            try:
                size = Path(local_path).stat().st_size
            except OSError:
                size = None
        row = DomFile(filename=fn, competencia=comp, published_at=pub,
                      local_path=local_path, size_bytes=size, upload_url=str(url))
        session.add(row)
        try:
            await session.commit(); inserted += 1
        except IntegrityError:
            await session.rollback()
            q = await session.execute(select(DomFile).where(DomFile.filename == fn))
            existing = q.scalar_one_or_none()
            if existing:
                changed = False
                if local_path and existing.local_path != local_path:
                    existing.local_path = local_path; changed = True
                if existing.upload_url != str(url):
                    existing.upload_url = str(url); changed = True
                if size and existing.size_bytes != size:
                    existing.size_bytes = size; changed = True
                if changed:
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()
            skipped += 1
    return inserted, skipped
