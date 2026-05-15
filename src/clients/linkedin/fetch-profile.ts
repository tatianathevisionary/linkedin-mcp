/**
 * Fetch full LinkedIn profile using chrome-auth
 * Run: npm run linkedin:profile
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

export interface LinkedInProfile {
  id: string;
  firstName: string;
  lastName: string;
  headline?: string;
  summary?: string;
  profilePicture?: string;
  profileUrl?: string;
  location?: string;
  emails?: string[];
  positions: Position[];
  education: Education[];
  skills: string[];
  certifications: Certification[];
  projects: Project[];
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

  if (!res.ok) throw new Error(`${res.status}: ${await res.text().then((t) => t.slice(0, 150))}`);
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

function buildProfilePictureUrl(pic: Record<string, unknown> | undefined): string | undefined {
  if (!pic) return undefined;
  const rootUrl = pic.rootUrl as string | undefined;
  if (!rootUrl) return undefined;
  const artifacts = (pic.artifacts as Array<{ width?: number; fileIdentifyingUrlPathSegment?: string }>) ?? [];
  const best = [...artifacts].sort((a, b) => (b.width ?? 0) - (a.width ?? 0))[0];
  return best?.fileIdentifyingUrlPathSegment ? rootUrl + best.fileIdentifyingUrlPathSegment : rootUrl;
}

// ---------- Main ----------

export async function fetchProfile(): Promise<LinkedInProfile | null> {
  // Step 1: Get profile ID via job seeker preferences
  const prefs = await voyagerFetch('/voyagerJobsDashJobSeekerPreferences', {
    decorationId: 'com.linkedin.voyager.dash.deco.jobs.FullJobSeekerPreference-8',
  });

  const profileId = prefs?.data?.entityUrn?.match(/ACo[A-Za-z0-9_-]+/)?.[0];
  if (!profileId) return null;

  // Step 2: Get basic profile (for emails + profile picture)
  const basic = await voyagerFetch(`/identity/normalizedProfiles/${profileId}`, {
    decorationId: 'com.linkedin.voyager.deco.identity.normalizedprofile.shared.WebApplicantProfile-13',
  });

  // Step 3: Get full profile with all entities via dash API
  const publicId = basic?.data?.publicIdentifier;
  if (!publicId) return null;

  const full = await voyagerFetch('/identity/dash/profiles', {
    q: 'memberIdentity',
    memberIdentity: publicId,
    decorationId: 'com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93',
  });

  const entities = byType(full?.included ?? []);
  const T = (suffix: string) => `com.linkedin.voyager.dash.identity.profile.${suffix}`;

  // Employment type lookup
  const empTypes: Record<string, string> = {};
  for (const e of entities[T('EmploymentType')] ?? []) {
    if (e.entityUrn && e.name) empTypes[e.entityUrn] = e.name;
  }

  // Find own profile (filter out other people who appear in included)
  const profileData = (entities[T('Profile')] ?? []).find(
    (p: any) => p.entityUrn?.includes(profileId),
  );

  // Emails from basic profile
  const emails: string[] = [];
  for (const item of basic?.included ?? []) {
    if (item.email && typeof item.email === 'string') emails.push(item.email);
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

  const d = basic?.data ?? {};
  const loc = d.location;

  return {
    id: profileId,
    firstName: String(d.firstName ?? '').trim(),
    lastName: String(d.lastName ?? '').trim(),
    headline: (d.headline as string)?.trim(),
    summary: profileData?.summary?.trim() ?? undefined,
    profilePicture: buildProfilePictureUrl(d.profilePicture),
    profileUrl: publicId ? `https://www.linkedin.com/in/${publicId}` : undefined,
    location: loc?.locationDisplayName ?? loc?.defaultLocalizedName ?? undefined,
    emails: emails.length ? emails : undefined,
    positions,
    education,
    skills,
    certifications,
    projects,
  };
}

if (process.argv[1]?.endsWith('fetch-profile.ts')) {
  fetchProfile()
    .then((p) => (p ? console.log(JSON.stringify(p, null, 2)) : process.exit(1)))
    .catch((e) => { console.error(e); process.exit(1); });
}
