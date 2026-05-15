/**
 * LinkedIn Jobs Search (Voyager API)
 * Uses chrome-auth for authenticated session cookies
 *
 * CLI: npm run linkedin:search -- "keywords" "location" [flags]
 * Flags: --remote --hybrid --onsite --easy-apply --past-24h --past-week --past-month
 *        --fulltime --parttime --contract --intern --start N --count N
 */

import { getCookieHeader } from '../../chrome.js';

const BASE = 'https://www.linkedin.com/voyager/api';
const DECORATION = 'com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollection-218';

// ---------- Types ----------

export interface SearchOptions {
  location?: string;
  start?: number;
  count?: number;
  /** 1=On-site, 2=Remote, 3=Hybrid */
  workplaceType?: 1 | 2 | 3;
  /** F=Full-time, P=Part-time, C=Contract, T=Temporary, I=Internship */
  jobType?: 'F' | 'P' | 'C' | 'T' | 'I';
  /** r86400=24h, r604800=week, r2592000=month */
  timePosted?: 'r86400' | 'r604800' | 'r2592000';
  /** Easy Apply only */
  easyApply?: boolean;
  /** Experience level: 1=Intern, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Director, 6=Executive */
  experience?: 1 | 2 | 3 | 4 | 5 | 6;
  /** Company ID */
  companyId?: string;
}

export interface JobResult {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  posted: string;
  insight?: string;
}

export interface SearchResult {
  jobs: JobResult[];
  total: number;
  start: number;
  count: number;
  geoId?: string;
}

// ---------- Helpers ----------

async function getAuthHeaders() {
  const cookieHeader = await getCookieHeader('https://www.linkedin.com');
  const csrfToken = (cookieHeader.match(/JSESSIONID="?([^";]+)"?/)?.[1] ?? '').replace(/^"|"$/g, '');
  return {
    Cookie: cookieHeader,
    'csrf-token': csrfToken,
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    Accept: 'application/vnd.linkedin.normalized+json+2.1',
    'X-Restli-Protocol-Version': '2.0.0',
    Referer: 'https://www.linkedin.com/jobs/search/',
  };
}

async function resolveGeoId(location: string): Promise<string | null> {
  const cookieHeader = await getCookieHeader('https://www.linkedin.com');
  const url = `https://www.linkedin.com/jobs/search/?keywords=test&location=${encodeURIComponent(location)}`;
  const res = await fetch(url, {
    headers: {
      Cookie: cookieHeader,
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      Accept: 'text/html',
    },
    redirect: 'follow',
  });
  const html = await res.text();
  return html.match(/fsd_geo:(\d+)/)?.[1] ?? null;
}

function buildQuery(keywords: string, geoId?: string, opts?: SearchOptions): string {
  const filters: string[] = ['sortBy:List(DD)'];

  if (opts?.workplaceType) filters.push(`workplaceType:List(${opts.workplaceType})`);
  if (opts?.jobType) filters.push(`jobType:List(${opts.jobType})`);
  if (opts?.timePosted) filters.push(`timePostedRange:List(${opts.timePosted})`);
  if (opts?.easyApply) filters.push('applyWithLinkedin:List(true)');
  if (opts?.experience) filters.push(`experience:List(${opts.experience})`);
  if (opts?.companyId) filters.push(`company:List(${opts.companyId})`);

  const locationPart = geoId ? `,locationUnion:(geoId:${geoId})` : '';
  const filterStr = filters.join(',');

  return `(origin:JOB_SEARCH_PAGE_QUERY_EXPANSION,keywords:${encodeURIComponent(keywords)}${locationPart},selectedFilters:(${filterStr}))`;
}

