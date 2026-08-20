import re


def split_into_chunks(text: str, max_length: int = 500) -> list[str]:
    """
    Split text into TTS-friendly chunks.

    Prefers sentence boundaries and falls back to splitting
    oversized sentences when necessary.
    """

    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:

        # Handle unusually long individual sentences
        if len(sentence) > max_length:

            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            chunks.extend(
                split_long_sentence(sentence, max_length)
            )

            continue

        new_length = len(current_chunk) + len(sentence) + 1

        if new_length <= max_length:
            current_chunk += sentence + " "

        else:
            if current_chunk:
                chunks.append(current_chunk.strip())

            current_chunk = sentence + " "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def split_long_sentence(sentence: str, max_length: int) -> list[str]:
    """
    Fallback for sentences longer than the TTS limit.
    Splits at word boundaries.
    """

    words = sentence.split()

    chunks = []
    current_chunk = ""

    for word in words:

        if len(current_chunk) + len(word) + 1 <= max_length:
            current_chunk += word + " "

        else:
            if current_chunk:
                chunks.append(current_chunk.strip())

            current_chunk = word + " "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks