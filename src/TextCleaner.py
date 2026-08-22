import re
from dataclasses import dataclass


@dataclass
class CleaningOptions:
    read_author_notes: bool = True
    replace_yn: bool = True
    yn_name: str = "Corey"

    # How author section / scene separators should be handled.
    #
    # Supported values:
    #   "pause"    -> keep a special marker for Generator.py
    #   "announce" -> speak the configured scene_change_text
    #   "ignore"   -> remove the separator entirely
    section_break_mode: str = "pause"
    scene_change_text: str = "Scene change"


def clean_text(text: str, options: CleaningOptions) -> str:
    # Normalize weird spaces
    text = text.replace("\xa0", " ")

    # Replace Y/N variants
    if options.replace_yn:
        text = replace_yn(text, options.yn_name)

    # Handle author section / scene separators.
    #
    # A pause is represented by a marker rather than blank lines because
    # the whitespace cleanup below intentionally removes empty lines.
    text = replace_scene_separators(
        text,
        mode=options.section_break_mode,
        scene_change_text=options.scene_change_text
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


# Special marker preserved through text cleaning.
# Generator.py will later convert this marker into actual audio silence.
SECTION_BREAK_MARKER = "[[REMREADER_SECTION_BREAK]]"


def replace_scene_separators(
    text: str,
    mode: str = "pause",
    scene_change_text: str = "Scene change"
) -> str:
    """
    Convert author separators into one of three behaviours.

    pause:
        Preserve a RemReader marker so the Generator can insert a
        real timed silence into the final audio.

    announce:
        Replace the separator with spoken words.

    ignore:
        Remove the separator completely.
    """

    mode = mode.lower().strip()

    if mode == "pause":
        replacement = f"\n{SECTION_BREAK_MARKER}\n"

    elif mode == "announce":
        replacement = f"\n{scene_change_text.strip()}.\n"

    elif mode == "ignore":
        replacement = "\n"

    else:
        raise ValueError(
            f"Unknown section break mode: {mode}"
        )

    # Things like:
    # — — —
    # -----
    # *****
    # _____
    #
    # These patterns intentionally require three or more repeated
    # separator characters so ordinary punctuation is left alone.
    patterns = [
        r"(?:—\s*){3,}",
        r"-{3,}",
        r"\*{3,}",
        r"_{3,}",
    ]

    for pattern in patterns:
        text = re.sub(
            pattern,
            replacement,
            text
        )

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