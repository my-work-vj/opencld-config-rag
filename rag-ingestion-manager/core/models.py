"""SQLAlchemy models for ingestion metadata.

This module re-exports the DocumentRecord from rag_shared.models to avoid
circular imports and duplicate table definitions.
"""

from rag_shared.models import DocumentRecord

# Re-export for backward compatibility with existing imports
__all__ = ["DocumentRecord"]