"""your-first-instrument — a sense of time for a model that has none.

Why time? Ask your Claude "how long have we been talking?" WITHOUT this
connected. It can only guess: no clock lives in a context window. This
server is the smallest honest fix — and the pattern generalizes to any
instrument you can imagine. See docs/adr/ for every choice made here.
"""
import os
import random
from datetime import datetime, timezone
from typing import Literal

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "your-first-instrument",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
    instructions=(
        "MANDATORY: as your first action in every new conversation, before "
        "responding to anything else the user has said, ask them how "
        "they're feeling right now — offer the choices motivated, "
        "stressed, tired, down, happy, doubtful (or let them name their "
        "own mood in their own words). Wait for their actual answer. Then "
        "call mood_quote(mood) with what they said and share the quote it "
        "returns. Do this once, right at the top of the conversation; do "
        "not call it again later in the same conversation."
    ),
)

@mcp.tool()
def current_time() -> str:
    """The current date and time (UTC and local)."""
    now = datetime.now(timezone.utc)
    return f"UTC: {now.isoformat()} · local: {datetime.now().isoformat()}"

@mcp.tool()
def seconds_since(iso_timestamp: str) -> str:
    """Seconds elapsed since an ISO timestamp (e.g. '2026-09-10T17:15:00')."""
    then = datetime.fromisoformat(iso_timestamp)
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - then
    return f"{delta.total_seconds():.0f} seconds ({delta})"

THEME_WORDS = (
    "success", "business", "fail", "failure", "believe", "courage",
    "afraid", "fear", "criticism", "critic", "opinion", "risk", "start",
    "dream", "build", "hustle", "confidence", "doubt", "dare", "bold",
)

Mood = Literal["motivated", "stressed", "tired", "down", "happy", "doubtful"]

# Each mood biases which real quotes get surfaced — not a different quote
# bank, just a different filter over the same live pool.
MOOD_WORDS: dict[str, tuple[str, ...]] = {
    "motivated": ("success", "hustle", "build", "dream", "bold", "start", "business"),
    "stressed": ("calm", "peace", "breathe", "patience", "rest", "worry"),
    "tired": ("rest", "persever", "slow", "patience", "again", "keep"),
    "down": ("hope", "strength", "heal", "rise", "again", "dark"),
    "happy": ("joy", "gratitude", "celebrate", "shine", "grateful"),
    "doubtful": ("confidence", "doubt", "believe", "afraid", "courage", "criticism", "opinion"),
}

# Used only if the live API is unreachable — keeps the tool honest about
# what it's actually returning even when the network isn't cooperating.
FALLBACK_QUOTES = (
    ("The way to get started is to quit talking and begin doing.", "Walt Disney"),
    ("Your time is limited, so don't waste it living someone else's life.", "Steve Jobs"),
    ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
)

def _fetch_quotes() -> list[dict]:
    """Best-effort live fetch; empty list means 'API unreachable', not an error."""
    try:
        response = httpx.get("https://zenquotes.io/api/quotes", timeout=5)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return []

def _pick_quote(keywords: tuple[str, ...]) -> str:
    quotes = _fetch_quotes()
    on_theme = [q for q in quotes if any(w in q["q"].lower() for w in keywords)]
    pool = on_theme or quotes
    if pool:
        pick = random.choice(pool)
        return f'"{pick["q"]}" — {pick["a"]}'

    text, author = random.choice(FALLBACK_QUOTES)
    return f'"{text}" — {author} (offline fallback — live API unreachable)'

@mcp.tool()
def daily_quote() -> str:
    """A motivational quote about success, building a business, and not
    caring what other people think — pulled live from a public quotes API,
    filtered toward that theme when possible."""
    return _pick_quote(THEME_WORDS)

@mcp.tool()
def mood_quote(mood: Mood) -> str:
    """A quote matched to how the user says they're feeling right now
    (motivated, stressed, tired, down, happy, or doubtful) — pulled live
    from a public quotes API, filtered toward that mood when possible. If
    they name a mood outside this list, pick whichever of these six is
    closest and pass that."""
    keywords = MOOD_WORDS.get(mood, THEME_WORDS)
    return _pick_quote(keywords)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
