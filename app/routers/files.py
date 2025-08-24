from __future__ import annotations

"""
Endpoints para gestão dos arquivos do Diário Oficial (DOM).

Rotas:
- POST /files/bulk: insere/atualiza em massa metadados já coletados (ex.: após upload para 0x0.st).
- GET  /files: lista arquivos persistidos, opcionalmente filtrando por competência (YYYY-MM).
- POST /files/import-local: lê um JSON local com uploads e salva no banco (sem chamadas externas).
- POST /files/sync: garante que um mês esteja no banco; se faltar, dispara o scraper, importa e retorna um resumo.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.database.models import DomFile
from app.schemas import UploadItem, DomFileOut
from app.crud import upsert_many
from app.services.pipeline import ensure_month_in_db, import_local_uploads_json
from app.utils.dates import Competencia

router = APIRouter(prefix="/files", tags=["files"])


@router.post(
    "/bulk",
    response_model=dict,
    summary="Insere/Atualiza metadados de arquivos em massa.",
    description=(
        "Recebe uma lista de metadados de arquivos do Diário Oficial (DOM) e os insere ou atualiza no banco de dados. "
        "Ideal para registrar informações após um processo de upload de arquivos para um serviço de armazenamento externo. "
        "A rota retorna a contagem de itens inseridos, ignorados (já existentes) e o total."
    ),
)
async def bulk_insert(payload: List[UploadItem], db: AsyncSession = Depends(get_db)):
    items = [it.model_dump() for it in payload]
    inserted, skipped = await upsert_many(db, items)
    return {"inserted": inserted, "skipped": skipped, "total": len(items)}


@router.get(
    "",
    response_model=list[DomFileOut],
    summary="Lista os arquivos do Diário Oficial.",
    description=(
        "Retorna uma lista com os metadados de todos os arquivos do Diário Oficial persistidos no banco de dados. "
        "Permite a filtragem opcional por competência (mês e ano) no formato 'YYYY-MM'."
        "Para filtrar por mes deverá ser passado o filtro via endpoint da seguinte forma: /files?competencia=2025-07"
    ),
)
async def list_files(
    competencia: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(DomFile).order_by(DomFile.published_at.asc(), DomFile.id.asc())
    if competencia:
        stmt = stmt.where(DomFile.competencia == competencia)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    return [DomFileOut.model_validate(r) for r in rows]


def _mes_to_int(mes: str | int) -> int:
    if isinstance(mes, int):
        return mes
    mapa = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
        "outubro": 10, "novembro": 11, "dezembro": 12
    }
    m = mes.strip().lower()
    if m.isdigit():
        return int(m)
    if m not in mapa:
        raise HTTPException(status_code=422, detail=f"mes inválido: {mes}")
    return mapa[m]


@router.post(
    "/import-local",
    response_model=dict,
    summary="Importa metadados de um arquivo JSON local.",
    description=(
        "Lê um arquivo JSON local contendo metadados de uploads e os salva no banco de dados. "
        "A competência (mês/ano) pode ser informada via 'competencia=YYYY-MM' ou através dos parâmetros 'ano' e 'mes'. "
        "Esta rota não realiza chamadas externas, apenas lê o sistema de arquivos local."
    ),
)
async def import_local(
    competencia: Optional[str] = Query(None, description="Formato YYYY-MM"),
    ano: Optional[int] = Query(None),
    mes: Optional[str | int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if not competencia:
        if ano is None or mes is None:
            raise HTTPException(status_code=422, detail="Informe 'competencia=YYYY-MM' ou 'ano' e 'mes'.")
        competencia = f"{ano:04d}-{_mes_to_int(mes):02d}"

    year, month = int(competencia[:4]), int(competencia[5:7])
    comp = Competencia(year=year, month=month)

    try:
        inserted, skipped = await import_local_uploads_json(db, comp)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"competencia": comp.ym, "inserted": inserted, "skipped": skipped}


@router.post(
    "/sync",
    response_model=dict,
    summary="Sincroniza os arquivos de um período.",
    description=(
        "Garante que todos os arquivos de um determinado mês e ano (`competencia`) estejam registrados no banco de dados. "
        "Se os dados do período não forem encontrados, a rota dispara o processo de scraping para coletá-los, faz o upload e os insere no banco. "
        "Retorna um resumo da operação, incluindo o status e uma amostra dos arquivos."
    ),
)
async def sync_period(
    payload: dict = Body(..., example={"mes": "junho", "ano": 2025}),
    db: AsyncSession = Depends(get_db),
):
    if "ano" not in payload or "mes" not in payload:
        raise HTTPException(status_code=422, detail="Body deve conter 'mes' e 'ano'.")
    ano = int(payload["ano"])
    mes = _mes_to_int(payload["mes"])
    comp = Competencia(year=ano, month=mes)

    status, total = await ensure_month_in_db(db, comp)

    res = await db.execute(
        select(DomFile).where(DomFile.competencia == comp.ym).order_by(DomFile.published_at.asc(), DomFile.id.asc()).limit(5)
    )
    sample = [DomFileOut.model_validate(r) for r in res.scalars().all()]
    return {"competencia": comp.ym, "status": status, "total": total, "sample": [s.model_dump() for s in sample]}
