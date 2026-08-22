import re
import zipfile
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from src.BookModel import (
    Book,
    Chapter
)


# ============================================================
# Helpers
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
    """Return (number, title) for common chapter headings."""

    match = CHAPTER_HEADING_PATTERN.match(
        text
    )

    if match is None:
        return None

    return (
        int(match.group("number")),
        (
            match.group("title")
            or ""
        ).strip()
    )


def _local_name(
    tag: str
) -> str:
    """Strip an XML namespace from a tag."""

    if "}" in tag:
        return tag.split(
            "}",
            1
        )[1]

    return tag


def _normalise_epub_path(
    base_path: str,
    relative_path: str
) -> str:
    """
    Resolve EPUB-internal POSIX paths without touching the real
    filesystem.
    """

    base = PurePosixPath(
        base_path
    ).parent

    combined = base / relative_path

    parts = []

    for part in combined.parts:

        if part in {
            "",
            "."
        }:
            continue

        if part == "..":

            if parts:
                parts.pop()

            continue

        parts.append(
            part
        )

    return "/".join(
        parts
    )


# ============================================================
# EPUB Structure
# ============================================================

def _find_package_path(
    archive: zipfile.ZipFile
) -> str:
    """
    Read META-INF/container.xml and locate the OPF package file.
    """

    try:

        container_xml = archive.read(
            "META-INF/container.xml"
        )

    except KeyError as error:

        raise ValueError(
            "Invalid EPUB: META-INF/container.xml was not found."
        ) from error

    root = ET.fromstring(
        container_xml
    )

    for element in root.iter():

        if _local_name(
            element.tag
        ) == "rootfile":

            package_path = element.attrib.get(
                "full-path"
            )

            if package_path:
                return package_path

    raise ValueError(
        "Invalid EPUB: package document could not be located."
    )


def _read_package(
    archive: zipfile.ZipFile,
    package_path: str
):
    """
    Parse EPUB metadata, manifest and reading-order spine.
    """

    try:

        package_xml = archive.read(
            package_path
        )

    except KeyError as error:

        raise ValueError(
            f"Invalid EPUB: package file is missing: {package_path}"
        ) from error

    root = ET.fromstring(
        package_xml
    )

    title = "Unknown Story"
    author = "Unknown Author"

    manifest = {}
    spine_ids = []

    for element in root.iter():

        name = _local_name(
            element.tag
        )

        if name == "title":

            value = (
                element.text
                or ""
            ).strip()

            if value:
                title = value

        elif name == "creator":

            value = (
                element.text
                or ""
            ).strip()

            if value:
                author = value

        elif name == "item":

            item_id = element.attrib.get(
                "id"
            )

            href = element.attrib.get(
                "href"
            )

            media_type = element.attrib.get(
                "media-type",
                ""
            )

            properties = element.attrib.get(
                "properties",
                ""
            )

            if item_id and href:

                manifest[item_id] = {
                    "href": href,
                    "media_type": media_type,
                    "properties": properties,
                }

        elif name == "itemref":

            idref = element.attrib.get(
                "idref"
            )

            linear = element.attrib.get(
                "linear",
                "yes"
            ).lower()

            if (
                idref
                and linear != "no"
            ):

                spine_ids.append(
                    idref
                )

    return (
        title,
        author,
        manifest,
        spine_ids
    )


# ============================================================
# Chapter Extraction
# ============================================================

def _extract_document_text(
    document_bytes: bytes
):
    """
    Extract readable text from one EPUB XHTML/HTML spine document.

    Returns:
        detected title, body text
    """

    soup = BeautifulSoup(
        document_bytes,
        "html.parser"
    )

    # Remove non-reading content.
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

    body = (
        soup.body
        if soup.body is not None
        else soup
    )

    chapter_title = ""
    text_parts = []

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

        # Avoid nested duplicate text.
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

            text_parts.append(
                "*****"
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

            # Use the first useful heading as the chapter title.
            if not chapter_title:

                chapter_heading = detect_chapter_heading(
                    text
                )

                if chapter_heading is not None:

                    _, detected_title = chapter_heading

                    chapter_title = (
                        detected_title
                        or text
                    )

                else:
                    chapter_title = text

            # Don't speak the same heading again; RemReader already
            # announces the chapter title before the body.
            continue

        text_parts.append(
            text
        )

    body_text = "\n".join(
        text_parts
    ).strip()

    return (
        chapter_title,
        body_text
    )


# ============================================================
# Public Parser
# ============================================================

def parse_epub(
    file_path: str | Path
) -> Book:
    """
    Parse an EPUB into RemReader's common Book model.

    Reading order follows the EPUB spine rather than ZIP filename
    order.
    """

    path = Path(
        file_path
    )

    if not path.exists():

        raise FileNotFoundError(
            f"EPUB file does not exist: {path}"
        )

    if not zipfile.is_zipfile(
        path
    ):

        raise ValueError(
            "The selected file is not a valid EPUB/ZIP container."
        )

    chapters = []

    with zipfile.ZipFile(
        path,
        "r"
    ) as archive:

        package_path = _find_package_path(
            archive
        )

        (
            story_title,
            story_author,
            manifest,
            spine_ids
        ) = _read_package(
            archive,
            package_path
        )

        for spine_index, item_id in enumerate(
            spine_ids,
            start=1
        ):

            item = manifest.get(
                item_id
            )

            if item is None:
                continue

            media_type = (
                item["media_type"]
                or ""
            ).lower()

            # EPUB chapter documents are normally XHTML.
            if media_type not in {
                "application/xhtml+xml",
                "text/html",
            }:
                continue

            document_path = _normalise_epub_path(
                package_path,
                item["href"]
            )

            try:

                document_bytes = archive.read(
                    document_path
                )

            except KeyError:

                # Broken manifest entries should not destroy an
                # otherwise readable book.
                continue

            (
                chapter_title,
                chapter_text
            ) = _extract_document_text(
                document_bytes
            )

            # Skip empty structural pages.
            if not chapter_text:
                continue

            if not chapter_title:

                chapter_title = (
                    f"Chapter {len(chapters) + 1}"
                )

            chapters.append(
                Chapter(
                    number=len(chapters) + 1,
                    title=chapter_title,
                    text=chapter_text
                )
            )

    if not chapters:

        raise ValueError(
            "EPUB parser could not find any readable spine chapters."
        )

    if (
        not story_title
        or story_title == "Unknown Story"
    ):

        story_title = (
            path.stem.strip()
            or "Unknown Story"
        )

    return Book(
        title=story_title,
        author=story_author,
        source_type="EPUB",
        chapters=chapters
    )
