import re
from dataclasses import dataclass


@dataclass
class CleaningOptions:
    read_author_notes: bool = True
    replace_yn: bool = True
    yn_name: str = "Corey"
    announce_scene_changes: bool = True
    scene_change_text: str = "Next scene"


def clean_text(text: str, options: CleaningOptions) -> str:
    # Normalize weird spaces
    text = text.replace("\xa0", " ")

    # Replace Y/N variants
    if options.replace_yn:
        text = replace_yn(text, options.yn_name)

    # Handle scene separators
    text = replace_scene_separators(
        text,
        options.announce_scene_changes
    )

    # Remove obvious URLs
    text = remove_urls(text)

    # Remove author notes if disabled
    if not options.read_author_notes:
        text = remove_author_notes(text)

    # Clean whitespace
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    text = "\n".join(lines)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def replace_yn(text: str, name: str) -> str:
    patterns = [
        r"\bY/N\b",
        r"\bYN\b",
        r"\bY\.N\.\b",
    ]

    for pattern in patterns:
        text = re.sub(
            pattern,
            name,
            text,
            flags=re.IGNORECASE
        )

    return text


def replace_scene_separators(text: str, announce: bool) -> str:
    replacement = "\nNext scene.\n" if announce else "\n"

    # Things like:
    # — — —
    # -----
    # *****
    patterns = [
        r"(?:—\s*){3,}",
        r"-{3,}",
        r"\*{3,}",
        r"_{3,}",
    ]

    for pattern in patterns:
        text = re.sub(pattern, replacement, text)

    return text


def remove_urls(text: str) -> str:
    return re.sub(
        r"https?://\S+|www\.\S+",
        "",
        text
    )


def remove_author_notes(text: str) -> str:
    # First-pass implementation.
    # We'll improve this after checking how the fic formats its A/N sections.
    patterns = [
        r"(?is)\bA/N\s*:.*?(?=\n(?:Chapter|\w+\s*:)|$)",
        r"(?is)\bAuthor(?:'s)? Note\s*:.*?(?=\n(?:Chapter|\w+\s*:)|$)",
    ]

    for pattern in patterns:
        text = re.sub(pattern, "", text)

    return text