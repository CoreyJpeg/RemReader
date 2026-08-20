import re


def parse_chapter_selection(selection: str) -> list[int]:
    """
    Convert chapter selection text into a list of chapter numbers.

    Examples:

    1
    1, 3, 5
    1 3 5
    1-5
    1, 3, 5-8
    """

    chapters = []

    # Allow commas OR spaces between chapter selections
    parts = re.split(
        r"[,\s]+",
        selection.strip()
    )

    for part in parts:

        if not part:
            continue

        # Handle chapter ranges such as 5-8
        if "-" in part:

            start, end = part.split(
                "-",
                1
            )

            start = int(
                start.strip()
            )

            end = int(
                end.strip()
            )

            # Prevent backwards ranges such as 8-5
            if start > end:
                raise ValueError(
                    f"Invalid chapter range: {start}-{end}"
                )

            chapters.extend(
                range(start, end + 1)
            )

        else:

            # Single chapter
            chapters.append(
                int(part)
            )

    if not chapters:
        raise ValueError(
            "No chapters were selected."
        )

    # Remove duplicates and sort
    chapters = sorted(
        set(chapters)
    )

    return chapters