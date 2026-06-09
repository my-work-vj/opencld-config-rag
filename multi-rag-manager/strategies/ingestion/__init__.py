"""Ingestion strategies — from files, web, raw text."""

import os
import uuid
from pathlib import Path

from core.base_strategies import BaseIngestionStrategy, Document
from core.registry import StrategyRegistry


@StrategyRegistry.register("ingestion", "text_ingestion")
class TextIngestion(BaseIngestionStrategy):
    """Ingest plain text files (.txt, .md)."""

    def ingest(self, source: str | list | os.PathLike, **kwargs) -> list[Document]:
        documents = []
        encoding = kwargs.get("encoding", "utf-8")

        if isinstance(source, str) and (os.path.isfile(source) or os.path.isdir(source)):
            paths = [Path(source)] if os.path.isfile(source) else list(Path(source).rglob("*"))
            for p in paths:
                if p.suffix.lower() in (".txt", ".md", ".py", ".yaml", ".yml", ".json", ".csv", ".html"):
                    try:
                        content = p.read_text(encoding=encoding)
                        doc = Document(
                            id=str(uuid.uuid4()),
                            content=content,
                            metadata={"path": str(p), "size": len(content)},
                            filename=p.name,
                        )
                        documents.append(doc)
                    except Exception as e:
                        print(f"  Skipping {p}: {e}")
        elif isinstance(source, str):
            # Raw text
            doc = Document(
                id=str(uuid.uuid4()),
                content=source,
                metadata={"source": "raw_text"},
                filename="raw_input.txt",
            )
            documents.append(doc)
        elif isinstance(source, list):
            for item in source:
                if isinstance(item, Document):
                    documents.append(item)
                elif isinstance(item, str):
                    doc = Document(
                        id=str(uuid.uuid4()),
                        content=item,
                        metadata={"source": "list_input"},
                        filename="list_input.txt",
                    )
                    documents.append(doc)
        return documents


@StrategyRegistry.register("ingestion", "pdf_ingestion")
class PDFIngestion(BaseIngestionStrategy):
    """Ingest PDF files using PyPDF2."""

    def ingest(self, source: str | list, **kwargs) -> list[Document]:
        from PyPDF2 import PdfReader
        from PyPDF2.errors import PdfReadError
        documents = []

        paths = []
        if isinstance(source, str):
            if os.path.isfile(source):
                paths = [Path(source)]
            elif os.path.isdir(source):
                paths = list(Path(source).rglob("*.pdf"))
            else:
                raise FileNotFoundError(f"Source not found: {source}")
        elif isinstance(source, list):
            paths = [Path(s) for s in source]

        for p in paths:
            try:
                reader = PdfReader(str(p))
                text = ""
                for i, page in enumerate(reader.pages):
                    try:
                        text += page.extract_text() or ""
                    except Exception as e:
                        print(f"  Warning: skipping page {i+1} in {p.name}: {e}")
                doc = Document(
                    id=str(uuid.uuid4()),
                    content=text,
                    metadata={"path": str(p), "pages": len(reader.pages), "source": "pdf"},
                    filename=p.name,
                )
                documents.append(doc)
            except Exception as e:
                print(f"  Skipping {p.name}: {e}")

        return documents


@StrategyRegistry.register("ingestion", "web_ingestion")
class WebIngestion(BaseIngestionStrategy):
    """Ingest web pages via HTTP."""

    def ingest(self, source: str | list, **kwargs) -> list[Document]:
        import requests
        from bs4 import BeautifulSoup

        documents = []
        urls = [source] if isinstance(source, str) else source

        for url in urls:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            doc = Document(
                id=str(uuid.uuid4()),
                content=text,
                metadata={"url": url, "source": "web"},
                filename=f"web_{url.split('//')[1].split('/')[0]}.txt",
            )
            documents.append(doc)

        return documents
