"""The network boundary: the only module that imports or touches `yt-dlp`.

`yt-dlp` is used as a library, never shelled out to, and one client is reused
for every caption fetch in a run. Everything else talks to YouTube only through
`list_channel_entries` and `fetch_video`, which are also the only surfaces a
test may fake.

No cookies, no proxies, no custom User-Agent, no audio download: only what
yt-dlp sends by default for a metadata extraction plus the caption file itself.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from yt_dlp import YoutubeDL  # type: ignore[import-untyped]

# Caption tracks arrive under codes like `en`, `en-orig`, `en-US`; matching on
# the prefix takes whichever the video has.
_ENGLISH = "en"

JSON3 = "json3"
VTT = "vtt"
UNKNOWN_FORMAT = "unknown"


def list_channel_entries(channel_url: str) -> Iterator[dict[str, object]]:
    """Yield one raw flat-playlist entry per upload on the channel (all tabs).

    Flat extraction downloads nothing. Its entries omit `upload_date` unless
    `youtubetab:approximate_date` is set; the dates it then gives (as
    `timestamp`) are approximate, which is fine for ordering and picks.
    """
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "extractor_args": {"youtubetab": {"approximate_date": ["true"]}},
    }
    with YoutubeDL(options) as client:
        info = client.extract_info(channel_url, download=False)
        yield from _walk(info, client)


def _walk(info: dict[str, Any], client: Any) -> Iterator[dict[str, object]]:
    """Flatten a nested extraction result (channel -> tabs -> videos)."""
    entries = info.get("entries")
    if entries is None:
        yield info
        return
    for entry in entries:
        if not entry:
            continue
        if entry.get("entries") is not None:
            yield from _walk(entry, client)
        elif entry.get("ie_key") == "YoutubeTab" or entry.get("_type") == "playlist":
            resolved = client.extract_info(entry["url"], download=False)
            yield from _walk(resolved, client)
        else:
            yield entry


@dataclass(frozen=True)
class VideoFetch:
    """One per-video extraction: the captions (or None), the description, and
    the format the captions are in, so the caller picks a parser without sniffing."""

    captions: str | None
    description: str
    caption_format: str


def fetch_video(video_id: str) -> VideoFetch:
    """Return one video's English captions and its description.

    Manual tracks win over automatic ones. `captions` is None only when the
    video offers no English track; anything that goes wrong reaching YouTube
    raises, so the caller can tell "nothing to fetch" from "could not fetch".
    """
    client = _caption_client()
    info = client.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    description = info.get("description") if isinstance(info, dict) else None
    text = description if isinstance(description, str) else ""
    track = _caption_track(info)
    if track is None:
        return VideoFetch(captions=None, description=text, caption_format=UNKNOWN_FORMAT)
    url, caption_format = track
    # Through the client, so the caption request carries the same session as
    # the extraction did.
    raw: bytes = client.urlopen(url).read()
    return VideoFetch(
        captions=raw.decode("utf-8", errors="replace"),
        description=text,
        caption_format=caption_format,
    )


# One client for every caption fetch in a run, built on first use so that
# importing this module opens nothing.
_CAPTION_CLIENT: Any = None


def _caption_client() -> Any:
    global _CAPTION_CLIENT
    if _CAPTION_CLIENT is None:
        _CAPTION_CLIENT = YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitlesformat": "json3/vtt/best",
            }
        )
    return _CAPTION_CLIENT


def _caption_track(info: dict[str, Any]) -> tuple[str, str] | None:
    """The English track's URL and format: manual before automatic, and within
    either json3 before vtt (vtt auto-captions are roll-up and repeat lines).

    Automatic captions also list machine translations into English from other
    languages (`en-xx`); the original-language tracks (`en`, `en-orig`) come
    first because they are tried in key order with exact matches preferred.
    """
    for key in ("subtitles", "automatic_captions"):
        tracks = info.get(key) or {}
        if not isinstance(tracks, dict):
            continue
        languages = sorted(
            (str(lang) for lang in tracks if str(lang).lower().startswith(_ENGLISH)),
            key=lambda lang: (lang not in ("en", "en-orig"), lang),
        )
        for language in languages:
            formats = tracks.get(language)
            if not formats:
                continue
            chosen = _preferred(formats)
            if chosen.get("url"):
                return str(chosen["url"]), str(chosen.get("ext") or UNKNOWN_FORMAT)
    return None


def _preferred(formats: list[dict[str, Any]]) -> dict[str, Any]:
    for wanted in (JSON3, VTT):
        for fmt in formats:
            if fmt.get("ext") == wanted:
                return fmt
    return formats[0]
