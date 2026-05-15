/**
 * Fetch any LinkedIn person's profile by vanity name or URL
 * Uses chrome-auth for authenticated session cookies
 *
 * CLI: npm run linkedin:person -- "johndoe"
 *      npm run linkedin:person -- "https://linkedin.com/in/johndoe"
 */

import { getCookieHeader } from '../../chrome.js';

const BASE = 'https://www.linkedin.com/voyager/api';

// ---------- Types ----------

interface DateField {
  month?: number;
  year?: number;
}

interface DateRange {
  start?: DateField;
  end?: DateField;
}

export interface Position {
  title: string;
  companyName: string;
  description?: string;
  location?: string;
  startDate?: string;
  endDate?: string;
  employmentType?: string;
}

export interface Education {
  schoolName: string;
  degreeName?: string;
  fieldOfStudy?: string;
  startDate?: string;
  endDate?: string;
  description?: string;
}

export interface Certification {
  name: string;
  authority?: string;
  startDate?: string;
  endDate?: string;
}

export interface Project {
  title: string;
  description?: string;
  url?: string;
  startDate?: string;
  endDate?: string;
}

export interface PersonProfile {
  publicIdentifier: string;
  firstName: string;
  lastName: string;
  headline?: string;
  summary?: string;
  profilePicture?: string;
  profileUrl: string;
  location?: string;
  industry?: string;
  connectionDegree?: string;
  connectionsCount?: number;
  positions: Position[];
  education: Education[];
  skills: string[];
  certifications: Certification[];
  projects: Project[];
  languages: string[];
}

// ---------- Helpers ----------

async function voyagerFetch(path: string, params?: Record<string, string>) {
  const cookieHeader = await getCookieHeader('https://www.linkedin.com');
  const csrfToken = (cookieHeader.match(/JSESSIONID="?([^";]+)"?/)?.[1] ?? '').replace(/^"|"$/g, '');

  const url = params ? `${BASE}${path}?${new URLSearchParams(params)}` : `${BASE}${path}`;
  const res = await fetch(url, {
    headers: {
      Cookie: cookieHeader,
      'csrf-token': csrfToken,
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      Accept: 'application/vnd.linkedin.normalized+json+2.1',
      'X-Restli-Protocol-Version': '2.0.0',
      Referer: 'https://www.linkedin.com/feed/',
    },
  });

  if (!res.ok) throw new Error(`${res.status}: ${await res.text().then((t) => t.slice(0, 200))}`);
  return res.json();
}

function formatDate(d?: DateField): string | undefined {
  if (!d?.year) return undefined;
  return d.month ? `${d.year}-${String(d.month).padStart(2, '0')}` : String(d.year);
}

function byType(included: any[]): Record<string, any[]> {
  const map: Record<string, any[]> = {};
  for (const item of included) {
    const t: string = item.$type || 'unknown';
    (map[t] ??= []).push(item);
  }
  return map;
}

function sortByDate(a: { startDate?: string }, b: { startDate?: string }): number {
  return (b.startDate ?? '').localeCompare(a.startDate ?? '');
}

function buildPictureUrl(pic: Record<string, unknown> | undefined): string | undefined {
  if (!pic) return undefined;
  const rootUrl = pic.rootUrl as string | undefined;
  if (!rootUrl) return undefined;
  const artifacts = (pic.artifacts as Array<{ width?: number; fileIdentifyingUrlPathSegment?: string }>) ?? [];
  const best = [...artifacts].sort((a, b) => (b.width ?? 0) - (a.width ?? 0))[0];
  return best?.fileIdentifyingUrlPathSegment ? rootUrl + best.fileIdentifyingUrlPathSegment : rootUrl;
}

/**
 * Extract vanity name from a LinkedIn URL or bare username.
 * Handles: "johndoe", "https://linkedin.com/in/johndoe", "https://www.linkedin.com/in/johndoe/"
 */
