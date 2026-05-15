"""Tests for the LinkedIn parsers (date, picture URL, public ID extraction)."""

from __future__ import annotations

from linkedin.parsers import (
    build_picture_url,
    extract_public_id,
    format_date,
    group_by_type,
    parse_positions,
    profile_type,
)


class TestFormatDate:
    def test_year_only(self):
        assert format_date({"year": 2024}) == "2024"

    def test_year_and_month(self):
        assert format_date({"year": 2024, "month": 5}) == "2024-05"

    def test_month_padded(self):
        assert format_date({"year": 2024, "month": 1}) == "2024-01"

    def test_no_year_returns_none(self):
        assert format_date({"month": 5}) is None

    def test_none_returns_none(self):
        assert format_date(None) is None

    def test_empty_returns_none(self):
        assert format_date({}) is None


class TestExtractPublicId:
    def test_bare_vanity(self):
        assert extract_public_id("johndoe") == "johndoe"

    def test_full_url(self):
        assert extract_public_id("https://linkedin.com/in/johndoe") == "johndoe"

    def test_www_url(self):
        assert extract_public_id("https://www.linkedin.com/in/johndoe/") == "johndoe"

    def test_trailing_slash(self):
        assert extract_public_id("johndoe/") == "johndoe"

    def test_with_query(self):
        assert extract_public_id("https://www.linkedin.com/in/johndoe?foo=bar") == "johndoe"

    def test_uppercase_url(self):
        assert extract_public_id("HTTPS://LINKEDIN.COM/IN/johndoe") == "johndoe"


class TestGroupByType:
    def test_groups_by_type(self):
        items = [
            {"$type": "A", "x": 1},
            {"$type": "A", "x": 2},
            {"$type": "B", "x": 3},
        ]
        groups = group_by_type(items)
        assert len(groups["A"]) == 2
        assert len(groups["B"]) == 1

    def test_unknown_type(self):
        groups = group_by_type([{"x": 1}])
        assert "unknown" in groups


class TestBuildPictureUrl:
    def test_returns_none_for_empty(self):
        assert build_picture_url(None) is None
        assert build_picture_url({}) is None

    def test_returns_root_if_no_artifacts(self):
        assert build_picture_url({"rootUrl": "https://media.example.com/"}) == (
            "https://media.example.com/"
        )

    def test_picks_widest_artifact(self):
        pic = {
            "rootUrl": "https://media.example.com/",
            "artifacts": [
                {"width": 100, "fileIdentifyingUrlPathSegment": "small.jpg"},
                {"width": 800, "fileIdentifyingUrlPathSegment": "large.jpg"},
                {"width": 400, "fileIdentifyingUrlPathSegment": "medium.jpg"},
            ],
        }
        assert build_picture_url(pic) == "https://media.example.com/large.jpg"


class TestProfileType:
    def test_prefixes(self):
        assert profile_type("Position") == "com.linkedin.voyager.dash.identity.profile.Position"


class TestParsePositions:
    def test_sorts_newest_first(self):
        entities = {
            profile_type("Position"): [
                {
                    "title": "Old Job",
                    "companyName": "Acme",
                    "dateRange": {"start": {"year": 2015}},
                },
                {
                    "title": "New Job",
                    "companyName": "Beta",
                    "dateRange": {"start": {"year": 2024}},
                },
            ]
        }
        positions = parse_positions(entities)
        assert positions[0]["title"] == "New Job"
        assert positions[1]["title"] == "Old Job"

    def test_empty_returns_empty(self):
        assert parse_positions({}) == []

    def test_resolves_employment_type(self):
        entities = {
            profile_type("Position"): [
                {
                    "title": "Engineer",
                    "companyName": "Acme",
                    "employmentTypeUrn": "urn:li:fsd_employmentType:1",
                }
            ],
            profile_type("EmploymentType"): [
                {"entityUrn": "urn:li:fsd_employmentType:1", "name": "Full-time"}
            ],
        }
        positions = parse_positions(entities)
        assert positions[0]["employmentType"] == "Full-time"
