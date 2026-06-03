"""
Tests for job search query building + response parsing.

These cover the pure, network-free parts of `search_jobs` so the parse path
is regression-covered without a live LinkedIn cookie. The `included[]` fixture
mirrors the verified-working TS edition's response shape
(`src/clients/linkedin/search-jobs.ts`).
"""

from __future__ import annotations

from linkedin.jobs import _build_query, _parse_jobs

# Representative Voyager response (included[] shape, normalized+json+2.1).
# Trimmed to the fields the parser reads.
INCLUDED_SHAPE_RESPONSE = {
    "data": {
        "paging": {"start": 0, "count": 25, "total": 1234},
        "elements": [],
    },
    "included": [
        {
            "$type": "com.linkedin.voyager.dash.jobs.JobPostingCard",
            "jobPostingUrn": "urn:li:fsd_jobPosting:3811001122",
            "jobPostingTitle": "Senior Software Engineer",
            "primaryDescription": {"text": "Acme Corp"},
            "secondaryDescription": {"text": "San Francisco, CA (Remote)"},
        },
        {
            "$type": "com.linkedin.voyager.dash.jobs.JobPostingCard",
            "jobPostingUrn": "urn:li:fsd_jobPosting:3811003344",
            "jobPostingTitle": "Staff Engineer",
            "primaryDescription": {"text": "Beta Inc"},
            "secondaryDescription": {"text": "New York, NY"},
        },
        # Non-job entity that must be ignored.
        {
            "$type": "com.linkedin.voyager.dash.jobs.JobSearchHeader",
            "title": "Results",
        },
        # JobPostingCard without a title must be skipped.
        {
            "$type": "com.linkedin.voyager.dash.jobs.JobPostingCard",
            "jobPostingUrn": "urn:li:fsd_jobPosting:3811005566",
        },
    ],
}

# Legacy half-port shape: cards under data.elements[].jobCardUnion.
ELEMENTS_SHAPE_RESPONSE = {
    "data": {
        "paging": {"start": 0, "count": 25, "total": 7},
        "elements": [
            {
                "jobCardUnion": {
                    "jobPostingCard": {
                        "jobPostingUrn": "urn:li:fsd_jobPosting:99887766",
                        "jobPostingTitle": "Backend Engineer",
                        "primaryDescription": {"text": "Gamma LLC"},
                        "secondaryDescription": {"text": "Austin, TX"},
                    }
                }
            }
        ],
    },
    "included": [],
}


class TestParseJobsIncludedShape:
    def test_parses_job_cards(self):
        result = _parse_jobs(INCLUDED_SHAPE_RESPONSE, start=0, count=25)
        jobs = result["jobs"]
        # 2 valid cards (header + untitled card filtered out).
        assert len(jobs) == 2
        assert jobs[0] == {
            "jobId": "3811001122",
            "title": "Senior Software Engineer",
            "company": "Acme Corp",
            "location": "San Francisco, CA (Remote)",
            "url": "https://www.linkedin.com/jobs/view/3811001122/",
        }
        assert jobs[1]["jobId"] == "3811003344"
        assert jobs[1]["title"] == "Staff Engineer"

    def test_uses_paging_total(self):
        result = _parse_jobs(INCLUDED_SHAPE_RESPONSE, start=0, count=25)
        assert result["total"] == 1234
        assert result["paging"] == {"start": 0, "count": 25}

    def test_ignores_non_job_entities(self):
        result = _parse_jobs(INCLUDED_SHAPE_RESPONSE, start=0, count=25)
        titles = [j["title"] for j in result["jobs"]]
        assert "Results" not in titles


class TestParseJobsElementsShape:
    def test_fallback_to_elements(self):
        result = _parse_jobs(ELEMENTS_SHAPE_RESPONSE, start=0, count=25)
        jobs = result["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["jobId"] == "99887766"
        assert jobs[0]["title"] == "Backend Engineer"
        assert jobs[0]["company"] == "Gamma LLC"
        assert jobs[0]["url"] == "https://www.linkedin.com/jobs/view/99887766/"


class TestParseJobsEmpty:
    def test_empty_response(self):
        result = _parse_jobs({}, start=5, count=10)
        assert result["jobs"] == []
        assert result["total"] == 0
        assert result["paging"] == {"start": 5, "count": 10}


class TestBuildQuery:
    def test_list_filter_encoding(self):
        query = _build_query("data scientist", None, ["sortBy:List(DD)", "workplaceType:List(2)"])
        assert "selectedFilters:(sortBy:List(DD),workplaceType:List(2))" in query
        assert "JOB_SEARCH_PAGE_QUERY_EXPANSION" in query
        # No arrow syntax — that was the buggy half-port.
        assert "->" not in query

    def test_keywords_url_encoded(self):
        query = _build_query("data scientist", None, ["sortBy:List(DD)"])
        assert "keywords:data%20scientist" in query

    def test_geo_id_included_as_location_union(self):
        query = _build_query("engineer", "102095887", ["sortBy:List(DD)"])
        assert "locationUnion:(geoId:102095887)" in query

    def test_no_geo_id_omits_location_union(self):
        query = _build_query("engineer", None, ["sortBy:List(DD)"])
        assert "locationUnion" not in query
