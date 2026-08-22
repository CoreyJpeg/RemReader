import re
from datetime import datetime
from pathlib import Path

from src.InputManager import (
    PARSER_AUTO,
    load_book
)

from src.TextCleaner import (
    clean_text,
    CleaningOptions,
    SECTION_BREAK_MARKER
)

from src.Chunker import (
    split_into_chunks
)

from src.AudioExporter import (
    save_audio_file
)


# ============================================================
# Debug Logging
# ============================================================

def _write_debug_file(
    file_path: Path,
    text: str
):
    """Write a UTF-8 debug file."""

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path.write_text(
        text,
        encoding="utf-8"
    )


def _debug_log(
    log_file: Path | None,
    message: str,
    enabled: bool
):
    """Write a timestamped message to the log and mirror it to CMD."""

    if not enabled:
        return

    timestamp = datetime.now().strftime(
        "%H:%M:%S"
    )

    line = f"[{timestamp}] {message}"

    print(
        line,
        flush=True
    )

    if log_file is not None:

        with log_file.open(
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                line + "\n"
            )


# ============================================================
# Shared TTS Engine
# ============================================================

_tts_engine = None


def get_tts_engine(
    voice: str
):
    """
    Load Kokoro once and reuse it.

    The TTS engine handles changing voices
    and rebuilding the language pipeline when required.
    """

    global _tts_engine

    from src.TTSEngine import (
        TTSEngine
    )

    # Load engine only once
    if _tts_engine is None:

        _tts_engine = TTSEngine(
            voice=voice
        )

    else:

        # Change voice using TTSEngine's own logic.
        # This also handles language changes.
        _tts_engine.set_voice(
            voice
        )

    return _tts_engine


# ============================================================
# Voice Preview
# ============================================================

def generate_voice_preview(
    voice: str,
    output_file: str | Path
):
    """
    Generate a short preview using the shared TTS engine.
    """

    output_file = Path(
        output_file
    )

    # Make sure preview folder exists
    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Reuse existing Kokoro engine
    tts = get_tts_engine(
        voice
    )

    preview_text = (
        "Hello. This is a preview of the selected voice. "
        "This is how I will sound while reading your story."
    )

    # Generate preview audio
    audio = tts.generate_audio(
        preview_text
    )

    # Save preview
    tts.save_audio(
        audio,
        output_file
    )

    return output_file


# ============================================================
# Filename Cleaning
# ============================================================

def clean_filename(
    name: str
) -> str:
    """
    Remove characters that Windows does not allow in filenames.
    """

    name = re.sub(
        r'[<>:"/\\|?*]',
        "",
        name
    )

    # Windows also dislikes filenames ending in
    # spaces or periods.
    name = name.rstrip(
        " ."
    )

    # Fallback in case title becomes empty
    if not name:
        return "Unknown"

    return name


def clean_chapter_title(
    title: str,
    chapter_number: int
) -> str:
    """
    Remove AO3's repeated chapter-number prefixes.

    Examples:
        "Chapter 1: Ch.1: Convenience Store Blues"
        -> "Convenience Store Blues"

        "Chapter 150: Bound by What Remains"
        -> "Bound by What Remains"
    """

    cleaned = title.strip()

    # AO3 may repeat chapter numbering more than once.
    # Run several passes so:
    #
    # Chapter 1: Ch.1: Title
    #
    # becomes:
    #
    # Title
    prefixes = [
        rf"^\s*Chapter\s*{chapter_number}\s*[:.\-–—]*\s*",
        rf"^\s*Ch\.?\s*{chapter_number}\s*[:.\-–—]*\s*",
    ]

    changed = True

    while changed:
        changed = False

        for pattern in prefixes:
            new_value = re.sub(
                pattern,
                "",
                cleaned,
                count=1,
                flags=re.IGNORECASE
            )

            if new_value != cleaned:
                cleaned = new_value.strip()
                changed = True

    cleaned = clean_filename(
        cleaned
    )

    if not cleaned:
        return f"Chapter {chapter_number}"

    return cleaned