function formatTimeAgo(epochMs: number): string {
  const diff = Date.now() - epochMs;
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w ago`;
}

// ---------- Main ----------

export async function searchJobs(
  keywords: string,
  options?: SearchOptions | string,
  startOrCount?: number,
): Promise<SearchResult> {
  // Support (keywords, location) and (keywords, options) signatures
  const opts: SearchOptions =
    typeof options === 'string'
      ? { location: options, start: startOrCount ?? 0 }
      : { start: 0, count: 25, ...options };

  // Resolve location to geoId
  let geoId: string | undefined;
  if (opts.location) {
    geoId = (await resolveGeoId(opts.location)) ?? undefined;
  }

  const query = buildQuery(keywords, geoId, opts);
  const start = opts.start ?? 0;
  const count = opts.count ?? 25;

  const url = `${BASE}/voyagerJobsDashJobCards?decorationId=${DECORATION}&count=${count}&start=${start}&q=jobSearch&query=${query}`;
  const headers = await getAuthHeaders();
  const res = await fetch(url, { headers });

  if (!res.ok) {
    throw new Error(`LinkedIn API error: ${res.status} ${await res.text().then((t) => t.slice(0, 150))}`);
  }

  const raw = await res.json();
  const included: any[] = raw.included ?? [];
  const paging = raw.data?.paging;

  // Parse JobPostingCard entities (JOBS_SEARCH variant has the data)
  const cards = included.filter(
    (i) =>
      i.$type === 'com.linkedin.voyager.dash.jobs.JobPostingCard' &&
      i.jobPostingTitle,
  );

  const jobs: JobResult[] = cards.map((card) => {
    const jobId = card.jobPostingUrn?.match(/(\d+)/)?.[1] ?? '';
    const listedAt = card.footerItems?.find((f: any) => f.type === 'LISTED_DATE')?.timeAt;

    return {
      id: jobId,
      title: (card.jobPostingTitle ?? '').trim(),
      company: (card.primaryDescription?.text ?? '').trim(),
      location: (card.secondaryDescription?.text ?? '').trim(),
      url: `https://www.linkedin.com/jobs/view/${jobId}/`,
      posted: listedAt ? formatTimeAgo(listedAt) : '',
      insight: card.relevanceInsight?.text?.text?.trim() ?? undefined,
    };
  });

  return {
    jobs,
    total: paging?.total ?? 0,
    start,
    count,
    geoId,
  };
}

// ---------- CLI ----------

async function main() {
  const args = process.argv.slice(2);

  // Extract positional args, skipping values consumed by --flag pairs
  const valuedFlags = new Set(['--start', '--count']);
  const positional: string[] = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--')) {
      if (valuedFlags.has(args[i])) i++; // skip next arg (the value)
    } else {
      positional.push(args[i]);
    }
  }
  const keywords = positional[0] || 'software engineer';
  const location = positional[1];

  const opts: SearchOptions = { location };
  if (args.includes('--remote')) opts.workplaceType = 2;
  if (args.includes('--hybrid')) opts.workplaceType = 3;
  if (args.includes('--onsite')) opts.workplaceType = 1;
  if (args.includes('--easy-apply')) opts.easyApply = true;
  if (args.includes('--past-24h')) opts.timePosted = 'r86400';
  if (args.includes('--past-week')) opts.timePosted = 'r604800';
  if (args.includes('--past-month')) opts.timePosted = 'r2592000';
  if (args.includes('--fulltime')) opts.jobType = 'F';
  if (args.includes('--parttime')) opts.jobType = 'P';
  if (args.includes('--contract')) opts.jobType = 'C';
  if (args.includes('--intern')) opts.jobType = 'I';

  const startIdx = args.indexOf('--start');
  if (startIdx >= 0 && args[startIdx + 1]) opts.start = parseInt(args[startIdx + 1], 10);

  const countIdx = args.indexOf('--count');
  if (countIdx >= 0 && args[countIdx + 1]) opts.count = parseInt(args[countIdx + 1], 10);

  const filterStr = [
    opts.workplaceType === 1 && 'On-site',
    opts.workplaceType === 2 && 'Remote',
    opts.workplaceType === 3 && 'Hybrid',
    opts.easyApply && 'Easy Apply',
    opts.jobType === 'F' && 'Full-time',
    opts.jobType === 'P' && 'Part-time',
    opts.jobType === 'C' && 'Contract',
    opts.jobType === 'I' && 'Internship',
    opts.timePosted === 'r86400' && 'Past 24h',
    opts.timePosted === 'r604800' && 'Past week',
    opts.timePosted === 'r2592000' && 'Past month',
  ]
    .filter(Boolean)
    .join(', ');

  console.log(
    `\nLinkedIn Jobs: "${keywords}"${location ? ` in ${location}` : ''}${filterStr ? ` [${filterStr}]` : ''}\n`,
  );

  try {
    const result = await searchJobs(keywords, opts);

    if (result.jobs.length === 0) {
      console.log('No jobs found.');
      return;
    }

    console.log(`${result.jobs.length} of ${result.total.toLocaleString()} jobs (start: ${result.start}):\n`);

    result.jobs.forEach((job, i) => {
      console.log(`${i + 1 + result.start}. ${job.title}`);
      console.log(`   ${job.company} · ${job.location}`);
      if (job.insight) console.log(`   ${job.insight}`);
      console.log(`   ${job.url}`);
      if (job.posted) console.log(`   ${job.posted}`);
      console.log('');
    });
  } catch (err) {
    console.error('Error:', err instanceof Error ? err.message : err);
  }
}

if (process.argv[1]?.includes('linkedin/search-jobs')) main();
