"""
AI news aggregation endpoints for Sage mobile.
"""
from __future__ import annotations

import hashlib
import html
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Sequence, Tuple
import xml.etree.ElementTree as ET

import requests
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/news", tags=["news"])

_DEFAULT_FEED_SOURCES: Tuple[Dict[str, str], ...] = (
    {
        "name": "Google News Tech",
        "url": "https://news.google.com/rss/search?q=technology+OR+software+OR+cloud+OR+developer&hl=en-US&gl=US&ceid=US:en",
        "source_type": "news",
    },
    {
        "name": "Google News AI",
        "url": "https://news.google.com/rss/search?q=artificial+intelligence+OR+generative+AI+OR+LLM&hl=en-US&gl=US&ceid=US:en",
        "source_type": "news",
    },
    {
        "name": "Hacker News Frontpage",
        "url": "https://hnrss.org/frontpage",
        "source_type": "news",
    },
    {
        "name": "Hacker News AI",
        "url": "https://hnrss.org/newest?q=artificial+intelligence+OR+LLM+OR+OpenAI",
        "source_type": "news",
    },
    {
        "name": "Reddit r/artificial",
        "url": "https://www.reddit.com/r/artificial/.rss",
        "source_type": "news",
    },
)

_DEFAULT_X_HANDLES: Tuple[str, ...] = ("OpenAI", "AnthropicAI", "xAI")

_KEYWORD_WEIGHTS: Tuple[Tuple[str, float], ...] = (
    ("artificial intelligence", 3.0),
    ("generative ai", 3.5),
    ("large language model", 3.2),
    ("llm", 2.7),
    ("ai model", 2.5),
    ("reasoning model", 2.3),
    ("openai", 2.8),
    ("anthropic", 2.8),
    ("xai", 2.5),
    ("google deepmind", 2.4),
    ("gemini", 2.0),
    ("claude", 2.0),
    ("gpt", 2.0),
    ("mistral", 1.8),
    ("hugging face", 1.7),
    ("agent", 1.4),
    ("inference", 1.3),
    ("benchmark", 1.2),
)

_REQUEST_TIMEOUT_SEC = float(os.getenv("SAGE_NEWS_REQUEST_TIMEOUT_SEC", "3.0"))
_SUMMARY_MAX_CHARS = int(os.getenv("SAGE_NEWS_SUMMARY_MAX_CHARS", "280"))


class AiNewsItem(BaseModel):
    id: str
    title: str
    url: str
    summary: str
    source: str
    source_type: str
    published_at: Optional[str] = None
    relevance_score: float
    tags: List[str] = Field(default_factory=list)


class AiNewsResponse(BaseModel):
    success: bool = True
    generated_at: str
    query: str
    scanned_sources: int
    failed_sources: int
    source_errors: List[str] = Field(default_factory=list)
    items: List[AiNewsItem] = Field(default_factory=list)


@dataclass
class SourceConfig:
    name: str
    url: str
    source_type: str


@dataclass
class CandidateItem:
    title: str
    url: str
    summary: str
    source: str
    source_type: str
    published_at: Optional[datetime]


def _local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1].lower()
    return tag.lower()


def _clean_text(raw: str, max_chars: int = _SUMMARY_MAX_CHARS) -> str:
    if not raw:
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", raw)
    unescaped = html.unescape(no_tags)
    compact = re.sub(r"\s+", " ", unescaped).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _parse_date(raw_date: str) -> Optional[datetime]:
    if not raw_date:
        return None

    value = raw_date.strip()
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _extract_entry_field(entry: ET.Element, names: Sequence[str]) -> str:
    wanted = {name.lower() for name in names}
    for child in list(entry):
        if _local_name(child.tag) in wanted:
            text = "".join(child.itertext()).strip()
            if text:
                return text
    return ""


def _extract_entry_link(entry: ET.Element) -> str:
    for child in list(entry):
        if _local_name(child.tag) != "link":
            continue
        href = (child.attrib.get("href") or "").strip()
        if href:
            rel = (child.attrib.get("rel") or "alternate").strip().lower()
            if rel in {"", "alternate"}:
                return href
        text_link = "".join(child.itertext()).strip()
        if text_link.startswith("http://") or text_link.startswith("https://"):
            return text_link
    return ""


def _extract_entries(xml_text: str) -> List[Tuple[str, str, str, Optional[datetime]]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    root_name = _local_name(root.tag)
    nodes: List[ET.Element] = []
    if root_name in {"rss", "rdf"}:
        channel = next((child for child in list(root) if _local_name(child.tag) == "channel"), None)
        if channel is not None:
            nodes = [child for child in list(channel) if _local_name(child.tag) == "item"]
    elif root_name == "feed":
        nodes = [child for child in list(root) if _local_name(child.tag) == "entry"]
    else:
        nodes = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]

    items: List[Tuple[str, str, str, Optional[datetime]]] = []
    for node in nodes:
        title = _clean_text(_extract_entry_field(node, ("title",)), max_chars=160)
        link = _extract_entry_link(node)
        summary = _clean_text(_extract_entry_field(node, ("description", "summary", "content")), max_chars=_SUMMARY_MAX_CHARS)
        pub_raw = _extract_entry_field(node, ("pubdate", "published", "updated", "date"))
        published_at = _parse_date(pub_raw)

        if not title or not link:
            continue
        items.append((title, link, summary, published_at))

    return items


