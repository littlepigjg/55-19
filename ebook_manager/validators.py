import re
import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
from functools import wraps


class ValidationSeverity(Enum):
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"


class ValidationStatus(Enum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class ValidationResult:
    field_name: str
    status: ValidationStatus
    severity: ValidationSeverity
    message: str = ""
    suggestion: str = ""
    rule_name: str = ""
    value: Any = None

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "status": self.status.value,
            "severity": self.severity.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "rule_name": self.rule_name,
        }


@dataclass
class ValidationRule:
    name: str
    validate_func: Callable
    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: str = ""
    suggestion: str = ""
    params: Dict[str, Any] = field(default_factory=dict)

    def execute(self, value: Any, field_name: str) -> ValidationResult:
        try:
            is_valid, message, suggestion = self.validate_func(value, **self.params)
            if is_valid:
                return ValidationResult(
                    field_name=field_name,
                    status=ValidationStatus.SUCCESS,
                    severity=ValidationSeverity.VALID,
                    rule_name=self.name,
                    value=value,
                )
            else:
                return ValidationResult(
                    field_name=field_name,
                    status=ValidationStatus.ERROR if self.severity == ValidationSeverity.ERROR else ValidationStatus.WARNING,
                    severity=self.severity,
                    message=message or self.message,
                    suggestion=suggestion or self.suggestion,
                    rule_name=self.name,
                    value=value,
                )
        except Exception as e:
            return ValidationResult(
                field_name=field_name,
                status=ValidationStatus.ERROR,
                severity=ValidationSeverity.ERROR,
                message=f"验证执行错误: {str(e)}",
                suggestion="请检查输入内容",
                rule_name=self.name,
                value=value,
            )


class ValidationCache:
    def __init__(self):
        self._cache: Dict[str, ValidationResult] = {}

    def _make_key(self, field_name: str, value: Any) -> str:
        value_str = str(value) if value is not None else ""
        combined = f"{field_name}:{value_str}"
        return hashlib.md5(combined.encode("utf-8")).hexdigest()

    def get(self, field_name: str, value: Any) -> Optional[ValidationResult]:
        key = self._make_key(field_name, value)
        return self._cache.get(key)

    def set(self, field_name: str, value: Any, result: ValidationResult) -> None:
        key = self._make_key(field_name, value)
        self._cache[key] = result

    def clear(self) -> None:
        self._cache.clear()

    def invalidate(self, field_name: str = None) -> None:
        if field_name:
            self._cache = {
                k: v for k, v in self._cache.items()
                if not k.startswith(hashlib.md5(field_name.encode("utf-8")).hexdigest()[:8])
            }
        else:
            self.clear()


class FieldValidator:
    def __init__(self, field_name: str, rules: List[ValidationRule] = None):
        self.field_name = field_name
        self.rules: List[ValidationRule] = rules or []
        self.cache = ValidationCache()

    def add_rule(self, rule: ValidationRule) -> "FieldValidator":
        self.rules.append(rule)
        return self

    def validate(self, value: Any, use_cache: bool = True) -> List[ValidationResult]:
        results: List[ValidationResult] = []

        if use_cache:
            cached = self.cache.get(self.field_name, value)
            if cached:
                return [cached]

        has_error = False
        for rule in self.rules:
            if has_error and rule.severity != ValidationSeverity.ERROR:
                continue

            result = rule.execute(value, self.field_name)

            if use_cache and result.status != ValidationStatus.PENDING:
                self.cache.set(self.field_name, value, result)

            results.append(result)

            if result.status == ValidationStatus.ERROR:
                has_error = True

        return results

    def validate_chain(self, value: Any, use_cache: bool = True) -> ValidationResult:
        results = self.validate(value, use_cache)
        for result in results:
            if result.status == ValidationStatus.ERROR:
                return result
        for result in results:
            if result.status == ValidationStatus.WARNING:
                return result
        if results:
            return results[0]
        return ValidationResult(
            field_name=self.field_name,
            status=ValidationStatus.SUCCESS,
            severity=ValidationSeverity.VALID,
            value=value,
        )


