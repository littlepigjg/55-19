from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QPushButton, QGroupBox, QLabel, QListWidget,
    QDialog, QDialogButtonBox, QMessageBox, QCheckBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QToolTip,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPoint
from PyQt6.QtGui import QIcon, QPainter, QColor, QBrush, QPen, QFont

from ..models import BookMeta
from ..validators import ValidationStatus, ValidationResult, MetadataValidator


class ValidationIconLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = ValidationStatus.PENDING
        self._message = ""
        self._suggestion = ""
        self.setFixedSize(20, 20)
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._update_icon()

    def set_validation_result(self, result: ValidationResult):
        self._status = result.status
        self._message = result.message
        self._suggestion = result.suggestion
        self._update_icon()

    def set_status(self, status: ValidationStatus, message: str = "", suggestion: str = ""):
        self._status = status
        self._message = message
        self._suggestion = suggestion
        self._update_icon()

    def _update_icon(self):
        icon = self._create_icon()
        self.setPixmap(icon.pixmap(20, 20))
        self.update()

    def _create_icon(self) -> QIcon:
        pixmap = QIcon()
        if self._status == ValidationStatus.SUCCESS:
            pixmap = self._create_check_icon()
        elif self._status == ValidationStatus.WARNING:
            pixmap = self._create_warning_icon()
        elif self._status == ValidationStatus.ERROR:
            pixmap = self._create_error_icon()
        else:
            pixmap = self._create_pending_icon()
        return pixmap

    def _create_check_icon(self) -> QIcon:
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor("#22c55e"), 2))
        painter.setBrush(QBrush(QColor("#22c55e")))
        painter.drawEllipse(2, 2, 16, 16)

        painter.setPen(QPen(QColor("white"), 2))
        painter.drawLine(6, 10, 9, 13)
        painter.drawLine(9, 13, 14, 7)

        painter.end()
        return QIcon(pixmap)

    def _create_warning_icon(self) -> QIcon:
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor("#f59e0b"), 2))
        painter.setBrush(QBrush(QColor("#f59e0b")))
        points = [
            painter.viewport().center() + Qt.QPoint(0, -8),
            painter.viewport().center() + Qt.QPoint(-8, 8),
            painter.viewport().center() + Qt.QPoint(8, 8),
        ]
        painter.drawPolygon(*points)

        painter.setPen(QPen(QColor("white"), 1))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "!")

        painter.end()
        return QIcon(pixmap)

    def _create_error_icon(self) -> QIcon:
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor("#ef4444"), 2))
        painter.setBrush(QBrush(QColor("#ef4444")))
        painter.drawEllipse(2, 2, 16, 16)

        painter.setPen(QPen(QColor("white"), 2))
        painter.drawLine(7, 7, 13, 13)
        painter.drawLine(13, 7, 7, 13)

        painter.end()
        return QIcon(pixmap)

    def _create_pending_icon(self) -> QIcon:
        from PyQt6.QtGui import QPixmap
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor("#9ca3af"), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(2, 2, 16, 16)

        painter.end()
        return QIcon(pixmap)

    def enterEvent(self, event):
        if self._message or self._suggestion:
            tooltip_text = ""
            if self._message:
                tooltip_text += f"<b>{self._message}</b>"
            if self._suggestion:
                if tooltip_text:
                    tooltip_text += "<br><br>"
                tooltip_text += f"<span style='color:#666'>{self._suggestion}</span>"
            if tooltip_text:
                QToolTip.showText(event.globalPosition().toPoint(), f"<div style='max-width:250px'>{tooltip_text}</div>", self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)


class ValidatedLineEdit(QWidget):
    text_changed = pyqtSignal(str)

    def __init__(self, field_name: str, parent=None):
        super().__init__(parent)
        self._field_name = field_name
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.edit = QLineEdit()
        self.edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.edit, 1)

        self.icon_label = ValidationIconLabel()
        layout.addWidget(self.icon_label)

    def _on_text_changed(self, text: str):
        self.text_changed.emit(text)

    def text(self) -> str:
        return self.edit.text()

    def setText(self, text: str):
        self.edit.setText(text)

    def clear(self):
        self.edit.clear()

    def setPlaceholderText(self, text: str):
        self.edit.setPlaceholderText(text)

    def set_validation_result(self, result: ValidationResult):
        self.icon_label.set_validation_result(result)

        if result.status == ValidationStatus.ERROR:
            self.edit.setStyleSheet("QLineEdit { border: 1px solid #ef4444; }")
        elif result.status == ValidationStatus.WARNING:
            self.edit.setStyleSheet("QLineEdit { border: 1px solid #f59e0b; }")
        elif result.status == ValidationStatus.SUCCESS:
            self.edit.setStyleSheet("QLineEdit { border: 1px solid #22c55e; }")
        else:
            self.edit.setStyleSheet("")

    def setEnabled(self, enabled: bool):
        self.edit.setEnabled(enabled)
        super().setEnabled(enabled)


