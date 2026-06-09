"""Embedding strategies using LiteLLM proxy."""

import os
import uuid
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

from core.base_strategies import BaseEmbeddingStrategy, Chunk, EmbeddingVector
from core.registry import StrategyRegistry

load_dotenv()


class LiteLLMClient:
    """Shared LiteLLM client."""
    _instance: Optional["LiteLLMClient"] = None

    def __init__(self):
        self.base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:4000/v1")
        self.api_key = os.getenv("LITELLM_API_KEY", "sk-vj")
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @classmethod
    def get_client(cls) -> "LiteLLMClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


@StrategyRegistry.register("embedding", "litellm_embedding")
class LiteLLMEmbedding(BaseEmbeddingStrategy):
    """Generate embeddings via LiteLLM proxy."""

    def __init__(self, **kwargs):
        self.client = LiteLLMClient.get_client().client
        self.model = kwargs.get("model", os.getenv("EMBEDDING_MODEL", "nvidia-embed"))
        self.dimensions = kwargs.get("dimensions", 2048)

    def embed(self, chunks: list[Chunk], **kwargs) -> list[EmbeddingVector]:
        model = kwargs.get("model", self.model)
        batch_size = kwargs.get("batch_size", 32)
        input_type = kwargs.get("input_type", "passage")

        all_vectors = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.content for c in batch]

            try:
                kwargs_body = {}
                if input_type:
                    kwargs_body["extra_body"] = {"input_type": input_type, "encoding_format": "float"}

                resp = self.client.embeddings.create(
                    model=model,
                    input=texts,
                    **kwargs_body,
                )
                for chunk, data in zip(batch, resp.data):
                    all_vectors.append(EmbeddingVector(
                        chunk=chunk,
                        vector=data.embedding,
                    ))
            except Exception as e:
                print(f"  Embedding batch error: {e}")
                # Return zero vectors for failed batch
                for chunk in batch:
                    all_vectors.append(EmbeddingVector(
                        chunk=chunk,
                        vector=[0.0] * self.dimensions,
                    ))

        return all_vectors
