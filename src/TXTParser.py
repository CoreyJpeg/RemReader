import re
from pathlib import Path

from src.BookModel import (
    Book,
    Chapter
)


# ============================================================
# TXT Loading
# ============================================================

def load_text(
    file_path: str | Path
) -> str:
    """
    Read a UTF-8 text file.

    Invalid UTF-8 bytes are replaced rather than crashing so
    loosely formatted text files still have a chance to load.
    """

    path = Path(
        file_path
    )

    return path.read_text(
        encoding="utf-8",
        errors="replace"
    )


# ============================================================
# Chapter Heading Detection
# ============================================================

# Supported examples:
#
# Chapter 1
# Chapter 1: Convenience Store Blues
# Chapter 1 - Convenience Store Blues
# CHAPTER 1
# Ch. 1
# Ch 1: Title
#
# The title portion is optional.
CHAPTER_HEADING_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        chapter
        |
        ch\.?
    )
    \s*
    (?P<number>\d+)
    \s*
    (?:
        [:\-–—]\s*
        (?P<title>.+?)
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE
)


def detect_chapter_heading(
    line: str
):
    """
    Return (chapter_number, title) if the line looks like a
    chapter heading, otherwise return None.
    """

    match = CHAPTER_HEADING_PATTERN.match(
        line
    )

    if match is None:
        return None

    chapter_number = int(
        match.group("number")
    )

    chapter_title = (
        match.group("title")
        or ""
    ).strip()

    return (
        chapter_number,
        chapter_title
    )


# ============================================================
# TXT Parsing
# ============================================================

def parse_txt(
    file_path: str | Path
) -> Book:
    """
    Convert a plain text file into RemReader's common Book model.

    If chapter headings are detected, the file is split into
    chapters.

    If no headings are found, the entire file becomes Chapter 1.
    """

    path = Path(
        file_path
    )

    text = load_text(
        path
    )

    if not text.strip():
        raise ValueError(
            "The selected TXT file is empty."
        )

    lines = text.splitlines()

    headings = []

    for index, line in enumerate(
        lines
    ):

        heading = detect_chapter_heading(
            line
        )

        if heading is not None:

            chapter_number, chapter_title = heading

            headings.append(
                (
                    index,
                    chapter_number,
                    chapter_title
                )
            )

    # -------------------------
    # No chapter headings
    # -------------------------

    if not headings:

        story_title = (
            path.stem.strip()
            or "Untitled"
        )

        return Book(
            title=story_title,
            author="Unknown Author",
            source_type="TXT",
            chapters=[
                Chapter(
                    number=1,
                    title=story_title,
                    text=text.strip()
                )
            ]
        )

    # -------------------------
    # Split detected chapters
    # -------------------------

    chapters = []

    for heading_index, (
        line_index,
        detected_number,
        detected_title
    ) in enumerate(
        headings
    ):

        next_line_index = (
            headings[heading_index + 1][0]
            if heading_index + 1 < len(headings)
            else len(lines)
        )

        body_lines = lines[
            line_index + 1:
            next_line_index
        ]

        body_text = "\n".join(
            body_lines
        ).strip()

        # Prefer the author's title if one exists.
        # Otherwise use a simple generic chapter title.
        title = (
            detected_title
            or f"Chapter {detected_number}"
        )

        chapters.append(
            Chapter(
                number=detected_number,
                title=title,
                text=body_text
            )
        )

    # Use the filename as the book title because plain TXT has no
    # standard metadata container.
    story_title = (
        path.stem.strip()
        or "Untitled"
    )

    return Book(
        title=story_title,
        author="Unknown Author",
        source_type="TXT",
        chapters=chapters
    )
