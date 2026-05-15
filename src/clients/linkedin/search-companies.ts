/**
 * LinkedIn Companies (guest API) - Typeahead search
 * Uses chrome-auth for session cookies
 *
 * Run: npm run linkedin:companies -- "Microsoft"
 *      npm run linkedin:companies -- "Google" 10
 */

import { getCookieHeader } from '../../chrome.js';

const COMPANIES_API = 'https://www.linkedin.com/jobs-guest/api/typeaheadHits';

export interface CompanyResult {
  id: string;
  name: string;
  url?: string;
}

interface TypeaheadHit {
  id?: string | number;
  type?: string;
  displayName?: string;
  trackingId?: string;
  navigationUrl?: string;
}

export async function searchCompanies(
  query: string,
  limit = 10
): Promise<CompanyResult[]> {
  const cookieHeader = await getCookieHeader('https://www.linkedin.com');

  const params = new URLSearchParams({
    typeaheadType: 'COMPANY',
    query,
  });

  const res = await fetch(`${COMPANIES_API}?${params}`, {
    headers: {
      Cookie: cookieHeader,
      'User-Agent':
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      Accept: 'application/json',
      'Accept-Language': 'en-US,en;q=0.9',
    },
  });

  if (!res.ok) {
    throw new Error(`LinkedIn API error: ${res.status} ${res.statusText}`);
  }

  const data = await res.json();
  const elements: TypeaheadHit[] = Array.isArray(data) ? data : data.elements ?? [];

  const companies: CompanyResult[] = elements.slice(0, limit).map((el) => ({
    id: String(el.id ?? ''),
    name: el.displayName ?? 'Unknown',
    url: el.navigationUrl,
  }));

  return companies;
}

async function main() {
  const query = process.argv[2] || 'Microsoft';
  const limit = parseInt(process.argv[3] || '10', 10);

  console.log(`\n🏢 Searching companies: "${query}"\n`);

  try {
    const companies = await searchCompanies(query, limit);

    if (companies.length === 0) {
      console.log('No companies found. Try a different search term.');
      return;
    }

    console.log(`Found ${companies.length} companies:\n`);
    companies.forEach((c, i) => {
      console.log(`${i + 1}. ${c.name} (ID: ${c.id})`);
      if (c.url) console.log(`   ${c.url}`);
      console.log('');
    });
  } catch (err) {
    console.error('Error:', err instanceof Error ? err.message : err);
  }
}

if (process.argv[1]?.includes('linkedin/search-companies')) main();
