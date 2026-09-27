"""데이터 모델과 필드 단위 검증 함수."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .errors import ValidationError

TX_TYPES: tuple[str, ...] = ("income", "expense")
ID_PREFIX = "TX-"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def parse_date(value: str) -> str:
    value = value.strip()
    try:
        if not _DATE_RE.match(value):
            raise ValueError
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValidationError("날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).", "예: 2024-01-15") from None
    return value


def parse_month(value: str) -> str:
    value = value.strip()
    try:
        if not _MONTH_RE.match(value):
            raise ValueError
        datetime.strptime(value, "%Y-%m")
    except ValueError:
        raise ValidationError("월 형식이 올바르지 않습니다 (YYYY-MM).", "예: 2024-01") from None
    return value


def parse_type(value: str) -> str:
    value = value.strip().lower()
    if value not in TX_TYPES:
        raise ValidationError(f"허용되지 않은 타입입니다: '{value}'", "income 또는 expense 중 하나를 입력하세요.")
    return value


def parse_amount(value: str | int) -> int:
    try:
        amount = int(str(value).strip())
    except ValueError:
        raise ValidationError(f"금액은 정수여야 합니다: '{value}'", "예: 15000 (쉼표/단위 없이 숫자만)") from None
    if amount <= 0:
        raise ValidationError("금액은 0보다 큰 양수여야 합니다.", "예: 15000")
    return amount


def parse_tags(value: str) -> list[str]:
    return [t.strip() for t in value.split(",") if t.strip()]


def id_number(tx_id: str) -> int:
    try:
        return int(tx_id.removeprefix(ID_PREFIX))
    except ValueError:
        return 0


def format_id(number: int) -> str:
    return f"{ID_PREFIX}{number:06d}"


@dataclass
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transaction:
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            date=str(data["date"]),
            amount=int(data["amount"]),
            category=str(data["category"]),
            memo=str(data.get("memo", "")),
            tags=list(data.get("tags", [])),
        )

    def sort_key(self) -> tuple[str, int]:
        """최신순 정렬 키: 날짜 → 같은 날짜면 나중에 생성된 id."""
        return (self.date, id_number(self.id))


@dataclass
class Budget:
    month: str
    amount: int


@dataclass
class MonthlySummary:
    month: str
    income: int
    expense: int
    count: int
    top_categories: list[tuple[str, int]]
    budget: int | None = None

    @property
    def balance(self) -> int:
        return self.income - self.expense

    @property
    def usage_rate(self) -> float | None:
        if not self.budget:
            return None
        return self.expense / self.budget * 100

    @property
    def over_budget(self) -> bool:
        return self.budget is not None and self.expense > self.budget
