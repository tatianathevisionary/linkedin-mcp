#!/usr/bin/env npx tsx
/**
 * LinkedIn MCP Server — stdio transport
 *
 * Exposes 5 LinkedIn tools: job search, company search, own-profile fetch,
 * people search, and arbitrary-person profile fetch. All calls authenticate
 * by reading the active Chrome session cookies (macOS Keychain).
 *
 * Run: npx tsx src/server.ts
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

import { searchJobs, type SearchOptions } from './clients/linkedin/search-jobs.js';
import { searchCompanies } from './clients/linkedin/search-companies.js';
import { fetchProfile } from './clients/linkedin/fetch-profile.js';
import { searchPeople, type PeopleSearchOptions } from './clients/linkedin/search-people.js';
import { fetchPerson } from './clients/linkedin/fetch-person.js';
import { fetchJob } from './clients/linkedin/fetch-job.js';

// ---------- Server ----------

const server = new McpServer({
  name: 'linkedin-mcp',
  version: '1.0.0',
});

const SEARCH_ANNOTATIONS = {
  readOnlyHint: true,
  destructiveHint: false,
  openWorldHint: true,
  idempotentHint: true,
} as const;

// ---------- Helpers ----------

function ok(data: unknown) {
  return { content: [{ type: 'text' as const, text: JSON.stringify(data, null, 2) }] };
}

function err(message: string) {
  return { content: [{ type: 'text' as const, text: message }], isError: true as const };
}

// ---------- LinkedIn enum maps ----------

const WORKPLACE_MAP: Record<string, 1 | 2 | 3> = {
  onsite: 1,
  remote: 2,
  hybrid: 3,
};

const JOBTYPE_MAP: Record<string, 'F' | 'P' | 'C' | 'T' | 'I'> = {
  fulltime: 'F',
  parttime: 'P',
  contract: 'C',
  temporary: 'T',
  internship: 'I',
};

const TIMEPOSTED_MAP: Record<string, 'r86400' | 'r604800' | 'r2592000'> = {
  past_24h: 'r86400',
  past_week: 'r604800',
  past_month: 'r2592000',
};

const EXPERIENCE_MAP: Record<string, 1 | 2 | 3 | 4 | 5 | 6> = {
  intern: 1,
  entry: 2,
  associate: 3,
  mid_senior: 4,
  director: 5,
  executive: 6,
};

const NETWORK_MAP: Record<string, 'F' | 'S' | 'O'> = {
  '1st': 'F',
  '2nd': 'S',
  '3rd': 'O',
};

// ============================================================
// Tool 1: search_linkedin_jobs
// ============================================================

server.registerTool('search_linkedin_jobs', {
  title: 'Search LinkedIn Jobs',
  description:
    'Search job listings on LinkedIn via the Voyager API. Requires an active Chrome session logged into LinkedIn. Supports filtering by workplace type, job type, posting recency, Easy Apply, and experience level.',
  annotations: SEARCH_ANNOTATIONS,
  inputSchema: {
    keywords: z.string().describe('Job title, skills, or keywords to search for'),
    location: z.string().optional().describe('City, state, or region to filter jobs by'),
    workplace_type: z
      .enum(['onsite', 'remote', 'hybrid'])
      .optional()
      .describe('Filter by workplace arrangement'),
    job_type: z
      .enum(['fulltime', 'parttime', 'contract', 'temporary', 'internship'])
      .optional()
      .describe('Filter by employment type'),
    time_posted: z
      .enum(['past_24h', 'past_week', 'past_month'])
      .optional()
      .describe('Filter by posting recency'),
    easy_apply: z.boolean().optional().describe('Only show LinkedIn Easy Apply listings'),
    experience_level: z
      .enum(['intern', 'entry', 'associate', 'mid_senior', 'director', 'executive'])
      .optional()
      .describe('Filter by required experience level'),
    start: z.number().int().min(0).optional().describe('Pagination offset (default 0)'),
    count: z.number().int().min(1).max(50).optional().describe('Results per page (default 25)'),
  },
}, async (args) => {
  try {
    const opts: SearchOptions = {
      location: args.location,
      start: args.start,
      count: args.count,
      easyApply: args.easy_apply,
    };
    if (args.workplace_type) opts.workplaceType = WORKPLACE_MAP[args.workplace_type];
    if (args.job_type) opts.jobType = JOBTYPE_MAP[args.job_type];
    if (args.time_posted) opts.timePosted = TIMEPOSTED_MAP[args.time_posted];
    if (args.experience_level) opts.experience = EXPERIENCE_MAP[args.experience_level];

    const result = await searchJobs(args.keywords, opts);
    return ok(result);
  } catch (e) {
    return err(`LinkedIn search failed: ${e instanceof Error ? e.message : String(e)}`);
  }
});

// ============================================================
// Tool 2: search_linkedin_companies
// ============================================================

server.registerTool('search_linkedin_companies', {
  title: 'Search LinkedIn Companies',
  description:
    'Search for companies on LinkedIn by name using the guest typeahead API. Returns company names, IDs, and profile URLs. Requires an active Chrome session logged into LinkedIn.',
  annotations: SEARCH_ANNOTATIONS,
  inputSchema: {
    query: z.string().describe('Company name or partial name to search for'),
    limit: z.number().int().min(1).max(25).optional().describe('Max results to return (default 10)'),
  },
}, async (args) => {
  try {
    const companies = await searchCompanies(args.query, args.limit);
    return ok({ companies, total: companies.length, query: args.query });
  } catch (e) {
    return err(`LinkedIn company search failed: ${e instanceof Error ? e.message : String(e)}`);
  }
});

// ============================================================
// Tool 3: fetch_linkedin_profile
// ============================================================

server.registerTool('fetch_linkedin_profile', {
  title: 'Fetch LinkedIn Profile',
  description:
    'Fetch the authenticated user\'s full LinkedIn profile including positions, education, skills, certifications, and projects. Requires an active Chrome session logged into LinkedIn. Returns the profile of the currently logged-in user.',
  annotations: SEARCH_ANNOTATIONS,
  inputSchema: {},
}, async () => {
  try {
    const profile = await fetchProfile();
    if (!profile) return err('Could not fetch profile. Ensure you are logged into LinkedIn in Chrome.');
    return ok(profile);
  } catch (e) {
    return err(`LinkedIn profile fetch failed: ${e instanceof Error ? e.message : String(e)}`);
  }
});

// ============================================================
// Tool 4: search_linkedin_people
// ============================================================

server.registerTool('search_linkedin_people', {
  title: 'Search LinkedIn People',
  description:
    'Search for people on LinkedIn by name, title, or keywords. Searches your connections and LinkedIn typeahead suggestions. Requires an active Chrome session logged into LinkedIn. Returns names, headlines, locations, profile URLs, and connection degree. Use fetch_linkedin_person to get full profile details for any result.',
  annotations: SEARCH_ANNOTATIONS,
  inputSchema: {
    keywords: z.string().describe('Name, title, skills, or keywords to search for'),
    network: z
      .enum(['1st', '2nd', '3rd'])
      .optional()
      .describe('Filter by connection degree'),
    title: z.string().optional().describe('Filter by current job title'),
    start: z.number().int().min(0).optional().describe('Pagination offset (default 0)'),
    count: z.number().int().min(1).max(50).optional().describe('Results per page (default 10)'),
  },
}, async (args) => {
  try {
    const opts: PeopleSearchOptions = {
      start: args.start,
      count: args.count,
      title: args.title,
    };
    if (args.network) opts.network = NETWORK_MAP[args.network];

    const result = await searchPeople(args.keywords, opts);
    return ok(result);
  } catch (e) {
    return err(`LinkedIn people search failed: ${e instanceof Error ? e.message : String(e)}`);
  }
});

// ============================================================
// Tool 5: fetch_linkedin_person
// ============================================================

server.registerTool('fetch_linkedin_person', {
  title: 'Fetch LinkedIn Person',
  description:
    'Fetch any LinkedIn user\'s full profile by vanity name or profile URL. Returns positions, education, skills, certifications, projects, and languages. Requires an active Chrome session logged into LinkedIn.',
  annotations: SEARCH_ANNOTATIONS,
  inputSchema: {
    profile: z.string().describe('LinkedIn vanity username (e.g. "johndoe") or full profile URL (e.g. "https://linkedin.com/in/johndoe")'),
  },
}, async (args) => {
  try {
    const person = await fetchPerson(args.profile);
    if (!person) return err('Profile not found. Check the vanity name or URL.');
    return ok(person);
  } catch (e) {
    return err(`LinkedIn person fetch failed: ${e instanceof Error ? e.message : String(e)}`);
  }
});

// ============================================================
// Tool 6: fetch_linkedin_job
// ============================================================

server.registerTool('fetch_linkedin_job', {
  title: 'Fetch LinkedIn Job',
  description:
    'Fetch a single LinkedIn job posting by ID or URL. Returns the full job description, company, location, workplace type, employment type, experience level, applicant count, listed date, salary (if posted), industries, job functions, and any LinkedIn-extracted skills. Useful for analyzing required skills and keyword density across a target role set. Requires an active Chrome session logged into LinkedIn.',
  annotations: SEARCH_ANNOTATIONS,
  inputSchema: {
    job: z.string().describe('LinkedIn job ID (e.g. "4411284996") or full job URL (e.g. "https://www.linkedin.com/jobs/view/4411284996/")'),
  },
}, async (args) => {
  try {
    const job = await fetchJob(args.job);
    if (!job) return err('Job not found. Check the job ID or URL.');
    return ok(job);
  } catch (e) {
    return err(`LinkedIn job fetch failed: ${e instanceof Error ? e.message : String(e)}`);
  }
});

// ---------- Start ----------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('linkedin-mcp server running on stdio');
}

main().catch((e) => {
  console.error('Fatal:', e);
  process.exit(1);
});