class ValidationRuleLibrary:
    _instance = None
    _rules: Dict[str, Callable] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._register_default_rules()
        return cls._instance

    def _register_default_rules(self):
        self.register("required", self._required)
        self.register("optional", self._optional)
        self.register("isbn13", self._isbn13)
        self.register("date_format", self._date_format)
        self.register("email", self._email)
        self.register("url", self._url)
        self.register("max_length", self._max_length)
        self.register("min_length", self._min_length)
        self.register("language_code", self._language_code)
        self.register("numeric", self._numeric)
        self.register("regex", self._regex)

    def register(self, name: str, func: Callable) -> None:
        self._rules[name] = func

    def get(self, name: str) -> Optional[Callable]:
        return self._rules.get(name)

    def has(self, name: str) -> bool:
        return name in self._rules

    @staticmethod
    def _required(value: Any, **kwargs) -> Tuple[bool, str, str]:
        if value is None:
            return False, "字段不能为空", "请填写该字段"
        if isinstance(value, str) and not value.strip():
            return False, "字段不能为空", "请填写该字段"
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False, "字段不能为空", "请填写该字段"
        return True, "", ""

    @staticmethod
    def _optional(value: Any, **kwargs) -> Tuple[bool, str, str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, "", ""
        return True, "", ""

    @staticmethod
    def _isbn13(value: Any, **kwargs) -> Tuple[bool, str, str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, "", ""

        isbn = str(value).replace("-", "").replace(" ", "").strip()

        if not isbn.isdigit():
            return False, "ISBN必须是数字", "请输入纯数字，可包含连字符"

        if len(isbn) != 13:
            return False, f"ISBN长度应为13位，当前为{len(isbn)}位", "请检查ISBN长度"

        total = 0
        for i, digit in enumerate(isbn[:12]):
            weight = 1 if i % 2 == 0 else 3
            total += int(digit) * weight

        check_digit = (10 - (total % 10)) % 10
        if int(isbn[12]) != check_digit:
            return False, f"ISBN校验位错误，应为{check_digit}", "请检查ISBN是否正确，或使用在线ISBN校验工具"

        return True, "", ""

    @staticmethod
    def _date_format(value: Any, **kwargs) -> Tuple[bool, str, str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, "", ""

        date_str = str(value).strip()

        pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(pattern, date_str):
            return False, "日期格式不正确", "请使用 YYYY-MM-DD 格式，如 2023-01-15"

        try:
            year, month, day = map(int, date_str.split("-"))
            if month < 1 or month > 12:
                return False, "月份范围不正确", "月份应在 01-12 之间"
            if day < 1 or day > 31:
                return False, "日期范围不正确", "日期应在 01-31 之间"
            if month in [4, 6, 9, 11] and day > 30:
                return False, "该月份日期范围不正确", f"{month}月最多30天"
            if month == 2:
                is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
                max_day = 29 if is_leap else 28
                if day > max_day:
                    return False, "二月份日期不正确", f"{year}年二月最多{max_day}天"
        except ValueError:
            return False, "日期解析失败", "请检查日期格式"

        return True, "", ""

    @staticmethod
    def _email(value: Any, **kwargs) -> Tuple[bool, str, str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, "", ""

        email = str(value).strip()
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            return False, "邮箱格式不正确", "请输入有效的邮箱地址，如 name@example.com"

        return True, "", ""

    @staticmethod
    def _url(value: Any, **kwargs) -> Tuple[bool, str, str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, "", ""

        url = str(value).strip()
        pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        if not re.match(pattern, url):
            return False, "URL格式不正确", "请输入有效的URL，如 https://example.com"

        return True, "", ""

    @staticmethod
    def _max_length(value: Any, max: int = 100, **kwargs) -> Tuple[bool, str, str]:
        if value is None:
            return True, "", ""

        length = len(str(value))
        if length > max:
            return False, f"内容过长（{length}字符）", f"请控制在{max}字符以内"

        return True, "", ""

    @staticmethod
    def _min_length(value: Any, min: int = 1, **kwargs) -> Tuple[bool, str, str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, "", ""

        length = len(str(value))
        if length < min:
            return False, f"内容过短（{length}字符）", f"请至少输入{min}个字符"

        return True, "", ""

    @staticmethod
    def _language_code(value: Any, **kwargs) -> Tuple[bool, str, str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, "", ""

        lang = str(value).strip().lower()
        valid_codes = {
            "zh", "en", "ja", "ko", "fr", "de", "es", "it", "pt", "ru",
            "ar", "hi", "bn", "pa", "te", "vi", "th", "id", "ms", "tr",
            "pl", "nl", "sv", "no", "da", "fi", "cs", "hu", "ro", "uk",
            "el", "he", "fa", "ur", "ta", "mr", "gu", "kn", "ml", "si",
            "zh-cn", "zh-tw", "zh-hans", "zh-hant", "en-us", "en-gb",
        }

        if lang not in valid_codes and not re.match(r"^[a-z]{2}(-[a-z0-9]{2,})?$", lang):
            return False, "语言代码不规范", "请使用ISO 639-1标准代码，如 zh、en、ja"

        return True, "", ""

    @staticmethod
    def _numeric(value: Any, **kwargs) -> Tuple[bool, str, str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, "", ""

        if not str(value).replace(".", "", 1).isdigit():
            return False, "必须为数字", "请输入有效的数字"

        return True, "", ""

    @staticmethod
    def _regex(value: Any, pattern: str = "", **kwargs) -> Tuple[bool, str, str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return True, "", ""

        if not pattern:
            return True, "", ""

        if not re.match(pattern, str(value)):
            return False, "格式不符合要求", f"请符合正则表达式: {pattern}"

        return True, "", ""


class ValidationConfig:
    def __init__(self, config_path: str = None):
        self.config: Dict[str, Any] = {}
        self.config_path = config_path or str(Path(__file__).parent / "validation_rules.json")
        self.library = ValidationRuleLibrary()
        self.load()

    def load(self) -> None:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "library_name": "默认图书馆",
                "severity_weights": {"critical": 100, "error": 50, "warning": 10},
                "fields": {},
            }

    def save(self) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def get_field_rules(self, field_name: str) -> List[ValidationRule]:
        field_config = self.config.get("fields", {}).get(field_name, {})

        if not field_config.get("enabled", True):
            return []

        rules: List[ValidationRule] = []
        for rule_config in field_config.get("rules", []):
            rule_name = rule_config.get("name", "")
            if not self.library.has(rule_name):
                continue

            severity_str = rule_config.get("severity", "error")
            severity = {
                "warning": ValidationSeverity.WARNING,
                "error": ValidationSeverity.ERROR,
                "critical": ValidationSeverity.ERROR,
            }.get(severity_str, ValidationSeverity.ERROR)

            rule = ValidationRule(
                name=rule_name,
                validate_func=self.library.get(rule_name),
                severity=severity,
                message=rule_config.get("message", ""),
                suggestion=rule_config.get("suggestion", ""),
                params=rule_config.get("params", {}),
            )
            rules.append(rule)

        return rules

    def get_field_label(self, field_name: str) -> str:
        return self.config.get("fields", {}).get(field_name, {}).get("label", field_name)

    def get_all_fields(self) -> Dict[str, Any]:
        return {k: v for k, v in self.config.get("fields", {}).items() if v.get("enabled", True)}

    def get_severity_weight(self, severity: str) -> int:
        return self.config.get("severity_weights", {}).get(severity, 10)

    def enable_field(self, field_name: str) -> None:
        if field_name in self.config.get("fields", {}):
            self.config["fields"][field_name]["enabled"] = True
            self.save()

    def disable_field(self, field_name: str) -> None:
        if field_name in self.config.get("fields", {}):
            self.config["fields"][field_name]["enabled"] = False
            self.save()

    def add_custom_rule(self, field_name: str, rule_config: Dict[str, Any]) -> None:
        if field_name not in self.config.get("fields", {}):
            self.config["fields"][field_name] = {"label": field_name, "rules": []}
        self.config["fields"][field_name]["rules"].append(rule_config)
        self.save()


class MetadataValidator:
    def __init__(self, config: ValidationConfig = None):
        self.config = config or ValidationConfig()
        self.field_validators: Dict[str, FieldValidator] = {}
        self._init_field_validators()

    def _init_field_validators(self) -> None:
        for field_name in self.config.get_all_fields().keys():
            rules = self.config.get_field_rules(field_name)
            if rules:
                self.field_validators[field_name] = FieldValidator(field_name, rules)

    def add_validator(self, field_name: str, validator: FieldValidator) -> None:
        self.field_validators[field_name] = validator

    def validate_field(self, field_name: str, value: Any, use_cache: bool = True) -> ValidationResult:
        if field_name not in self.field_validators:
            return ValidationResult(
                field_name=field_name,
                status=ValidationStatus.SUCCESS,
                severity=ValidationSeverity.VALID,
                value=value,
            )

        return self.field_validators[field_name].validate_chain(value, use_cache)

    def validate_all_fields(self, data: Dict[str, Any], use_cache: bool = True) -> Dict[str, ValidationResult]:
        results: Dict[str, ValidationResult] = {}
        for field_name, value in data.items():
            results[field_name] = self.validate_field(field_name, value, use_cache)
        return results

    def validate_object(self, obj: Any, use_cache: bool = True) -> Dict[str, ValidationResult]:
        data = {}
        for field_name in self.field_validators.keys():
            if hasattr(obj, field_name):
                data[field_name] = getattr(obj, field_name)
        return self.validate_all_fields(data, use_cache)

    def has_errors(self, results: Dict[str, ValidationResult]) -> bool:
        return any(r.status == ValidationStatus.ERROR for r in results.values())

    def has_warnings(self, results: Dict[str, ValidationResult]) -> bool:
        return any(r.status == ValidationStatus.WARNING for r in results.values())

    def get_errors(self, results: Dict[str, ValidationResult]) -> List[ValidationResult]:
        return [r for r in results.values() if r.status == ValidationStatus.ERROR]

    def get_warnings(self, results: Dict[str, ValidationResult]) -> List[ValidationResult]:
        return [r for r in results.values() if r.status == ValidationStatus.WARNING]

    def clear_cache(self) -> None:
        for validator in self.field_validators.values():
            validator.cache.clear()


def validate_field(field_name: str, rules: List[str] = None):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            value = func(self, *args, **kwargs)

            if not hasattr(self, "_validators"):
                self._validators = {}

            if field_name not in self._validators:
                config = ValidationConfig()
                field_rules = []
                if rules:
                    library = ValidationRuleLibrary()
                    for rule_name in rules:
                        if library.has(rule_name):
                            field_rules.append(ValidationRule(
                                name=rule_name,
                                validate_func=library.get(rule_name),
                            ))
                else:
                    field_rules = config.get_field_rules(field_name)

                self._validators[field_name] = FieldValidator(field_name, field_rules)

            result = self._validators[field_name].validate_chain(value)

            if not hasattr(self, "_validation_results"):
                self._validation_results = {}
            self._validation_results[field_name] = result

            return value

        wrapper.__validation_field__ = field_name
        wrapper.__validation_rules__ = rules
        return wrapper

    return decorator


def validate_class(cls):
    original_init = cls.__init__

    @wraps(cls.__init__)
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._validation_results = {}
        self._validators = {}

    cls.__init__ = new_init

    def get_validation_result(self, field_name: str) -> Optional[ValidationResult]:
        return getattr(self, "_validation_results", {}).get(field_name)

    def get_all_validation_results(self) -> Dict[str, ValidationResult]:
        return getattr(self, "_validation_results", {})

    def has_validation_errors(self) -> bool:
        results = getattr(self, "_validation_results", {})
        return any(r.status == ValidationStatus.ERROR for r in results.values())

    cls.get_validation_result = get_validation_result
    cls.get_all_validation_results = get_all_validation_results
    cls.has_validation_errors = has_validation_errors

    return cls
