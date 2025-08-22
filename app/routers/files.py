from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.database.models import DomFile
from app.schemas import UploadItem, DomFileOut
from app.crud import upsert_many

router = APIRouter(prefix="/files", tags=["files"])

@router.post("/bulk", response_model=dict)
async def bulk_insert(payload: List[UploadItem], db: AsyncSession = Depends(get_db)):
    items = [it.model_dump() for it in payload]
    inserted, skipped = await upsert_many(db, items)
    return {"inserted": inserted, "skipped": skipped, "total": len(items)}

@router.get("", response_model=list[DomFileOut])
async def list_files(competencia: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
                     db: AsyncSession = Depends(get_db)):
    stmt = select(DomFile).order_by(DomFile.published_at.asc(), DomFile.id.asc())
    if competencia:
        stmt = stmt.where(DomFile.competencia == competencia)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    return [DomFileOut.model_validate(r) for r in rows]
