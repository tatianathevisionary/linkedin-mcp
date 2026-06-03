# fetch-posts.ts — v0 (NOT REGISTERED)

This client exists as a starting point but **does NOT currently work** and is not registered in `server.ts`. Save here for v1 work.

## What was tried (2026-05-06)

Tested ~30 endpoint variations against the authenticated Voyager API using the same Chrome-cookie auth that works for `fetch-profile.ts`:

| Endpoint pattern | Result |
|---|---|
| `/identity/profileUpdatesV2?profileId=<URN>&q=memberShareFeed&moduleKey=member-shares:phone` | 400 |
| Same with `moduleKey=member-shares:tab-content`, `:desktop`, `:profile-view-base-creator-feed`, `:profile-view-base-recent-activity-details-shares` | 400 (all) |
| `profileId=` with bare URN, `urn:li:fsd_profile:` prefix, member-id, `urn:li:member:` | 400 (all) |
| `q=memberPosts` | 400 |
| `q=memberShareFeed` without moduleKey | 401 |
| `/feed/dashProfileUpdates` | 404 |
| `/feed/updatesV3` | 404 |
| `/feed/updates?q=byAuthor` | 400 |
| `/feed/memberRecentActivity` | 404 |
| `/identity/profileViews/<id>/activity` | 410 (gone) |
| `/identity/profiles/<id>/posts` | 410 (gone) |
| `/feed/shares?q=member&author=<URN>` | 404 |
| `/search/dash/clusters?...types=CONTENT` | 401 |
| `/graphql?queryId=voyagerFeedDashProfileUpdates.<old-hash>` | 500 |

The activity page HTML (`/in/<vanity>/recent-activity/all/`) returns `999` (anti-scrape) so we can't scrape the embedded preloaded data either.

## What works (for context)

- `/identity/dash/profiles?q=memberIdentity&memberIdentity=<vanity>` → 200, returns profile + recent hashtags used (no post bodies though)
- `fetch_linkedin_profile` and `fetch_linkedin_person` work fine
- All the search endpoints work fine

So **auth is not the issue** — the posts/activity paths have moved.

## What's actually happening

LinkedIn migrated member activity to a GraphQL-only path:
```
/voyager/api/graphql?variables=(memberIdentity:<vanity>,start:0,count:N,paginationToken:null)&queryId=voyagerFeedDashProfileUpdates.<HASH>
```

The hash is a SHA-256 of the persisted query text. It's embedded in the LinkedIn web JS bundle and rotates whenever LinkedIn redeploys (weekly-ish). Without browser-inspecting current devtools traffic, you can't get a working hash.

## Path to v1

Two options for making this work:

1. **Persisted-query hash discovery** — Fetch the LinkedIn JS bundle (chunked across many files), parse it to extract current `voyagerFeedDashProfileUpdates.*` and related query IDs, cache them, retry on hash misses. ~1 day of work + ongoing maintenance.

2. **Browser automation** — Drive Playwright/Puppeteer in a hidden Chrome to load the activity page, intercept the actual API call, extract post data. More reliable but heavier (adds Chromium dep).

3. **LinkedIn data export** — Skip the API entirely, parse the user-requested CSV export. **This is what we're doing for the demo.** Most complete dataset; no API maintenance.

For the linkedin-agent demo, option 3 is the right answer. For automated daily/weekly post pulls, option 1 or 2 would eventually be needed.

## The v0 client

It tries the legacy endpoint that's now broken. Keep it as a skeleton — the parsing helpers (hashtags, mentions, media classification) and types are reusable. The endpoint URL/params need to change.
