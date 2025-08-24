from __future__ import annotations
from datetime import datetime, date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Date, DateTime, UniqueConstraint, BigInteger


class Base(DeclarativeBase):
    pass


class DomFile(Base):
    __tablename__ = "dom_files"
    __table_args__ = (UniqueConstraint("filename", name="uq_domfile_filename"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(300), index=True)
    competencia: Mapped[str] = mapped_column(String(7), index=True)  # "YYYY-MM"
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    upload_url: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
