import sys
import os
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QVBoxLayout, QPushButton, QLabel,
    QListWidget, QMessageBox, QWidget, QListWidgetItem, QCheckBox
)
from PySide2.QtGui import QBrush, QColor
from datetime import datetime

# NOTE: PIL imports were in the original file, but not used.
# Kept out to avoid needing extra dependencies.
# from PIL import Image
# from PIL.ExifTags import TAGS


class FileSorterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Sorter by Modified Date")

        # Layout and widgets
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)

        self.folder_label = QLabel("Selected Folder: None")
        layout.addWidget(self.folder_label)

        self.choose_folder_button = QPushButton("Choose Folder")
        self.choose_folder_button.clicked.connect(self.choose_folder)
        layout.addWidget(self.choose_folder_button)

        self.file_list = QListWidget()
        layout.addWidget(self.file_list)

        # -------- File Type Sorting checkbox + description --------
        self.enable_type_sorting_checkbox = QCheckBox("Enable File Type Sorting")
        self.enable_type_sorting_checkbox.stateChanged.connect(self.update_preview)
        layout.addWidget(self.enable_type_sorting_checkbox)

        # Extensions that this option will sort into subfolders
        self.type_sorting_formats = [
            ".jpg", ".jpeg", ".png",
            ".dng",
            ".mp4", ".mov",
            ".insv",  # Insta360 video
            ".insp",  # Insta360 photo container
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
        self.type_sorting_desc.setStyleSheet("color: #666666; font-size: 11px;")
        layout.addWidget(self.type_sorting_desc)
        # --------------------------------------------------------

        self.confirm_button = QPushButton("Confirm and Move Files")
        self.confirm_button.clicked.connect(self.confirm_and_move_files)
        self.confirm_button.setEnabled(False)
        layout.addWidget(self.confirm_button)

        self.folder_path = ""
        self.files_to_sort = {}

    def choose_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.folder_path = folder_path
            self.folder_label.setText(f"Selected Folder: {folder_path}")
            self.list_files()

    def list_files(self):
        self.file_list.clear()
        if not os.path.isdir(self.folder_path):
            QMessageBox.warning(self, "Error", "The selected path is not a valid folder.")
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
            folder_item = QListWidgetItem(f"Folder: {folder}")
            folder_item.setBackground(QBrush(QColor("#d1e7dd")))  # Light green background for folder headers
            folder_item.setForeground(QBrush(QColor("#0f5132")))  # Dark green text for folder headers
            self.file_list.addItem(folder_item)

            for file in files:
                file_item = QListWidgetItem(f"  - {file}")
                file_item.setForeground(QBrush(QColor("#000000")))  # Black text for file names
                self.file_list.addItem(file_item)

    def confirm_and_move_files(self):
        if not self.files_to_sort:
            QMessageBox.warning(self, "Error", "No files to sort.")
            return

        reply = QMessageBox.question(
            self, "Confirm", "Do you want to move the files to folders based on their modified dates?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            for date, files in self.files_to_sort.items():
                for file in files:
                    source_path = os.path.join(self.folder_path, file)
                    file_lower = file.lower()

                    # Determine the destination folder (kept compatible with original behavior)
                    if file_lower.endswith(".srt"):
                        destination_folder = os.path.join(self.folder_path, date, "Video")
                        os.makedirs(destination_folder, exist_ok=True)
                    elif file_lower.endswith(".db"):
                        destination_folder = os.path.join(self.folder_path, date)
                        os.makedirs(destination_folder, exist_ok=True)
                    else:
                        destination_folder = os.path.join(self.folder_path, date)
                        if self.enable_type_sorting_checkbox.isChecked():
                            file_type = self.get_file_type(file)
                            destination_folder = os.path.join(destination_folder, file_type)
                            os.makedirs(destination_folder, exist_ok=True)

                    destination_path = os.path.join(destination_folder, file)
                    os.rename(source_path, destination_path)

            QMessageBox.information(self, "Success", "Files have been moved successfully.")
            self.list_files()

    def get_file_type(self, file_name):
        name = file_name.lower()

        # Photos / stills
        if name.endswith((".jpg", ".jpeg", ".png", ".insp")):
            return "Jpg"

        # Video
        if name.endswith((".mp4", ".mov", ".insv", ".srt")):
            return "Video"

        # Raw
        if name.endswith(".dng"):
            return "Raw"

        # Database
        if name.endswith(".db"):
            return "Database"

        return "Other"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileSorterApp()
    window.show()
    sys.exit(app.exec_())