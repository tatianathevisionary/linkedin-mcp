"""Tests for the LinkedIn data export parser."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest

from linkedin.posts import fetch_my_posts_from_export


def _make_export_zip(tmp_path: Path, rows: list[dict]) -> Path:
    """Build a minimal LinkedIn-style data export ZIP for testing."""
    zip_path = tmp_path / "test-export.zip"

    csv_buffer = io.StringIO()
    fieldnames = ["Date", "ShareCommentary", "Visibility", "ShareLink", "MediaUrl"]
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Shares.csv", csv_buffer.getvalue())

    return zip_path


@pytest.mark.asyncio
async def test_empty_export(tmp_path):
    zip_path = _make_export_zip(tmp_path, [])
    result = await fetch_my_posts_from_export(str(zip_path))
    assert result["total"] == 0
    assert result["posts"] == []
    assert result["source"] == "linkedin-data-export"


@pytest.mark.asyncio
async def test_single_post(tmp_path):
    zip_path = _make_export_zip(
        tmp_path,
        [
            {
                "Date": "2024-05-14 10:30:00 UTC",
                "ShareCommentary": "Shipped a new agent today. #AIEngineering",
                "Visibility": "PUBLIC",
                "ShareLink": "https://www.linkedin.com/feed/update/urn:li:activity:123/",
                "MediaUrl": "",
            }
        ],
    )
    result = await fetch_my_posts_from_export(str(zip_path))
    assert result["total"] == 1
    post = result["posts"][0]
    assert post["text"] == "Shipped a new agent today. #AIEngineering"
    assert post["hashtags"] == ["AIEngineering"]
    assert post["wordCount"] == 5
    assert post["visibility"] == "PUBLIC"
    assert post["url"] == "https://www.linkedin.com/feed/update/urn:li:activity:123/"


@pytest.mark.asyncio
async def test_sorts_newest_first(tmp_path):
    zip_path = _make_export_zip(
        tmp_path,
        [
            {"Date": "2024-01-01 09:00:00", "ShareCommentary": "Old"},
            {"Date": "2024-12-01 09:00:00", "ShareCommentary": "New"},
            {"Date": "2024-06-01 09:00:00", "ShareCommentary": "Mid"},
        ],
    )
    result = await fetch_my_posts_from_export(str(zip_path))
    texts = [p["text"] for p in result["posts"]]
    assert texts == ["New", "Mid", "Old"]


@pytest.mark.asyncio
async def test_limit(tmp_path):
    rows = [
        {"Date": f"2024-0{i+1}-01 09:00:00", "ShareCommentary": f"Post {i}"}
        for i in range(5)
    ]
    zip_path = _make_export_zip(tmp_path, rows)
    result = await fetch_my_posts_from_export(str(zip_path), limit=2)
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        await fetch_my_posts_from_export(str(tmp_path / "nonexistent.zip"))


@pytest.mark.asyncio
async def test_zip_without_shares_csv(tmp_path):
    zip_path = tmp_path / "no-shares.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("connections.csv", "Name,Email\nJohn,j@example.com\n")

    with pytest.raises(ValueError, match="Shares CSV"):
        await fetch_my_posts_from_export(str(zip_path))


@pytest.mark.asyncio
async def test_extracts_mentions(tmp_path):
    zip_path = _make_export_zip(
        tmp_path,
        [{"Date": "2024-05-14 09:00:00", "ShareCommentary": "Working with @alice on this"}],
    )
    result = await fetch_my_posts_from_export(str(zip_path))
    assert result["posts"][0]["mentions"] == ["alice"]
