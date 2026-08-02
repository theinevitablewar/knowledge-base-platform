import asyncio
from pathlib import Path

from app.core.exceptions import ParserError
from app.rag.types import ParsedDocument, ParsedPage

from .common import normalize_text


class TextParser:
    async def parse(self, file_path: str) -> ParsedDocument:
        try:
            raw = await asyncio.to_thread(Path(file_path).read_bytes)
            content = normalize_text(raw.decode("utf-8-sig"))
        except (OSError, UnicodeDecodeError) as exc:
            raise ParserError("文本文件解析失败") from exc
        return ParsedDocument(
            title=Path(file_path).stem,
            pages=[ParsedPage(page_number=None, title=None, content=content, metadata={})],
            metadata={"source_file": Path(file_path).name},
        )


class MarkdownParser(TextParser):
    pass
