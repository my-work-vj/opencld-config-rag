"""Slug helpers for knowledge source names and collection names."""

import re


def slugify_name(name: str) -> str:
    """Convert a display name to a lowercase slug for collection/id use."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:64] if slug else "source"
