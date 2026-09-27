"""비즈니스 로직 계층. 저장소를 조합해 검색/요약/입출력을 수행한다."""
from __future__ import annotations

import csv
import heapq
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import AppError, NotFoundError, ValidationError
from .models import (
    MonthlySummary,
    Transaction,
    format_id,
    id_number,
    parse_amount,
    parse_date,
    parse_tags,
    parse_type,
)
from .storage import BudgetStore, CategoryStore, TransactionRepository

CSV_COLUMNS: tuple[str, ...] = ("date", "type", "category", "amount", "memo", "tags")
CSV_REQUIRED: tuple[str, ...] = ("date", "type", "category", "amount")


@dataclass
class SearchFilter:
    date_from: str | None = None
    date_to: str | None = None
    month: str | None = None
    category: str | None = None
    type: str | None = None
    q: str | None = None
    tag: str | None = None

    def matches(self, tx: Transaction) -> bool:
        if self.date_from and tx.date < self.date_from:
            return False
        if self.date_to and tx.date > self.date_to:
            return False
        if self.month and not tx.date.startswith(self.month + "-"):
            return False
        if self.category and tx.category != self.category:
            return False
        if self.type and tx.type != self.type:
            return False
        if self.q and self.q.lower() not in tx.memo.lower():
            return False
        if self.tag and self.tag not in tx.tags:
            return False
        return True


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0


