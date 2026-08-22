import os
import subprocess
import sys
import time

from pathlib import Path


APP_VERSION = "0.3.3"

from PySide6.QtCore import (
    QObject,
    QThread,
    Signal,
    Qt,
    QUrl
)

from PySide6.QtGui import (
    QPainter,
    QPixmap,
    QDesktopServices,
    QIcon
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QCheckBox,
    QComboBox,
    QProgressBar,
    QMessageBox,
    QFrame
)

from src.Generator import (
    get_story_chapters,
    generate_chapters,
    generate_voice_preview
)

from src.TextCleaner import (
    CleaningOptions
)

from src.ChapterSelectionParser import (
    parse_chapter_selection
)

from src.InputManager import (
    PARSER_AUTO,
    SUPPORTED_PARSERS
)


# ============================================================
# Story Loading Worker
# ============================================================

class StoryLoaderWorker(QObject):

    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        file_path,
        parser_mode=PARSER_AUTO
    ):
        super().__init__()

        self.file_path = file_path
        self.parser_mode = parser_mode


    def run(self):
        """
        Load the fanfic without freezing the GUI.
        """

        try:

            chapters = get_story_chapters(
                self.file_path,
                parser_mode=self.parser_mode
            )

            self.finished.emit(
                chapters
            )

        except Exception as error:

            self.error.emit(
                str(error)
            )


# ============================================================
# TTS Generation Worker
# ============================================================

class GenerationWorker(QObject):

    # chapter number in queue,
    # total chapters,
    # current chunk,
    # total chunks
    progress = Signal(
        int,
        int,
        int,
        int
    )

    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        input_path,
        chapter_numbers,
        output_folder,
        options,
        voice,
        output_format,
        cover_image=None,
        parser_mode=PARSER_AUTO,
        debug_enabled=False
    ):
        super().__init__()

        self.input_path = input_path
        self.chapter_numbers = chapter_numbers
        self.output_folder = output_folder
        self.options = options
        self.voice = voice
        self.output_format = output_format
        self.cover_image = cover_image
        self.parser_mode = parser_mode
        self.debug_enabled = debug_enabled


    def run(self):
        """
        Generate selected chapters without freezing the GUI.
        """

        try:

            output_files = generate_chapters(
                input_path=self.input_path,
                chapter_numbers=self.chapter_numbers,
                output_folder=self.output_folder,
                options=self.options,
                voice=self.voice,
                progress_callback=self.report_progress,
                debug_enabled=self.debug_enabled,
                output_format=self.output_format,
                cover_image=self.cover_image,
                parser_mode=self.parser_mode
            )

            self.finished.emit(
                output_files
            )

        except Exception as error:

            self.error.emit(
                str(error)
            )


    def report_progress(
        self,
        chapter_index,
        chapter_total,
        chunk_number,
        chunk_total
    ):
        """
        Send generation progress back to GUI.
        """

        self.progress.emit(
            chapter_index,
            chapter_total,
            chunk_number,
            chunk_total
        )


# ============================================================
# Voice Preview Worker
# ============================================================

class VoicePreviewWorker(QObject):

    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        voice,
        output_file
    ):
        super().__init__()

        self.voice = voice
        self.output_file = output_file


    def run(self):
        """
        Generate a short voice preview without freezing the GUI.
        """

        try:

            preview_file = generate_voice_preview(
                voice=self.voice,
                output_file=self.output_file
            )

            self.finished.emit(
                preview_file
            )

        except Exception as error:

            self.error.emit(
                str(error)
            )


# ============================================================
# Main Window
# ============================================================

class RemReaderWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            f"RemReader v{APP_VERSION}"
        )



        # Wider main window
        self.resize(
            1200,
            800
        )

        # Store loaded chapters
        self.chapters = []

        # Store worker threads
        self.load_thread = None
        self.load_worker = None

        self.generation_thread = None
        self.generation_worker = None

        self.preview_thread = None
        self.preview_worker = None

        # -------------------------
        # Application icon
        # -------------------------

        icon_path = (
            Path(__file__).parent
            / "assets"
            / "RemReader.ico"
        )

        self.setWindowIcon(
            QIcon(
                str(icon_path)
            )
        )

        # -------------------------
        # Generation timing
        # -------------------------

        self.generation_start_time = None

        # -------------------------
        # Background image
        # -------------------------

        background_path = (
            Path(__file__).parent
            / "assets"
            / "REM.png"
        )

        self.background_pixmap = QPixmap(
            str(background_path)
        )

        # Debug output
        print(
            "Background path:",
            background_path
        )

        print(
            "Background exists:",
            background_path.exists()
        )

        print(
            "Background loaded:",
            not self.background_pixmap.isNull()
        )

        # -------------------------
        # Main layout
        # -------------------------

        main_layout = QVBoxLayout()

        main_layout.setContentsMargins(
            80,
            50,
            80,
            50
        )

        # -------------------------
        # Main control panel
        # -------------------------

        panel = QFrame()

        panel.setStyleSheet(
            """
            QFrame {
                background-color: rgba(20, 20, 20, 150);
                border-radius: 14px;
            }

            QLabel {
                background: transparent;
                color: white;
            }

            QCheckBox {
                background: transparent;
                color: white;
            }

            QLineEdit {
                background-color: rgba(255, 255, 255, 230);
                padding: 6px;
                border-radius: 5px;
            }

            QLineEdit:disabled {
                background-color: rgba(150, 150, 150, 180);
                color: rgba(60, 60, 60, 220);
            }

            QComboBox {
                background-color: rgba(255, 255, 255, 230);
                padding: 6px;
                border-radius: 5px;
            }

            QPushButton {
                padding: 8px;
            }
            """
        )

        panel_layout = QVBoxLayout()

        panel_layout.setSpacing(
            10
        )

        panel_layout.setContentsMargins(
            20,
            20,
            20,
            20
        )

        panel.setLayout(
            panel_layout
        )

        main_layout.addWidget(
            panel
        )

        # ====================================================
        # Story Input Group
        # ====================================================

        input_group = QFrame()

        input_group.setObjectName(
            "InputGroup"
        )

        input_group.setStyleSheet(
            """
            #InputGroup {
                background-color: rgba(0, 0, 0, 60);
                border-radius: 8px;
            }
            """
        )

        input_layout = QVBoxLayout()

        input_layout.setContentsMargins(
            12,
            10,
            12,
            10
        )

        input_layout.setSpacing(
            6
        )

        input_layout.addWidget(
            QLabel("Story file")
        )

        file_layout = QHBoxLayout()

        self.file_input = QLineEdit()

        self.file_input.setPlaceholderText(
            "Select a story file..."
        )

        self.browse_button = QPushButton(
            "Browse"
        )

        self.browse_button.clicked.connect(
            self.browse_file
        )

        file_layout.addWidget(
            self.file_input
        )

        file_layout.addWidget(
            self.browse_button
        )

        input_layout.addLayout(
            file_layout
        )

        # -------------------------
        # Input parser
        # -------------------------
        # Auto Detect is the normal user-facing path. The selector is
        # deliberately kept here for now as the manual override; it can
        # move into the full Advanced panel when that UI is introduced.

        parser_layout = QHBoxLayout()

        parser_layout.addWidget(
            QLabel("Input parser")
        )

        self.parser_select = QComboBox()

        self.parser_select.addItems(
            SUPPORTED_PARSERS
        )

        self.parser_select.setCurrentText(
            PARSER_AUTO
        )

        parser_layout.addWidget(
            self.parser_select,
            1
        )

        input_layout.addLayout(
            parser_layout
        )

        self.chapter_info = QLabel(
            "No story loaded."
        )

        input_layout.addWidget(
            self.chapter_info
        )

        input_group.setLayout(
            input_layout
        )

        panel_layout.addWidget(
            input_group
        )

        # ====================================================
        # Chapter Selection Group
        # ====================================================

        chapter_group = QFrame()

        chapter_group.setObjectName(
            "ChapterGroup"
        )

        chapter_group.setStyleSheet(
            """
            #ChapterGroup {
                background-color: rgba(0, 0, 0, 60);
                border-radius: 8px;
            }
            """
        )

        chapter_layout = QVBoxLayout()

        chapter_layout.setContentsMargins(
            12,
            10,
            12,
            10
        )

        chapter_layout.setSpacing(
            6
        )

        chapter_layout.addWidget(
            QLabel("Chapters")
        )

        self.chapter_input = QLineEdit()

        self.chapter_input.setPlaceholderText(
            "Example: 1, 3, 5-8"
        )

        chapter_layout.addWidget(
            self.chapter_input
        )

        chapter_group.setLayout(
            chapter_layout
        )

        # Chapter and Voice groups are placed side-by-side below.

        # ====================================================
        # Voice Group
        # ====================================================

        voice_group = QFrame()

        voice_group.setObjectName(
            "VoiceGroup"
        )

        voice_group.setStyleSheet(
            """
            #VoiceGroup {
                background-color: rgba(0, 0, 0, 60);
                border-radius: 8px;
            }
            """
        )

        voice_layout = QVBoxLayout()

        voice_layout.setContentsMargins(
            12,
            10,
            12,
            10
        )

        voice_layout.setSpacing(
            6
        )

        voice_layout.addWidget(
            QLabel("Voice")
        )

        # Voice dropdown + preview button
        voice_control_layout = QHBoxLayout()

        self.voice_select = QComboBox()

        self.voice_select.addItems(
            [
                "af_heart",
                "af_bella",
                "af_nicole",
                "af_sarah",
                "af_nova",
                "af_sky",
                "am_michael",
                "am_adam",
                "am_fenrir",
                "am_puck",
                "am_liam",
                "am_onyx",
                "bf_emma",
                "bf_isabella",
                "bm_george",
                "bm_fable"
            ]
        )

        self.preview_voice_button = QPushButton(
            "Preview Voice"
        )

        self.preview_voice_button.clicked.connect(
            self.preview_voice
        )

        self.preview_voice_button.setMinimumWidth(
            130
        )

        voice_control_layout.addWidget(
            self.voice_select,
            7
        )

        voice_control_layout.addWidget(
            self.preview_voice_button,
            1
        )

        voice_layout.addLayout(
            voice_control_layout
        )

        voice_group.setLayout(
            voice_layout
        )

        # Voice, Chapters and Y/N Replacement are placed
        # together in the left settings column below.

        # ====================================================
        # Y/N Replacement Group
        # ====================================================

        replace_group = QFrame()

        replace_group.setObjectName(
            "ReplaceGroup"
        )

        replace_group.setStyleSheet(
            """
            #ReplaceGroup {
                background-color: rgba(0, 0, 0, 60);
                border-radius: 8px;
            }
            """
        )

        replace_layout = QVBoxLayout()

        replace_layout.setContentsMargins(
            12,
            10,
            12,
            10
        )

        replace_layout.setSpacing(
            6
        )

        self.replace_yn = QCheckBox(
            "Replace Y/N"
        )

        self.replace_yn.setChecked(
            True
        )

        replace_layout.addWidget(
            self.replace_yn
        )

        self.name_label = QLabel(
            "Replacement name"
        )

        replace_layout.addWidget(
            self.name_label
        )

        self.name_input = QLineEdit(
            "Y/N"
        )

        replace_layout.addWidget(
            self.name_input
        )

        self.replace_yn.toggled.connect(
            self.name_input.setEnabled
        )

        self.replace_yn.toggled.connect(
            self.name_label.setEnabled
        )

        self.name_input.setEnabled(
            self.replace_yn.isChecked()
        )

        self.name_label.setEnabled(
            self.replace_yn.isChecked()
        )

        replace_group.setLayout(
            replace_layout
        )

        # Y/N Replacement and Other Options are placed
        # side-by-side below.

        # ====================================================
        # Other Options Group
        # ====================================================

        options_group = QFrame()

        options_group.setObjectName(
            "OptionsGroup"
        )

        options_group.setStyleSheet(
            """
            #OptionsGroup {
                background-color: rgba(0, 0, 0, 60);
                border-radius: 8px;
            }
            """
        )

        options_layout = QVBoxLayout()

        options_layout.setContentsMargins(
            12,
            10,
            12,
            10
        )

        options_layout.setSpacing(
            6
        )

        options_layout.addWidget(
            QLabel("Other options")
        )

        self.author_notes = QCheckBox(
            "Read author notes"
        )

        self.author_notes.setChecked(
            True
        )

        options_layout.addWidget(
            self.author_notes
        )

        # -------------------------
        # Section break handling
        # -------------------------

        section_break_label = QLabel(
            "Section breaks"
        )

        options_layout.addWidget(
            section_break_label
        )

        self.section_break_mode = QComboBox()

        self.section_break_mode.addItems(
            [
                "Pause",
                "Say \"Scene Change\"",
                "Ignore"
            ]
        )

        # Pause is the new default because many authors use separators
        # for pacing rather than a literal change of scene.
        self.section_break_mode.setCurrentText(
            "Pause"
        )

        options_layout.addWidget(
            self.section_break_mode
        )

        # -------------------------
        # Output format
        # -------------------------

        output_format_label = QLabel(
            "Output format"
        )

        options_layout.addWidget(
            output_format_label
        )

        self.output_format_select = QComboBox()

        self.output_format_select.addItems(
            [
                "MP3",
                "WAV",
                "FLAC",
                "M4A",
                "OGG"
            ]
        )

        self.output_format_select.setCurrentText(
            "MP3"
        )

        options_layout.addWidget(
            self.output_format_select
        )

        # -------------------------
        # Optional cover image
        # -------------------------

        cover_label = QLabel(
            "Cover image"
        )

        options_layout.addWidget(
            cover_label
        )

        cover_layout = QHBoxLayout()

        self.cover_input = QLineEdit()

        self.cover_input.setPlaceholderText(
            "Optional cover image..."
        )

        self.cover_browse_button = QPushButton(
            "Browse"
        )

        self.cover_browse_button.clicked.connect(
            self.browse_cover_image
        )

        cover_layout.addWidget(
            self.cover_input,
            7
        )

        cover_layout.addWidget(
            self.cover_browse_button,
            1
        )

        options_layout.addLayout(
            cover_layout
        )

        self.debug_logs = QCheckBox(
            "Generate debug logs"
        )

        self.debug_logs.setChecked(
            False
        )

        options_layout.addWidget(
            self.debug_logs
        )

        options_group.setLayout(
            options_layout
        )

        # -------------------------
        # Main settings columns
        # -------------------------

        settings_layout = QHBoxLayout()

        settings_layout.setSpacing(
            12
        )

        # -------------------------
        # Left column
        # -------------------------

        left_settings_layout = QVBoxLayout()

        left_settings_layout.setSpacing(
            10
        )

        left_settings_layout.addWidget(
            chapter_group
        )

        left_settings_layout.addWidget(
            voice_group
        )

        left_settings_layout.addWidget(
            replace_group
        )

        left_settings_layout.addStretch()

        # -------------------------
        # Right column
        # -------------------------

        right_settings_layout = QVBoxLayout()

        right_settings_layout.setSpacing(
            10
        )

        right_settings_layout.addWidget(
            options_group
        )

        right_settings_layout.addStretch()

        settings_layout.addLayout(
            left_settings_layout,
            1
        )

        settings_layout.addLayout(
            right_settings_layout,
            1
        )

        panel_layout.addLayout(
            settings_layout
        )

        # ====================================================
        # Generate Audio Group
        # ====================================================

        generate_group = QFrame()

        generate_group.setObjectName(
            "GenerateGroup"
        )

        generate_group.setStyleSheet(
            """
            #GenerateGroup {
                background-color: rgba(0, 0, 0, 60);
                border-radius: 8px;
            }
            """
        )

        generate_layout = QVBoxLayout()

        generate_layout.setContentsMargins(
            12,
            10,
            12,
            10
        )

        generate_layout.setSpacing(
            8
        )

        # -------------------------
        # Generate button row
        # -------------------------

        button_layout = QHBoxLayout()

        button_layout.setSpacing(
            8
        )

        self.generate_button = QPushButton(
            "Generate Audio"
        )

        self.generate_button.clicked.connect(
            self.generate_audio
        )

        self.open_output_button = QPushButton(
            "Open Output Folder"
        )

        self.open_output_button.clicked.connect(
            self.open_output_folder
        )

        self.open_output_button.setMinimumWidth(
            140
        )

        button_layout.addWidget(
            self.generate_button,
            7
        )

        button_layout.addWidget(
            self.open_output_button,
            1
        )

        generate_layout.addLayout(
            button_layout
        )

        # -------------------------
        # Progress bar
        # -------------------------

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(
            0,
            100
        )

        self.progress_bar.setValue(
            0
        )

        generate_layout.addWidget(
            self.progress_bar
        )

        # -------------------------
        # Status / ETA
        # -------------------------

        self.status_label = QLabel(
            "Ready."
        )

        generate_layout.addWidget(
            self.status_label
        )

        generate_group.setLayout(
            generate_layout
        )

        panel_layout.addWidget(
            generate_group
        )

        # -------------------------
        # Version label
        # -------------------------

        version_layout = QHBoxLayout()
        version_layout.addStretch()

        self.version_label = QLabel(
            f"v{APP_VERSION}"
        )

        self.version_label.setStyleSheet(
            "color: rgba(255, 255, 255, 110); font-size: 11px;"
        )

        version_layout.addWidget(
            self.version_label
        )

        main_layout.addLayout(
            version_layout
        )

        # -------------------------
        # Apply main layout
        # -------------------------

        self.setLayout(
            main_layout
        )


    # ========================================================
    # Background Drawing
    # ========================================================

    def paintEvent(
        self,
        event
    ):
        """
        Draw and scale the background image.
        """

        super().paintEvent(
            event
        )

        if self.background_pixmap.isNull():
            return

        painter = QPainter(
            self
        )

        scaled_background = (
            self.background_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        )

        x = (
            self.width()
            - scaled_background.width()
        ) // 2

        y = (
            self.height()
            - scaled_background.height()
        ) // 2

        painter.drawPixmap(
            x,
            y,
            scaled_background
        )


    # ========================================================
    # Voice Preview
    # ========================================================

    def preview_voice(self):
        """
        Generate and play a short preview of the selected voice.
        """

        voice = (
            self.voice_select.currentText()
        )

        output_folder = Path(
            "Output"
        )

        output_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        preview_file = (
            output_folder
            / "voice_preview.wav"
        )

        self.preview_voice_button.setEnabled(
            False
        )

        self.status_label.setText(
            f"Loading preview for {voice}..."
        )

        # Create preview thread
        self.preview_thread = QThread()

        self.preview_worker = VoicePreviewWorker(
            voice=voice,
            output_file=preview_file
        )

        self.preview_worker.moveToThread(
            self.preview_thread
        )

        # Start worker
        self.preview_thread.started.connect(
            self.preview_worker.run
        )

        # Preview finished
        self.preview_worker.finished.connect(
            self.voice_preview_finished
        )

        # Preview error
        self.preview_worker.error.connect(
            self.voice_preview_error
        )

        # Stop thread
        self.preview_worker.finished.connect(
            self.preview_thread.quit
        )

        self.preview_worker.error.connect(
            self.preview_thread.quit
        )

        # Clean up worker
        self.preview_worker.finished.connect(
            self.preview_worker.deleteLater
        )

        self.preview_worker.error.connect(
            self.preview_worker.deleteLater
        )

        # Clean up thread
        self.preview_thread.finished.connect(
            self.preview_thread.deleteLater
        )

        self.preview_thread.start()


    def voice_preview_finished(
        self,
        preview_file
    ):
        """
        Play the generated voice preview.
        """

        self.preview_voice_button.setEnabled(
            True
        )

        self.status_label.setText(
            "Voice preview ready."
        )
        
        # DISABLED TEMPORARILY
        #self.open_file(
        #    preview_file
        #)


    def voice_preview_error(
        self,
        error_message
    ):
        """
        Called if voice preview generation fails.
        """

        self.preview_voice_button.setEnabled(
            True
        )

        self.status_label.setText(
            "Voice preview failed."
        )

        QMessageBox.critical(
            self,
            "Voice Preview Error",
            error_message
        )


    # ========================================================
    # File / Folder Opening
    # ========================================================

    def open_file(
        self,
        file_path
    ):
        """
        Open a file using the operating system's default program.
        """

        file_path = Path(
            file_path
        ).resolve()

        # Windows
        if sys.platform.startswith(
            "win"
        ):
            os.startfile(
                file_path
            )

        # macOS
        elif sys.platform == "darwin":
            subprocess.run(
                [
                    "open",
                    str(file_path)
                ]
            )

        # Linux
        else:
            subprocess.run(
                [
                    "xdg-open",
                    str(file_path)
                ]
            )


    def open_output_folder(self):
        """
        Open the RemReader Output folder.
        """

        output_folder = Path(
            "Output"
        )

        output_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        self.open_file(
            output_folder
        )


    # ========================================================
    # File Selection
    # ========================================================

    def browse_file(self):
        """
        Ask the user to select an AO3 HTML file.
        """

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select story",
            "",
            (
                "Story Files (*.html *.htm *.txt *.epub *.pdf);;"
                "HTML Files (*.html *.htm);;"
                "Text Files (*.txt);;"
                "EPUB Files (*.epub);;"
                "PDF Files (*.pdf);;"
                "All Files (*)"
            )
        )

        if not file_path:
            return

        self.file_input.setText(
            file_path
        )

        self.load_story(
            file_path
        )


    def browse_cover_image(self):
        """
        Ask the user to select optional cover artwork.
        """

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select cover image",
            "",
            (
                "Image Files (*.jpg *.jpeg *.png *.webp);;"
                "All Files (*)"
            )
        )

        if not file_path:
            return

        self.cover_input.setText(
            file_path
        )


    # ========================================================
    # Story Loading
    # ========================================================

    def load_story(
        self,
        file_path
    ):
        """
        Load story in a background thread.
        """

        self.browse_button.setEnabled(
            False
        )

        self.generate_button.setEnabled(
            False
        )

        self.status_label.setText(
            "Loading story..."
        )

        self.chapter_info.setText(
            "Reading chapters..."
        )

        self.load_thread = QThread()

        self.load_worker = StoryLoaderWorker(
            file_path,
            parser_mode=self.parser_select.currentText()
        )

        self.load_worker.moveToThread(
            self.load_thread
        )

        self.load_thread.started.connect(
            self.load_worker.run
        )

        self.load_worker.finished.connect(
            self.story_loaded
        )

        self.load_worker.error.connect(
            self.story_load_error
        )

        self.load_worker.finished.connect(
            self.load_thread.quit
        )

        self.load_worker.error.connect(
            self.load_thread.quit
        )

        self.load_worker.finished.connect(
            self.load_worker.deleteLater
        )

        self.load_worker.error.connect(
            self.load_worker.deleteLater
        )

        self.load_thread.finished.connect(
            self.load_thread.deleteLater
        )

        self.load_thread.start()


    def story_loaded(
        self,
        chapters
    ):
        """
        Called when story loading succeeds.
        """

        self.chapters = chapters

        self.chapter_info.setText(
            f"Detected {len(chapters)} chapters."
        )

        self.chapter_input.setPlaceholderText(
            f"Example: 1, 3, 5-{min(10, len(chapters))}"
        )

        self.status_label.setText(
            "Story loaded."
        )

        self.browse_button.setEnabled(
            True
        )

        self.generate_button.setEnabled(
            True
        )


    def story_load_error(
        self,
        error_message
    ):
        """
        Called if story loading fails.
        """

        self.chapter_info.setText(
            "Failed to load story."
        )

        self.status_label.setText(
            "Story loading failed."
        )

        self.browse_button.setEnabled(
            True
        )

        self.generate_button.setEnabled(
            True
        )

        QMessageBox.critical(
            self,
            "Story Loading Error",
            error_message
        )


    # ========================================================
    # Audio Generation
    # ========================================================

    def generate_audio(self):
        """
        Generate the selected chapters.
        """

        if not self.chapters:

            QMessageBox.warning(
                self,
                "No Story Loaded",
                "Please load a story first."
            )

            return

        # -------------------------
        # Parse chapter selection
        # -------------------------

        try:

            chapter_numbers = parse_chapter_selection(
                self.chapter_input.text()
            )

        except ValueError as error:

            QMessageBox.warning(
                self,
                "Invalid Chapter Selection",
                str(error)
            )

            return

        # Make sure all chapters exist
        for chapter_number in chapter_numbers:

            if (
                chapter_number < 1
                or chapter_number > len(self.chapters)
            ):

                QMessageBox.warning(
                    self,
                    "Invalid Chapter",
                    f"Chapter {chapter_number} does not exist."
                )

                return

        # -------------------------
        # Text cleaning options
        # -------------------------

        # Translate the friendly GUI label into the internal
        # TextCleaner section-break mode.
        section_break_modes = {
            "Pause": "pause",
            "Say \"Scene Change\"": "announce",
            "Ignore": "ignore"
        }

        section_break_mode = section_break_modes[
            self.section_break_mode.currentText()
        ]

        options = CleaningOptions(
            read_author_notes=
                self.author_notes.isChecked(),

            replace_yn=
                self.replace_yn.isChecked(),

            yn_name=
                self.name_input.text(),

            section_break_mode=
                section_break_mode,

            scene_change_text=
                "Scene change"
        )

        voice = (
            self.voice_select.currentText()
        )

        output_format = (
            self.output_format_select
            .currentText()
            .lower()
        )

        cover_image = (
            self.cover_input.text().strip()
            or None
        )

        input_path = (
            self.file_input.text()
        )

        output_folder = Path(
            "Output"
        )

        # Disable buttons while generating
        self.generate_button.setEnabled(
            False
        )

        self.browse_button.setEnabled(
            False
        )

        self.preview_voice_button.setEnabled(
            False
        )

        self.progress_bar.setValue(
            0
        )

        self.status_label.setText(
            "Loading TTS model..."
        )

        # Start ETA timer
        self.generation_start_time = (
            time.time()
        )

        # Create generation thread
        self.generation_thread = QThread()

        self.generation_worker = GenerationWorker(
            input_path=input_path,
            chapter_numbers=chapter_numbers,
            output_folder=output_folder,
            options=options,
            voice=voice,
            output_format=output_format,
            cover_image=cover_image,
            parser_mode=self.parser_select.currentText(),
            debug_enabled=self.debug_logs.isChecked()
        )

        self.generation_worker.moveToThread(
            self.generation_thread
        )

        self.generation_thread.started.connect(
            self.generation_worker.run
        )

        self.generation_worker.progress.connect(
            self.update_progress
        )

        self.generation_worker.finished.connect(
            self.generation_finished
        )

        self.generation_worker.error.connect(
            self.generation_error
        )

        self.generation_worker.finished.connect(
            self.generation_thread.quit
        )

        self.generation_worker.error.connect(
            self.generation_thread.quit
        )

        self.generation_worker.finished.connect(
            self.generation_worker.deleteLater
        )

        self.generation_worker.error.connect(
            self.generation_worker.deleteLater
        )

        self.generation_thread.finished.connect(
            self.generation_thread.deleteLater
        )

        self.generation_thread.start()


    # ========================================================
    # Progress Updates
    # ========================================================

    def update_progress(
        self,
        chapter_index,
        chapter_total,
        chunk_number,
        chunk_total
    ):
        """
        Update progress bar and calculate ETA during generation.
        """

        if chapter_index == 0:

            self.status_label.setText(
                "Loading TTS model..."
            )

            return

        if chunk_total <= 0:
            return

        chunk_percent = (
            chunk_number
            / chunk_total
        )

        completed_chapters = (
            chapter_index - 1
        )

        overall_progress = (
            completed_chapters
            + chunk_percent
        ) / chapter_total

        percent = int(
            overall_progress * 100
        )

        self.progress_bar.setValue(
            percent
        )

        # -------------------------
        # Calculate ETA
        # -------------------------

        eta_text = (
            "Calculating..."
        )

        if (
            self.generation_start_time is not None
            and overall_progress > 0
        ):

            elapsed = (
                time.time()
                - self.generation_start_time
            )

            estimated_total = (
                elapsed
                / overall_progress
            )

            remaining = (
                estimated_total
                - elapsed
            )

            eta_text = self.format_time(
                remaining
            )

        self.status_label.setText(
            f"Chapter {chapter_index}/{chapter_total} "
            f"- Chunk {chunk_number}/{chunk_total} "
            f"- Overall {percent}% "
            f"- ETA: {eta_text}"
        )


    # ========================================================
    # Time Formatting
    # ========================================================

    def format_time(
        self,
        seconds
    ):
        """
        Convert seconds into a readable ETA.
        """

        seconds = max(
            0,
            int(seconds)
        )

        hours = (
            seconds
            // 3600
        )

        minutes = (
            seconds % 3600
        ) // 60

        seconds = (
            seconds % 60
        )

        if hours > 0:

            return (
                f"{hours}h "
                f"{minutes}m "
                f"{seconds}s"
            )

        if minutes > 0:

            return (
                f"{minutes}m "
                f"{seconds}s"
            )

        return (
            f"{seconds}s"
        )


    # ========================================================
    # Generation Finished
    # ========================================================

    def generation_finished(
        self,
        output_files
    ):
        """
        Called after all selected chapters are generated.
        """

        self.progress_bar.setValue(
            100
        )

        elapsed_text = ""

        if self.generation_start_time is not None:

            elapsed = (
                time.time()
                - self.generation_start_time
            )

            elapsed_text = self.format_time(
                elapsed
            )

        self.status_label.setText(
            f"Finished {len(output_files)} chapter(s). "
            f"Time: {elapsed_text}"
        )

        self.generate_button.setEnabled(
            True
        )

        self.browse_button.setEnabled(
            True
        )

        self.preview_voice_button.setEnabled(
            True
        )

        self.generation_start_time = None

        QMessageBox.information(
            self,
            "Finished",
            f"Generated {len(output_files)} chapter(s).\n\n"
            f"Saved in the Output folder."
        )


    # ========================================================
    # Generation Error
    # ========================================================

    def generation_error(
        self,
        error_message
    ):
        """
        Called if generation fails.
        """

        self.status_label.setText(
            "Generation failed."
        )

        self.generate_button.setEnabled(
            True
        )

        self.browse_button.setEnabled(
            True
        )

        self.preview_voice_button.setEnabled(
            True
        )

        self.generation_start_time = None

        QMessageBox.critical(
            self,
            "Generation Error",
            error_message
        )