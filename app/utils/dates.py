from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


_PT_MONTHS = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


@dataclass(frozen=True)
class Competencia:
    year: int
    month: int

    @property
    def ym(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def yyyymm(self) -> str:
        return f"{self.year:04d}{self.month:02d}"

    @property
    def month_name_pt(self) -> str:
        return _PT_MONTHS[self.month - 1]


def previous_month(today: date | None = None) -> Competencia:
    if today is None:
        today = date.today()
    first = today.replace(day=1)
    last_prev = first - timedelta(days=1)
    return Competencia(year=last_prev.year, month=last_prev.month)
