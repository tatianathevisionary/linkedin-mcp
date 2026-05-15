/**
 * LinkedIn People Search
 * Uses chrome-auth for authenticated session cookies
 *
 * Strategy: Search connected profiles via the connections Voyager API,
 * then resolve each match to a full mini-profile. The general search
 * clusters endpoint (voyagerSearchDashClusters) returns 500 across all
 * decoration IDs as of Feb 2026, so we use the reliable connections +
 * profile resolution approach.
 *
 * CLI: npm run linkedin:people -- "keywords" [flags]
 * Flags: --network 1st|2nd|3rd  --title "Title"  --start N  --count N
 */

import { getCookieHeader } from '../../chrome.js';

// ---------- Types ----------

export interface PeopleSearchOptions {
  /** Filter by network proximity: F=1st, S=2nd, O=3rd+ */
  network?: 'F' | 'S' | 'O';
  /** Filter by current title */
  title?: string;
  /** Pagination offset */
  start?: number;
  /** Results per page (default 10) */
  count?: number;
}

export interface PersonResult {
  id: string;
  firstName: string;
  lastName: string;
  headline?: string;
  location?: string;
  profileUrl: string;
  profilePicture?: string;
  connectionDegree?: string;
  summary?: string;
}

export interface PeopleSearchResult {
  people: PersonResult[];
  total: number;
  start: number;
  count: number;
  query: string;
}

// ---------- Helpers ----------

const BASE = 'https://www.linkedin.com/voyager/api';

async function getAuthHeaders(referer?: string) {
  const cookieHeader = await getCookieHeader('https://www.linkedin.com');
  const csrfToken = (cookieHeader.match(/JSESSIONID="?([^";]+)"?/)?.[1] ?? '').replace(
    /^"|"$/g,
    '',
  );
  return {
    Cookie: cookieHeader,
    'csrf-token': csrfToken,
    'User-Agent':
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    Accept: 'application/vnd.linkedin.normalized+json+2.1',
    'X-Restli-Protocol-Version': '2.0.0',
    'X-Li-Lang': 'en_US',
    Referer: referer ?? 'https://www.linkedin.com/search/results/people/',
  };
}

function buildPictureUrl(pic: any): string | undefined {
  if (!pic) return undefined;
  const rootUrl: string | undefined = pic.rootUrl;
  if (!rootUrl) return undefined;
  const artifacts: any[] = pic.artifacts ?? [];
  const best = [...artifacts].sort(
    (a: any, b: any) => (b.width ?? 0) - (a.width ?? 0),
  )[0];
  return best?.fileIdentifyingUrlPathSegment
    ? rootUrl + best.fileIdentifyingUrlPathSegment
    : rootUrl;
}

// ---------- API calls ----------

/**
 * Search connections by keyword. Returns member URNs.
 */
async function searchConnections(
  keywords: string,
  count: number,
  start: number,
): Promise<{ memberIds: string[]; total: number }> {
  const headers = await getAuthHeaders(
    'https://www.linkedin.com/mynetwork/invite-connect/connections/',
  );
  const params = new URLSearchParams({
    q: 'search',
    keywords,
    count: String(count),
    start: String(start),
    sortType: 'RECENTLY_ADDED',
  });

  const res = await fetch(
    `${BASE}/relationships/dash/connections?${params}`,
    { headers },
  );

  if (!res.ok) {
    throw new Error(
      `Connections search ${res.status}: ${await res.text().then((t) => t.slice(0, 200))}`,
    );
  }

  const json = await res.json();
  const connections: any[] = json.included ?? [];
  const paging = json.data?.paging;

  const memberIds = connections
    .filter(
      (c: any) =>
        c.$type === 'com.linkedin.voyager.dash.relationships.Connection',
    )
    .map((c: any) => {
      const urn: string = c.connectedMember ?? '';
      return urn.match(/fsd_profile:(.+)/)?.[1] ?? '';
    })
    .filter(Boolean);

  return { memberIds, total: paging?.total ?? memberIds.length };
}

/**
 * Resolve a member ID to a mini-profile.
 */
async function resolveProfile(memberId: string): Promise<PersonResult | null> {
  const headers = await getAuthHeaders('https://www.linkedin.com/feed/');

  const params = new URLSearchParams({
    q: 'memberIdentity',
    memberIdentity: memberId,
    decorationId:
      'com.linkedin.voyager.dash.deco.identity.profile.TopCardSupplementary-185',
  });

  const res = await fetch(`${BASE}/identity/dash/profiles?${params}`, {
    headers,
  });

  if (!res.ok) return null;

  const json = await res.json();
  const included: any[] = json.included ?? [];

  const profile = included.find(
    (i: any) =>
      i.$type === 'com.linkedin.voyager.dash.identity.profile.Profile',
  );

  if (!profile) return null;

  const publicId = profile.publicIdentifier ?? '';

  return {
    id: memberId,
    firstName: (profile.firstName ?? '').trim(),
    lastName: (profile.lastName ?? '').trim(),
    headline: (profile.headline ?? '').trim() || undefined,
    location:
      (profile.geoLocationName ?? profile.locationName ?? '').trim() ||
      undefined,
    profileUrl: publicId
      ? `https://www.linkedin.com/in/${publicId}`
      : `https://www.linkedin.com/in/${memberId}`,
    profilePicture: buildPictureUrl(profile.profilePicture),
    connectionDegree: '1st',
    summary: undefined,
  };
}

/**
 * Search via the typeahead endpoint for entity suggestions (all of LinkedIn).
 * Returns a small set of people suggestions (typically 1-3).
 */
