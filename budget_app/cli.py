"""CLI 계층: 인자 파싱, 대화형 입력, 출력 포맷만 담당한다."""
from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeVar

from .decorators import EXIT_OK, handle_errors, log_execution, print_error
from .errors import ValidationError
from .models import TX_TYPES, MonthlySummary, Transaction, parse_amount, parse_date, parse_month, parse_tags, parse_type
from .services import LedgerService, SearchFilter

T = TypeVar("T")
DEFAULT_DATA_DIR = "./data"
DEFAULT_LIST_LIMIT = 20


# ---- 공통 헬퍼 -------------------------------------------------------------
def get_service(args: argparse.Namespace) -> LedgerService:
    service = LedgerService(Path(args.data_dir))
    if service.initialize():
        print(
            f"[안내] 저장 폴더를 초기화했습니다: {args.data_dir} "
            f"(기본 카테고리: {', '.join(service.categories.names())})"
        )
    return service


def ask(prompt: str, parse: Callable[[str], T]) -> T:
    """검증에 통과할 때까지 재입력을 요구한다."""
    while True:
        try:
            return parse(input(prompt))
        except ValidationError as e:
            print_error(e.message, e.hint)


def format_tx(tx: Transaction) -> str:
    line = f"{tx.id} | {tx.date} | {tx.type} | {tx.category} | {tx.amount} | {tx.memo}"
    if tx.tags:
        line += " | " + " ".join(f"#{t}" for t in tx.tags)
    return line


def print_transactions(txs: list[Transaction]) -> None:
    if not txs:
        print("(조회된 거래가 없습니다)")
        return
    for tx in txs:
        print(format_tx(tx))


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"정수가 아닙니다: {value}") from None
    if number <= 0:
        raise argparse.ArgumentTypeError(f"1 이상이어야 합니다: {value}")
    return number


def build_filter(args: argparse.Namespace) -> SearchFilter:
    return SearchFilter(
        date_from=parse_date(args.date_from) if getattr(args, "date_from", None) else None,
        date_to=parse_date(args.date_to) if getattr(args, "date_to", None) else None,
        month=parse_month(args.month) if getattr(args, "month", None) else None,
        category=getattr(args, "category", None),
        type=getattr(args, "type", None),
        q=getattr(args, "q", None),
        tag=getattr(args, "tag", None),
    )


def command(func: Callable[[argparse.Namespace], int]) -> Callable[[argparse.Namespace], int]:
    """모든 명령 핸들러에 적용하는 데코레이터 묶음."""
    return log_execution(handle_errors(func))


# ---- 명령 핸들러 -------------------------------------------------------------
@command
def cmd_add(args: argparse.Namespace) -> int:
    service = get_service(args)
    date = ask("날짜(YYYY-MM-DD): ", parse_date)
    type_ = ask("타입(income/expense): ", parse_type)
    category = ask(f"카테고리({', '.join(service.categories.names())}): ", service.require_category)
    amount = ask("금액(양수): ", parse_amount)
    memo = input("메모(선택): ")
    tags = parse_tags(input("태그(쉼표로 구분, 없으면 엔터): "))
    tx = service.add_transaction(date, type_, category, amount, memo, tags)
    print(f"[저장 완료] id={tx.id}")
    return EXIT_OK


@command
def cmd_list(args: argparse.Namespace) -> int:
    service = get_service(args)
    print_transactions(service.latest(limit=args.limit))
    return EXIT_OK


@command
def cmd_search(args: argparse.Namespace) -> int:
    service = get_service(args)
    print_transactions(service.latest(build_filter(args), limit=args.limit))
    return EXIT_OK


@command
def cmd_summary(args: argparse.Namespace) -> int:
    service = get_service(args)
    summary = service.monthly_summary(parse_month(args.month), top=args.top)
    print_summary(summary)
    return EXIT_OK


