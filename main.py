import sys
import os
import json
import shutil
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QWidget, QCheckBox, QGroupBox, QFrame, QStatusBar, QStyle,
    QLineEdit, QToolButton, QComboBox, QSplitter, QSizePolicy
)
from PySide6.QtGui import QColor, QPalette, QIcon
from datetime import datetime

try:
    import pythoncom
    import win32com.client
except ImportError:
    pythoncom = None
    win32com = None

# NOTE: PIL imports were in the original file, but not used.
# Kept out to avoid needing extra dependencies.
# from PIL import Image
# from PIL.ExifTags import TAGS


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class FileSorterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Sorter by Modified Date")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        self.folder_path = ""
        self.files_to_sort = {}
        self._keywords_cache: dict[str, list[str]] = {}
        self._settings_updates_paused = False
        self.settings = QSettings("Drone360", "FileSorter")
        self.ignored_system_files = {
            "desktop.ini",
            "thumbs.db",
            ".ds_store",
        }
        self.default_folder_names = self.build_default_folder_names()
        self.default_type_rules = self.build_default_type_rules()
        self.custom_type_rule_rows: list[dict[str, object]] = []
        self.type_rules_expanded = True
        self.date_format_options = [
            ("YYYY-MM-DD", "%Y-%m-%d"),
            ("DD-MM-YYYY", "%d-%m-%Y"),
            ("YYYY_MM_DD", "%Y_%m_%d"),
            ("DD_MM_YYYY", "%d_%m_%Y"),
            ("YYYY.MM.DD", "%Y.%m.%d"),
            ("DD.MM.YYYY", "%d.%m.%Y"),
        ]

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

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        layout.addWidget(self.content_splitter, 1)

        left_panel = QWidget()
        left_panel_layout = QVBoxLayout()
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        left_panel_layout.setSpacing(0)
        left_panel.setLayout(left_panel_layout)
        self.content_splitter.addWidget(left_panel)

        # Options section
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(10, 10, 10, 10)
        options_layout.setSpacing(8)
        options_group.setLayout(options_layout)
        options_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        left_panel_layout.addWidget(options_group)
        left_panel_layout.addStretch()

        self.date_structure_group = QGroupBox("Date Structure")
        date_structure_layout = QVBoxLayout()
        date_structure_layout.setContentsMargins(10, 10, 10, 10)
        date_structure_layout.setSpacing(8)
        self.date_structure_group.setLayout(date_structure_layout)
        options_layout.addWidget(self.date_structure_group)

        self.enable_year_folder_checkbox = QCheckBox("Add Year Folders")
        self.enable_year_folder_checkbox.stateChanged.connect(self.save_ui_settings)
        self.enable_year_folder_checkbox.stateChanged.connect(self.update_preview)
        date_structure_layout.addWidget(self.enable_year_folder_checkbox)

        self.enable_month_folder_checkbox = QCheckBox("Add Month Folders (01-12)")
        self.enable_month_folder_checkbox.stateChanged.connect(self.save_ui_settings)
        self.enable_month_folder_checkbox.stateChanged.connect(self.update_preview)
        date_structure_layout.addWidget(self.enable_month_folder_checkbox)

        self.date_format_group = QGroupBox("Date Format")
        date_format_group_layout = QVBoxLayout()
        date_format_group_layout.setContentsMargins(10, 10, 10, 10)
        date_format_group_layout.setSpacing(8)
        self.date_format_group.setLayout(date_format_group_layout)
        options_layout.addWidget(self.date_format_group)

        date_format_layout = QHBoxLayout()
        date_format_layout.setContentsMargins(0, 0, 0, 0)
        date_format_layout.setSpacing(8)
        date_format_group_layout.addLayout(date_format_layout)

        self.date_format_label = QLabel("Date format:")
        date_format_layout.addWidget(self.date_format_label)

        self.date_format_combo = QComboBox()
        for label, pattern in self.date_format_options:
            self.date_format_combo.addItem(label, pattern)
        self.date_format_combo.currentIndexChanged.connect(self.save_ui_settings)
        self.date_format_combo.currentIndexChanged.connect(self.update_preview)
        date_format_layout.addWidget(self.date_format_combo)
        date_format_layout.addStretch()

        # -------- File Type Sorting checkbox + description --------
        self.enable_type_sorting_checkbox = QCheckBox("Enable File Type Sorting")
        self.enable_type_sorting_checkbox.stateChanged.connect(self.update_preview)
        self.enable_type_sorting_checkbox.stateChanged.connect(self.update_type_rules_state)
        self.enable_type_sorting_checkbox.stateChanged.connect(self.save_ui_settings)
        options_layout.addWidget(self.enable_type_sorting_checkbox)

        # Extensions that this option will sort into subfolders
        self.type_sorting_formats = [
            ".jpg", ".jpeg",
            ".heic", ".heif",
            ".dng", ".arw", ".cr2", ".cr3", ".nef", ".nrw", ".orf", ".raf", ".rw2", ".pef",
            ".mp4", ".mov", ".avi", ".mkv", ".mts", ".m2ts", ".mpg", ".mpeg", ".wmv",
            ".insv",  # Insta360 video
            ".insp",  # Insta360 photo container
            ".lrv",   # Insta360 low-res preview video
            ".srt",
            ".db",
        ]
        formats_txt = ", ".join(self.type_sorting_formats)

        # Tooltip on the checkbox
        self.enable_type_sorting_checkbox.setToolTip(
            f"Sortowanie po rozszerzeniach plikow: {formats_txt}"
        )

        # Small label under the checkbox (always visible)
        self.type_sorting_desc = QLabel("Sortowanie po rozszerzeniach, np. .jpg, .mp4, .insv")
        self.type_sorting_desc.setObjectName("typeSortingDesc")
        options_layout.addWidget(self.type_sorting_desc)

        self.custom_type_rules_group = QGroupBox("Type Rules")
        custom_type_rules_layout = QVBoxLayout()
        custom_type_rules_layout.setContentsMargins(10, 10, 10, 10)
        custom_type_rules_layout.setSpacing(8)
        self.custom_type_rules_group.setLayout(custom_type_rules_layout)
        options_layout.addWidget(self.custom_type_rules_group)

        self.type_rules_toggle_button = QToolButton()
        self.type_rules_toggle_button.setText("Type Rules")
        self.type_rules_toggle_button.setCheckable(True)
        self.type_rules_toggle_button.setChecked(True)
        self.type_rules_toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.type_rules_toggle_button.setArrowType(Qt.ArrowType.DownArrow)
        self.type_rules_toggle_button.clicked.connect(self.toggle_type_rules_section)
        custom_type_rules_layout.addWidget(self.type_rules_toggle_button)

        self.type_rules_content_widget = QWidget()
        self.type_rules_content_layout = QVBoxLayout()
        self.type_rules_content_layout.setContentsMargins(0, 0, 0, 0)
        self.type_rules_content_layout.setSpacing(8)
        self.type_rules_content_widget.setLayout(self.type_rules_content_layout)
        custom_type_rules_layout.addWidget(self.type_rules_content_widget)

        self.custom_type_rules_info = QLabel(
            "Edit built-in rules, change folder names and extensions, or add your own new rules."
        )
        self.custom_type_rules_info.setObjectName("customFolderNamesInfo")
        self.type_rules_content_layout.addWidget(self.custom_type_rules_info)

        self.custom_type_rules_content = QVBoxLayout()
        self.custom_type_rules_content.setContentsMargins(0, 0, 0, 0)
        self.custom_type_rules_content.setSpacing(8)
        self.type_rules_content_layout.addLayout(self.custom_type_rules_content)

        self.add_custom_rule_button = QPushButton("Add Rule")
        self.add_custom_rule_button.setProperty("class", "secondary")
        self.add_custom_rule_button.clicked.connect(lambda checked=False: self.add_type_rule_row())
        self.type_rules_content_layout.addWidget(self.add_custom_rule_button)

        self.reset_settings_button = QPushButton("Reset to Defaults")
        self.reset_settings_button.setProperty("class", "secondary")
        self.reset_settings_button.clicked.connect(self.reset_to_defaults)
        options_layout.addWidget(self.reset_settings_button)

        self.load_ui_settings()
        if not self.custom_type_rule_rows:
            for rule in self.default_type_rules:
                self.add_type_rule_row(
                    rule_id=rule["id"],
                    folder_name=rule["folder_name"],
                    extensions=", ".join(rule["extensions"]),
                    description=rule["description"],
                    matcher=rule["matcher"],
                    removable=rule["removable"],
                )
        self.refresh_type_sorting_description()
        self.update_type_rules_state()
        # --------------------------------------------------------

        # Preview & Actions section
        preview_group = QGroupBox("Preview & Actions")
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(10, 10, 10, 10)
        preview_layout.setSpacing(8)
        preview_group.setLayout(preview_layout)
        self.content_splitter.addWidget(preview_group)
        self.content_splitter.setStretchFactor(0, 0)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setSizes([420, 680])

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
        if not hasattr(self, "destination_tree"):
            return

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

        keywords: list[str] = []
        file_name = os.path.basename(normalized_path)

        try:
            if os.name == "nt" and pythoncom is not None and win32com is not None:
                pythoncom.CoInitialize()
                shell = win32com.client.Dispatch("Shell.Application")
                folder = shell.NameSpace(os.path.dirname(normalized_path))
                if folder is not None:
                    item = folder.ParseName(file_name)
                    if item is not None:
                        raw_keywords = item.ExtendedProperty("System.Keywords")
                        if raw_keywords:
                            if isinstance(raw_keywords, (list, tuple)):
                                parts = raw_keywords
                            else:
                                parts = str(raw_keywords).split(";")
                            keywords = [
                                str(part).strip().lower()
                                for part in parts
                                if str(part).strip()
                            ]
        except Exception:
            keywords = []
        finally:
            if os.name == "nt" and pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        if not keywords and file_name.lower().endswith((".jpg", ".jpeg")):
            # Fallback for some files that keep pano-like metadata as UTF-16LE fragments.
            utf16_token = "pano".encode("utf-16le")
            try:
                with open(normalized_path, "rb") as f:
                    while True:
                        chunk = f.read(1024 * 256)
                        if not chunk:
                            break
                        if utf16_token in chunk:
                            keywords = ["pano"]
                            break
            except OSError:
                pass

        if os.environ.get("DRONESORT_DEBUG") == "1" and not keywords:
            self.statusBar().showMessage("Pano keywords empty", 3000)

        self._keywords_cache[normalized_path] = keywords
        return keywords

    def build_default_folder_names(self) -> dict[str, str]:
        return {
            "Pano": "Pano",
            "Insta360": "Insta360",
            "Jpg": "Jpg",
            "Video": "Video",
            "Raw": "Raw",
            "Database": "Database",
            "Other": "Other",
        }

    def build_default_type_rules(self) -> list[dict[str, object]]:
        return [
            {
                "id": "Pano",
                "folder_name": "Pano",
                "extensions": [],
                "description": "special rule: JPG/JPEG with pano tag or file name",
                "matcher": "pano",
                "removable": False,
            },
            {
                "id": "Insta360",
                "folder_name": "Insta360",
                "extensions": [".insv", ".insp", ".lrv", ".db"],
                "description": "Insta360 source files and helper databases",
                "matcher": "extension",
                "removable": False,
            },
            {
                "id": "Jpg",
                "folder_name": "Jpg",
                "extensions": [".jpg", ".jpeg"],
                "description": "photos / still images",
                "matcher": "extension",
                "removable": False,
            },
            {
                "id": "Video",
                "folder_name": "Video",
                "extensions": [".mp4", ".mov", ".avi", ".mkv", ".mts", ".m2ts", ".mpg", ".mpeg", ".wmv", ".srt"],
                "description": "video files and subtitles",
                "matcher": "extension",
                "removable": False,
            },
            {
                "id": "Raw",
                "folder_name": "Raw",
                "extensions": [".dng", ".arw", ".cr2", ".cr3", ".nef", ".nrw", ".orf", ".raf", ".rw2", ".pef"],
                "description": "raw photos",
                "matcher": "extension",
                "removable": False,
            },
            {
                "id": "Heic",
                "folder_name": "Heic",
                "extensions": [".heic", ".heif"],
                "description": "HEIC / HEIF photos",
                "matcher": "extension",
                "removable": False,
            },
            {
                "id": "Other",
                "folder_name": "Other",
                "extensions": [],
                "description": "fallback for everything else",
                "matcher": "catch_all",
                "removable": False,
            },
        ]

    def get_selected_date_format(self) -> str:
        selected_pattern = self.date_format_combo.currentData()
        if isinstance(selected_pattern, str) and selected_pattern:
            return selected_pattern
        return "%Y-%m-%d"

    def format_folder_date(self, iso_date: str) -> str:
        try:
            parsed = datetime.strptime(iso_date, "%Y-%m-%d")
        except ValueError:
            return iso_date
        return parsed.strftime(self.get_selected_date_format())

    def build_date_path_parts(self, iso_date: str) -> list[str]:
        try:
            parsed = datetime.strptime(iso_date, "%Y-%m-%d")
        except ValueError:
            return [iso_date]

        parts: list[str] = []
        if self.enable_year_folder_checkbox.isChecked():
            parts.append(parsed.strftime("%Y"))
        if self.enable_month_folder_checkbox.isChecked():
            parts.append(parsed.strftime("%m"))
        parts.append(parsed.strftime(self.get_selected_date_format()))
        return parts

    def normalize_extension(self, ext: str) -> str:
        normalized = ext.strip().lower()
        if not normalized:
            return ""
        if not normalized.startswith("."):
            normalized = f".{normalized}"
        return normalized

    def parse_extensions_input(self, raw_value: str) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        separators = raw_value.replace(";", ",").split(",")
        for part in separators:
            ext = self.normalize_extension(part)
            if ext and ext not in seen:
                normalized.append(ext)
                seen.add(ext)
        return normalized

    def clear_type_rule_rows(self):
        for row in self.custom_type_rule_rows:
            widget = row.get("widget")
            if isinstance(widget, QWidget):
                widget.setParent(None)
                widget.deleteLater()
        self.custom_type_rule_rows = []

    def apply_default_settings(self, save: bool = True):
        self._settings_updates_paused = True
        self.enable_year_folder_checkbox.setChecked(False)
        self.enable_month_folder_checkbox.setChecked(False)

        default_date_index = 0
        for index, (_, pattern) in enumerate(self.date_format_options):
            if pattern == "%Y-%m-%d":
                default_date_index = index
                break
        self.date_format_combo.setCurrentIndex(default_date_index)

        self.enable_type_sorting_checkbox.setChecked(False)
        self.type_rules_expanded = True
        self.type_rules_toggle_button.setChecked(True)

        self.clear_type_rule_rows()
        for rule in self.default_type_rules:
            self.add_type_rule_row(
                rule_id=rule["id"],
                folder_name=rule["folder_name"],
                extensions=", ".join(rule["extensions"]),
                description=rule["description"],
                matcher=rule["matcher"],
                removable=rule["removable"],
            )

        self._settings_updates_paused = False
        self.refresh_type_sorting_description()
        self.update_type_rules_state()
        if save:
            self.save_ui_settings()
        self.update_preview()

    def reset_to_defaults(self):
        reply = QMessageBox.question(
            self,
            "Reset settings",
            "Reset sorting settings to current factory defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for key in (
            "date_structure/year_folder",
            "date_structure/month_folder",
            "date_format/pattern",
            "type_sorting/enabled",
            "type_rules/expanded",
            "type_rules/items",
            "custom_type_rules/items",
            "custom_folder_names",
        ):
            self.settings.remove(key)

        self.apply_default_settings(save=True)
        self.set_status("Settings reset to defaults", 4000)

    def refresh_type_sorting_description(self):
        extensions: list[str] = []
        seen: set[str] = set()
        for rule in self.get_type_rules():
            if rule.get("matcher") != "extension":
                continue
            for ext in rule.get("extensions", []):
                if isinstance(ext, str) and ext not in seen:
                    extensions.append(ext)
                    seen.add(ext)

        formats_txt = ", ".join(extensions) if extensions else "(no extensions configured)"
        examples = ", ".join(extensions[:3]) if extensions else "brak"
        short_description = f"Sortowanie po rozszerzeniach, np. {examples}"
        tooltip = f"Sortowanie po rozszerzeniach plikow: {formats_txt}"
        self.type_sorting_desc.setText(short_description)
        self.enable_type_sorting_checkbox.setToolTip(tooltip)

    def update_type_rules_state(self):
        enabled = self.enable_type_sorting_checkbox.isChecked()
        self.custom_type_rules_group.setEnabled(enabled)
        self.type_rules_toggle_button.setEnabled(enabled)
        self.type_rules_content_widget.setVisible(enabled and self.type_rules_expanded)
        self.type_rules_toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if self.type_rules_expanded else Qt.ArrowType.RightArrow
        )
        tooltip = (
            "Type rules are active."
            if enabled else
            "Enable file type sorting to edit type rules."
        )
        self.custom_type_rules_group.setToolTip(tooltip)

    def toggle_type_rules_section(self):
        self.type_rules_expanded = self.type_rules_toggle_button.isChecked()
        self.update_type_rules_state()
        self.save_ui_settings()

    def add_type_rule_row(
        self,
        folder_name: str = "",
        extensions: str = "",
        description: str = "",
        matcher: str = "extension",
        removable: bool = True,
        rule_id: str = "",
    ):
        row_widget = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_widget.setLayout(row_layout)

        folder_edit = QLineEdit(folder_name)
        folder_edit.setPlaceholderText("Folder name, e.g. Archive")
        folder_edit.setToolTip("Target subfolder name for this rule")
        folder_edit.textChanged.connect(self.save_ui_settings)
        folder_edit.textChanged.connect(self.update_preview)
        row_layout.addWidget(folder_edit, 1)

        extensions_edit = QLineEdit(extensions)
        extensions_edit.setPlaceholderText("Extensions, e.g. .zip, .rar")
        extensions_edit.setToolTip("Comma-separated list of extensions")
        extensions_edit.textChanged.connect(self.save_ui_settings)
        extensions_edit.textChanged.connect(self.update_preview)
        if matcher != "extension":
            extensions_edit.setReadOnly(True)
        row_layout.addWidget(extensions_edit, 2)

        if description:
            description_label = QLabel(description)
            description_label.setObjectName("customFolderNamesInfo")
            row_layout.addWidget(description_label, 2)

        remove_button = QPushButton("Remove")
        remove_button.setProperty("class", "secondary")
        remove_button.clicked.connect(lambda checked=False: self.remove_type_rule_row(row_widget))
        remove_button.setEnabled(removable)
        row_layout.addWidget(remove_button)

        self.custom_type_rules_content.addWidget(row_widget)
        self.custom_type_rule_rows.append(
            {
                "widget": row_widget,
                "rule_id": rule_id,
                "matcher": matcher,
                "removable": removable,
                "folder_edit": folder_edit,
                "extensions_edit": extensions_edit,
            }
        )
        self.save_ui_settings()
        self.refresh_type_sorting_description()
        self.update_preview()

    def remove_type_rule_row(self, row_widget: QWidget):
        if len(self.custom_type_rule_rows) <= 1:
            row = self.custom_type_rule_rows[0]
            folder_edit = row["folder_edit"]
            extensions_edit = row["extensions_edit"]
            if isinstance(folder_edit, QLineEdit):
                folder_edit.clear()
            if isinstance(extensions_edit, QLineEdit):
                extensions_edit.clear()
            self.save_ui_settings()
            self.refresh_type_sorting_description()
            self.update_preview()
            return

        remaining_rows: list[dict[str, object]] = []
        for row in self.custom_type_rule_rows:
            widget = row["widget"]
            if widget is row_widget:
                if isinstance(widget, QWidget):
                    widget.setParent(None)
                    widget.deleteLater()
                continue
            remaining_rows.append(row)
        self.custom_type_rule_rows = remaining_rows
        self.save_ui_settings()
        self.refresh_type_sorting_description()
        self.update_preview()

    def get_type_rules(self) -> list[dict[str, object]]:
        rules: list[dict[str, object]] = []
        for row in self.custom_type_rule_rows:
            folder_edit = row["folder_edit"]
            extensions_edit = row["extensions_edit"]
            if not isinstance(folder_edit, QLineEdit) or not isinstance(extensions_edit, QLineEdit):
                continue

            folder_name = self.sanitize_folder_name(folder_edit.text())
            matcher = str(row.get("matcher", "extension"))
            extensions = self.parse_extensions_input(extensions_edit.text()) if matcher == "extension" else []
            if not folder_name:
                continue

            if matcher == "extension" and not extensions:
                continue

            rules.append(
                {
                    "id": row.get("rule_id", ""),
                    "folder_name": folder_name,
                    "extensions": extensions,
                    "matcher": matcher,
                }
            )
        return rules

    def get_matching_rule_folder_name(self, filename: str, source_path: str) -> str:
        for rule in self.get_type_rules():
            matcher = rule.get("matcher")
            folder_name = rule.get("folder_name")
            if not isinstance(folder_name, str):
                continue

            if matcher == "pano" and self.has_pano_tag(source_path):
                return folder_name

            if matcher == "extension":
                file_lower = filename.lower()
                extensions = rule.get("extensions", [])
                if any(file_lower.endswith(ext) for ext in extensions if isinstance(ext, str)):
                    return folder_name

        for rule in self.get_type_rules():
            if rule.get("matcher") == "catch_all":
                folder_name = rule.get("folder_name")
                if isinstance(folder_name, str):
                    return folder_name
        return "Other"

    def sanitize_folder_name(self, name: str) -> str:
        sanitized = name.replace("/", "_").replace("\\", "_")
        return sanitized.strip()

    def merge_missing_default_rules(self, saved_rules: list[dict[str, object]]) -> list[dict[str, object]]:
        merged_rules: list[dict[str, object]] = []
        existing_ids: set[str] = set()

        for rule in saved_rules:
            if not isinstance(rule, dict):
                continue
            merged_rules.append(rule)
            rule_id = str(rule.get("id", "")).strip()
            if rule_id:
                existing_ids.add(rule_id)

        for default_rule in self.default_type_rules:
            default_rule_id = str(default_rule.get("id", "")).strip()
            if default_rule_id and default_rule_id not in existing_ids:
                merged_rules.append(dict(default_rule))

        return merged_rules

    def load_ui_settings(self):
        self._settings_updates_paused = True
        self.clear_type_rule_rows()
        self.enable_year_folder_checkbox.setChecked(
            self.settings.value("date_structure/year_folder", False, type=bool)
        )
        self.enable_month_folder_checkbox.setChecked(
            self.settings.value("date_structure/month_folder", False, type=bool)
        )

        selected_date_format = self.settings.value("date_format/pattern", "%Y-%m-%d", type=str)
        selected_date_index = 0
        for index, (_, pattern) in enumerate(self.date_format_options):
            if pattern == selected_date_format:
                selected_date_index = index
                break
        self.date_format_combo.setCurrentIndex(selected_date_index)

        type_sorting_enabled = self.settings.value("type_sorting/enabled", False, type=bool)
        self.type_rules_expanded = self.settings.value("type_rules/expanded", True, type=bool)
        self.enable_type_sorting_checkbox.setChecked(type_sorting_enabled)
        self.type_rules_toggle_button.setChecked(self.type_rules_expanded)

        saved_rules_raw = self.settings.value("type_rules/items", "", type=str)
        if not saved_rules_raw:
            saved_rules_raw = self.settings.value("custom_type_rules/items", "[]", type=str)
        try:
            saved_rules = json.loads(saved_rules_raw)
        except json.JSONDecodeError:
            saved_rules = []

        if isinstance(saved_rules, list):
            saved_rules = self.merge_missing_default_rules(saved_rules)
            for rule in saved_rules:
                if not isinstance(rule, dict):
                    continue
                folder_name = str(rule.get("folder_name", "")).strip()
                matcher = str(rule.get("matcher", "extension"))
                extensions = rule.get("extensions", [])
                if isinstance(extensions, list):
                    normalized_extensions = [
                        self.normalize_extension(str(ext))
                        for ext in extensions
                        if self.normalize_extension(str(ext))
                    ]
                    extensions_text = ", ".join(normalized_extensions)
                else:
                    extensions_text = str(extensions)

                rule_id = str(rule.get("id", ""))
                description = str(rule.get("description", ""))
                removable = bool(rule.get("removable", True))
                self.add_type_rule_row(
                    rule_id=rule_id,
                    folder_name=folder_name,
                    extensions=extensions_text,
                    description=description,
                    matcher=matcher,
                    removable=removable,
                )
        else:
            self.load_legacy_type_rules()

        self._settings_updates_paused = False
        if not self.custom_type_rule_rows:
            self.apply_default_settings(save=False)
        else:
            self.refresh_type_sorting_description()
            self.update_type_rules_state()

    def load_legacy_type_rules(self):
        for rule in self.default_type_rules:
            saved_folder_name = self.settings.value(
                f"custom_folder_names/{rule['id']}",
                rule["folder_name"],
                type=str,
            )
            extensions = list(rule["extensions"])
            if rule["id"] == "Insta360":
                saved_database_name = self.settings.value("custom_folder_names/Database", "", type=str).strip()
                if saved_database_name and saved_database_name == saved_folder_name and ".db" not in extensions:
                    extensions.append(".db")
            self.add_type_rule_row(
                rule_id=rule["id"],
                folder_name=saved_folder_name,
                extensions=", ".join(extensions),
                description=rule["description"],
                matcher=rule["matcher"],
                removable=rule["removable"],
            )

        saved_rules_raw = self.settings.value("custom_type_rules/items", "[]", type=str)
        try:
            saved_rules = json.loads(saved_rules_raw)
        except json.JSONDecodeError:
            saved_rules = []

        if not isinstance(saved_rules, list):
            return

        for rule in saved_rules:
            if not isinstance(rule, dict):
                continue
            folder_name = str(rule.get("folder_name", "")).strip()
            extensions = rule.get("extensions", [])
            if isinstance(extensions, list):
                extensions_text = ", ".join(
                    self.normalize_extension(str(ext))
                    for ext in extensions
                    if self.normalize_extension(str(ext))
                )
            else:
                extensions_text = str(extensions)
            self.add_type_rule_row(folder_name=folder_name, extensions=extensions_text, description="custom rule")

    def save_ui_settings(self):
        if self._settings_updates_paused:
            return
        self.settings.setValue("date_structure/year_folder", self.enable_year_folder_checkbox.isChecked())
        self.settings.setValue("date_structure/month_folder", self.enable_month_folder_checkbox.isChecked())
        self.settings.setValue("date_format/pattern", self.get_selected_date_format())
        self.settings.setValue("type_sorting/enabled", self.enable_type_sorting_checkbox.isChecked())
        self.settings.setValue("type_rules/expanded", self.type_rules_expanded)
        custom_rules_payload = [
            {
                "id": rule["id"],
                "folder_name": rule["folder_name"],
                "extensions": rule["extensions"],
                "matcher": rule["matcher"],
            }
            for rule in self.get_type_rules()
        ]
        self.settings.setValue("type_rules/items", json.dumps(custom_rules_payload, ensure_ascii=True))

    # pano rule
    def get_destination_folder(self, date: str, filename: str) -> str:
        base = os.path.join(self.folder_path, *self.build_date_path_parts(date))

        if self.enable_type_sorting_checkbox.isChecked():
            source_path = os.path.join(self.folder_path, filename)
            folder_name = self.get_matching_rule_folder_name(filename, source_path)
            return os.path.join(base, folder_name)
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
        if name.endswith((".insv", ".insp", ".lrv", ".db")):
            return "Insta360"

        # Photos / stills
        if name.endswith((".jpg", ".jpeg")):
            return "Jpg"

        # HEIC / HEIF photos
        if name.endswith((".heic", ".heif")):
            return "Heic"

        # Video
        if name.endswith((".mp4", ".mov", ".avi", ".mkv", ".mts", ".m2ts", ".mpg", ".mpeg", ".wmv", ".srt")):
            return "Video"

        # Raw
        if name.endswith((".dng", ".arw", ".cr2", ".cr3", ".nef", ".nrw", ".orf", ".raf", ".rw2", ".pef")):
            return "Raw"

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
        QLabel#customFolderNamesInfo {
            color: #b8b8b8;
            font-size: 11px;
        }
        QLineEdit:disabled {
            color: #9a9a9a;
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
