"""명령 핸들러에 공통으로 적용하는 데코레이터(예외 처리, 실행 로그/시간 측정)."""
from __future__ import annotations

import argparse
import functools
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .errors import AppError

Handler = Callable[[argparse.Namespace], int]

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130


def print_error(message: str, hint: str = "") -> None:
    print(f"[오류] {message}", file=sys.stderr)
    if hint:
        print(f"[힌트] {hint}", file=sys.stderr)


def handle_errors(func: Handler) -> Handler:
    """예외를 스택트레이스 대신 '원인 + 힌트'로 출력하고 종료 코드로 바꾼다."""

    @functools.wraps(func)
    def wrapper(args: argparse.Namespace) -> int:
        try:
            return func(args)
        except AppError as e:
            print_error(e.message, e.hint)
            return EXIT_ERROR
        except (KeyboardInterrupt, EOFError):
            print("\n[중단] 입력이 취소되었습니다.", file=sys.stderr)
            return EXIT_INTERRUPTED
        except OSError as e:
            print_error(f"파일 처리 중 문제가 발생했습니다: {e.strerror} ({e.filename})", "경로와 쓰기 권한을 확인하세요.")
            return EXIT_ERROR
        except Exception as e:  # 예상하지 못한 오류도 스택트레이스는 숨긴다
            print_error(f"예기치 못한 오류: {type(e).__name__}: {e}", "데이터 파일이 손상되지 않았는지 확인하세요.")
            return EXIT_ERROR

    return wrapper


def log_execution(func: Handler) -> Handler:
    """명령 이름, 종료 코드, 실행 시간(ms)을 <data-dir>/app.log 에 남긴다."""

    @functools.wraps(func)
    def wrapper(args: argparse.Namespace) -> int:
        start = time.perf_counter()
        code = EXIT_ERROR
        try:
            code = func(args)
            return code
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            name = " ".join(filter(None, (args.command, getattr(args, "action", None))))
            line = f"{datetime.now().isoformat(timespec='seconds')} command={name} exit={code} elapsed={elapsed_ms:.1f}ms\n"
            try:
                log_path = Path(args.data_dir) / "app.log"
                if log_path.parent.exists():
                    with log_path.open("a", encoding="utf-8") as f:
                        f.write(line)
            except OSError:
                pass  # 로그 실패가 본 기능을 막지 않도록 무시

    return wrapper
