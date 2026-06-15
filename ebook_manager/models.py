from dataclasses import dataclass, field
from typing import Optional, Any
from pathlib import Path

from .validators import (
    MetadataValidator, ValidationResult, ValidationStatus,
    ValidationSeverity, ValidationConfig,
)


_VALIDATED_FIELDS = {
    "title", "author", "publisher", "publish_date",
    "isbn", "language", "description",
}


@dataclass
class BookMeta:
    title: str = ""
    author: str = ""
    publisher: str = ""
    publish_date: str = ""
    isbn: str = ""
    language: str = ""
    description: str = ""
    tags: list = field(default_factory=list)
    cover_path: Optional[str] = None
    file_path: str = ""
    file_format: str = ""
    file_size: int = 0

    def __post_init__(self):
        object.__setattr__(self, "_validation_results", {})
        object.__setattr__(self, "_validator", MetadataValidator())
        object.__setattr__(self, "_initialized", True)
        self._validate_all_fields()

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name in _VALIDATED_FIELDS and getattr(self, "_initialized", False):
            self._validate_field(name, value)

    def _validate_field(self, field_name: str, value: Any) -> None:
        try:
            validator = object.__getattribute__(self, "_validator")
            result = validator.validate_field(field_name, value)
            results = object.__getattribute__(self, "_validation_results")
            results[field_name] = result
        except AttributeError:
            pass

    def _validate_all_fields(self) -> None:
        try:
            for field_name in _VALIDATED_FIELDS:
                value = object.__getattribute__(self, field_name)
                self._validate_field(field_name, value)
        except AttributeError:
            pass

    def get_validation_result(self, field_name: str) -> Optional[ValidationResult]:
        results = object.__getattribute__(self, "_validation_results")
        return results.get(field_name)

    def get_all_validation_results(self) -> dict:
        return dict(object.__getattribute__(self, "_validation_results"))

    def has_validation_errors(self) -> bool:
        results = object.__getattribute__(self, "_validation_results")
        return any(
            r.status == ValidationStatus.ERROR
            for r in results.values()
        )

    def get_validation_errors(self) -> list:
        results = object.__getattribute__(self, "_validation_results")
        return [
            r for r in results.values()
            if r.status == ValidationStatus.ERROR
        ]

    def validate(self) -> dict:
        self._validate_all_fields()
        return self.get_all_validation_results()

    def to_dict(self):
        return {
            "title": self.title,
            "author": self.author,
            "publisher": self.publisher,
            "publish_date": self.publish_date,
            "isbn": self.isbn,
            "language": self.language,
            "description": self.description,
            "tags": self.tags,
            "cover_path": self.cover_path,
            "file_path": self.file_path,
            "file_format": self.file_format,
            "file_size": self.file_size,
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            title=d.get("title", ""),
            author=d.get("author", ""),
            publisher=d.get("publisher", ""),
            publish_date=d.get("publish_date", ""),
            isbn=d.get("isbn", ""),
            language=d.get("language", ""),
            description=d.get("description", ""),
            tags=d.get("tags", []),
            cover_path=d.get("cover_path"),
            file_path=d.get("file_path", ""),
            file_format=d.get("file_format", ""),
            file_size=d.get("file_size", 0),
        )

    @staticmethod
    def format_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

