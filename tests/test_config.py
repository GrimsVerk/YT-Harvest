from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from yt_harvest.cli import main
from yt_harvest.config import ConfigError, load_config

REPO = Path(__file__).parent.parent
EXAMPLE_LIST = '[[channels]]\nname = "Example Channel"\nurl = "https://www.youtube.com/@example"\n'


def test_channels_file_from_local_config_relative_to_it(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text('fetch_delay_seconds = 2.5\ndata_root = "committed"\n')
    (tmp_path / "lists").mkdir()
    (tmp_path / "lists" / "mine.toml").write_text(
        'topic_keywords = ["rsi"]\ndata_root = "from-list"\n' + EXAMPLE_LIST
    )
    (tmp_path / "local.toml").write_text(
        f'data_root = "{tmp_path / "mine"}"\nchannels_file = "lists/mine.toml"\n'
    )
    config = load_config(tmp_path / "config.toml")
    assert config.data_root == tmp_path / "mine"  # local.toml wins over the list
    assert config.fetch_delay_seconds == 2.5
    assert config.topic_keywords == ("rsi",)
    assert config.channels_file == tmp_path / "lists" / "mine.toml"
    assert config.channel("example-channel").url == "https://www.youtube.com/@example"


def test_channels_flag_overrides_local_channels_file(tmp_path: Path) -> None:
    (tmp_path / "local.toml").write_text('channels_file = "missing.toml"\n')
    (tmp_path / "other.toml").write_text(EXAMPLE_LIST)
    config = load_config(tmp_path / "config.toml", channels_path=tmp_path / "other.toml")
    assert [c.slug for c in config.channels] == ["example-channel"]


def test_missing_files_give_defaults_and_no_list(tmp_path: Path) -> None:
    config = load_config(tmp_path / "config.toml")
    assert config.data_root == Path("~/data/yt-harvest").expanduser()
    assert config.channels == ()
    assert config.channels_file is None
    assert config.start_date is None


def test_named_channels_file_that_does_not_exist_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="channels file not found"):
        load_config(tmp_path / "config.toml", channels_path=tmp_path / "nope.toml")


def test_channels_in_config_toml_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(EXAMPLE_LIST)
    with pytest.raises(ConfigError, match="channels file"):
        load_config(tmp_path / "config.toml")


def test_duplicate_slugs_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "list.toml").write_text(
        '[[channels]]\nname = "A"\nurl = "u1"\n[[channels]]\nname = "a"\nurl = "u2"\n'
    )
    with pytest.raises(ConfigError, match="duplicate"):
        load_config(tmp_path / "config.toml", channels_path=tmp_path / "list.toml")


def test_committed_config_has_no_channels_and_example_has_only_placeholders() -> None:
    committed = tomllib.loads((REPO / "config.toml").read_text())
    assert "channels" not in committed
    assert "topic_keywords" not in committed
    config = load_config(
        REPO / "config.toml", Path("/nonexistent"), channels_path=REPO / "channels.example.toml"
    )
    assert len(config.channels) == 2
    assert all(c.name.startswith("Example Channel") for c in config.channels)
    assert all(c.url.startswith("https://www.youtube.com/") for c in config.channels)


def test_cli_without_a_list_fails_clearly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "config.toml").write_text("")
    for command in ("channels", "index", "fetch", "status", "picks", "select"):
        assert main(["--config", str(tmp_path / "config.toml"), command]) == 2
        assert "no channel list given" in capsys.readouterr().err


def test_cli_where_needs_no_list_and_channels_lists_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "config.toml").write_text(f'data_root = "{tmp_path / "data"}"\n')
    assert main(["--config", str(tmp_path / "config.toml"), "where"]) == 0
    assert capsys.readouterr().out.strip() == str(tmp_path / "data")
    (tmp_path / "list.toml").write_text(EXAMPLE_LIST)
    args = ["--config", str(tmp_path / "config.toml"), "--channels", str(tmp_path / "list.toml")]
    assert main([*args, "channels"]) == 0
    assert "example-channel\tExample Channel\thttps://www.youtube.com/@example" in (
        capsys.readouterr().out
    )
