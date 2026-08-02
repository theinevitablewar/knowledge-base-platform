from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.rag.types import ChunkingStrategy, DocumentChunkData, ParsedDocument


class RecursiveChunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", "，", ",", " ", ""],
        )

    def split(self, parsed_document: ParsedDocument) -> list[DocumentChunkData]:
        chunks: list[DocumentChunkData] = []
        for page in parsed_document.pages:
            if not page.content.strip():
                continue
            documents = self.splitter.create_documents([page.content])
            for document in documents:
                start = int(document.metadata.get("start_index", 0))
                chunks.append(
                    DocumentChunkData(
                        content=document.page_content,
                        page_number=page.page_number,
                        start_index=start,
                        end_index=start + len(document.page_content),
                        token_count=max(1, len(document.page_content) // 4),
                        metadata={**page.metadata, "title": page.title},
                    )
                )
        return chunks


class PageChunker:
    def split(self, parsed_document: ParsedDocument) -> list[DocumentChunkData]:
        return [
            DocumentChunkData(
                content=page.content,
                page_number=page.page_number,
                token_count=max(1, len(page.content) // 4),
                metadata=page.metadata,
            )
            for page in parsed_document.pages
            if page.content.strip()
        ]


class MarkdownHeaderChunker:
    def split(self, parsed_document: ParsedDocument) -> list[DocumentChunkData]:
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
            strip_headers=False,
        )
        chunks: list[DocumentChunkData] = []
        for page in parsed_document.pages:
            for document in splitter.split_text(page.content):
                chunks.append(
                    DocumentChunkData(
                        content=document.page_content,
                        page_number=page.page_number,
                        token_count=max(1, len(document.page_content) // 4),
                        metadata={**page.metadata, **document.metadata},
                    )
                )
        return chunks


def chunker_for(strategy: str, chunk_size: int, chunk_overlap: int) -> ChunkingStrategy:
    if strategy == "page":
        return PageChunker()
    if strategy == "markdown":
        return MarkdownHeaderChunker()
    return RecursiveChunker(chunk_size, chunk_overlap)
