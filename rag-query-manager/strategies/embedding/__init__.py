"""LiteLLM client helper for query-time embeddings."""

import os
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class LiteLLMClient:
    """Shared LiteLLM client for retrieval strategies."""
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
