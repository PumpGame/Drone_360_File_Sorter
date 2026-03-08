import sys
import os
import subprocess
import json
import shutil
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QWidget, QCheckBox, QGroupBox, QFrame, QStatusBar, QStyle
)
from PySide6.QtGui import QColor, QPalette
from datetime import datetime

# NOTE: PIL imports were in the original file, but not used.
# Kept out to avoid needing extra dependencies.
# from PIL import Image
# from PIL.ExifTags import TAGS


class FileSorterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Sorter by Modified Date")

        self.folder_path = ""
        self.files_to_sort = {}
        self._keywords_cache: dict[str, list[str]] = {}
        self.ignored_system_files = {
            "desktop.ini",
            "thumbs.db",
            ".ds_store",
        }

        # Main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self.central_widget.setLayout(layout)

        # Source section
        source_group = QGroupBox("Source")
        source_layout = QVBoxLayout()
        source_layout.setContentsMargins(10, 10, 10, 10)
        source_layout.setSpacing(8)
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        self.folder_label = QLabel("Selected Folder: None")
        source_layout.addWidget(self.folder_label)

        self.choose_folder_button = QPushButton("Choose Folder")
        self.choose_folder_button.clicked.connect(self.choose_folder)
        self.choose_folder_button.setProperty("class", "secondary")
        source_layout.addWidget(self.choose_folder_button)

        # Options section
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(10, 10, 10, 10)
        options_layout.setSpacing(8)
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # -------- File Type Sorting checkbox + description --------
        self.enable_type_sorting_checkbox = QCheckBox("Enable File Type Sorting")
        self.enable_type_sorting_checkbox.stateChanged.connect(self.update_preview)
        options_layout.addWidget(self.enable_type_sorting_checkbox)

        # Extensions that this option will sort into subfolders
        self.type_sorting_formats = [
            ".jpg", ".jpeg", ".png",
            ".dng",
            ".mp4", ".mov",
            ".insv",  # Insta360 video
            ".insp",  # Insta360 photo container
            ".lrv",   # Insta360 low-res preview video
            ".srt",
            ".db",
        ]
        formats_txt = ", ".join(self.type_sorting_formats)

        # Tooltip on the checkbox
        self.enable_type_sorting_checkbox.setToolTip(
            f"Sortuje po typie pliku: {formats_txt}"
        )

        # Small label under the checkbox (always visible)
        self.type_sorting_desc = QLabel(f"Sortuje po typie pliku: {formats_txt}")
        self.type_sorting_desc.setObjectName("typeSortingDesc")
        options_layout.addWidget(self.type_sorting_desc)
        # --------------------------------------------------------

        # Preview & Actions section
        preview_group = QGroupBox("Preview & Actions")
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(10, 10, 10, 10)
        preview_layout.setSpacing(8)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        self.destination_tree = QTreeWidget()
        self.destination_tree.setHeaderLabel("Destination structure")
        self.destination_tree.setRootIsDecorated(True)
        self.destination_tree.setAlternatingRowColors(True)
        preview_layout.addWidget(self.destination_tree)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        preview_layout.addWidget(separator)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        action_layout.addStretch()
        preview_layout.addLayout(action_layout)

        self.confirm_button = QPushButton("Confirm and Move Files")
        self.confirm_button.clicked.connect(self.confirm_and_move_files)
        self.confirm_button.setEnabled(False)
        self.confirm_button.setProperty("class", "primary")
        self.confirm_button.setDefault(True)

        self.undo_button = QPushButton("Undo Last Run")
        self.undo_button.clicked.connect(self.undo_last_run)
        self.undo_button.setProperty("class", "secondary")
        self.undo_button.setEnabled(False)
        action_layout.addWidget(self.undo_button)

        action_layout.addWidget(self.confirm_button)

        self.setStatusBar(QStatusBar(self))
        self.apply_styles()
        self.set_status("Ready")

    def choose_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.folder_path = folder_path
            self._keywords_cache.clear()
            self.folder_label.setText(f"Selected Folder: {folder_path}")
            self.set_status("Folder selected")
            self.list_files()
            self.update_undo_button_state()

    def list_files(self):
        self.destination_tree.clear()
        if not os.path.isdir(self.folder_path):
            QMessageBox.warning(self, "Error", "The selected path is not a valid folder.")
            self.set_status("Invalid folder selected")
            return

        self.files_to_sort = {}
        self._keywords_cache.clear()

        for file_name in os.listdir(self.folder_path):
            full_path = os.path.join(self.folder_path, file_name)
            if os.path.isfile(full_path) and not self.should_skip_file(file_name):
                modified_time = os.path.getmtime(full_path)
                modified_date = datetime.fromtimestamp(modified_time).strftime("%Y-%m-%d")
                if modified_date not in self.files_to_sort:
                    self.files_to_sort[modified_date] = []
                self.files_to_sort[modified_date].append(file_name)

        self.update_preview()
        self.confirm_button.setEnabled(True)
        self.update_undo_button_state()
        file_count = sum(len(files) for files in self.files_to_sort.values())
        self.set_status(f"Files found: {file_count}")

    def update_preview(self):
        self.destination_tree.clear()

        organized_files = {}
        for date, files in self.files_to_sort.items():
            for file in files:
                destination_folder = self.get_destination_folder(date, file)

                if destination_folder not in organized_files:
                    organized_files[destination_folder] = []
                organized_files[destination_folder].append(file)

        self.populate_destination_tree(organized_files)
        total_files = sum(len(files) for files in organized_files.values())
        self.set_status(f"Preview ready: {total_files} files")

    def populate_destination_tree(self, organized_files: dict[str, list[str]]) -> None:
        self.destination_tree.clear()
        if not self.folder_path:
            return

        folder_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)

        root_name = os.path.basename(os.path.normpath(self.folder_path)) or "Destination"
        total_files = sum(len(files) for files in organized_files.values())
        root_item = QTreeWidgetItem([f"{root_name} ({total_files})"])
        root_item.setIcon(0, folder_icon)
        self.destination_tree.addTopLevelItem(root_item)

        node_cache: dict[tuple[str, ...], QTreeWidgetItem] = {}
        counts: dict[tuple[str, ...], int] = {}

        for destination_folder, files in organized_files.items():
            rel_path = os.path.relpath(destination_folder, self.folder_path)
            if rel_path in (".", ""):
                parts: list[str] = []
            else:
                parts = [p for p in rel_path.split(os.sep) if p and p != "."]

            for depth in range(1, len(parts) + 1):
                key = tuple(parts[:depth])
                counts[key] = counts.get(key, 0) + len(files)

            parent_item = root_item
            for depth, part in enumerate(parts, start=1):
                key = tuple(parts[:depth])
                if key not in node_cache:
                    folder_item = QTreeWidgetItem([part])
                    folder_item.setIcon(0, folder_icon)
                    node_cache[key] = folder_item
                    parent_item.addChild(folder_item)
                parent_item = node_cache[key]

            for file_name in sorted(files):
                file_item = QTreeWidgetItem([file_name])
                file_item.setIcon(0, file_icon)
                parent_item.addChild(file_item)

        for key, item in node_cache.items():
            item.setText(0, f"{key[-1]} ({counts.get(key, 0)})")

        root_item.setExpanded(True)
        self.destination_tree.expandToDepth(1)

    def confirm_and_move_files(self):
        if not self.files_to_sort:
            QMessageBox.warning(self, "Error", "No files to sort.")
            self.set_status("No files to sort")
            return

        reply = QMessageBox.question(
            self, "Confirm", "Do you want to move the files to folders based on their modified dates?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.set_status("Moving...", 2000)
            moved_count = 0
            skipped_count = 0
            errors: list[str] = []
            by_folder: dict[str, int] = {}
            moved_pairs: list[dict[str, str]] = []
            for date, files in self.files_to_sort.items():
                for file in files:
                    source_path = os.path.abspath(os.path.join(self.folder_path, file))

                    if not os.path.exists(source_path):
                        skipped_count += 1
                        errors.append(f"{file} -> file not found")
                        continue

                    destination_folder = os.path.abspath(self.get_destination_folder(date, file))

                    os.makedirs(destination_folder, exist_ok=True)

                    destination_path = os.path.join(destination_folder, file)
                    try:
                        shutil.move(source_path, destination_path)
                        moved_count += 1
                        by_folder[destination_folder] = by_folder.get(destination_folder, 0) + 1
                        moved_pairs.append({"src": source_path, "dst": os.path.abspath(destination_path)})
                    except OSError as exc:
                        skipped_count += 1
                        errors.append(f"{file} -> {exc}")

            if moved_pairs:
                self.save_last_run_log(moved_pairs)
            self.update_undo_button_state()

            errors_count = len(errors)
            summary_text = (
                f"Moved: {moved_count}\n"
                f"Skipped: {skipped_count}\n"
                f"Errors: {errors_count}\n"
                f"Dest folders: {len(by_folder)}\n"
                f"Undo is available: click 'Undo Last Run'."
            )

            by_folder_lines = [
                f"{folder} ({count})"
                for folder, count in sorted(by_folder.items(), key=lambda kv: kv[1], reverse=True)
            ]
            details_parts = ["By folder:"]
            details_parts.extend(by_folder_lines or ["(none)"])
            if errors:
                details_parts.append("")
                details_parts.append("Errors:")
                details_parts.extend(errors)
            detailed_text = "\n".join(details_parts)

            summary_box = QMessageBox(self)
            summary_box.setWindowTitle("Move summary")
            summary_box.setText(summary_text)
            summary_box.setDetailedText(detailed_text)
            if errors_count > 0:
                summary_box.setIcon(QMessageBox.Icon.Warning)
            else:
                summary_box.setIcon(QMessageBox.Icon.Information)
            summary_box.exec()

            self.set_status(f"Moved {moved_count} files, errors {errors_count}", 5000)
            self.list_files()

    def undo_last_run(self):
        log_data = self.load_last_run_log()
        if not log_data or not log_data.get("moves"):
            QMessageBox.information(self, "Undo", "No undo data found for this folder.")
            self.update_undo_button_state()
            return

        timestamp = log_data.get("timestamp", "unknown time")
        reply = QMessageBox.question(
            self,
            "Confirm Undo",
            f"Undo last move from {timestamp}? This will move files back to their original locations.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.set_status("Undo in progress...", 2000)

        moves = log_data.get("moves", [])
        moved_back = 0
        missing_count = 0
        conflicts_count = 0
        errors: list[str] = []
        conflict_details: list[str] = []
        remaining_moves: list[dict[str, str]] = []

        for move in reversed(moves):
            src = os.path.abspath(move.get("src", ""))
            dst = os.path.abspath(move.get("dst", ""))

            if not src or not dst:
                errors.append(f"{dst or '(unknown)'} -> invalid log entry")
                remaining_moves.append(move)
                continue

            if not os.path.exists(dst):
                missing_count += 1
                errors.append(f"{dst} -> missing")
                remaining_moves.append(move)
                continue

            os.makedirs(os.path.dirname(src), exist_ok=True)
            target_src = src
            if os.path.exists(src):
                conflicts_count += 1
                target_src = self.resolve_undo_conflict_path(src)
                conflict_details.append(f"{dst} -> {target_src}")

            try:
                shutil.move(dst, target_src)
                moved_back += 1
            except OSError as exc:
                errors.append(f"{dst} -> {exc}")
                remaining_moves.append(move)

        errors_count = len(errors)

        summary_text = (
            f"Moved back: {moved_back}\n"
            f"Missing: {missing_count}\n"
            f"Conflicts renamed: {conflicts_count}\n"
            f"Errors: {errors_count}"
        )

        details_parts = ["Conflicts renamed:"]
        details_parts.extend(conflict_details or ["(none)"])
        details_parts.append("")
        details_parts.append("Missing/Errors:")
        details_parts.extend(errors or ["(none)"])

        summary_box = QMessageBox(self)
        summary_box.setWindowTitle("Move summary")
        summary_box.setText(summary_text)
        summary_box.setDetailedText("\n".join(details_parts))
        if errors_count > 0 or missing_count > 0:
            summary_box.setIcon(QMessageBox.Icon.Warning)
        else:
            summary_box.setIcon(QMessageBox.Icon.Information)
        summary_box.exec()

        if remaining_moves:
            self.save_last_run_log(remaining_moves)
        else:
            log_path = self.get_undo_log_path()
            if os.path.exists(log_path):
                os.remove(log_path)

        self.update_undo_button_state()
        self.set_status(
            f"Undo finished: moved back {moved_back}, errors {errors_count + missing_count}",
            5000
        )
        self.list_files()

    # pano rule
    def has_pano_tag(self, file_path: str) -> bool:
        file_name_lower = os.path.basename(file_path).lower()
        if "pano" in file_name_lower:
            return True

        if not file_name_lower.endswith((".jpg", ".jpeg")):
            return False

        keywords = self.get_windows_keywords(file_path)
        if "pano" in keywords:
            return True

        try:
            with open(file_path, "rb") as f:
                raw = f.read(1024 * 1024)
            text = raw.decode("utf-8", errors="ignore").lower()
        except OSError:
            return False

        if ">pano<" in text:
            return True
        if "dc:subject" in text and "pano" in text:
            return True
        if "xmp:subject" in text and "pano" in text:
            return True
        return False

    def get_windows_keywords(self, file_path: str) -> list[str]:
        normalized_path = os.path.normpath(file_path)
        if normalized_path in self._keywords_cache:
            return self._keywords_cache[normalized_path]

        dir_path = os.path.dirname(normalized_path)
        file_name = os.path.basename(normalized_path)
        keywords: list[str] = []
        ps_script = (
            "& { param($dir,$name) "
            "$shell = New-Object -ComObject Shell.Application; "
            "$folder = $shell.NameSpace($dir); "
            "if ($null -eq $folder) { return }; "
            "$item = $folder.ParseName($name); "
            "if ($null -eq $item) { return }; "
            "$kw = $item.ExtendedProperty('System.Keywords'); "
            "if ($null -eq $kw) { return }; "
            "if ($kw -is [System.Array]) { [Console]::Out.Write(($kw -join ';')) } "
            "else { [Console]::Out.Write([string]$kw) } "
            "}"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script, dir_path, file_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                keywords = [
                    part.strip().lower()
                    for part in result.stdout.split(";")
                    if part.strip()
                ]
        except Exception:
            keywords = []

        self._keywords_cache[normalized_path] = keywords
        return keywords

    # pano rule
    def get_destination_folder(self, date: str, filename: str) -> str:
        base = os.path.join(self.folder_path, date)
        file_lower = filename.lower()

        if file_lower.endswith(".db"):
            return base
        if file_lower.endswith(".srt"):
            return os.path.join(base, "Video")

        source_path = os.path.join(self.folder_path, filename)
        is_pano = self.has_pano_tag(source_path)
        if is_pano:
            return os.path.join(base, "Pano")

        if self.enable_type_sorting_checkbox.isChecked():
            return os.path.join(base, self.get_file_type(filename))
        return base

    def get_undo_log_path(self) -> str:
        if not self.folder_path:
            return ""
        return os.path.join(self.folder_path, "_sorter_undo_last.json")

    def load_last_run_log(self) -> dict:
        log_path = self.get_undo_log_path()
        if not log_path or not os.path.exists(log_path):
            return {}
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("moves"), list):
                return data
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def save_last_run_log(self, moved_pairs: list[dict[str, str]]):
        log_path = self.get_undo_log_path()
        if not log_path:
            return
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "root": os.path.abspath(self.folder_path),
            "moves": moved_pairs,
        }
        temp_path = f"{log_path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, log_path)
        except OSError:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def update_undo_button_state(self):
        log_data = self.load_last_run_log()
        has_moves = bool(log_data.get("moves"))
        self.undo_button.setEnabled(has_moves)

    def resolve_undo_conflict_path(self, src_path: str) -> str:
        base_dir = os.path.dirname(src_path)
        name, ext = os.path.splitext(os.path.basename(src_path))
        index = 1
        while True:
            candidate = os.path.join(base_dir, f"{name}_UNDO_{index:03d}{ext}")
            if not os.path.exists(candidate):
                return candidate
            index += 1

    def should_skip_file(self, file_name: str) -> bool:
        lower = file_name.lower()
        if lower in self.ignored_system_files:
            return True
        if lower.startswith("._"):
            return True
        return False

    def get_file_type(self, file_name):
        name = file_name.lower()

        # Insta360 recording-related files
        if name.endswith((".insv", ".insp", ".lrv")):
            return "Insta360"

        # Photos / stills
        if name.endswith((".jpg", ".jpeg", ".png")):
            return "Jpg"

        # Video
        if name.endswith((".mp4", ".mov", ".srt")):
            return "Video"

        # Raw
        if name.endswith(".dng"):
            return "Raw"

        # Database
        if name.endswith(".db"):
            return "Database"

        return "Other"

    def set_status(self, text: str, timeout_ms: int = 3000):
        self.statusBar().showMessage(text, timeout_ms)

    def apply_styles(self):
        app = QApplication.instance()
        app.setStyle("Fusion")

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(230, 230, 230))
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.Text, QColor(230, 230, 230))
        palette.setColor(QPalette.ColorRole.Button, QColor(60, 60, 60))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(235, 235, 235))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(62, 130, 247))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)

        qss = """
        QGroupBox {
            border: 1px solid #4a4a4a;
            border-radius: 8px;
            margin-top: 10px;
            padding: 8px;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }
        QLabel#typeSortingDesc {
            color: #b8b8b8;
            font-size: 11px;
        }
        QTreeWidget {
            border: 1px solid #4a4a4a;
            border-radius: 6px;
            padding: 6px;
        }
        QTreeWidget::item {
            padding: 2px 0;
        }
        QPushButton {
            border: 1px solid #5a5a5a;
            border-radius: 6px;
            padding: 6px 12px;
        }
        QPushButton[class="primary"] {
            background-color: #2f81f7;
            color: #ffffff;
            border: 1px solid #2b74de;
            font-weight: 600;
        }
        QPushButton[class="primary"]:hover {
            background-color: #246fe0;
        }
        QStatusBar {
            border-top: 1px solid #4a4a4a;
        }
        """
        app.setStyleSheet(qss)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileSorterApp()
    window.show()
    sys.exit(app.exec())