def _load_x_handles() -> Tuple[str, ...]:
    raw = os.getenv("SAGE_NEWS_X_HANDLES", "")
    if not raw.strip():
        return _DEFAULT_X_HANDLES
    parsed = tuple(part.strip().lstrip("@") for part in raw.split(",") if part.strip())
    return parsed or _DEFAULT_X_HANDLES


def _build_sources(include_x: bool) -> List[SourceConfig]:
    sources: List[SourceConfig] = [
        SourceConfig(name=s["name"], url=s["url"], source_type=s["source_type"])
        for s in _DEFAULT_FEED_SOURCES
    ]
    if include_x:
        nitter_base = (os.getenv("SAGE_NEWS_NITTER_BASE_URL", "https://nitter.net") or "").strip().rstrip("/")
        if nitter_base:
            for handle in _load_x_handles():
                sources.append(
                    SourceConfig(
                        name=f"@{handle}",
                        url=f"{nitter_base}/{handle}/rss",
                        source_type="x",
                    )
                )
    return sources


def _fetch_source(source: SourceConfig) -> List[CandidateItem]:
    response = requests.get(
        source.url,
        timeout=_REQUEST_TIMEOUT_SEC,
        headers={"User-Agent": "sage-news/1.0 (+https://sage.local)"},
    )
    response.raise_for_status()
    entries = _extract_entries(response.text)
    return [
        CandidateItem(
            title=title,
            url=url,
            summary=summary,
            source=source.name,
            source_type=source.source_type,
            published_at=published_at,
        )
        for title, url, summary, published_at in entries
    ]


def _normalize_title(text: str) -> str:
    lowered = text.lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def _score_item(item: CandidateItem, query: str) -> Tuple[float, List[str]]:
    corpus = f"{item.title}\n{item.summary}".lower()
    score = 0.0
    tags: List[str] = []

    for keyword, weight in _KEYWORD_WEIGHTS:
        if keyword in corpus:
            score += weight
            tag = keyword.upper() if len(keyword) <= 4 else keyword.title()
            if tag not in tags and len(tags) < 5:
                tags.append(tag)

    query_terms = [part for part in re.split(r"\s+", query.lower().strip()) if len(part) > 1]
    for term in query_terms:
        if term in corpus:
            score += 0.8

    if item.source_type == "x":
        score += 0.3
        if "X" not in tags:
            tags.append("X")

    if any(token in corpus for token in ("launch", "release", "announce", "open source")):
        score += 0.6

    if item.published_at:
        age_hours = max(
            0.0,
            (datetime.now(timezone.utc) - item.published_at).total_seconds() / 3600.0,
        )
        if age_hours <= 6:
            score += 0.5
        elif age_hours <= 24:
            score += 0.25

    return round(score, 2), tags


def _dedupe_and_rank(
    items: List[CandidateItem],
    query: str,
    max_age_hours: int,
    limit: int,
) -> List[AiNewsItem]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)

    dedup: Dict[str, CandidateItem] = {}
    for item in items:
        if item.published_at and item.published_at < cutoff:
            continue
        key = _normalize_title(item.title)
        if not key:
            continue

        existing = dedup.get(key)
        if not existing:
            dedup[key] = item
            continue

        existing_ts = existing.published_at or datetime.fromtimestamp(0, tz=timezone.utc)
        candidate_ts = item.published_at or datetime.fromtimestamp(0, tz=timezone.utc)
        if candidate_ts > existing_ts:
            dedup[key] = item

    ranked: List[Tuple[float, datetime, CandidateItem, List[str]]] = []
    for item in dedup.values():
        score, tags = _score_item(item, query)
        if score <= 0:
            continue
        published = item.published_at or datetime.fromtimestamp(0, tz=timezone.utc)
        ranked.append((score, published, item, tags))

    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)

    response_items: List[AiNewsItem] = []
    for score, published, item, tags in ranked[:limit]:
        item_id = hashlib.sha1(f"{item.url}|{item.title}".encode("utf-8")).hexdigest()[:16]
        response_items.append(
            AiNewsItem(
                id=item_id,
                title=item.title,
                url=item.url,
                summary=item.summary,
                source=item.source,
                source_type=item.source_type,
                published_at=published.isoformat() if item.published_at else None,
                relevance_score=score,
                tags=tags,
            )
        )
    return response_items


@router.get("/ai", response_model=AiNewsResponse)
def get_ai_news(
    limit: int = Query(default=25, ge=1, le=80),
    max_age_hours: int = Query(default=72, ge=1, le=336),
    include_x: bool = Query(default=True),
    query: str = Query(default="technology ai"),
) -> AiNewsResponse:
    """
    Pull and rank AI-relevant news from RSS and optional X (via Nitter RSS).
    """
    sources = _build_sources(include_x=include_x)
    errors: List[str] = []
    all_items: List[CandidateItem] = []

    max_workers = min(8, max(1, len(sources)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {executor.submit(_fetch_source, source): source for source in sources}
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                all_items.extend(future.result())
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")

    ranked = _dedupe_and_rank(all_items, query=query, max_age_hours=max_age_hours, limit=limit)
    return AiNewsResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        query=query,
        scanned_sources=len(sources),
        failed_sources=len(errors),
        source_errors=errors[:20],
        items=ranked,
    )