class LedgerService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.transactions = TransactionRepository(data_dir / "transactions.jsonl")
        self.categories = CategoryStore(data_dir / "categories.jsonl")
        self.budgets = BudgetStore(data_dir / "budgets.jsonl")

    def initialize(self) -> bool:
        """저장 폴더/파일이 없으면 만든다. 새로 초기화했으면 True."""
        created = not self.data_dir.exists()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.transactions.path, self.categories.path, self.budgets.path):
            path.touch(exist_ok=True)
        seeded = self.categories.ensure_defaults()
        return created or seeded

    # ---- 거래 -------------------------------------------------------------
    def require_category(self, name: str) -> str:
        name = name.strip()
        if not self.categories.exists(name):
            raise ValidationError(
                f"등록되지 않은 카테고리입니다: '{name}'",
                f"등록된 카테고리: {', '.join(self.categories.names())} "
                f"/ 새로 쓰려면 `category add --name {name or '<이름>'}`",
            )
        return name

    def add_transaction(
        self, date: str, type_: str, category: str, amount: int, memo: str = "", tags: list[str] | None = None
    ) -> Transaction:
        tx = Transaction(
            id=self.transactions.next_id(),
            type=parse_type(type_),
            date=parse_date(date),
            amount=parse_amount(amount),
            category=self.require_category(category),
            memo=memo.strip(),
            tags=tags or [],
        )
        self.transactions.add(tx)
        return tx

    def stream(self, flt: SearchFilter | None = None) -> Iterator[Transaction]:
        """조건에 맞는 거래를 한 건씩 흘려보내는 제너레이터."""
        for tx in self.transactions.iter_all():
            if flt is None or flt.matches(tx):
                yield tx

    def latest(self, flt: SearchFilter | None = None, limit: int | None = None) -> list[Transaction]:
        """최신순 정렬. limit이 있으면 heap으로 N건만 메모리에 유지한다."""
        if limit is not None:
            return heapq.nlargest(limit, self.stream(flt), key=Transaction.sort_key)
        return sorted(self.stream(flt), key=Transaction.sort_key, reverse=True)

    def get_transaction(self, tx_id: str) -> Transaction:
        tx = self.transactions.get(tx_id)
        if tx is None:
            raise NotFoundError(f"id={tx_id} 거래가 없습니다.", "`list` 또는 `search`로 id를 확인하세요.")
        return tx

    def update_transaction(
        self,
        tx_id: str,
        date: str | None = None,
        type_: str | None = None,
        category: str | None = None,
        amount: str | None = None,
        memo: str | None = None,
        tags: str | None = None,
    ) -> Transaction:
        if all(v is None for v in (date, type_, category, amount, memo, tags)):
            raise ValidationError(
                "수정할 항목이 없습니다.", "--date/--type/--category/--amount/--memo/--tags 중 하나 이상 지정하세요."
            )
        current = self.get_transaction(tx_id)
        updated = replace(
            current,
            date=parse_date(date) if date is not None else current.date,
            type=parse_type(type_) if type_ is not None else current.type,
            category=self.require_category(category) if category is not None else current.category,
            amount=parse_amount(amount) if amount is not None else current.amount,
            memo=memo.strip() if memo is not None else current.memo,
            tags=parse_tags(tags) if tags is not None else current.tags,
        )
        self.transactions.replace(updated)
        return updated

    def delete_transaction(self, tx_id: str) -> None:
        self.get_transaction(tx_id)
        self.transactions.delete(tx_id)

    # ---- 요약/예산 -----------------------------------------------------------
    def monthly_summary(self, month: str, top: int = 3) -> MonthlySummary:
        income = expense = count = 0
        by_category: dict[str, int] = defaultdict(int)
        for tx in self.stream(SearchFilter(month=month)):
            count += 1
            if tx.type == "income":
                income += tx.amount
            else:
                expense += tx.amount
                by_category[tx.category] += tx.amount
        top_categories = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)[:top]
        budget = self.budgets.get(month)
        return MonthlySummary(
            month=month,
            income=income,
            expense=expense,
            count=count,
            top_categories=top_categories,
            budget=budget.amount if budget else None,
        )

    def set_budget(self, month: str, amount: int) -> None:
        self.budgets.set(month, parse_amount(amount))

    # ---- 카테고리 ------------------------------------------------------------
    def add_category(self, name: str) -> str:
        name = name.strip()
        if not name or "," in name:
            raise ValidationError("카테고리명이 비어 있거나 쉼표(,)를 포함합니다.", "예: food")
        if self.categories.exists(name):
            raise ValidationError(f"이미 등록된 카테고리입니다: '{name}'", "`category list`로 목록을 확인하세요.")
        self.categories.add(name)
        return name

    def remove_category(self, name: str, replace_with: str | None = None) -> int:
        """카테고리를 삭제한다. 사용 중이면 replace_with가 있어야 하며, 옮긴 건수를 반환한다."""
        name = name.strip()
        if not self.categories.exists(name):
            raise NotFoundError(f"등록되지 않은 카테고리입니다: '{name}'", "`category list`로 목록을 확인하세요.")
        used = self.transactions.count_by_category(name)
        if used and replace_with is None:
            raise AppError(
                f"'{name}' 카테고리를 사용하는 거래가 {used}건 있어 삭제할 수 없습니다.",
                f"`category remove --name {name} --replace <대체카테고리>`로 옮긴 뒤 삭제하세요.",
            )
        if replace_with is not None:
            if replace_with == name:
                raise ValidationError("대체 카테고리가 삭제할 카테고리와 같습니다.", "다른 카테고리를 지정하세요.")
            self.require_category(replace_with)
            if used:
                self.transactions.reassign_category(name, replace_with)
        self.categories.remove(name)
        return used

    # ---- CSV import/export ---------------------------------------------------
    def import_csv(self, src: Path) -> tuple[ImportResult, list[str]]:
        if not src.exists():
            raise NotFoundError(f"파일을 찾을 수 없습니다: {src}", "경로를 확인하세요.")
        result = ImportResult()
        problems: list[str] = []
        categories = set(self.categories.names())
        start = id_number(self.transactions.next_id())

        with src.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            missing = [c for c in CSV_REQUIRED if c not in (reader.fieldnames or [])]
            if missing:
                raise ValidationError(
                    f"CSV 헤더에 필수 컬럼이 없습니다: {', '.join(missing)}",
                    f"헤더 예: {','.join(CSV_COLUMNS)}",
                )

            def valid_rows() -> Iterator[Transaction]:
                for lineno, row in enumerate(reader, start=2):
                    try:
                        category = (row.get("category") or "").strip()
                        if category not in categories:
                            raise ValidationError(f"등록되지 않은 카테고리 '{category}'")
                        tx = Transaction(
                            id=format_id(start + result.imported),
                            date=parse_date(row.get("date") or ""),
                            type=parse_type(row.get("type") or ""),
                            category=category,
                            amount=parse_amount(row.get("amount") or ""),
                            memo=(row.get("memo") or "").strip(),
                            tags=parse_tags(row.get("tags") or ""),
                        )
                    except ValidationError as e:
                        result.skipped += 1
                        problems.append(f"{lineno}행: {e.message}")
                        continue
                    result.imported += 1
                    yield tx

            self.transactions.add_many(valid_rows())
        return result, problems

    def export_csv(self, dest: Path, flt: SearchFilter) -> int:
        rows = sorted(self.stream(flt), key=Transaction.sort_key)
        with dest.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
            for tx in rows:
                writer.writerow([tx.date, tx.type, tx.category, tx.amount, tx.memo, ",".join(tx.tags)])
        return len(rows)
