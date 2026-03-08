import sys
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QMessageBox, QWidget, QListWidgetItem, QCheckBox, QGroupBox, QFrame, QStatusBar
)
from PySide6.QtGui import QColor, QFont
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

        self.file_list = QListWidget()
        preview_layout.addWidget(self.file_list)

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
        action_layout.addWidget(self.confirm_button)

        self.setStatusBar(QStatusBar(self))
        self.apply_styles()
        self.set_status("Ready")

    def choose_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.folder_path = folder_path
            self.folder_label.setText(f"Selected Folder: {folder_path}")
            self.set_status("Folder selected")
            self.list_files()

    def list_files(self):
        self.file_list.clear()
        if not os.path.isdir(self.folder_path):
            QMessageBox.warning(self, "Error", "The selected path is not a valid folder.")
            self.set_status("Invalid folder selected")
            return

        self.files_to_sort = {}

        for file_name in os.listdir(self.folder_path):
            full_path = os.path.join(self.folder_path, file_name)
            if os.path.isfile(full_path):
                modified_time = os.path.getmtime(full_path)
                modified_date = datetime.fromtimestamp(modified_time).strftime("%Y-%m-%d")
                if modified_date not in self.files_to_sort:
                    self.files_to_sort[modified_date] = []
                self.files_to_sort[modified_date].append(file_name)

        self.update_preview()
        self.confirm_button.setEnabled(True)
        file_count = sum(len(files) for files in self.files_to_sort.values())
        self.set_status(f"Files found: {file_count}")

    def update_preview(self):
        self.file_list.clear()

        organized_files = {}
        for date, files in self.files_to_sort.items():
            for file in files:
                destination_folder = os.path.join(self.folder_path, date)

                if self.enable_type_sorting_checkbox.isChecked():
                    file_lower = file.lower()
                    file_type = self.get_file_type(file)

                    # Special cases from original logic
                    if file_lower.endswith(".srt"):
                        destination_folder = os.path.join(self.folder_path, date, "Video")
                    elif file_lower.endswith(".db"):
                        destination_folder = os.path.join(self.folder_path, date)
                    else:
                        destination_folder = os.path.join(destination_folder, file_type)

                if destination_folder not in organized_files:
                    organized_files[destination_folder] = []
                organized_files[destination_folder].append(file)

        for folder, files in organized_files.items():
            folder_item = QListWidgetItem(f"Folder: {folder} ({len(files)})")
            folder_item.setData(Qt.ItemDataRole.UserRole, "header")
            header_font = QFont(self.file_list.font())
            header_font.setBold(True)
            header_font.setPointSize(header_font.pointSize() + 1)
            folder_item.setFont(header_font)
            folder_item.setForeground(QColor("#1f4f46"))
            self.file_list.addItem(folder_item)

            for file in files:
                file_item = QListWidgetItem(f"  └ {file}")
                file_item.setData(Qt.ItemDataRole.UserRole, "file")
                file_item.setForeground(QColor("#1e1e1e"))
                self.file_list.addItem(file_item)
        total_items = self.file_list.count()
        self.set_status(f"Preview ready: {total_items} rows")

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
            moved_count = 0
            skipped_files = []
            for date, files in self.files_to_sort.items():
                for file in files:
                    source_path = os.path.join(self.folder_path, file)

                    if not os.path.exists(source_path):
                        skipped_files.append(file)
                        continue

                    file_lower = file.lower()

                    # Determine the destination folder (kept compatible with original behavior)
                    if file_lower.endswith(".srt"):
                        destination_folder = os.path.join(self.folder_path, date, "Video")
                    elif file_lower.endswith(".db"):
                        destination_folder = os.path.join(self.folder_path, date)
                    else:
                        destination_folder = os.path.join(self.folder_path, date)
                        if self.enable_type_sorting_checkbox.isChecked():
                            file_type = self.get_file_type(file)
                            destination_folder = os.path.join(destination_folder, file_type)

                    os.makedirs(destination_folder, exist_ok=True)

                    destination_path = os.path.join(destination_folder, file)
                    os.rename(source_path, destination_path)
                    moved_count += 1

            if skipped_files:
                QMessageBox.warning(
                    self,
                    "Completed With Warnings",
                    f"Moved {moved_count} files. Skipped {len(skipped_files)} missing files."
                )
                self.set_status(
                    f"Moved {moved_count}, skipped {len(skipped_files)}",
                    5000
                )
            else:
                QMessageBox.information(self, "Success", f"Moved {moved_count} files successfully.")
                self.set_status(f"Moved {moved_count} files", 5000)
            self.list_files()

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
        qss = """
        QWidget {
            background-color: #f6f7f9;
            color: #1f2328;
            font-size: 13px;
        }
        QGroupBox {
            border: 1px solid #d8dee4;
            border-radius: 8px;
            margin-top: 10px;
            padding: 8px;
            background-color: #fbfcfe;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #374151;
        }
        QLabel#typeSortingDesc {
            color: #5f6b7a;
            font-size: 11px;
        }
        QListWidget {
            background-color: #ffffff;
            border: 1px solid #d8dee4;
            border-radius: 6px;
            padding: 6px;
        }
        QListWidget:focus {
            border: 1px solid #7aa2ff;
        }
        QPushButton {
            background-color: #eef1f5;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #e5eaf1;
        }
        QPushButton:disabled {
            background-color: #f1f3f6;
            color: #9aa4b2;
            border-color: #e1e5ea;
        }
        QPushButton[class="primary"] {
            background-color: #1f6feb;
            color: white;
            border: 1px solid #1b63d1;
            font-weight: 600;
        }
        QPushButton[class="primary"]:hover {
            background-color: #1a61cf;
        }
        QFrame {
            color: #e3e8ef;
        }
        QStatusBar {
            background-color: #f6f7f9;
            color: #4b5563;
            border-top: 1px solid #dde3ea;
        }
        """
        QApplication.instance().setStyleSheet(qss)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileSorterApp()
    window.show()
    sys.exit(app.exec())
