# app/main.py
from __future__ import annotations
from fastapi import FastAPI
from app.database.db import engine
from app.database.models import Base
from app.routers.files import router as files_router

app = FastAPI(title="DOM Files API")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(files_router)

@app.get("/health")
async def health():
    return {"ok": True}
