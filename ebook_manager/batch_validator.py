from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

from .models import BookMeta
from .validators import (
    MetadataValidator, ValidationResult, ValidationStatus,
    ValidationSeverity, ValidationConfig,
)


@dataclass
class BookValidationReport:
    book: BookMeta
    results: Dict[str, ValidationResult] = field(default_factory=dict)
    error_count: int = 0
    warning_count: int = 0
    score: int = 0

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def has_warnings(self) -> bool:
        return self.warning_count > 0

    @property
    def severity(self) -> str:
        if self.error_count > 0:
            return "critical"
        if self.warning_count > 0:
            return "warning"
        return "good"

    def to_dict(self) -> dict:
        return {
            "book_title": self.book.title,
            "book_file": self.book.file_path,
            "severity": self.severity,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "completeness_score": self.score,
            "issues": [
                {
                    "field": r.field_name,
                    "status": r.status.value,
                    "severity": r.severity.value,
                    "message": r.message,
                    "suggestion": r.suggestion,
                    "current_value": str(r.value) if r.value is not None else "",
                }
                for r in self.results.values()
                if r.status != ValidationStatus.SUCCESS
            ],
        }


@dataclass
class BatchValidationReport:
    total_books: int = 0
    validated_books: int = 0
    books_with_errors: int = 0
    books_with_warnings: int = 0
    perfect_books: int = 0
    average_score: float = 0.0
    book_reports: List[BookValidationReport] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    library_name: str = ""

    def calculate_statistics(self):
        if not self.book_reports:
            return

        self.total_books = len(self.book_reports)
        self.validated_books = self.total_books
        self.books_with_errors = sum(1 for r in self.book_reports if r.has_errors)
        self.books_with_warnings = sum(1 for r in self.book_reports if r.has_warnings and not r.has_errors)
        self.perfect_books = sum(1 for r in self.book_reports if not r.has_errors and not r.has_warnings)

        scores = [r.score for r in self.book_reports]
        self.average_score = sum(scores) / len(scores) if scores else 0.0

    def sort_by_severity(self):
        severity_order = {"critical": 0, "warning": 1, "good": 2}
        self.book_reports.sort(key=lambda r: (severity_order.get(r.severity, 99), -r.error_count, -r.warning_count))

    def get_missing_fields_summary(self) -> Dict[str, int]:
        field_counts: Dict[str, int] = {}
        for report in self.book_reports:
            for result in report.results.values():
                if result.status == ValidationStatus.ERROR and result.rule_name == "required":
                    field_name = result.field_name
                    field_counts[field_name] = field_counts.get(field_name, 0) + 1
        return dict(sorted(field_counts.items(), key=lambda x: -x[1]))

    def to_dict(self) -> dict:
        return {
            "library_name": self.library_name,
            "generated_at": self.generated_at,
            "statistics": {
                "total_books": self.total_books,
                "validated_books": self.validated_books,
                "books_with_errors": self.books_with_errors,
                "books_with_warnings": self.books_with_warnings,
                "perfect_books": self.perfect_books,
                "average_score": round(self.average_score, 2),
            },
            "missing_fields_summary": self.get_missing_fields_summary(),
            "books": [r.to_dict() for r in self.book_reports],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save_to_file(self, file_path: str) -> bool:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.to_json())
            return True
        except Exception:
            return False

    def to_text_report(self) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("书库元数据批量验证报告")
        lines.append("=" * 60)
        lines.append(f"生成时间: {self.generated_at}")
        lines.append(f"图书馆: {self.library_name}")
        lines.append("")
        lines.append("统计概览:")
        lines.append(f"  总书籍数: {self.total_books}")
        lines.append(f"  有错误的书籍: {self.books_with_errors}")
        lines.append(f"  有警告的书籍: {self.books_with_warnings}")
        lines.append(f"  元数据完整的书籍: {self.perfect_books}")
        lines.append(f"  平均完整性评分: {self.average_score:.1f}/100")
        lines.append("")

        missing_fields = self.get_missing_fields_summary()
        if missing_fields:
            lines.append("缺失最严重的字段:")
            for field, count in list(missing_fields.items())[:10]:
                lines.append(f"  {field}: {count} 本书缺失")
            lines.append("")

        lines.append("问题书籍详情（按严重程度排序）:")
        lines.append("-" * 60)

        for i, report in enumerate(self.book_reports, 1):
            if report.severity == "good":
                continue

            severity_icon = "🔴" if report.severity == "critical" else "🟡"
            lines.append(f"\n{i}. {severity_icon} {report.book.title or '无标题'}")
            lines.append(f"   文件: {report.book.file_path}")
            lines.append(f"   评分: {report.score}/100")

            for result in report.results.values():
                if result.status == ValidationStatus.SUCCESS:
                    continue

                status_icon = "❌" if result.status == ValidationStatus.ERROR else "⚠️"
                lines.append(f"   {status_icon} [{result.field_name}] {result.message}")
                if result.suggestion:
                    lines.append(f"      建议: {result.suggestion}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


class BatchValidator:
    def __init__(self, config: ValidationConfig = None):
        self.config = config or ValidationConfig()
        self.validator = MetadataValidator(self.config)

    def validate_book(self, book: BookMeta) -> BookValidationReport:
        results = self.validator.validate_object(book, use_cache=False)

        error_count = sum(1 for r in results.values() if r.status == ValidationStatus.ERROR)
        warning_count = sum(1 for r in results.values() if r.status == ValidationStatus.WARNING)

        max_score = 100
        error_penalty = self.config.get_severity_weight("error")
        warning_penalty = self.config.get_severity_weight("warning")
        score = max(0, max_score - error_count * error_penalty - warning_count * warning_penalty)

        return BookValidationReport(
            book=book,
            results=results,
            error_count=error_count,
            warning_count=warning_count,
            score=score,
        )

    def validate_all(self, books: List[BookMeta]) -> BatchValidationReport:
        report = BatchValidationReport()
        report.library_name = self.config.config.get("library_name", "默认图书馆")

        for book in books:
            book_report = self.validate_book(book)
            report.book_reports.append(book_report)

        report.calculate_statistics()
        report.sort_by_severity()

        return report

    def validate_with_progress(self, books: List[BookMeta], callback=None) -> BatchValidationReport:
        report = BatchValidationReport()
        report.library_name = self.config.config.get("library_name", "默认图书馆")

        total = len(books)
        for i, book in enumerate(books, 1):
            book_report = self.validate_book(book)
            report.book_reports.append(book_report)

            if callback:
                callback(i, total, book)

        report.calculate_statistics()
        report.sort_by_severity()

        return report

    def get_problem_books(self, report: BatchValidationReport) -> List[BookValidationReport]:
        return [r for r in report.book_reports if r.has_errors or r.has_warnings]

    def get_books_missing_field(self, report: BatchValidationReport, field_name: str) -> List[BookValidationReport]:
        result = []
        for book_report in report.book_reports:
            field_result = book_report.results.get(field_name)
            if field_result and field_result.status == ValidationStatus.ERROR and field_result.rule_name == "required":
                result.append(book_report)
        return result
