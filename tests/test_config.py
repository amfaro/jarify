"""Tests for config loading."""

from jarify.config import JarifyConfig


def test_default_config():
    config = JarifyConfig()
    assert config.dialect == "duckdb"
    assert config.uppercase_keywords is True
    assert config.leading_commas is True
    assert config.trailing_commas is False
    assert config.indent == 2


def test_config_from_dict():
    config = JarifyConfig.from_dict({"indent": 4, "uppercase_keywords": False})
    assert config.indent == 4
    assert config.uppercase_keywords is False
