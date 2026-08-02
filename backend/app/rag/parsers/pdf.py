import asyncio
from pathlib import Path

import fitz

from app.core.exceptions import ParserError
from app.rag.types import ParsedDocument, ParsedPage

from .common import normalize_text


class PdfParser:
    async def parse(self, file_path: str) -> ParsedDocument:
        def parse_sync() -> ParsedDocument:
            try:
                with fitz.open(file_path) as document:
                    metadata = dict(document.metadata or {})
                    pages = [
                        ParsedPage(
                            page_number=index + 1,
                            title=None,
                            content=normalize_text(page.get_text("text")),
                            metadata={"has_text": bool(page.get_text("text").strip())},
                        )
                        for index, page in enumerate(document)
                    ]
                    self._remove_repeated_margins(pages)
                return ParsedDocument(
                    title=metadata.get("title") or Path(file_path).stem,
                    pages=pages,
                    metadata={**metadata, "source_file": Path(file_path).name},
                )
            except Exception as exc:
                raise ParserError("PDF 解析失败") from exc

        return await asyncio.to_thread(parse_sync)

    @staticmethod
    def _remove_repeated_margins(pages: list[ParsedPage]) -> None:
        """Remove repeated first/last lines that are likely headers or footers."""
        if len(pages) < 3:
            return
        lines = [[line.strip() for line in page.content.splitlines() if line.strip()] for page in pages]
        threshold = max(3, (len(pages) + 1) // 2)
        first_counts: dict[str, int] = {}
        last_counts: dict[str, int] = {}
        for item in lines:
            if item:
                first_counts[item[0]] = first_counts.get(item[0], 0) + 1
                last_counts[item[-1]] = last_counts.get(item[-1], 0) + 1
        headers = {value for value, count in first_counts.items() if count >= threshold}
        footers = {value for value, count in last_counts.items() if count >= threshold}
        for page, item in zip(pages, lines, strict=True):
            if item and item[0] in headers:
                item = item[1:]
            if item and item[-1] in footers:
                item = item[:-1]
            page.content = "\n".join(item)
