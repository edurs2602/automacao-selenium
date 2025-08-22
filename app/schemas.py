from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, Field, HttpUrl


class UploadItem(BaseModel):
    filename: str
    path: str | None = None
    url: HttpUrl


class DomFileOut(BaseModel):
    id: int
    filename: str
    competencia: str = Field(examples=["2025-07"])
    published_at: date | None = None
    local_path: str | None = None
    size_bytes: int | None = None
    upload_url: HttpUrl
    created_at: datetime

    class Config:
        from_attributes = True
