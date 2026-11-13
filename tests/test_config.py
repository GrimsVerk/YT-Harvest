from __future__ import annotations

from pathlib import Path

import pytest

from yt_harvest.config import load_config


def test_local_file_overrides_data_root_and_channels_get_slugs(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        'fetch_delay_seconds = 2.5\ndata_root = "committed"\n'
        '[[channels]]\nname = "EC Krown"\nurl = "https://www.youtube.com/@ECKrown"\n'
    )
    (tmp_path / "local.toml").write_text(f'data_root = "{tmp_path / "mine"}"\n')
    config = load_config(tmp_path / "config.toml")
    assert config.data_root == tmp_path / "mine"
    assert config.fetch_delay_seconds == 2.5
    assert config.channel("ec-krown").url == "https://www.youtube.com/@ECKrown"


def test_missing_files_give_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "config.toml")
    assert config.data_root == Path("~/data/yt-harvest").expanduser()
    assert config.channels == ()
    assert config.start_date is None


def test_duplicate_slugs_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        '[[channels]]\nname = "A"\nurl = "u1"\n[[channels]]\nname = "a"\nurl = "u2"\n'
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_config(tmp_path / "config.toml")


def test_committed_config_parses_and_lists_the_channels() -> None:
    config = load_config(Path(__file__).parent.parent / "config.toml", Path("/nonexistent"))
    assert len(config.channels) == 12
    assert all(c.url.startswith("https://www.youtube.com/") for c in config.channels)
