"""Tests for the auth module."""

from __future__ import annotations

import os

import pytest

from auth import LinkedInAuth, _build_cookie_header, load_from_env


def test_cookie_header_format():
    header = _build_cookie_header("test_li_at", "test_jsessionid")
    assert "li_at=test_li_at" in header
    assert 'JSESSIONID="test_jsessionid"' in header


def test_cookie_header_strips_quotes_from_jsessionid():
    header = _build_cookie_header("x", '"ajax:12345"')
    # The quotes should be stripped and re-added once
    assert header.count('JSESSIONID="ajax:12345"') == 1


def test_cookie_header_extras():
    header = _build_cookie_header("x", "y", extras={"bcookie": "v=2", "lang": "v=2&lang=en"})
    assert "bcookie=v=2" in header
    assert "lang=v=2&lang=en" in header


def test_csrf_token_strips_quotes():
    auth = LinkedInAuth(li_at="x", jsessionid='"ajax:test"', cookie_header="")
    assert auth.csrf_token == "ajax:test"


def test_headers_include_required_fields():
    auth = LinkedInAuth(li_at="x", jsessionid='"y"', cookie_header="li_at=x")
    headers = auth.headers()
    assert "Cookie" in headers
    assert "csrf-token" in headers
    assert "User-Agent" in headers
    assert headers["csrf-token"] == "y"


def test_load_from_env_with_both(monkeypatch):
    monkeypatch.setenv("LINKEDIN_LI_AT_COOKIE", "li_at_value")
    monkeypatch.setenv("LINKEDIN_JSESSIONID", '"jsessionid_value"')
    auth = load_from_env()
    assert auth is not None
    assert auth.li_at == "li_at_value"
    assert auth.csrf_token == "jsessionid_value"


def test_load_from_env_missing_returns_none(monkeypatch):
    monkeypatch.delenv("LINKEDIN_LI_AT_COOKIE", raising=False)
    monkeypatch.delenv("LINKEDIN_JSESSIONID", raising=False)
    assert load_from_env() is None


def test_load_from_env_partial_returns_none(monkeypatch):
    monkeypatch.setenv("LINKEDIN_LI_AT_COOKIE", "x")
    monkeypatch.delenv("LINKEDIN_JSESSIONID", raising=False)
    assert load_from_env() is None