class ValidatedTextEdit(QWidget):
    text_changed = pyqtSignal(str)

    def __init__(self, field_name: str, parent=None):
        super().__init__(parent)
        self._field_name = field_name
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)
        header_layout.addStretch()
        self.icon_label = ValidationIconLabel()
        header_layout.addWidget(self.icon_label)
        layout.addLayout(header_layout)

        self.edit = QTextEdit()
        self.edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.edit)

    def _on_text_changed(self):
        self.text_changed.emit(self.edit.toPlainText())

    def toPlainText(self) -> str:
        return self.edit.toPlainText()

    def setText(self, text: str):
        self.edit.setText(text)

    def clear(self):
        self.edit.clear()

    def setMaximumHeight(self, h: int):
        self.edit.setMaximumHeight(h)

    def set_validation_result(self, result: ValidationResult):
        self.icon_label.set_validation_result(result)

        if result.status == ValidationStatus.ERROR:
            self.edit.setStyleSheet("QTextEdit { border: 1px solid #ef4444; }")
        elif result.status == ValidationStatus.WARNING:
            self.edit.setStyleSheet("QTextEdit { border: 1px solid #f59e0b; }")
        elif result.status == ValidationStatus.SUCCESS:
            self.edit.setStyleSheet("QTextEdit { border: 1px solid #22c55e; }")
        else:
            self.edit.setStyleSheet("")


