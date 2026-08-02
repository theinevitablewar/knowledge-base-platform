from pathlib import Path

from app.core.exceptions import ParserError
from app.rag.types import DocumentParser

from .docx import DocxParser
from .pdf import PdfParser
from .text import MarkdownParser, TextParser


def parser_for(filename: str) -> DocumentParser:
    extension = Path(filename).suffix.casefold()
    parsers: dict[str, DocumentParser] = {
        ".pdf": PdfParser(),
        ".docx": DocxParser(),
        ".txt": TextParser(),
        ".md": MarkdownParser(),
        ".markdown": MarkdownParser(),
    }
    if extension not in parsers:
        raise ParserError(f"不支持的文件类型：{extension}")
    return parsers[extension]
