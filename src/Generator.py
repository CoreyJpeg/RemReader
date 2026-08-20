import re
from pathlib import Path

from src.AO3Parser import (
    get_chapters,
    get_story_title
)

from src.TextCleaner import (
    clean_text,
    CleaningOptions
)

from src.Chunker import (
    split_into_chunks
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


# ============================================================
# Story Loading
# ============================================================

def get_story_chapters(
    input_path: str | Path
):
    """
    Load a story and return all detected chapters.
    """

    chapters = get_chapters(
        input_path
    )

    return chapters


# ============================================================
# Chapter Generation
# ============================================================

def generate_chapters(
    input_path: str | Path,
    chapter_numbers: list[int],
    output_folder: str | Path,
    options: CleaningOptions,
    voice: str = "af_heart",
    progress_callback=None
):
    """
    Generate multiple chapters as WAV files.

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
    # Load story
    # -------------------------

    chapters = get_chapters(
        input_path
    )

    # Get AO3 story title
    story_title = get_story_title(
        input_path
    )

    # Make title safe for filenames
    story_title = clean_filename(
        story_title
    )

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

    tts = get_tts_engine(
        voice
    )

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
        # Clean chapter text
        # -------------------------

        cleaned_text = clean_text(
            chapter["text"],
            options
        )

        # -------------------------
        # Split into TTS chunks
        # -------------------------

        chunks = split_into_chunks(
            cleaned_text,
            max_length=500
        )

        print(
            f"Chapter {chapter_number} "
            f"split into {len(chunks)} chunks."
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

            audio = tts.generate_audio(
                chunk
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

        chapter_audio = np.concatenate(
            audio_chunks
        )

        # -------------------------
        # Create output filename
        # -------------------------

        chapter_title = clean_filename(
            chapter["title"]
        )

        output_file = (
            output_folder
            / (
                f"{story_title} - "
                f"{chapter_title}.wav"
            )
        )

        # -------------------------
        # Save completed chapter
        # -------------------------

        tts.save_audio(
            chapter_audio,
            output_file
        )

        output_files.append(
            output_file
        )

        print(
            f"Finished chapter "
            f"{chapter_number}: "
            f"{output_file}"
        )

    return output_files