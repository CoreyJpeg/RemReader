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

        text = content_element.get_text("\n", strip=True)

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