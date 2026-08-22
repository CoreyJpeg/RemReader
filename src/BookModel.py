from dataclasses import dataclass, field


@dataclass
class Chapter:
    """A parser-independent story chapter."""
    number: int
    title: str
    text: str


@dataclass
class Book:
    """Parser-independent representation used by RemReader."""
    title: str = "Unknown Story"
    author: str = "Unknown Author"
    chapters: list[Chapter] = field(default_factory=list)
    source_type: str = "unknown"