async function searchTypeahead(
  keywords: string,
): Promise<PersonResult[]> {
  const headers = await getAuthHeaders();
  const params = new URLSearchParams({
    q: 'globalTypeahead',
    query: keywords,
  });

  const res = await fetch(`${BASE}/voyagerSearchDashTypeahead?${params}`, {
    headers,
  });

  if (!res.ok) return [];

  const json = await res.json();
  const elements: any[] = json.data?.elements ?? [];

  const people: PersonResult[] = [];

  for (const el of elements) {
    if (el.suggestionType !== 'ENTITY_TYPEAHEAD') continue;

    const lockup = el.entityLockupView;
    if (!lockup) continue;

    const navUrl: string = lockup.navigationUrl ?? '';
    if (!navUrl.includes('/in/')) continue;

    const publicId = navUrl.match(/\/in\/([^/?#]+)/)?.[1] ?? '';
    if (!publicId) continue;

    const title = lockup.title?.text ?? '';
    const subtitle = lockup.subtitle?.text ?? '';
    const spaceIdx = title.indexOf(' ');

    // Extract picture from image attributes
    let profilePicture: string | undefined;
    const imgAttrs = lockup.image?.attributes ?? [];
    for (const attr of imgAttrs) {
      const vec = attr.detailDataUnion?.vectorImage;
      if (vec?.rootUrl) {
        const bestArt = (vec.artifacts ?? []).sort(
          (a: any, b: any) => (b.width ?? 0) - (a.width ?? 0),
        )[0];
        if (bestArt?.fileIdentifyingUrlPathSegment) {
          profilePicture = vec.rootUrl + bestArt.fileIdentifyingUrlPathSegment;
        }
        break;
      }
      const nonVec = attr.detailDataUnion?.nonEntityProfilePicture;
      if (nonVec?.vectorImage?.rootUrl) {
        const v = nonVec.vectorImage;
        const bestA = (v.artifacts ?? []).sort(
          (a: any, b: any) => (b.width ?? 0) - (a.width ?? 0),
        )[0];
        if (bestA?.fileIdentifyingUrlPathSegment) {
          profilePicture = v.rootUrl + bestA.fileIdentifyingUrlPathSegment;
        }
        break;
      }
    }

    people.push({
      id: publicId,
      firstName: spaceIdx > 0 ? title.slice(0, spaceIdx) : title,
      lastName: spaceIdx > 0 ? title.slice(spaceIdx + 1) : '',
      headline: subtitle || undefined,
      location: undefined,
      profileUrl: `https://www.linkedin.com/in/${publicId}`,
      profilePicture,
      connectionDegree: undefined,
      summary: undefined,
    });
  }

  return people;
}

// ---------- Main search ----------

export async function searchPeople(
  keywords: string,
  options?: PeopleSearchOptions,
): Promise<PeopleSearchResult> {
  const start = options?.start ?? 0;
  const count = options?.count ?? 10;

  // Run connections search + typeahead in parallel
  const [connResult, typeaheadPeople] = await Promise.all([
    searchConnections(keywords, count + 5, start).catch(() => ({
      memberIds: [] as string[],
      total: 0,
    })),
    start === 0
      ? searchTypeahead(keywords).catch(() => [] as PersonResult[])
      : Promise.resolve([] as PersonResult[]),
  ]);

  // Resolve connection profiles in parallel (batches of 5)
  const connectionPeople: PersonResult[] = [];
  const batchSize = 5;
  for (let i = 0; i < connResult.memberIds.length; i += batchSize) {
    const batch = connResult.memberIds.slice(i, i + batchSize);
    const results = await Promise.all(batch.map(resolveProfile));
    for (const r of results) {
      if (r) connectionPeople.push(r);
    }
  }

  // Filter by title if specified
  let filtered = connectionPeople;
  if (options?.title) {
    const titleLower = options.title.toLowerCase();
    filtered = connectionPeople.filter(
      (p) => p.headline?.toLowerCase().includes(titleLower),
    );
  }

  // Merge: typeahead suggestions first (broader reach), then connections
  const seen = new Set<string>();
  const merged: PersonResult[] = [];

  // Add typeahead results first (these may include non-connections)
  for (const p of typeaheadPeople) {
    if (!seen.has(p.id)) {
      seen.add(p.id);
      merged.push(p);
    }
  }

  // Add connection results
  for (const p of filtered) {
    if (!seen.has(p.id)) {
      seen.add(p.id);
      merged.push(p);
    }
  }

  // Filter by network if specified
  let finalPeople = merged;
  if (options?.network === 'F') {
    // Only 1st-degree connections
    finalPeople = merged.filter((p) => p.connectionDegree === '1st');
  }
  // For 2nd/3rd, we can only return typeahead suggestions since connections
  // endpoint only returns 1st-degree

  return {
    people: finalPeople.slice(0, count),
    total: connResult.total + typeaheadPeople.length,
    start,
    count,
    query: keywords,
  };
}

// ---------- CLI ----------

async function main() {
  const args = process.argv.slice(2);

  const valuedFlags = new Set([
    '--start',
    '--count',
    '--network',
    '--title',
  ]);
  const positional: string[] = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--')) {
      if (valuedFlags.has(args[i])) i++;
    } else {
      positional.push(args[i]);
    }
  }

  const keywords = positional[0] || 'software engineer';

  const opts: PeopleSearchOptions = {};
  const networkIdx = args.indexOf('--network');
  if (networkIdx >= 0 && args[networkIdx + 1]) {
    const v = args[networkIdx + 1].toLowerCase();
    if (v === '1st') opts.network = 'F';
    else if (v === '2nd') opts.network = 'S';
    else if (v === '3rd') opts.network = 'O';
  }
  const titleIdx = args.indexOf('--title');
  if (titleIdx >= 0 && args[titleIdx + 1]) opts.title = args[titleIdx + 1];
  const startIdx = args.indexOf('--start');
  if (startIdx >= 0 && args[startIdx + 1])
    opts.start = parseInt(args[startIdx + 1], 10);
  const countIdx = args.indexOf('--count');
  if (countIdx >= 0 && args[countIdx + 1])
    opts.count = parseInt(args[countIdx + 1], 10);

  console.log(`\nLinkedIn People: "${keywords}"\n`);

  try {
    const result = await searchPeople(keywords, opts);

    if (result.people.length === 0) {
      console.log('No people found.');
      return;
    }

    console.log(
      `${result.people.length} of ${result.total.toLocaleString()} people (start: ${result.start}):\n`,
    );

    result.people.forEach((p, i) => {
      console.log(`${i + 1 + result.start}. ${p.firstName} ${p.lastName}`);
      if (p.headline) console.log(`   ${p.headline}`);
      if (p.location) console.log(`   ${p.location}`);
      if (p.connectionDegree) console.log(`   ${p.connectionDegree}`);
      console.log(`   ${p.profileUrl}`);
      console.log('');
    });
  } catch (err) {
    console.error('Error:', err instanceof Error ? err.message : err);
  }
}

if (process.argv[1]?.includes('linkedin/search-people')) main();
