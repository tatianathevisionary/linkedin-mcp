/**
 * Fetch a single LinkedIn job posting by ID or URL.
 * Uses chrome-auth for authenticated session cookies (Voyager API).
 *
 * CLI: npm run linkedin:job -- "4411284996"
 *      npm run linkedin:job -- "https://www.linkedin.com/jobs/view/4411284996/"
 */

import { getCookieHeader } from '../../chrome.js';

const BASE = 'https://www.linkedin.com/voyager/api';

// ---------- Types ----------

export interface JobDetails {
  id: string;
  title: string;
  company: string;
  companyId?: string;
  companyUrl?: string;
  location: string;
  workplaceType?: string;
  employmentType?: string;
  experienceLevel?: string;
  description: string;
  applies?: number;
  views?: number;
  listedAt?: string;
  postedAgo?: string;
  applyUrl?: string;
  jobUrl: string;
  salary?: string;
  industries?: string[];
  jobFunctions?: string[];
  /** Skills LinkedIn extracted from the JD (when available). */
  skills?: string[];
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
    Referer: 'https://www.linkedin.com/jobs/',
  };
}

/**
 * Extract a numeric job ID from a URL or bare string.
 * Handles: "4411284996", "https://www.linkedin.com/jobs/view/4411284996/", URN forms.
 */
export function extractJobId(input: string): string | null {
  const trimmed = input.trim();
  // Bare numeric ID
  if (/^\d+$/.test(trimmed)) return trimmed;
  // URL or URN-like string — first long number wins
  const m = trimmed.match(/(\d{8,})/);
  return m ? m[1] : null;
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
  if (weeks < 4) return `${weeks}w ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function stripHtml(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<li[^>]*>/gi, '• ')
    .replace(/<\/li>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

const WORKPLACE_TYPES: Record<string, string> = {
  '1': 'On-site',
  '2': 'Remote',
  '3': 'Hybrid',
};

const EXPERIENCE_LEVELS: Record<string, string> = {
  '1': 'Internship',
  '2': 'Entry level',
  '3': 'Associate',
  '4': 'Mid-Senior level',
  '5': 'Director',
  '6': 'Executive',
  '7': 'Not Applicable',
};

const EMPLOYMENT_TYPES: Record<string, string> = {
  FULL_TIME: 'Full-time',
  PART_TIME: 'Part-time',
  CONTRACT: 'Contract',
  TEMPORARY: 'Temporary',
  INTERNSHIP: 'Internship',
  VOLUNTEER: 'Volunteer',
  OTHER: 'Other',
};

// ---------- Main ----------

export async function fetchJob(input: string): Promise<JobDetails | null> {
  const jobId = extractJobId(input);
  if (!jobId) return null;

  const headers = await getAuthHeaders();
  // Use the legacy WebFullJobPosting decoration which still returns rich data.
  const decoration = 'com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65';
  const url = `${BASE}/jobs/jobPostings/${jobId}?decorationId=${decoration}`;

  const res = await fetch(url, { headers });
  if (!res.ok) {
    const body = await res.text().then((t) => t.slice(0, 200));
    throw new Error(`LinkedIn job fetch error: ${res.status} ${body}`);
  }

  const raw = await res.json();
  // Voyager normalized responses put the primary entity in `data` and related entities in `included`.
  const data = raw.data ?? {};
  const included: any[] = raw.included ?? [];

  // Title
  const title = (data.title ?? '').trim();

  // Description (rich text)
  const descRaw = data.description?.text ?? data.description ?? '';
  const description = stripHtml(typeof descRaw === 'string' ? descRaw : descRaw.text ?? '');

  // Location
  const location = (data.formattedLocation ?? data.locationName ?? '').trim();

  // Workplace type — string id ("1" | "2" | "3")
  const workplaceType = data.workplaceTypesResolutionResults
    ? Object.values(data.workplaceTypesResolutionResults)
        .map((w: any) => w.localizedName)
        .join(', ')
    : data.workplaceType
      ? WORKPLACE_TYPES[String(data.workplaceType)] ?? undefined
      : undefined;

  // Employment type
  const employmentType = data.formattedEmploymentStatus
    ?? (data.employmentStatus ? EMPLOYMENT_TYPES[data.employmentStatus] : undefined);

  // Experience level
  const experienceLevel = data.formattedExperienceLevel
    ?? (data.experienceLevel ? EXPERIENCE_LEVELS[String(data.experienceLevel)] : undefined);

  // Company — included entity with $type containing "Company"
  const companyEntity = included.find((i) => /Company$/.test(i.$type ?? ''));
  const company =
    (companyEntity?.name ?? data.companyDetails?.company?.name ?? data.companyName ?? '').trim();
  const companyId = companyEntity?.entityUrn?.match(/\d+/)?.[0];
  const companyUrl = companyEntity?.url ?? (companyId ? `https://www.linkedin.com/company/${companyId}/` : undefined);

  // Counts
  const applies = data.applies ?? data.numApplies ?? undefined;
  const views = data.views ?? data.numViews ?? undefined;

  // Listed date
  const listedAtMs = data.listedAt ?? data.originalListedAt ?? undefined;
  const listedAt = listedAtMs ? new Date(listedAtMs).toISOString().slice(0, 10) : undefined;
  const postedAgo = listedAtMs ? formatTimeAgo(listedAtMs) : undefined;

  // Apply URL
  const applyUrl =
    data.applyMethod?.companyApplyUrl
    ?? data.applyMethod?.easyApplyUrl
    ?? data.applyMethod?.applyStartersPreferenceVoid?.applyUrl
    ?? undefined;

  // Salary insights
  let salary: string | undefined;
  const salaryInsight = data.salaryInsights ?? data.compensation ?? undefined;
  if (salaryInsight) {
    if (typeof salaryInsight === 'string') salary = salaryInsight;
    else if (salaryInsight.formattedAnnualSalary) salary = salaryInsight.formattedAnnualSalary;
    else if (salaryInsight.minSalary && salaryInsight.maxSalary) {
      const cur = salaryInsight.currencyCode ?? '';
      salary = `${cur}${salaryInsight.minSalary}–${cur}${salaryInsight.maxSalary}`;
    }
  }

  // Industries / functions
  const industries = (data.formattedIndustries ?? data.industries ?? [])
    .map((i: any) => (typeof i === 'string' ? i : i?.name ?? ''))
    .filter(Boolean);

  const jobFunctions = (data.formattedJobFunctions ?? data.jobFunctions ?? [])
    .map((f: any) => (typeof f === 'string' ? f : f?.name ?? ''))
    .filter(Boolean);

  // Skills (LinkedIn's extracted skill matches)
  // These typically live in $type ending with "JobSkillMatchInsight" or "JobApplicantInsights"
  const skillEntities = included.filter(
    (i) => /Skill/.test(i.$type ?? '') && i.name,
  );
  const skills = skillEntities.map((s) => (s.name ?? '').trim()).filter(Boolean);

  return {
    id: jobId,
    title,
    company,
    companyId,
    companyUrl,
    location,
    workplaceType,
    employmentType,
    experienceLevel,
    description,
    applies,
    views,
    listedAt,
    postedAgo,
    applyUrl,
    jobUrl: `https://www.linkedin.com/jobs/view/${jobId}/`,
    salary,
    industries: industries.length ? industries : undefined,
    jobFunctions: jobFunctions.length ? jobFunctions : undefined,
    skills: skills.length ? skills : undefined,
  };
}