function extractPublicId(input: string): string {
  const trimmed = input.trim();
  // If it looks like a URL, extract the /in/VANITY part
  const match = trimmed.match(/linkedin\.com\/in\/([^/?#]+)/i);
  if (match) return match[1];
  // Otherwise treat the whole input as the vanity name
  return trimmed.replace(/^\/+|\/+$/g, '');
}

// ---------- Main ----------

export async function fetchPerson(profileInput: string): Promise<PersonProfile | null> {
  const publicId = extractPublicId(profileInput);
  if (!publicId) return null;

  // Fetch full profile with all entities via dash API
  const full = await voyagerFetch('/identity/dash/profiles', {
    q: 'memberIdentity',
    memberIdentity: publicId,
    decorationId: 'com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93',
  });

  const included: any[] = full?.included ?? [];
  if (included.length === 0) return null;

  const entities = byType(included);
  const T = (suffix: string) => `com.linkedin.voyager.dash.identity.profile.${suffix}`;

  // Find the target profile
  const profileEntities = entities[T('Profile')] ?? [];
  const profileData = profileEntities.find(
    (p: any) => p.publicIdentifier === publicId,
  ) ?? profileEntities[0];

  if (!profileData) return null;

  // Employment type lookup
  const empTypes: Record<string, string> = {};
  for (const e of entities[T('EmploymentType')] ?? []) {
    if (e.entityUrn && e.name) empTypes[e.entityUrn] = e.name;
  }

  // Positions
  const positions: Position[] = (entities[T('Position')] ?? [])
    .map((p: any) => {
      const dr: DateRange | undefined = p.dateRange;
      return {
        title: (p.title ?? '').trim(),
        companyName: (p.companyName ?? '').trim(),
        description: p.description?.trim() ?? undefined,
        location: (p.geoLocationName ?? p.locationName ?? '').trim() || undefined,
        startDate: formatDate(dr?.start),
        endDate: formatDate(dr?.end),
        employmentType: empTypes[p.employmentTypeUrn] ?? undefined,
      };
    })
    .sort(sortByDate);

  // Education
  const education: Education[] = (entities[T('Education')] ?? [])
    .map((e: any) => {
      const dr: DateRange | undefined = e.dateRange;
      return {
        schoolName: (e.schoolName ?? '').trim(),
        degreeName: e.degreeName?.trim() ?? undefined,
        fieldOfStudy: e.fieldOfStudy?.trim() ?? undefined,
        startDate: formatDate(dr?.start),
        endDate: formatDate(dr?.end),
        description: e.description?.trim() ?? undefined,
      };
    })
    .sort(sortByDate);

  // Skills
  const skills: string[] = (entities[T('Skill')] ?? [])
    .map((s: any) => (s.name ?? '').trim())
    .filter(Boolean);

  // Certifications
  const certifications: Certification[] = (entities[T('Certification')] ?? [])
    .map((c: any) => {
      const dr: DateRange | undefined = c.timePeriod;
      return {
        name: (c.name ?? '').trim(),
        authority: c.authority?.trim() ?? undefined,
        startDate: formatDate(dr?.start),
        endDate: formatDate(dr?.end),
      };
    });

  // Projects
  const projects: Project[] = (entities[T('Project')] ?? [])
    .map((p: any) => {
      const dr: DateRange | undefined = p.dateRange;
      return {
        title: (p.title ?? '').trim(),
        description: p.description?.trim() ?? undefined,
        url: p.url ?? undefined,
        startDate: formatDate(dr?.start),
        endDate: formatDate(dr?.end),
      };
    });

  // Languages
  const languages: string[] = (entities[T('Language')] ?? [])
    .map((l: any) => (l.name ?? '').trim())
    .filter(Boolean);

  // Location from profile data
  const geoLocation = profileData.geoLocation ?? profileData.location ?? {};
  const locationName =
    geoLocation.geo?.defaultLocalizedName ??
    profileData.geoLocationName ??
    profileData.locationName ??
    undefined;

  // Connection info
  const networkInfo = included.find(
    (i: any) => i.$type === 'com.linkedin.voyager.dash.identity.profile.NetworkInfo',
  );

  return {
    publicIdentifier: publicId,
    firstName: (profileData.firstName ?? '').trim(),
    lastName: (profileData.lastName ?? '').trim(),
    headline: profileData.headline?.trim() ?? undefined,
    summary: profileData.summary?.trim() ?? undefined,
    profilePicture: buildPictureUrl(profileData.profilePicture),
    profileUrl: `https://www.linkedin.com/in/${publicId}`,
    location: locationName,
    industry: profileData.industryName?.trim() ?? undefined,
    connectionDegree: networkInfo?.distance?.value ?? undefined,
    connectionsCount: networkInfo?.connectionsCount ?? undefined,
    positions,
    education,
    skills,
    certifications,
    projects,
    languages,
  };
}

// ---------- CLI ----------

async function main() {
  const input = process.argv[2];
  if (!input) {
    console.error('Usage: npm run linkedin:person -- "vanity-name-or-url"');
    process.exit(1);
  }

  console.log(`\nFetching LinkedIn profile: "${input}"\n`);

  try {
    const profile = await fetchPerson(input);

    if (!profile) {
      console.log('Profile not found.');
      process.exit(1);
    }

    console.log(`${profile.firstName} ${profile.lastName}`);
    if (profile.headline) console.log(profile.headline);
    if (profile.location) console.log(profile.location);
    if (profile.connectionDegree) console.log(`Connection: ${profile.connectionDegree}`);
    console.log(profile.profileUrl);
    console.log('');

    if (profile.summary) {
      console.log('--- Summary ---');
      console.log(profile.summary);
      console.log('');
    }

    if (profile.positions.length) {
      console.log(`--- Experience (${profile.positions.length}) ---`);
      profile.positions.forEach((p) => {
        const dates = [p.startDate, p.endDate ?? 'Present'].filter(Boolean).join(' - ');
        console.log(`  ${p.title} @ ${p.companyName} (${dates})`);
        if (p.location) console.log(`    ${p.location}`);
      });
      console.log('');
    }

    if (profile.education.length) {
      console.log(`--- Education (${profile.education.length}) ---`);
      profile.education.forEach((e) => {
        const degree = [e.degreeName, e.fieldOfStudy].filter(Boolean).join(', ');
        console.log(`  ${e.schoolName}${degree ? ` — ${degree}` : ''}`);
      });
      console.log('');
    }

    if (profile.skills.length) {
      console.log(`--- Skills (${profile.skills.length}) ---`);
      console.log(`  ${profile.skills.join(', ')}`);
      console.log('');
    }

    if (profile.languages.length) {
      console.log(`--- Languages ---`);
      console.log(`  ${profile.languages.join(', ')}`);
    }
  } catch (err) {
    console.error('Error:', err instanceof Error ? err.message : err);
  }
}

if (process.argv[1]?.includes('linkedin/fetch-person')) main();
