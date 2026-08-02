"""Rendu du rapport : JSON signé pour la machine, HTML pour l'humain."""

from .build import build, headline
from .html import render

__all__ = ["build", "headline", "render"]
