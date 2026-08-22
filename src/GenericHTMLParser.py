import re
from pathlib import Path

from bs4 import BeautifulSoup

from src.BookModel import (
    Book,
    Chapter
)


# ============================================================
# Chapter Heading Detection
# ============================================================

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
    text: str
):
    """
    Return (chapter_number, chapter_title) when a heading looks
    like a chapter heading, otherwise return None.
    """

    match = CHAPTER_HEADING_PATTERN.match(
        text
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
# HTML Loading / Cleanup
# ============================================================

def load_html(
    file_path: str | Path
) -> BeautifulSoup:

    path = Path(
        file_path
    )

    html = path.read_text(
        encoding="utf-8",
        errors="replace"
    )

    return BeautifulSoup(
        html,
        "html.parser"
    )


def remove_non_reading_content(
    soup: BeautifulSoup
):
    """
    Remove common page chrome that should never be narrated.
    """

    for tag in soup.find_all(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "form",
            "nav",
        ]
    ):
        tag.decompose()


# ============================================================
# Metadata
# ============================================================

def get_generic_title(
    soup: BeautifulSoup,
    file_path: str | Path
) -> str:
    """
    Try common HTML metadata locations, then fall back to filename.
    """

    selectors = [
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "title"}),
    ]

    for tag_name, attrs in selectors:

        element = soup.find(
            tag_name,
            attrs=attrs
        )

        if element is not None:

            value = element.get(
                "content"
            )

            if value and value.strip():
                return value.strip()

    title_tag = soup.find(
        "title"
    )

    if title_tag is not None:

        title = title_tag.get_text(
            " ",
            strip=True
        )

        if title:
            return title

    h1 = soup.find(
        "h1"
    )

    if h1 is not None:

        title = h1.get_text(
            " ",
            strip=True
        )

        # Avoid treating "Chapter 1" as the book title.
        if (
            title
            and detect_chapter_heading(title) is None
        ):
            return title

    return (
        Path(file_path).stem.strip()
        or "Unknown Story"
    )


def get_generic_author(
    soup: BeautifulSoup
) -> str:
    """
    Try common author metadata / byline patterns.
    """

    meta_author = soup.find(
        "meta",
        attrs={"name": "author"}
    )

    if meta_author is not None:

        value = meta_author.get(
            "content"
        )

        if value and value.strip():
            return value.strip()

    selectors = [
        "a[rel='author']",
        ".byline",
        ".author",
        "[class*='author']",
    ]

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if element is not None:

            author = element.get_text(
                " ",
                strip=True
            )

            if author:
                return author

    return "Unknown Author"


# ============================================================
# Readable Block Extraction
# ============================================================

def extract_readable_blocks(
    soup: BeautifulSoup,
    story_title: str
):
    """
    Return page content as ordered blocks.

    Each block is:
        ("chapter", number, title)
        ("text", text)
        ("separator", "*****")

    Paragraph-like tags preserve inline formatting as normal text.
    """

    body = (
        soup.body
        if soup.body is not None
        else soup
    )

    blocks = []

    readable_tags = [
        "h1",
        "h2",
        "h3",
        "h4",
        "p",
        "blockquote",
        "li",
        "pre",
        "hr",
    ]

    for element in body.find_all(
        readable_tags
    ):

        # Avoid duplicate nested content such as <li><p>...</p></li>.
        if element.name in {
            "p",
            "blockquote",
            "li",
            "pre",
        }:

            if element.find_parent(
                [
                    "p",
                    "blockquote",
                    "li",
                    "pre",
                ]
            ) is not None:
                continue

        if element.name == "hr":

            blocks.append(
                (
                    "separator",
                    "*****"
                )
            )

            continue

        text = element.get_text(
            " ",
            strip=True
        )

        if not text:
            continue

        if element.name in {
            "h1",
            "h2",
            "h3",
            "h4",
        }:

            chapter_heading = detect_chapter_heading(
                text
            )

            if chapter_heading is not None:

                chapter_number, chapter_title = chapter_heading

                blocks.append(
                    (
                        "chapter",
                        chapter_number,
                        chapter_title
                    )
                )

                continue

            # Do not narrate a page heading that merely repeats the
            # detected story title.
            if text.casefold() == story_title.casefold():
                continue

        blocks.append(
            (
                "text",
                text
            )
        )

    return blocks


# ============================================================
# Generic HTML Parsing
# ============================================================

def parse_generic_html(
    file_path: str | Path
) -> Book:
    """
    Convert arbitrary readable HTML into RemReader's Book model.

    Strategy:
    1. Extract common title / author metadata.
    2. Detect chapter-style headings where possible.
    3. Preserve paragraphs and horizontal-rule section breaks.
    4. If no chapter headings exist, treat all readable content as
       one chapter.
    """

    soup = load_html(
        file_path
    )

    remove_non_reading_content(
        soup
    )

    story_title = get_generic_title(
        soup,
        file_path
    )

    story_author = get_generic_author(
        soup
    )

    blocks = extract_readable_blocks(
        soup,
        story_title
    )

    if not blocks:
        raise ValueError(
            "Generic HTML parser could not find any readable text."
        )

    has_chapters = any(
        block[0] == "chapter"
        for block in blocks
    )

    # -------------------------
    # Fallback: one chapter
    # -------------------------

    if not has_chapters:

        text_parts = []

        for block in blocks:

            if block[0] == "text":
                text_parts.append(
                    block[1]
                )

            elif block[0] == "separator":
                text_parts.append(
                    block[1]
                )

        body_text = "\n".join(
            text_parts
        ).strip()

        if not body_text:
            raise ValueError(
                "Generic HTML parser could not find readable body text."
            )

        return Book(
            title=story_title,
            author=story_author,
            source_type="Generic HTML",
            chapters=[
                Chapter(
                    number=1,
                    title=story_title,
                    text=body_text
                )
            ]
        )

    # -------------------------
    # Split detected chapters
    # -------------------------

    chapters = []

    current_number = None
    current_title = ""
    current_parts = []

    def finish_current_chapter():

        if current_number is None:
            return

        chapter_text = "\n".join(
            current_parts
        ).strip()

        chapters.append(
            Chapter(
                number=current_number,
                title=(
                    current_title
                    or f"Chapter {current_number}"
                ),
                text=chapter_text
            )
        )

    for block in blocks:

        kind = block[0]

        if kind == "chapter":

            finish_current_chapter()

            current_number = block[1]
            current_title = block[2]
            current_parts = []

            continue

        # Ignore readable content before the first detected chapter.
        # This is commonly page navigation, summaries, or metadata.
        if current_number is None:
            continue

        if kind == "text":
            current_parts.append(
                block[1]
            )

        elif kind == "separator":
            current_parts.append(
                block[1]
            )

    finish_current_chapter()

    if not chapters:
        raise ValueError(
            "Generic HTML chapter headings were detected, but no "
            "chapter content could be extracted."
        )

    return Book(
        title=story_title,
        author=story_author,
        source_type="Generic HTML",
        chapters=chapters
    )
