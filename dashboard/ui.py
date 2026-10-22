"""Shared presentation helpers: the stylesheet loader and small HTML builders.

Builders return HTML strings for st.html and escape every piece of text they're
given. Classes are styled in style.css.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

import streamlit as st

from freshness import LABELS

_CSS = Path(__file__).with_name("style.css")


def inject_css() -> None:
    """Load the dashboard's only stylesheet. Called once per run, from app.py."""
    st.html(f"<style>{_CSS.read_text()}</style>")


@dataclass
class Node:
    """One stage of the medallion flow on the Overview page."""

    name: str
    tech: str
    rows: int | None = None
    updated: str = ""
    counts: bool = True  # Source and Serving have no row count to show


def status_pill(state: str, text: str) -> str:
    return (
        f'<span class="fd-pill fd-state--{escape(state)}">'
        f'<span class="fd-dot"></span><span>{escape(text)}</span></span>'
    )


def tile(label: str, value: str, note: str = "", state: str | None = None) -> str:
    parts = [
        f'<div class="fd-tile"><div class="fd-tile__label">{escape(label)}</div>',
        f'<div class="fd-tile__value">{escape(value)}</div>',
    ]
    if state:
        parts.append(
            f'<div class="fd-tile__state fd-state--{escape(state)}">'
            f'<span class="fd-dot"></span>{escape(LABELS[state])}</div>'
        )
    if note:
        parts.append(f'<div class="fd-tile__note">{escape(note)}</div>')
    parts.append("</div>")
    return "".join(parts)


def tiles(items: list[str]) -> str:
    return f'<div class="fd-tiles">{"".join(items)}</div>'


def flow(nodes: list[Node]) -> str:
    cards = []
    for node in nodes:
        rows = ""
        if node.counts:
            value = "—" if node.rows is None else f"{node.rows:,}"
            rows = f'<div class="fd-node__rows">{value}</div>'
        cards.append(
            f'<div class="fd-node" role="listitem">'
            f'<div class="fd-node__name">{escape(node.name)}</div>'
            f'<div class="fd-node__tech">{escape(node.tech)}</div>'
            f'{rows}<div class="fd-node__updated">{escape(node.updated)}</div></div>'
        )
    arrow = '<div class="fd-arrow" aria-hidden="true">→</div>'
    return f'<div class="fd-flow" role="list">{arrow.join(cards)}</div>'


def defs(items: list[tuple[str, str]]) -> str:
    rows = "".join(f"<dt>{escape(term)}</dt><dd>{escape(text)}</dd>" for term, text in items)
    return f'<dl class="fd-defs">{rows}</dl>'
