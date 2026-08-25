import pytest

from app.services.claude_cli import extract_json
from app.services.fingerprint import make_fingerprint
from app.services.gitops import authed_repo_url, parse_repo_url, redact


def test_extract_json_plain():
    assert extract_json('{"has_error": true}') == {"has_error": True}


def test_extract_json_fenced():
    text = '```json\n{"has_error": true, "error_type": "X"}\n```'
    assert extract_json(text)["error_type"] == "X"


def test_extract_json_with_prefix_text():
    text = '分析结果如下：\n{"has_error": false}\n以上。'
    assert extract_json(text) == {"has_error": False}


def test_extract_json_invalid():
    assert extract_json("没有任何 JSON") is None


def test_fingerprint_stable_across_noise():
    a = make_fingerprint("ZeroDivisionError: division by zero @app.py:42")
    b = make_fingerprint("ZeroDivisionError:  division by zero @app.py:42  ")
    assert a == b


def test_fingerprint_differs_across_errors():
    a = make_fingerprint("ZeroDivisionError: division by zero @app.py:42")
    b = make_fingerprint("KeyError: 'user' @app.py:42")
    assert a != b


def test_fingerprint_ignores_hex_and_numbers():
    a = make_fingerprint("TimeoutError db=8ab31f09e2 after 3000 ms @repo")
    b = make_fingerprint("TimeoutError db=9c22 after 5000 ms @repo")
    assert a == b


def test_parse_repo_url_gitlab():
    assert parse_repo_url("https://jihulab.com/ns/repo.git") == (
        "jihulab.com", "ns/repo",
    )


def test_parse_repo_url_ssh_style():
    assert parse_repo_url("git@github.com:owner/repo.git") == (
        "github.com", "owner/repo",
    )


def test_authed_url_github():
    url = authed_repo_url("https://github.com/o/r.git", "github", "tok")
    assert url == "https://x-access-token:tok@github.com/o/r.git"


def test_authed_url_gitlab():
    url = authed_repo_url("https://gitlab.example.com/ns/r.git", "gitlab", "tok")
    assert url == "https://oauth2:tok@gitlab.example.com/ns/r.git"


def test_redact():
    assert (
        redact("failed: https://oauth2:secret@host/ns/r.git denied")
        == "failed: https://oauth2:***@host/ns/r.git denied"
    )
