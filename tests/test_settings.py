import pytest

from jalboot.config import ConfigError, load_settings
from jalboot.env import load_env_file, parse_env
from jalboot.text.normalize import detect_language, normalize


def test_parse_env_handles_quotes_comments_and_export():
    text = 'A=1\n# skip=me\nexport B="two words"\nC=three # note\n'
    assert parse_env(text) == {"A": "1", "B": "two words", "C": "three"}


def test_file_never_overrides_the_process_environment(tmp_path):
    path = tmp_path / ".env"
    path.write_text("A=file\nB=file\n", encoding="utf-8")
    env = {"A": "process"}
    assert load_env_file(path, env) == ["B"]
    assert env == {"A": "process", "B": "file"}


def test_bom_does_not_corrupt_the_first_name(tmp_path):
    path = tmp_path / ".env"
    path.write_bytes(b"\xef\xbb\xbfA=1\n")
    env = {}
    load_env_file(path, env)
    assert env == {"A": "1"}


def test_default_is_mock_mode():
    assert load_settings({}).llm_mode == "mock"


@pytest.mark.parametrize("env", [
    {"LLM_MODE": "magic"},
    {"ALLOWED_ORIGINS": "*"},
    {"COOKIE_SAMESITE": "none"},
    {"ENVIRONMENT": "production"},
    {"ENVIRONMENT": "production", "SECRET_KEY": "x" * 40, "COOKIE_SECURE": "true"},
])
def test_unsafe_settings_refuse_to_start(env):
    with pytest.raises(ConfigError):
        load_settings(env)


def test_production_settings_can_be_valid():
    settings = load_settings({
        "ENVIRONMENT": "production", "SECRET_KEY": "x" * 40,
        "COOKIE_SECURE": "true", "SHOW_SIMULATED_OTP": "false",
    })
    assert settings.is_production


def test_normalize_folds_arabic_and_digits():
    assert normalize("أَهلاً بالطلبيّة ٤٥") == normalize("اهلا بالطلبيه 45")


def test_invisible_characters_cannot_split_a_word():
    assert normalize("ig​nore") == "ignore"


def test_detect_language():
    assert detect_language("وين طلبي JB-1001") == "ar"
    assert detect_language("where is my order") == "en"
    assert detect_language("12345", default="ar") == "ar"
