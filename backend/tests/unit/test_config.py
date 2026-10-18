from __future__ import annotations

from app.core.config import Settings, resolve_tokens_file


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(cors_origins="http://localhost:5173, https://factweft.dev ,")
    assert settings.cors_origin_list == ["http://localhost:5173", "https://factweft.dev"]


def test_timeout_and_node_cap_have_sane_defaults() -> None:
    settings = Settings()
    assert settings.query_timeout_ms == 5000
    assert settings.max_graph_nodes == 500
    assert settings.llm_mode == "fixture"


def test_tokens_path_resolves_to_a_real_file() -> None:
    settings = Settings()
    assert settings.tokens_path.is_file(), f"missing token file at {settings.tokens_path}"


def test_relative_tokens_path_falls_back_to_cwd(tmp_path) -> None:
    resolved = resolve_tokens_file(tmp_path / "nope.json")
    assert resolved == tmp_path / "nope.json"


def test_password_is_not_leaked_in_repr() -> None:
    settings = Settings(falkordb_password="super-secret")
    assert "super-secret" not in repr(settings)
    assert settings.falkordb_password_value == "super-secret"