# ============================================================
# Story Loading
# ============================================================

def get_story_chapters(
    input_path: str | Path,
    parser_mode: str = PARSER_AUTO
):
    """
    Load a story through InputManager and return chapters in the
    dictionary shape currently expected by the GUI.
    """

    book = load_book(
        input_path,
        parser_mode=parser_mode
    )

    return [
        {
            "title": chapter.title,
            "text": chapter.text
        }
        for chapter in book.chapters
    ]


# ============================================================
# Chapter Generation
# ============================================================

# Length of the real audio silence inserted for author section breaks.
SECTION_BREAK_PAUSE_SECONDS = 1.75

def generate_chapters(
    input_path: str | Path,
    chapter_numbers: list[int],
    output_folder: str | Path,
    options: CleaningOptions,
    voice: str = "af_heart",
    progress_callback=None,
    debug_enabled: bool = False,
    output_format: str = "mp3",
    cover_image: str | Path | None = None,
    parser_mode: str = PARSER_AUTO
):
    """
    Generate multiple chapters and export them to the requested
    audio format.

    Kokoro is loaded once and reused for every selected chapter.
    """

    # Heavy library is imported here so opening
    # the GUI stays fast.
    import numpy as np

    input_path = Path(
        input_path
    )

    output_folder = Path(
        output_folder
    )

    # -------------------------
    # Make sure output exists
    # -------------------------

    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    # -------------------------
    # Debug logging setup
    # -------------------------

    debug_run_folder = None
    log_file = None

    if debug_enabled:

        run_name = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )

        debug_run_folder = (
            output_folder
            / "debug"
            / run_name
        )

        debug_run_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        log_file = (
            debug_run_folder
            / "generation.log"
        )

        _debug_log(log_file, "RemReader v0.1.0-alpha debug session started.", True)
        _debug_log(log_file, f"Input file: {input_path}", True)
        _debug_log(log_file, f"Output folder: {output_folder.resolve()}", True)
        _debug_log(log_file, f"Selected chapters: {chapter_numbers}", True)
        _debug_log(log_file, f"Voice: {voice}", True)

    # -------------------------
    # Load story
    # -------------------------

    book = load_book(
        input_path,
        parser_mode=parser_mode
    )

    chapters = [
        {
            "title": chapter.title,
            "text": chapter.text
        }
        for chapter in book.chapters
    ]

    story_title = book.title
    story_author = book.author

    # Make title safe for filenames
    story_title = clean_filename(
        story_title
    )

    output_format = (
        output_format
        .lower()
        .strip()
        .lstrip(".")
    )

    # Every fic/book gets its own output folder.
    story_output_folder = (
        output_folder
        / story_title
    )

    story_output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    # -------------------------
    # Optional cover image
    # -------------------------

    exported_cover_image = None

    if cover_image:

        cover_image = Path(
            cover_image
        )

        if not cover_image.exists():
            raise FileNotFoundError(
                f"Cover image does not exist: {cover_image}"
            )

        cover_suffix = (
            cover_image.suffix.lower()
            or ".jpg"
        )

        exported_cover_image = (
            story_output_folder
            / f"cover{cover_suffix}"
        )

        # Copy the selected artwork into the fic folder so the
        # generated book remains self-contained.
        import shutil

        if (
            cover_image.resolve()
            != exported_cover_image.resolve()
        ):

            shutil.copy2(
                cover_image,
                exported_cover_image
            )

    _debug_log(log_file, f"Story title: {story_title}", debug_enabled)
    _debug_log(log_file, f"Story author: {story_author}", debug_enabled)
    _debug_log(log_file, f"Cover image: {exported_cover_image}", debug_enabled)
    _debug_log(log_file, f"Story output folder: {story_output_folder.resolve()}", debug_enabled)
    _debug_log(log_file, f"Audio output format: {output_format}", debug_enabled)
    _debug_log(log_file, f"Detected chapters: {len(chapters)}", debug_enabled)

    # -------------------------
    # Check selected chapters
    # -------------------------

    for chapter_number in chapter_numbers:

        if (
            chapter_number < 1
            or chapter_number > len(chapters)
        ):
            raise ValueError(
                f"Chapter {chapter_number} does not exist. "
                f"Story contains {len(chapters)} chapters."
            )

    # -------------------------
    # Tell GUI TTS is loading
    # -------------------------

    if progress_callback is not None:

        progress_callback(
            0,
            len(chapter_numbers),
            0,
            0
        )

    # -------------------------
    # Load / reuse Kokoro
    # -------------------------

    _debug_log(log_file, "Loading / reusing Kokoro TTS engine...", debug_enabled)

    tts = get_tts_engine(
        voice
    )

    _debug_log(log_file, "TTS engine ready.", debug_enabled)

    output_files = []

    # ========================================================
    # Generate selected chapters
    # ========================================================

    for chapter_index, chapter_number in enumerate(
        chapter_numbers,
        start=1
    ):

        # Python lists start at 0
        chapter = chapters[
            chapter_number - 1
        ]

        print(
            f"\nPreparing chapter "
            f"{chapter_number}: "
            f"{chapter['title']}"
        )

        # -------------------------
        # Debug: raw extracted text
        # -------------------------

        chapter_debug_folder = None

        if debug_enabled:

            chapter_debug_name = clean_filename(
                f"Chapter {chapter_number} - {chapter['title']}"
            )

            chapter_debug_folder = (
                debug_run_folder
                / chapter_debug_name
            )

            chapter_debug_folder.mkdir(
                parents=True,
                exist_ok=True
            )

            _write_debug_file(
                chapter_debug_folder / "01_raw_extracted.txt",
                chapter["text"]
            )

            _debug_log(
                log_file,
                f"Chapter {chapter_number}: raw text saved ({len(chapter['text'])} characters).",
                True
            )

        # -------------------------
        # Clean chapter text
        # -------------------------

        cleaned_text = clean_text(
            chapter["text"],
            options
        )

        # -------------------------
        # Chapter announcement
        # -------------------------
        #
        # Announce the chapter number and cleaned chapter title before
        # the chapter body. This uses the same title cleanup as the
        # output filename so AO3's repeated "Chapter X" prefixes are
        # not spoken twice.

        spoken_chapter_title = clean_chapter_title(
            chapter["title"],
            chapter_number
        )

        chapter_announcement = (
            f"Chapter {chapter_number}. "
            f"{spoken_chapter_title}."
        )

        cleaned_text = (
            chapter_announcement
            + "\n"
            + cleaned_text
        )

        if debug_enabled:

            _write_debug_file(
                chapter_debug_folder / "02_cleaned.txt",
                cleaned_text
            )

            _debug_log(
                log_file,
                f"Chapter {chapter_number}: cleaned text saved ({len(cleaned_text)} characters).",
                True
            )

        # -------------------------
        # Split into TTS chunks
        # -------------------------

        # Split around section-break markers first so the marker is
        # never sent to Kokoro. Normal text is then chunked as usual.
        chunks = []

        for section_index, section in enumerate(
            cleaned_text.split(SECTION_BREAK_MARKER)
        ):
            section = section.strip()

            if section:
                chunks.extend(
                    split_into_chunks(
                        section,
                        max_length=500
                    )
                )

            # Keep a pause token between sections, but never after the
            # final section.
            if (
                section_index
                < len(cleaned_text.split(SECTION_BREAK_MARKER)) - 1
            ):
                chunks.append(
                    SECTION_BREAK_MARKER
                )

        print(
            f"Chapter {chapter_number} "
            f"split into {len(chunks)} chunks / section breaks."
        )

        if debug_enabled:

            chunk_debug_text = "\n\n".join(
                f"===== CHUNK {index}/{len(chunks)} =====\n{chunk}"
                for index, chunk in enumerate(
                    chunks,
                    start=1
                )
            )

            _write_debug_file(
                chapter_debug_folder / "03_tts_chunks.txt",
                chunk_debug_text
            )

            _debug_log(
                log_file,
                f"Chapter {chapter_number}: split into {len(chunks)} TTS chunks.",
                True
            )

        if not chunks:
            raise RuntimeError(
                f"Chapter {chapter_number} contains no readable text."
            )

        audio_chunks = []

        # -------------------------
        # Generate each chunk
        # -------------------------

        for chunk_number, chunk in enumerate(
            chunks,
            start=1
        ):

            print(
                f"Generating chapter "
                f"{chapter_number}: "
                f"chunk {chunk_number}/{len(chunks)}..."
            )

            _debug_log(
                log_file,
                f"Chapter {chapter_number}: generating chunk {chunk_number}/{len(chunks)} ({len(chunk)} characters).",
                debug_enabled
            )

            if chunk == SECTION_BREAK_MARKER:

                # Insert real silence rather than asking Kokoro to
                # interpret punctuation as a pause.
                sample_rate = getattr(
                    tts,
                    "sample_rate",
                    24000
                )

                audio = np.zeros(
                    int(
                        sample_rate
                        * SECTION_BREAK_PAUSE_SECONDS
                    ),
                    dtype=np.float32
                )

                _debug_log(
                    log_file,
                    (
                        f"Chapter {chapter_number}: "
                        f"section break {chunk_number}/{len(chunks)} - "
                        f"inserted {SECTION_BREAK_PAUSE_SECONDS:.2f}s silence "
                        f"at {sample_rate} Hz."
                    ),
                    debug_enabled
                )

            else:

                audio = tts.generate_audio(
                    chunk
                )

                _debug_log(
                    log_file,
                    f"Chapter {chapter_number}: chunk {chunk_number} generated ({len(audio)} samples).",
                    debug_enabled
                )

            audio_chunks.append(
                audio
            )

            # Update GUI progress
            if progress_callback is not None:

                progress_callback(
                    chapter_index,
                    len(chapter_numbers),
                    chunk_number,
                    len(chunks)
                )

        # -------------------------
        # Combine audio chunks
        # -------------------------

        _debug_log(
            log_file,
            f"Chapter {chapter_number}: combining {len(audio_chunks)} audio chunks.",
            debug_enabled
        )

        chapter_audio = np.concatenate(
            audio_chunks
        )

        # -------------------------
        # Create output filename
        # -------------------------

        chapter_title = clean_chapter_title(
            chapter["title"],
            chapter_number
        )

        output_file = (
            story_output_folder
            / (
                f"Chapter {chapter_number} - "
                f"{chapter_title}."
                f"{output_format}"
            )
        )

        # -------------------------
        # Save / export completed chapter
        # -------------------------

        _debug_log(
            log_file,
            (
                f"Chapter {chapter_number}: "
                f"exporting {output_format.upper()} to {output_file}"
            ),
            debug_enabled
        )

        chapter_metadata = {
            "title": (
                f"Chapter {chapter_number} - "
                f"{chapter_title}"
            ),
            "album": story_title,
            "artist": story_author,
            "track": chapter_number,
            "genre": "Audiobook",
            "comment": "Generated by RemReader",
        }

        save_audio_file(
            tts=tts,
            audio=chapter_audio,
            output_file=output_file,
            output_format=output_format,
            metadata=chapter_metadata,
            cover_image=exported_cover_image
        )

        output_files.append(
            output_file
        )

        print(
            f"Finished chapter "
            f"{chapter_number}: "
            f"{output_file}"
        )

    _debug_log(
        log_file,
        f"Generation complete. Created {len(output_files)} chapter(s).",
        debug_enabled
    )

    return output_files