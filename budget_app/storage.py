"""JSONL 파일 I/O 계층. 모든 읽기는 제너레이터로 한 줄씩 스트리밍한다."""
from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

from .errors import AppError
from .models import Budget, Transaction, format_id, id_number

DEFAULT_CATEGORIES: tuple[str, ...] = ("food", "transport", "rent", "salary", "etc")


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """파일을 통째로 읽지 않고 한 줄씩 dict로 yield 한다."""
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                raise AppError(
                    f"{path} 의 {lineno}번째 줄이 손상되었습니다.",
                    "해당 줄을 올바른 JSON으로 고치거나 삭제한 뒤 다시 실행하세요.",
                ) from None


def append_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def rewrite_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    """임시 파일에 전부 쓴 뒤 os.replace로 교체한다.

    쓰는 도중 실패해도 원본 파일은 그대로 남는다. records가 path를 스트리밍으로
    읽는 제너레이터여도 안전하다(원본은 교체 직전까지 건드리지 않음).
    """
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


class TransactionRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def iter_all(self) -> Iterator[Transaction]:
        for record in read_jsonl(self.path):
            yield Transaction.from_dict(record)

    def next_id(self) -> str:
        last = max((id_number(tx.id) for tx in self.iter_all()), default=0)
        return format_id(last + 1)

    def add(self, tx: Transaction) -> None:
        append_jsonl(self.path, [tx.to_dict()])

    def add_many(self, txs: Iterable[Transaction]) -> int:
        return append_jsonl(self.path, (tx.to_dict() for tx in txs))

    def get(self, tx_id: str) -> Transaction | None:
        return next((tx for tx in self.iter_all() if tx.id == tx_id), None)

    def _rewrite(self, transform: Callable[[Transaction], Transaction | None]) -> None:
        """각 거래에 transform을 적용해 재작성한다. None을 반환하면 삭제."""

        def records() -> Iterator[dict[str, Any]]:
            for tx in self.iter_all():
                result = transform(tx)
                if result is not None:
                    yield result.to_dict()

        rewrite_jsonl(self.path, records())

    def replace(self, updated: Transaction) -> None:
        self._rewrite(lambda tx: updated if tx.id == updated.id else tx)

    def delete(self, tx_id: str) -> None:
        self._rewrite(lambda tx: None if tx.id == tx_id else tx)

    def count_by_category(self, category: str) -> int:
        return sum(1 for tx in self.iter_all() if tx.category == category)

    def reassign_category(self, old: str, new: str) -> None:
        def transform(tx: Transaction) -> Transaction:
            if tx.category == old:
                tx.category = new
            return tx

        self._rewrite(transform)


class CategoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def names(self) -> list[str]:
        return [str(r["name"]) for r in read_jsonl(self.path)]

    def exists(self, name: str) -> bool:
        return any(r["name"] == name for r in read_jsonl(self.path))

    def add(self, name: str) -> None:
        append_jsonl(self.path, [{"name": name}])

    def remove(self, name: str) -> None:
        rewrite_jsonl(self.path, (r for r in read_jsonl(self.path) if r["name"] != name))

    def ensure_defaults(self) -> bool:
        """카테고리가 하나도 없으면 기본 카테고리를 만든다(안 A)."""
        if self.names():
            return False
        append_jsonl(self.path, ({"name": n} for n in DEFAULT_CATEGORIES))
        return True


class BudgetStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def all(self) -> list[Budget]:
        return [Budget(month=str(r["month"]), amount=int(r["amount"])) for r in read_jsonl(self.path)]

    def get(self, month: str) -> Budget | None:
        return next((b for b in self.all() if b.month == month), None)

    def set(self, month: str, amount: int) -> None:
        budgets = {b.month: b.amount for b in self.all()}
        budgets[month] = amount
        rewrite_jsonl(self.path, ({"month": m, "amount": a} for m, a in sorted(budgets.items())))
