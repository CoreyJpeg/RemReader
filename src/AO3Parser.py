from bs4 import BeautifulSoup
from pathlib import Path


def load_html(file_path: str) -> BeautifulSoup:
    path = Path(file_path)

    with path.open("r", encoding="utf-8") as file:
        html = file.read()

    return BeautifulSoup(html, "html.parser")


def get_chapters(file_path: str):
    soup = load_html(file_path)

    results = []

    metadata_blocks = soup.select("div.meta.group")

    for metadata in metadata_blocks:
        title_element = metadata.select_one("h2.heading")

        if title_element is None:
            continue

        title = title_element.get_text(" ", strip=True)

        if not title.lower().startswith("chapter"):
            continue

        content_element = metadata.find_next_sibling(
            "div",
            class_="userstuff"
        )

        if content_element is None:
            continue

        # Extract each top-level block separately.
        #
        # Using get_text("\\n") on the whole chapter caused BeautifulSoup
        # to insert line breaks around inline tags such as <em>, <b>, and
        # <span>. For example:
        #
        #     I <Em>Love</Em> you
        #
        # could be broken into separate lines even though it is one sentence.
        #
        # Reading each paragraph/block with a SPACE separator keeps inline
        # formatting together, while joining the blocks with newlines still
        # preserves paragraph boundaries.
        text_blocks = []

        for element in content_element.children:

            # Ignore plain whitespace between HTML tags.
            if not getattr(element, "name", None):
                plain_text = str(element).strip()

                if plain_text:
                    text_blocks.append(
                        plain_text
                    )

                continue

            # Horizontal rules contain no spoken text.
            if element.name == "hr":
                continue

            block_text = element.get_text(
                " ",
                strip=True
            )

            if block_text:
                text_blocks.append(
                    block_text
                )

        text = "\n".join(
            text_blocks
        )

        results.append({
            "title": title,
            "text": text
        })

    return results

def get_story_title(file_path: str) -> str:
    """
    Get the title of the AO3 work.
    """

    soup = load_html(
        file_path
    )

    # AO3 downloaded HTML stores the work title
    # inside the preface message.
    title_element = soup.select_one(
        "#preface p.message b"
    )

    if title_element is None:
        return "Unknown Story"

    return title_element.get_text(
        " ",
        strip=True
    )

def get_story_author(file_path: str) -> str:
    """
    Get the AO3 work author.

    Downloaded AO3 works normally store the author in the preface
    byline. Several selectors are tried so older/newer downloads
    still have a sensible fallback.
    """

    soup = load_html(
        file_path
    )

    selectors = [
        "#preface .byline a[rel='author']",
        "#preface .byline a",
        ".preface .byline a[rel='author']",
        ".preface .byline a",
    ]

    for selector in selectors:

        author_element = soup.select_one(
            selector
        )

        if author_element is not None:

            author = author_element.get_text(
                " ",
                strip=True
            )

            if author:
                return author

    return "Unknown Author"
