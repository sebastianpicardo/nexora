from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractedContent:
    text: str = ""
    tables_text: str = ""
    images: list[bytes] = field(default_factory=list)
    page_count: int = 0
    is_scanned: bool = False

    @property
    def combined_text(self) -> str:
        parts = [self.text.strip(), self.tables_text.strip()]
        return "\n\n".join(part for part in parts if part)
