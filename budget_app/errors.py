"""사용자에게 '원인 + 해결 힌트'로 보여줄 예외 타입."""
from __future__ import annotations


class AppError(Exception):
    """예상 가능한 오류. CLI 계층에서 스택트레이스 없이 출력된다."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(AppError):
    """입력값 검증 실패."""


class NotFoundError(AppError):
    """존재하지 않는 데이터(id, 카테고리 등)."""