// ---------- CLI ----------

async function main() {
  const input = process.argv[2];
  if (!input) {
    console.error('Usage: npm run linkedin:job -- "<job_id_or_url>"');
    process.exit(1);
  }

  console.log(`\nFetching LinkedIn job: ${input}\n`);

  try {
    const job = await fetchJob(input);
    if (!job) {
      console.log('Job not found or invalid input.');
      process.exit(1);
    }

    console.log(`${job.title}`);
    console.log(`@ ${job.company}${job.companyUrl ? ` (${job.companyUrl})` : ''}`);
    console.log(`${job.location}`);
    if (job.workplaceType) console.log(`Workplace: ${job.workplaceType}`);
    if (job.employmentType) console.log(`Type: ${job.employmentType}`);
    if (job.experienceLevel) console.log(`Level: ${job.experienceLevel}`);
    if (job.salary) console.log(`Salary: ${job.salary}`);
    if (job.applies !== undefined) console.log(`Applicants: ${job.applies}`);
    if (job.views !== undefined) console.log(`Views: ${job.views}`);
    if (job.listedAt) console.log(`Listed: ${job.listedAt}${job.postedAgo ? ` (${job.postedAgo})` : ''}`);
    console.log(`URL: ${job.jobUrl}`);
    if (job.applyUrl) console.log(`Apply: ${job.applyUrl}`);
    if (job.industries?.length) console.log(`Industries: ${job.industries.join(', ')}`);
    if (job.jobFunctions?.length) console.log(`Functions: ${job.jobFunctions.join(', ')}`);
    if (job.skills?.length) console.log(`Skills: ${job.skills.join(', ')}`);
    console.log('\n--- Description ---\n');
    console.log(job.description);
  } catch (e) {
    console.error('Error:', e instanceof Error ? e.message : e);
    process.exit(1);
  }
}

if (process.argv[1]?.includes('linkedin/fetch-job')) main();
