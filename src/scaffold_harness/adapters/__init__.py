"""Adaptateurs : transformer « un modèle » ou « un échafaudage » en chemin mesurable."""

from .base import AdapterError, ChatAdapter, estimate_tokens
from .ollama import OllamaChat
from .openai_compatible import OpenAICompatibleChat
from .python_callable import PythonPath, Refusal

__all__ = [
    "AdapterError",
    "ChatAdapter",
    "OllamaChat",
    "OpenAICompatibleChat",
    "PythonPath",
    "Refusal",
    "estimate_tokens",
]
