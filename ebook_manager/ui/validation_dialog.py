from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QTextEdit, QSplitter, QGroupBox, QFileDialog, QMessageBox,
    QAbstractItemView, QComboBox, QLineEdit, QFormLayout, QWidget,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QColor, QBrush

from ..models import BookMeta
from ..batch_validator import (
    BatchValidator, BatchValidationReport, BookValidationReport,
)
from ..validators import ValidationStatus, ValidationSeverity


class ValidationWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished_signal = pyqtSignal(object)

    def __init__(self, books: list, validator: BatchValidator):
        super().__init__()
        self._books = books
        self._validator = validator

    def run(self):
        def callback(current, total, book):
            title = book.title or Path(book.file_path).name
            self.progress.emit(current, total, title)

        report = self._validator.validate_with_progress(self._books, callback)
        self.finished_signal.emit(report)


class ValidationReportDialog(QDialog):
    def __init__(self, books: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 书库元数据批量验证")
        self.setMinimumSize(1000, 700)
        self._books = books
        self._validator = BatchValidator()
        self._report: BatchValidationReport = None
        self._worker: ValidationWorker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "仅显示有错误", "仅显示有警告", "仅显示完整"])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索书名或文件路径...")
        self.search_edit.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.search_edit, 1)

        self.export_btn = QPushButton("📤 导出报告")
        self.export_btn.clicked.connect(self._export_report)
        self.export_btn.setEnabled(False)
        filter_layout.addWidget(self.export_btn)

        self.revalidate_btn = QPushButton("🔄 重新验证")
        self.revalidate_btn.clicked.connect(self._start_validation)
        filter_layout.addWidget(self.revalidate_btn)

        layout.addLayout(filter_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("准备就绪")
        layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Vertical)

        stats_group = QGroupBox("统计概览")
        stats_layout = QHBoxLayout(stats_group)

        self.stats_total = self._create_stat_widget("总书籍数", "0")
        stats_layout.addWidget(self.stats_total)

        self.stats_errors = self._create_stat_widget("有错误", "0", "#ef4444")
        stats_layout.addWidget(self.stats_errors)

        self.stats_warnings = self._create_stat_widget("有警告", "0", "#f59e0b")
        stats_layout.addWidget(self.stats_warnings)

        self.stats_perfect = self._create_stat_widget("完整", "0", "#22c55e")
        stats_layout.addWidget(self.stats_perfect)

        self.stats_score = self._create_stat_widget("平均评分", "0", "#3b82f6")
        stats_layout.addWidget(self.stats_score)

        splitter.addWidget(stats_group)

        self.books_table = QTableWidget()
        self.books_table.setColumnCount(5)
        self.books_table.setHorizontalHeaderLabels(["状态", "书名", "错误", "警告", "评分"])
        self.books_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.books_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.books_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.books_table.setAlternatingRowColors(True)
        self.books_table.verticalHeader().setVisible(False)
        self.books_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.books_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.books_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.books_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.books_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.books_table.selectionModel().selectionChanged.connect(self._on_book_selected)
        splitter.addWidget(self.books_table)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("选择一本书籍查看详细验证结果...")
        splitter.addWidget(self.details_text)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        layout.addWidget(splitter, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

        QTimer.singleShot(100, self._start_validation)

    def _create_stat_widget(self, label: str, value: str, color: str = "#333") -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)

        label_widget = QLabel(label)
        label_widget.setStyleSheet("color: #666; font-size: 12px;")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_widget)

        return widget

    def _update_stat_widget(self, widget: QWidget, value: str, color: str = None):
        value_label = widget.findChild(QLabel, "")
        if value_label and value_label.parent() == widget:
            children = widget.findChildren(QLabel)
            if children:
                children[0].setText(value)
                if color:
                    children[0].setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")

    def _start_validation(self):
        if not self._books:
            QMessageBox.information(self, "提示", "书库为空，没有需要验证的书籍")
            return

        self.books_table.setRowCount(0)
        self.details_text.clear()
        self.export_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self._books))
        self.progress_bar.setValue(0)
        self.status_label.setText("正在验证...")
        self.revalidate_btn.setEnabled(False)
        self.filter_combo.setEnabled(False)
        self.search_edit.setEnabled(False)

        self._worker = ValidationWorker(self._books, self._validator)
        self._worker.progress.connect(self._on_validation_progress)
        self._worker.finished_signal.connect(self._on_validation_finished)
        self._worker.start()

    def _on_validation_progress(self, current: int, total: int, title: str):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"正在验证 ({current}/{total}): {title}")

    def _on_validation_finished(self, report: BatchValidationReport):
        self._report = report
        self.progress_bar.setVisible(False)
        self.revalidate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.filter_combo.setEnabled(True)
        self.search_edit.setEnabled(True)

        self._update_stats()
        self._populate_table()

        self.status_label.setText(
            f"验证完成: {report.total_books} 本书, "
            f"{report.books_with_errors} 本有错误, "
            f"{report.books_with_warnings} 本有警告, "
            f"{report.perfect_books} 本完整"
        )

    def _update_stats(self):
        if not self._report:
            return

        self._update_stat_widget(self.stats_total, str(self._report.total_books))
        self._update_stat_widget(self.stats_errors, str(self._report.books_with_errors), "#ef4444")
        self._update_stat_widget(self.stats_warnings, str(self._report.books_with_warnings), "#f59e0b")
        self._update_stat_widget(self.stats_perfect, str(self._report.perfect_books), "#22c55e")
        self._update_stat_widget(self.stats_score, f"{self._report.average_score:.1f}", "#3b82f6")

    def _populate_table(self):
        if not self._report:
            return

        filter_text = self.search_edit.text().lower()
        filter_mode = self.filter_combo.currentIndex()

        self.books_table.setRowCount(0)
        filtered_reports = []

        for book_report in self._report.book_reports:
            if filter_mode == 1 and not book_report.has_errors:
                continue
            if filter_mode == 2 and not (book_report.has_warnings and not book_report.has_errors):
                continue
            if filter_mode == 3 and (book_report.has_errors or book_report.has_warnings):
                continue

            if filter_text:
                title = book_report.book.title.lower()
                file_path = book_report.book.file_path.lower()
                if filter_text not in title and filter_text not in file_path:
                    continue

            filtered_reports.append(book_report)

        self.books_table.setRowCount(len(filtered_reports))

        for row, book_report in enumerate(filtered_reports):
            self._add_book_row(row, book_report)

        self.status_label.setText(
            f"显示 {len(filtered_reports)}/{self._report.total_books} 本书"
        )

    def _add_book_row(self, row: int, book_report: BookValidationReport):
        if book_report.has_errors:
            status_icon = "🔴"
            bg_color = QColor("#fef2f2")
        elif book_report.has_warnings:
            status_icon = "🟡"
            bg_color = QColor("#fffbeb")
        else:
            status_icon = "🟢"
            bg_color = QColor("#f0fdf4")

        title = book_report.book.title or "无标题"
        title_item = QTableWidgetItem(f"{title}")
        title_item.setToolTip(book_report.book.file_path)

        for col, value in enumerate([
            status_icon,
            title_item,
            str(book_report.error_count),
            str(book_report.warning_count),
            f"{book_report.score}",
        ]):
            if isinstance(value, QTableWidgetItem):
                item = value
            else:
                item = QTableWidgetItem(value)

            if book_report.has_errors or book_report.has_warnings:
                item.setBackground(QBrush(bg_color))

            if col == 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col >= 2:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item.setData(Qt.ItemDataRole.UserRole, book_report)
            self.books_table.setItem(row, col, item)

    def _apply_filter(self):
        self._populate_table()

    def _on_book_selected(self):
        selected_rows = self.books_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        item = self.books_table.item(row, 0)
        if not item:
            return

        book_report = item.data(Qt.ItemDataRole.UserRole)
        if not book_report:
            return

        self._show_book_details(book_report)

    def _show_book_details(self, book_report: BookValidationReport):
        details = []
        details.append(f"<h3>{book_report.book.title or '无标题'}</h3>")
        details.append(f"<p><b>文件:</b> {book_report.book.file_path}</p>")
        details.append(f"<p><b>完整性评分:</b> {book_report.score}/100</p>")
        details.append("<hr>")

        has_issues = False
        for field_name, result in book_report.results.items():
            if result.status == ValidationStatus.SUCCESS:
                continue

            has_issues = True
            if result.status == ValidationStatus.ERROR:
                status_html = '<span style="color:#ef4444">❌ 错误</span>'
            else:
                status_html = '<span style="color:#f59e0b">⚠️ 警告</span>'

            details.append(f"<p>{status_html} <b>[{field_name}]</b></p>")
            if result.message:
                details.append(f"<p>&nbsp;&nbsp;{result.message}</p>")
            if result.suggestion:
                details.append(f'<p style="color:#666">&nbsp;&nbsp;💡 建议: {result.suggestion}</p>')
            if result.value is not None and str(result.value):
                details.append(f'<p style="color:#999">&nbsp;&nbsp;当前值: {result.value}</p>')
            details.append("<br>")

        if not has_issues:
            details.append('<p style="color:#22c55e"><b>✅ 元数据完整，所有字段验证通过！</b></p>')

        self.details_text.setHtml("".join(details))

    def _export_report(self):
        if not self._report:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出验证报告", "",
            "JSON 报告 (*.json);;文本报告 (*.txt)"
        )

        if not file_path:
            return

        try:
            if file_path.endswith(".json"):
                self._report.save_to_file(file_path)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self._report.to_text_report())

            QMessageBox.information(self, "导出成功", f"报告已导出到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出报告时出错:\n{str(e)}")