def print_summary(s: MonthlySummary) -> None:
    print(f"[{s.month} 요약]")
    if s.count == 0:
        print("데이터 없음")
    else:
        print(f"총 수입: {s.income}원")
        print(f"총 지출: {s.expense}원")
        print(f"잔액: {s.balance}원")
    if s.budget is not None:
        print(f"예산: {s.budget}원 (사용률 {s.usage_rate:.1f}%)")
        if s.over_budget:
            print(f"[경고] 예산을 {s.expense - s.budget}원 초과했습니다!")
    if s.count and s.top_categories:
        print()
        print(f"지출 TOP {len(s.top_categories)}")
        for rank, (category, total) in enumerate(s.top_categories, start=1):
            print(f"{rank}) {category} {total}원")


@command
def cmd_budget_set(args: argparse.Namespace) -> int:
    service = get_service(args)
    month = parse_month(args.month)
    amount = parse_amount(args.amount)
    service.set_budget(month, amount)
    print(f"[저장 완료] {month} 예산 {amount}원")
    return EXIT_OK


@command
def cmd_budget_show(args: argparse.Namespace) -> int:
    service = get_service(args)
    if args.month:
        budget = service.budgets.get(parse_month(args.month))
        budgets = [budget] if budget else []
    else:
        budgets = service.budgets.all()
    if not budgets:
        print("(설정된 예산이 없습니다)")
    for b in budgets:
        print(f"{b.month}: {b.amount}원")
    return EXIT_OK


@command
def cmd_category_add(args: argparse.Namespace) -> int:
    service = get_service(args)
    name = args.name if args.name is not None else input("카테고리명: ")
    name = service.add_category(name)
    print(f"[저장 완료] category={name}")
    return EXIT_OK


@command
def cmd_category_list(args: argparse.Namespace) -> int:
    service = get_service(args)
    for name in service.categories.names():
        print(f"- {name}")
    return EXIT_OK


@command
def cmd_category_remove(args: argparse.Namespace) -> int:
    service = get_service(args)
    name = args.name if args.name is not None else input("삭제할 카테고리명: ")
    moved = service.remove_category(name, args.replace)
    suffix = f" (거래 {moved}건을 '{args.replace}'로 이동)" if moved else ""
    print(f"[삭제 완료] category={name.strip()}{suffix}")
    return EXIT_OK


@command
def cmd_update(args: argparse.Namespace) -> int:
    service = get_service(args)
    tx = service.update_transaction(
        args.id,
        date=args.date,
        type_=args.type,
        category=args.category,
        amount=args.amount,
        memo=args.memo,
        tags=args.tags,
    )
    print(f"[수정 완료] {format_tx(tx)}")
    return EXIT_OK


@command
def cmd_delete(args: argparse.Namespace) -> int:
    service = get_service(args)
    service.delete_transaction(args.id)
    print(f"[삭제 완료] id={args.id}")
    return EXIT_OK


@command
def cmd_import(args: argparse.Namespace) -> int:
    service = get_service(args)
    result, problems = service.import_csv(Path(args.src))
    for problem in problems:
        print(f"[건너뜀] {problem}")
    print(f"[완료] imported={result.imported}, skipped={result.skipped}")
    return EXIT_OK


@command
def cmd_export(args: argparse.Namespace) -> int:
    if not (args.month or args.date_from or args.date_to):
        raise ValidationError(
            "export에는 기간 조건이 필요합니다.", "--month YYYY-MM 또는 --from YYYY-MM-DD --to YYYY-MM-DD 를 지정하세요."
        )
    service = get_service(args)
    count = service.export_csv(Path(args.out), build_filter(args))
    print(f"[완료] {args.out} ({count} records)")
    return EXIT_OK


