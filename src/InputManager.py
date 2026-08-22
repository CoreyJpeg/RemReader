from pathlib import Path

from src.AO3Parser import (
    get_chapters,
    get_story_author,
    get_story_title,
)
from src.BookModel import Book, Chapter

from src.TXTParser import (
    parse_txt
)

from src.GenericHTMLParser import (
    parse_generic_html
)

from src.EPUBParser import (
    parse_epub
)


PARSER_AUTO = "Auto Detect"
PARSER_AO3 = "AO3 HTML"
PARSER_GENERIC_HTML = "Generic HTML"
PARSER_TXT = "TXT"
PARSER_EPUB = "EPUB"

SUPPORTED_PARSERS = [
    PARSER_AUTO,
    PARSER_AO3,
    PARSER_GENERIC_HTML,
    PARSER_TXT,
    PARSER_EPUB,
]


def _read_text(path: Path) -> str:
    """Read enough source text to identify the input safely."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def looks_like_ao3_html(file_path: str | Path) -> bool:
    """
    Detect the structural markers used by downloaded AO3 works.

    We intentionally require multiple AO3-style markers rather than
    trusting the .html extension alone.
    """
    path = Path(file_path)

    if path.suffix.lower() not in {".html", ".htm"}:
        return False

    source = _read_text(path).lower()

    has_preface = 'id="preface"' in source or "id='preface'" in source
    has_userstuff = "userstuff" in source
    has_chapter_meta = "meta group" in source

    return has_preface and has_userstuff and has_chapter_meta


def detect_parser(file_path: str | Path) -> str:
    """Return the best parser for the selected file."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Story file does not exist: {path}"
        )

    suffix = path.suffix.lower()

    if suffix in {".html", ".htm"}:

        # Prefer the specialised AO3 parser whenever its structural
        # markers are confidently detected.
        if looks_like_ao3_html(path):
            return PARSER_AO3

        # Any other HTML is handled by the forgiving generic parser.
        return PARSER_GENERIC_HTML

    if suffix == ".txt":
        return PARSER_TXT

    if suffix == ".epub":
        return PARSER_EPUB

    if suffix == ".pdf":
        raise ValueError(
            "PDF detected. PDF support is planned for a later release."
        )

    raise ValueError(
        f"Unsupported input type: {suffix or 'no file extension'}."
    )


def load_book(
    file_path: str | Path,
    parser_mode: str = PARSER_AUTO
) -> Book:
    """
    Load any supported source into RemReader's common Book model.
    """
    if parser_mode == PARSER_AUTO:
        parser_mode = detect_parser(file_path)

    if parser_mode == PARSER_AO3:
        raw_chapters = get_chapters(file_path)

        chapters = [
            Chapter(
                number=index,
                title=chapter["title"],
                text=chapter["text"],
            )
            for index, chapter in enumerate(
                raw_chapters,
                start=1
            )
        ]

        if not chapters:
            raise ValueError(
                "AO3 parser did not find any readable chapters."
            )

        return Book(
            title=get_story_title(file_path),
            author=get_story_author(file_path),
            chapters=chapters,
            source_type=PARSER_AO3,
        )

    if parser_mode == PARSER_GENERIC_HTML:
        return parse_generic_html(
            file_path
        )

    if parser_mode == PARSER_TXT:
        return parse_txt(
            file_path
        )

    if parser_mode == PARSER_EPUB:
        return parse_epub(
            file_path
        )

    raise ValueError(
        f"Unknown parser mode: {parser_mode}"
    )