class MetadataEditPanel(QWidget):
    save_requested = pyqtSignal(list, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._books: list = []
        self._validator = MetadataValidator()
        self._current_book: BookMeta = None
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._on_debounce_timeout)
        self._pending_field = None
        self._pending_value = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        info_label = QLabel("选择书籍后在此编辑元数据")
        info_label.setStyleSheet("font-weight:bold;font-size:13px;color:#555")
        layout.addWidget(info_label)

        form_group = QGroupBox("元数据编辑")
        form_layout = QFormLayout(form_group)

        self.title_edit = ValidatedLineEdit("title")
        self.title_edit.text_changed.connect(lambda v: self._on_field_changed("title", v))
        form_layout.addRow("书名:", self.title_edit)

        self.author_edit = ValidatedLineEdit("author")
        self.author_edit.text_changed.connect(lambda v: self._on_field_changed("author", v))
        form_layout.addRow("作者:", self.author_edit)

        self.publisher_edit = ValidatedLineEdit("publisher")
        self.publisher_edit.text_changed.connect(lambda v: self._on_field_changed("publisher", v))
        form_layout.addRow("出版社:", self.publisher_edit)

        self.date_edit = ValidatedLineEdit("publish_date")
        self.date_edit.setPlaceholderText("如: 2023-01-15")
        self.date_edit.text_changed.connect(lambda v: self._on_field_changed("publish_date", v))
        form_layout.addRow("出版日期:", self.date_edit)

        self.isbn_edit = ValidatedLineEdit("isbn")
        self.isbn_edit.text_changed.connect(lambda v: self._on_field_changed("isbn", v))
        form_layout.addRow("ISBN:", self.isbn_edit)

        self.lang_edit = ValidatedLineEdit("language")
        self.lang_edit.setPlaceholderText("如: zh, en")
        self.lang_edit.text_changed.connect(lambda v: self._on_field_changed("language", v))
        form_layout.addRow("语言:", self.lang_edit)

        self.desc_edit = ValidatedTextEdit("description")
        self.desc_edit.setMaximumHeight(100)
        self.desc_edit.text_changed.connect(lambda v: self._on_field_changed("description", v))
        form_layout.addRow("简介:", self.desc_edit)

        self.tags_edit = ValidatedLineEdit("tags")
        self.tags_edit.setPlaceholderText("用逗号分隔标签")
        form_layout.addRow("标签:", self.tags_edit)

        layout.addWidget(form_group)

        batch_group = QGroupBox("批量操作")
        batch_layout = QVBoxLayout(batch_group)

        self.batch_cb = QCheckBox("批量模式（非空字段将覆盖所有选中书籍）")
        batch_layout.addWidget(self.batch_cb)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("💾 保存修改")
        self.save_btn.setStyleSheet(
            "QPushButton{background:#4a9eff;color:white;border:none;border-radius:4px;padding:8px 16px;font-weight:bold}"
            "QPushButton:hover{background:#3d8be0}"
        )
        self.save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self.save_btn)
        batch_layout.addLayout(btn_row)

        layout.addWidget(batch_group)
        layout.addStretch()

    def _on_field_changed(self, field_name: str, value: str):
        self._pending_field = field_name
        self._pending_value = value
        self._debounce_timer.start()

    def _on_debounce_timeout(self):
        if self._pending_field and self._current_book:
            result = self._validator.validate_field(self._pending_field, self._pending_value)
            self._update_field_icon(self._pending_field, result)

    def _update_field_icon(self, field_name: str, result: ValidationResult):
        field_edits = {
            "title": self.title_edit,
            "author": self.author_edit,
            "publisher": self.publisher_edit,
            "publish_date": self.date_edit,
            "isbn": self.isbn_edit,
            "language": self.lang_edit,
            "description": self.desc_edit,
        }
        if field_name in field_edits:
            field_edits[field_name].set_validation_result(result)

    def _update_all_icons(self, book: BookMeta):
        if not book:
            return

        results = book.get_all_validation_results()
        for field_name, result in results.items():
            self._update_field_icon(field_name, result)

    def set_books(self, books: list):
        self._books = books
        self._current_book = None

        if not books:
            self._clear_fields()
            return

        if len(books) == 1:
            b = books[0]
            self._current_book = b
            self.title_edit.setText(b.title)
            self.author_edit.setText(b.author)
            self.publisher_edit.setText(b.publisher)
            self.date_edit.setText(b.publish_date)
            self.isbn_edit.setText(b.isbn)
            self.lang_edit.setText(b.language)
            self.desc_edit.setText(b.description)
            self.tags_edit.setText(", ".join(b.tags))

            QTimer.singleShot(10, lambda: self._update_all_icons(b))
        else:
            self._clear_fields()
            self.title_edit.setPlaceholderText(f"共 {len(books)} 本书选中")

    def _clear_fields(self):
        for w in [
            self.title_edit, self.author_edit, self.publisher_edit,
            self.date_edit, self.isbn_edit, self.lang_edit, self.tags_edit,
        ]:
            w.clear()
            w.setPlaceholderText("")
            w.set_validation_result(ValidationResult(
                field_name="",
                status=ValidationStatus.PENDING,
                severity=ValidationStatus.PENDING,
            ))
        self.desc_edit.clear()
        self.desc_edit.set_validation_result(ValidationResult(
            field_name="",
            status=ValidationStatus.PENDING,
            severity=ValidationStatus.PENDING,
        ))

    def _validate_all_fields(self) -> dict:
        changes = self._collect_changes()
        results = {}

        for field_name, value in changes.items():
            result = self._validator.validate_field(field_name, value, use_cache=False)
            results[field_name] = result
            self._update_field_icon(field_name, result)

        return results

    def _collect_changes(self) -> dict:
        changes = {}
        if self.title_edit.text():
            changes["title"] = self.title_edit.text()
        if self.author_edit.text():
            changes["author"] = self.author_edit.text()
        if self.publisher_edit.text():
            changes["publisher"] = self.publisher_edit.text()
        if self.date_edit.text():
            changes["publish_date"] = self.date_edit.text()
        if self.isbn_edit.text():
            changes["isbn"] = self.isbn_edit.text()
        if self.lang_edit.text():
            changes["language"] = self.lang_edit.text()
        if self.desc_edit.toPlainText():
            changes["description"] = self.desc_edit.toPlainText()
        if self.tags_edit.text():
            changes["tags"] = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        return changes

    def _on_save(self):
        changes = self._collect_changes()

        if not changes:
            QMessageBox.information(self, "提示", "没有修改内容")
            return

        validation_results = self._validate_all_fields()
        errors = [
            r for r in validation_results.values()
            if r.status == ValidationStatus.ERROR
        ]

        if errors:
            error_messages = "\n\n".join([
                f"• {r.message}\n  建议: {r.suggestion}"
                for r in errors
            ])
            QMessageBox.warning(
                self,
                "验证错误",
                f"以下字段存在错误，请修正后再保存：\n\n{error_messages}"
            )
            return

        if not self.batch_cb.isChecked() and len(self._books) > 1:
            reply = QMessageBox.question(
                self,
                "确认",
                f"将对 {len(self._books)} 本书应用修改，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.save_requested.emit(self._books, changes)