# ---- 파서 구성 ---------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    # 서브커맨드 뒤에서도 --data-dir 를 쓸 수 있게 공통 부모 파서를 둔다.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", default=argparse.SUPPRESS, help=f"저장 폴더 (기본: {DEFAULT_DATA_DIR})")

    parser = argparse.ArgumentParser(prog="python -m budget_app", description="파일 기반 콘솔 가계부")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help=f"저장 폴더 (기본: {DEFAULT_DATA_DIR})")
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    def add_cmd(target: argparse._SubParsersAction, name: str, help_: str, handler: Callable[..., int]) -> argparse.ArgumentParser:
        p = target.add_parser(name, parents=[common], help=help_, description=help_)
        p.set_defaults(handler=handler)
        return p

    add_cmd(sub, "add", "거래 추가 (대화형 입력)", cmd_add)

    p = add_cmd(sub, "list", "거래 목록 (최신순)", cmd_list)
    p.add_argument("--limit", type=positive_int, default=DEFAULT_LIST_LIMIT, help=f"출력 건수 (기본: {DEFAULT_LIST_LIMIT})")

    p = add_cmd(sub, "search", "조건 검색 (최신순)", cmd_search)
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="시작일(포함)")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="종료일(포함)")
    p.add_argument("--category", help="카테고리 일치")
    p.add_argument("--type", choices=TX_TYPES, help="거래 타입")
    p.add_argument("--q", help="메모 키워드(대소문자 무시)")
    p.add_argument("--tag", help="태그 일치")
    p.add_argument("--limit", type=positive_int, default=None, help="최대 출력 건수 (기본: 전체)")

    p = add_cmd(sub, "summary", "월별 요약 + 예산 사용률", cmd_summary)
    p.add_argument("--month", required=True, metavar="YYYY-MM")
    p.add_argument("--top", type=positive_int, default=3, help="카테고리별 지출 TOP N (기본: 3)")

    budget = sub.add_parser("budget", parents=[common], help="월 예산 설정/조회", description="월 예산 설정/조회")
    budget_sub = budget.add_subparsers(dest="action", metavar="<action>", required=True)
    p = add_cmd(budget_sub, "set", "월 예산 저장", cmd_budget_set)
    p.add_argument("--month", required=True, metavar="YYYY-MM")
    p.add_argument("--amount", required=True, help="예산 금액(양수 정수)")
    p = add_cmd(budget_sub, "show", "예산 조회", cmd_budget_show)
    p.add_argument("--month", metavar="YYYY-MM", help="특정 월만 조회 (생략 시 전체)")

    category = sub.add_parser("category", parents=[common], help="카테고리 관리", description="카테고리 관리")
    category_sub = category.add_subparsers(dest="action", metavar="<action>", required=True)
    p = add_cmd(category_sub, "add", "카테고리 추가 (--name 생략 시 대화형)", cmd_category_add)
    p.add_argument("--name")
    add_cmd(category_sub, "list", "카테고리 목록", cmd_category_list)
    p = add_cmd(category_sub, "remove", "카테고리 삭제 (사용 중이면 --replace 필요)", cmd_category_remove)
    p.add_argument("--name")
    p.add_argument("--replace", metavar="CATEGORY", help="사용 중인 거래를 옮길 대체 카테고리")

    p = add_cmd(sub, "update", "거래 수정 (옵션 방식, 지정한 필드만 변경)", cmd_update)
    p.add_argument("--id", required=True)
    p.add_argument("--date", metavar="YYYY-MM-DD")
    p.add_argument("--type", choices=TX_TYPES)
    p.add_argument("--category")
    p.add_argument("--amount")
    p.add_argument("--memo", help='빈 문자열("")이면 메모 삭제')
    p.add_argument("--tags", help='쉼표 구분, 빈 문자열("")이면 태그 삭제')

    p = add_cmd(sub, "delete", "거래 삭제", cmd_delete)
    p.add_argument("--id", required=True)

    p = add_cmd(sub, "import", "CSV에서 거래 일괄 등록", cmd_import)
    p.add_argument("--from", dest="src", required=True, metavar="CSV")

    p = add_cmd(sub, "export", "조건에 맞는 거래를 CSV로 저장", cmd_export)
    p.add_argument("--out", required=True, metavar="CSV")
    p.add_argument("--month", metavar="YYYY-MM")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)
