# 콘솔 가계부 (budget_app)

파일(JSONL) 기반으로 수입/지출을 기록하는 Python 콘솔 가계부입니다.
표준 라이브러리만 사용하며, 저장 파일은 제너레이터로 한 줄씩 스트리밍 처리합니다.

> 📸 실제 Windows 실행 결과는 **[평가 항목 1 실행 증빙 및 설명](docs/EXECUTION_EVIDENCE.md)**에서 확인할 수 있습니다.
> 🧭 구조·설계 근거(평가 항목 2~4)는 이 문서 하단의 **[설계 설명](#설계-설명-평가-항목-24)**에 정리했습니다.

## 실행 방법

- Python 3.10 이상, 별도 설치 불필요

```bash
python -m budget_app <command> [options]
python -m budget_app --help            # 전체 명령 목록
python -m budget_app <command> --help  # 명령별 사용법
```

- 모든 명령에서 `--data-dir <경로>`로 저장 폴더를 바꿀 수 있습니다 (기본값 `./data`).
  `python -m budget_app --data-dir ./mydata list`, `python -m budget_app list --data-dir ./mydata` 둘 다 가능합니다.
- 종료 코드: 정상 `0`, 오류 `1`, 인자 오류 `2`(argparse), 입력 중단(Ctrl+C/EOF) `130`
- 오류는 스택트레이스 없이 `[오류] 원인` + `[힌트] 해결 방법` 형태로 출력합니다.

## 저장 파일 위치/형식

기본 위치는 `./data/`이며, 형식은 **JSONL**(UTF-8, 한 줄에 JSON 객체 하나)입니다.

| 파일 | 내용 | 한 줄 예시 |
| --- | --- | --- |
| `transactions.jsonl` | 거래 내역 | `{"id": "TX-000001", "type": "expense", "date": "2024-01-15", "amount": 15000, "category": "food", "memo": "점심", "tags": ["meal"]}` |
| `categories.jsonl` | 카테고리 목록 | `{"name": "food"}` |
| `budgets.jsonl` | 월 예산 | `{"month": "2024-01", "amount": 500000}` |
| `app.log` | 명령 실행 로그(데코레이터) | `2024-01-15T12:00:00 command=list exit=0 elapsed=1.2ms` |

- **초기 실행**: 폴더/파일이 없으면 자동 생성하고 안내 메시지를 출력합니다.
- **기본 카테고리(안 A)**: 카테고리 파일이 비어 있으면 `food, transport, rent, salary, etc`를 자동 생성합니다.
- **수정/삭제 안정성**: `update`/`delete`/카테고리 대체는 원본을 스트리밍으로 읽으며 임시 파일에 전체를 다시 쓴 뒤 `os.replace`로 교체합니다. 쓰는 도중 실패해도 원본은 그대로 남습니다.

## 주요 명령 예시

```bash
# 거래 추가 (대화형: 날짜 → 타입 → 카테고리 → 금액 → 메모 → 태그, 잘못 입력하면 재입력)
python -m budget_app add

# 목록 (최신순, 기본 20건)
python -m budget_app list --limit 3

# 검색 (조건은 모두 선택, 조합 가능 / 최신순)
python -m budget_app search --from 2024-01-01 --to 2024-01-31 --type expense
python -m budget_app search --category food --q 점심 --tag meal --limit 10

# 월별 요약 (총수입/총지출/잔액 + 지출 TOP N, 예산이 있으면 사용률/초과 경고)
python -m budget_app summary --month 2024-01 --top 3

# 예산
python -m budget_app budget set --month 2024-01 --amount 500000
python -m budget_app budget show [--month 2024-01]

# 카테고리 (--name 생략 시 대화형으로 입력)
python -m budget_app category add --name hobby
python -m budget_app category list
python -m budget_app category remove --name hobby
python -m budget_app category remove --name food --replace dining   # 사용 중이면 대체 카테고리 필수

# 수정 (옵션 방식으로 고정: 지정한 필드만 변경)
python -m budget_app update --id TX-000003 --amount 13000 --memo "점심(수정)" --tags "meal,lunch"
python -m budget_app update --id TX-000003 --tags ""      # 빈 문자열이면 태그 비우기

# 삭제
python -m budget_app delete --id TX-000003

# 가져오기/내보내기
python -m budget_app import --from samples/import_sample.csv
python -m budget_app export --out export.csv --month 2024-01
python -m budget_app export --out export.csv --from 2024-01-01 --to 2024-03-31
```

### 명령 정책 요약

- `update`: **옵션 방식(안 A)** — `update --id <id> [--date] [--type] [--category] [--amount] [--memo] [--tags]`
- 없는 id로 `update`/`delete` 하면 `[오류] id=... 거래가 없습니다.`를 출력하고 종료 코드 1
- `category remove`: 해당 카테고리를 쓰는 거래가 있으면 삭제를 막고, `--replace <대체>`를 주면 거래를 옮긴 뒤 삭제
- `export`: `--month` 또는 `--from`/`--to` 중 하나 이상 필수
- `import`: 행 단위로 검증해 잘못된 행(날짜/타입/금액 오류, 미등록 카테고리)은 건너뛰고 사유를 출력

## import/export CSV 스키마

UTF-8, 헤더 포함 (import는 BOM이 있는 UTF-8도 허용)

| column | required | 설명 |
| --- | --- | --- |
| date | Y | YYYY-MM-DD |
| type | Y | income / expense |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표(,) 구분 문자열 (CSV 안에서는 `"meal,team"`처럼 따옴표로 감쌈) |

```csv
date,type,category,amount,memo,tags
2024-01-01,income,salary,3000000,1월 월급,
2024-01-10,expense,food,33000,저녁 회식,"meal,team"
```

id는 CSV에 포함하지 않으며 import 시 새로 발급됩니다.

## 구조

```
budget_app/
├── __main__.py    # 진입점 (python -m budget_app)
├── cli.py         # CLI 계층: argparse, 대화형 입력, 출력 포맷
├── services.py    # 서비스 계층: 검색 필터, 월별 요약, 카테고리 정책, CSV 입출력
├── storage.py     # 저장소 계층: JSONL 스트리밍 읽기/추가/원자적 재작성, Repository/Store 클래스
├── models.py      # 모델 계층: Transaction/Budget/MonthlySummary dataclass + 필드 검증
├── decorators.py  # 공통 관심사: @handle_errors(예외→원인+힌트, 종료코드), @log_execution(실행 로그/시간)
└── errors.py      # AppError / ValidationError / NotFoundError
```

- **제너레이터 스트리밍**: `read_jsonl()`이 파일을 한 줄씩 `yield`하고, `TransactionRepository.iter_all()` → `LedgerService.stream(filter)`로 이어집니다. `list --limit N`은 `heapq.nlargest`로 N건만 메모리에 유지합니다.
- **데코레이터**: 모든 명령 핸들러에 `@command`(= `log_execution(handle_errors(...))`)를 적용해, 핸들러는 정상 흐름만 작성합니다.
- **타입 힌트**: 모든 함수/데이터 구조에 타입을 명시했습니다 (예: `def latest(self, flt: SearchFilter | None = None, limit: int | None = None) -> list[Transaction]`).

---

## 설계 설명 (평가 항목 2~4)

### 항목 2. 모듈·클래스 책임과 안전한 update/delete

#### 2-1. 모듈 분리 기준: "무엇을 바꿀 때 어느 파일만 고치면 되는가"

코드를 6개 모듈로 나누고, 바뀌는 이유가 같은 코드끼리 모았습니다.

| 모듈 | 책임 | 모르는 것(의존하지 않는 것) |
| --- | --- | --- |
| `cli.py` | 인자 파싱, 대화형 입력, 출력 포맷 | 파일 경로·저장 형식 |
| `services.py` | 업무 규칙: 검색 조건, 월 요약, 카테고리 정책, CSV 입출력 | 화면 출력, argparse |
| `storage.py` | JSONL 읽기/추가/원자적 재작성, id 발급 | 업무 규칙(예: 사용 중 카테고리 삭제 금지) |
| `models.py` | 데이터 구조(dataclass)와 필드 단위 검증 | 파일 I/O, 화면 |
| `decorators.py` | 공통 관심사: 예외→메시지/종료 코드, 실행 로그 | 각 명령의 내용 |
| `errors.py` | 사용자에게 보여줄 예외 타입(원인 + 힌트) | 다른 모든 모듈 |

의존 방향은 `cli → services → storage → models → errors`의 한 방향뿐이고, 순환 참조가 없습니다. 실제 import 문으로 확인할 수 있습니다(`grep "^from \." budget_app/*.py`).

- `cli.py`는 `storage`를 import하지 않으므로, 화면에서 파일을 직접 건드릴 수 없습니다.
- 저장 형식을 SQLite로 바꾸더라도 `storage.py`만 교체하면 됩니다.
- 출력 문구를 바꿀 때는 `cli.py`만 수정하면 됩니다.

#### 2-2. 클래스 책임 경계: "어떻게 저장하는가" vs "무엇이 허용되는가"

| 클래스 | 경계 |
| --- | --- |
| `TransactionRepository` / `CategoryStore` / `BudgetStore` | 파일을 **어떻게** 읽고 쓰는지만 압니다. 규칙 판단은 하지 않습니다. 예를 들어 `CategoryStore.remove()`는 사용 중인지 묻지 않고 그냥 지웁니다. |
| `LedgerService` | **무엇이 허용되는지** 판단합니다. 저장소 3개를 조합해 "등록된 카테고리만 사용", "사용 중 카테고리는 `--replace` 없이 삭제 불가", "수정할 필드가 하나 이상 필요" 같은 규칙을 적용합니다. |
| `SearchFilter` | 검색 조건을 담은 값 객체입니다. `matches(tx)` 하나로 "이 거래가 조건에 맞는가"만 판단하는 순수 함수라, 파일 없이도 검증할 수 있습니다. |
| `Transaction` / `Budget` / `MonthlySummary` | 데이터와 파생 값만 가집니다. 잔액·사용률·초과 여부는 `MonthlySummary`의 `@property`로 계산하므로 저장 시점과 값이 어긋날 일이 없습니다. |
| `AppError` → `ValidationError` / `NotFoundError` | 서비스는 상황에 맞는 예외만 던지고, 출력 방식은 데코레이터가 정합니다. |

예를 들어 `category remove --name food`가 거부되는 판단은 `LedgerService.remove_category()`에 있습니다. 실제로 지우는 동작은 `CategoryStore.remove()`가 하고, 거래를 옮기는 동작은 `TransactionRepository.reassign_category()`가 합니다. 규칙이 바뀌면 서비스만, 저장 방식이 바뀌면 저장소만 고치면 됩니다.

#### 2-3. 파일 기반 update/delete를 안전하게 처리한 방법

JSONL은 중간 한 줄만 고칠 수 없으므로 파일 전체를 다시 써야 합니다. 원본을 직접 덮어쓰다가 실패하면 데이터가 반쯤 사라집니다. 그래서 `storage.rewrite_jsonl()`은 다음 순서로 처리합니다.

1. **먼저 검증**합니다. `update_transaction()`은 대상 id가 존재하는지(`NotFoundError`)와 새 값(`parse_date`, `parse_amount` 등)을 파일을 건드리기 전에 확인합니다. 잘못된 입력이면 파일은 전혀 바뀌지 않습니다.
2. **같은 폴더에 임시 파일**(`tempfile.mkstemp(dir=path.parent)`)을 만들고, 원본을 한 줄씩 읽으면서 수정된 결과를 임시 파일에 씁니다. 이 동안 원본은 읽기만 합니다.
3. 끝까지 쓰면 `os.replace(임시, 원본)`로 **한 번에 교체**합니다. 같은 파일 시스템 안의 rename이므로 원자적으로 처리되어, 다른 프로세스는 "이전 파일" 아니면 "완성된 새 파일"만 보게 됩니다.
4. 중간에 예외가 나면 Ctrl+C(`KeyboardInterrupt`)를 포함한 모든 경우(`except BaseException`)에 임시 파일을 지우고 예외를 다시 던집니다. **원본은 그대로** 남습니다.

같은 방식을 카테고리 이동(`reassign_category`), 카테고리 삭제, 예산 덮어쓰기에도 사용합니다.

한계도 있습니다. 파일 잠금이 없어서 두 프로세스가 동시에 수정하면 나중에 끝난 쪽이 이깁니다. 또 `fsync`를 하지 않으므로 정전 같은 OS 수준 장애까지 보장하지는 않습니다. 콘솔 단일 사용자 앱이라는 전제에서 받아들인 한계입니다.

### 항목 3. 제너레이터 · 데코레이터 · 타입 힌트

#### 3-1. list/search를 제너레이터로 스트리밍 처리한 방식과 장점

읽기는 세 단계 제너레이터 파이프라인으로 이어지고, 어느 단계도 파일 전체를 리스트로 만들지 않습니다.

```python
# storage.py: 파일을 한 줄씩 dict로
def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            ...
            yield json.loads(line)

# storage.py: dict → Transaction
def iter_all(self) -> Iterator[Transaction]:
    for record in read_jsonl(self.path):
        yield Transaction.from_dict(record)

# services.py: 조건에 맞는 것만 통과
def stream(self, flt: SearchFilter | None = None) -> Iterator[Transaction]:
    for tx in self.transactions.iter_all():
        if flt is None or flt.matches(tx):
            yield tx
```

마지막 소비 단계에서도 전체를 모으지 않습니다.

- `list --limit N`과 `search --limit N`은 `heapq.nlargest(N, stream(...))`로 **최신 N건만** 힙에 유지합니다.
- `summary`는 스트림을 돌며 합계와 카테고리별 합만 누적합니다.
- `get(id)`은 `next(...)`로 **찾는 즉시 읽기를 멈춥니다**.
- update/delete의 재작성과 import의 행 추가도 제너레이터를 그대로 파일 쓰기에 넘깁니다.

**왜 유리한가.** 거래 10만 건(JSONL 12.9MB)으로 직접 측정한 결과입니다(`tracemalloc` 최대 메모리).

| 처리 | 최대 메모리 |
| --- | --- |
| `list --limit 20` (스트림 + 힙) | **0.06 MB** |
| `summary --month 2024-06` (스트림 누적) | **0.05 MB** |
| 전체를 정렬해 메모리에 올리는 경우 (`latest()` limit 없음) | 57.09 MB |

데이터가 늘어도 메모리 사용량은 거의 일정합니다. 또 같은 `stream()`에 필터만 바꿔 끼우면 list, search, summary, export가 모두 동작하므로 읽기 코드를 한 곳에서 관리할 수 있습니다.

`search`에서 `--limit`을 생략하면 전체 정렬을 위해 결과를 모두 메모리에 올립니다. 그래서 기본 `list`는 `--limit 20`을 기본값으로 둡니다.

#### 3-2. 데코레이터로 분리한 공통 기능과 분리한 이유

| 데코레이터 | 공통 기능 |
| --- | --- |
| `@handle_errors` | `AppError` → `[오류] 원인` + `[힌트] 해결`, 종료 코드 1<br>`KeyboardInterrupt`/`EOFError` → `[중단]`, 종료 코드 130<br>`OSError`와 예상 못한 예외 → 스택트레이스 없이 메시지만 |
| `@log_execution` | 명령명, 종료 코드, 실행 시간(ms)을 `<data-dir>/app.log`에 한 줄 기록. 로그 쓰기가 실패해도 본 기능은 막지 않음 |
| `@command` | 위 두 개를 묶은 것(`log_execution(handle_errors(f))`). 13개 명령 핸들러 모두에 적용 |

**왜 분리했는가.**

- 예외 처리와 로그는 모든 명령에 똑같이 필요하지만 각 명령의 본래 일과는 관계가 없습니다. 핸들러마다 `try/except`와 시간 측정을 넣으면 13번 중복되고, 하나라도 빠뜨리면 그 명령만 스택트레이스를 내거나 로그가 비게 됩니다.
- 데코레이터로 빼면 핸들러에는 정상 흐름만 남습니다. 예를 들어 `cmd_delete`는 4줄이고, 오류 형식이나 종료 코드 정책도 한 곳(`decorators.py`)만 고치면 됩니다.
- 순서도 의도한 것입니다. `log_execution`이 바깥에 있어서, `handle_errors`가 예외를 종료 코드로 바꾼 **결과값**을 기록합니다. 그래서 실패한 명령도 `exit=1`로 로그에 남습니다([증빙 7](docs/EXECUTION_EVIDENCE.md#7-오류-상황의-종료-코드와-실행-로그)).

#### 3-3. 타입 힌트로 얻은 이점과 확인 방법

모든 함수의 인자·반환값과 dataclass 필드에 타입을 적었습니다(`from __future__ import annotations`로 `X | None` 문법 사용). 실제 코드에서 도움이 된 지점은 다음과 같습니다.

| 코드 | 타입이 알려주는 것 / 막아주는 실수 |
| --- | --- |
| `TransactionRepository.get(tx_id) -> Transaction \| None` | 없을 수 있음을 시그니처로 강제합니다. 그래서 서비스에서 `get_transaction()`이 `None`이면 `NotFoundError`로 바꾸는 처리를 빠뜨리지 않았습니다. |
| `def stream(...) -> Iterator[Transaction]` | 리스트가 아니라 한 번만 순회할 수 있는 이터레이터임을 알려줍니다. 두 번 순회하거나 `len()`을 쓰는 실수를 에디터가 바로 표시합니다. |
| `Handler = Callable[[argparse.Namespace], int]` | 데코레이터의 입력과 출력이 같은 시그니처임을 보장합니다. 핸들러가 종료 코드(int)를 반환하지 않으면 경고가 납니다. |
| `import_csv(...) -> tuple[ImportResult, list[str]]` | 호출하는 쪽(`cmd_import`)이 결과와 건너뛴 사유 목록을 받는다는 것을 문서 없이 알 수 있습니다. |
| `update_transaction(..., amount: str \| None)` | CLI 문자열을 그대로 받고 서비스에서 `parse_amount`로 검증한다는 책임 위치가 타입에 드러납니다. |

확인 방법은 VS Code(Pylance)에서 함수 위에 마우스를 올려 시그니처를 보고, 일부러 틀린 코드(예: `service.latest(limit="3")`, `tx = repo.get(id); tx.amount`)를 써서 빨간 줄 경고가 뜨는지 보는 것입니다. 정적 검사기로는 `python -m mypy budget_app`으로 같은 내용을 점검할 수 있습니다. 런타임 동작은 바뀌지 않지만, 계층 사이에 주고받는 값의 형태가 코드에 명시되어 있어 리팩터링과 리뷰 때 실수를 미리 잡습니다.

### 항목 4. 저장 포맷 · 확장성 · import 신뢰성

#### 4-1. JSONL vs CSV, JSONL을 저장 포맷으로 택한 근거

| 기준 | JSONL | CSV |
| --- | --- | --- |
| 리스트 필드(`tags`) | `["meal", "team"]` 그대로 저장 | 구분자 쉼표와 겹쳐 `"meal,team"`처럼 이중 인코딩 필요 |
| 타입 보존 | `amount`가 숫자로 저장 | 모두 문자열, 읽을 때마다 변환 |
| 필드 추가(스키마 변경) | 키를 추가하면 끝. 옛 줄은 `data.get("memo", "")` 기본값으로 읽힘 | 헤더와 모든 행의 열 개수를 맞춰야 함 |
| 줄 단위 처리 | 한 줄 = 한 레코드. 추가는 한 줄 append, 손상도 그 줄만(줄 번호로 안내) | 따옴표 안 줄바꿈 때문에 "한 줄 = 한 레코드"가 보장되지 않음 |
| 파일 크기 | 매 줄 키 이름이 반복되어 더 큼 | 헤더 1번이라 작음 |
| 사람/엑셀 친화성 | 엑셀로 바로 열기 어려움 | 엑셀에서 바로 열림 |

이 앱의 저장 파일은 프로그램이 읽고 쓰는 내부 데이터이므로, 타입·리스트 필드·스키마 확장·줄 단위 스트리밍이 중요해서 **저장은 JSONL**로 정했습니다. 반대로 사람이 엑셀로 열고 편집하는 **교환 용도에는 CSV**가 맞기 때문에 import/export만 CSV로 제공합니다. 두 포맷을 용도별로 나눠 각각의 단점을 피했습니다.

#### 4-2. 거래가 10만 건이 되면 병목과 개선 방법

거래 10만 건(12.9MB)으로 측정한 결과입니다. 시간은 측정 PC와 디스크 캐시 상태에 따라 차이가 있어 범위로 적었습니다.

| 작업 | 현재 동작 | 측정 |
| --- | --- | --- |
| list / search / summary / export | 매번 파일 전체를 읽고 JSON을 파싱 (O(N)) | 1회 약 1~3초 |
| `add` | `next_id()`가 최대 id를 찾으려고 **전체를 스캔**한 뒤 1줄 추가 | 약 0.7~2초 |
| `get` / update / delete 대상 조회 | id 인덱스가 없어 선형 탐색 (뒤쪽 id일수록 느림) | 앞쪽 1ms, 뒤쪽 약 1~2초 |
| update / delete 1건 | 조회 1회 + **전체 읽기 + 전체 다시 쓰기** | 약 4~6초 |

병목은 **인덱스가 없어서 모든 명령이 전체 파일을 읽는다는 점**과 **1건 수정에도 전체를 다시 쓴다는 점**입니다. 메모리는 스트리밍 덕분에 문제가 되지 않습니다. 개선 방법을 효과가 큰 순서로 정리하면 다음과 같습니다.

1. **SQLite로 저장소 교체(표준 라이브러리 `sqlite3`)**: `id`, `date`, `category`에 인덱스를 두면 조회와 수정이 O(log N)이고, update/delete는 1행만 바뀝니다. 트랜잭션으로 원자성도 그대로 지킵니다. 계층을 나눠 두었으므로 `storage.py`의 Repository 3개만 같은 메서드 이름으로 다시 구현하면 됩니다.
2. JSONL을 유지한다면:
   - `meta.json`에 마지막 id를 저장해 `add`의 전체 스캔을 없앱니다.
   - 월별 파일(`transactions/2024-01.jsonl`)로 나누면 `summary --month`와 `export --month`는 해당 월 파일만 읽습니다.
   - update/delete는 재작성 대신 "수정/삭제 기록"을 append하고, 일정 크기마다 압축 재작성(compaction)합니다.
3. 월별 요약을 캐시하고, 해당 월에 쓰기가 있을 때만 무효화합니다.

#### 4-3. import CSV에 깨진 행이 섞일 때 사용자 신뢰를 지키는 방법

**현재 구현: 부분 성공 + 행 번호 리포트**

- **파일 단위 오류는 아무것도 쓰기 전에 전체를 거부합니다.** 파일이 없거나 필수 헤더(`date,type,category,amount`)가 빠지면 0건 저장 후 종료 코드 1을 반환합니다.
- **행 단위 오류는 그 행만 건너뜁니다.** 날짜, 타입, 금액, 미등록 카테고리를 행마다 검증하고, 실패한 행은 `[건너뜀] 4행: 금액은 0보다 큰 양수여야 합니다.`처럼 **행 번호와 사유**를 출력합니다. 마지막에 `imported=N, skipped=M`을 보여주므로, 무엇이 들어갔고 무엇을 고쳐야 하는지 알 수 있습니다([증빙 6](docs/EXECUTION_EVIDENCE.md#6-잘못된-입력과-파일-오류-처리)).
- 행 하나 때문에 정상인 수천 행을 버리지 않는 것이, 가계부 import에서 사용자가 기대하는 동작이라고 판단했습니다.

**확인한 한계: 처리 도중 예외가 나면 롤백되지 않습니다.**

3,000행 뒤에 UTF-8이 아닌 바이트가 섞인 CSV로 실험했습니다. 결과는 `[오류] 예기치 못한 오류: UnicodeDecodeError`와 종료 코드 1이었지만, **오류 이전의 2,977행은 이미 저장되어 있었습니다.**

- 원인: 검증과 쓰기가 같은 스트림에서 동시에 일어나 `transactions.jsonl`에 바로 append되기 때문입니다.
- 위험: 사용자는 "실패했다"고 보고 다시 import할 것이고, 그러면 중복이 생깁니다.

**개선 계획**

1. **원자적 import(롤백)**: 원본을 복사한 임시 파일에 기존 거래와 새 행을 함께 쓰고, 끝까지 성공했을 때만 `os.replace`로 교체합니다. update/delete와 같은 방식입니다. 디코딩 오류나 Ctrl+C가 나면 임시 파일만 지우므로 **0건 반영**이 보장됩니다.
2. **정책 선택 옵션**: 기본값은 지금처럼 부분 성공으로 두고, `--strict`를 주면 한 행이라도 틀릴 때 전체를 거부합니다. `--dry-run`을 주면 저장 없이 검증 리포트만 출력합니다.
3. **리포트 파일**: 건너뛴 행을 원본 그대로 `import_rejected.csv`에 사유 컬럼과 함께 저장합니다. 사용자는 그 파일만 고쳐서 다시 import하면 됩니다.
4. **중복 방지**: 같은 파일을 다시 import할 때 중복이 생기지 않도록, 행 내용 해시나 import 배치 id를 기록해 이미 가져온 행은 건너뜁니다.
