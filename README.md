# 콘솔 가계부 (budget_app)

파일(JSONL) 기반으로 수입/지출을 기록하는 Python 콘솔 가계부입니다.
표준 라이브러리만 사용하며, 저장 파일은 제너레이터로 한 줄씩 스트리밍 처리합니다.

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
