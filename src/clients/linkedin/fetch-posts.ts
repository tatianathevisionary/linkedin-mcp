/**
 * Fetch the authenticated user's posts/activity using chrome-auth.
 *
 * Uses the legacy Voyager profileUpdatesV2 endpoint with q=memberShareFeed,
 * which returns the same data the LinkedIn web app shows on the "Posts"
 * tab of a member's activity page. Engagement counts (reactions, comments,
 * reposts) are pulled from the socialDetail block on each share.
 *
 * CLI: npm run linkedin:posts -- [--count N] [--raw path]
 */

import { writeFileSync } from 'fs';
import { getCookieHeader } from '../../chrome.js';

const BASE = 'https://www.linkedin.com/voyager/api';

// ---------- Types ----------

export interface PostMedia {
  type: 'image' | 'video' | 'article' | 'document' | 'poll' | 'celebration' | 'other';
  url?: string;
  title?: string;
  description?: string;
}

export interface PostEngagement {
  reactions: number;
  comments: number;
  reposts: number;
  reactionsByType?: Record<string, number>;
}

export interface LinkedInPost {
  urn: string;
  permalink?: string;
  postedAt?: string;
  postedAtTimestamp?: number;
  text: string;
  textLength: number;
  isRepost: boolean;
  originalAuthor?: string;
  media: PostMedia[];
  hashtags: string[];
  mentions: string[];
  engagement: PostEngagement;
}

export interface PostsResult {
  total: number;
  posts: LinkedInPost[];
  fetchedAt: string;
}

// ---------- Auth ----------

async function getAuthHeaders() {
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
    Referer: 'https://www.linkedin.com/in/me/recent-activity/all/',
  };
}

// ---------- Helpers ----------

async function getOwnProfileUrn(): Promise<string | null> {
  const headers = await getAuthHeaders();
  const params = new URLSearchParams({
    decorationId: 'com.linkedin.voyager.dash.deco.jobs.FullJobSeekerPreference-8',
  });
  const res = await fetch(
    `${BASE}/voyagerJobsDashJobSeekerPreferences?${params}`,
    { headers },
  );
  if (!res.ok) return null;
  const json = await res.json();
  return json?.data?.entityUrn?.match(/ACo[A-Za-z0-9_-]+/)?.[0] ?? null;
}

function extractHashtags(text: string): string[] {
  return [...text.matchAll(/#([A-Za-z0-9_]+)/g)].map((m) => m[1]);
}

function extractMentions(text: string): string[] {
  return [...text.matchAll(/@([A-Za-z0-9_-]+)/g)].map((m) => m[1]);
}

function classifyMedia(content: any): PostMedia[] {
  const out: PostMedia[] = [];
  if (!content) return out;

  if (content.images || content['com.linkedin.voyager.feed.render.ImageComponent']) {
    out.push({ type: 'image' });
  }
  const linkedVideo =
    content['com.linkedin.voyager.feed.render.LinkedInVideoComponent'] ||
    content.linkedInVideo;
  if (linkedVideo) out.push({ type: 'video' });

  const article =
    content['com.linkedin.voyager.feed.render.ArticleComponent'] || content.article;
  if (article) {
    out.push({
      type: 'article',
      url: article.navigationContext?.actionTarget,
      title: article.title?.text,
      description: article.subtitle?.text,
    });
  }

  const document =
    content['com.linkedin.voyager.feed.render.DocumentComponent'] || content.document;
  if (document) out.push({ type: 'document', title: document.title });

  const poll = content['com.linkedin.voyager.feed.render.PollComponent'] || content.poll;
  if (poll) out.push({ type: 'poll', title: poll.question?.text });

  const celebration = content['com.linkedin.voyager.feed.render.CelebrationComponent'];
  if (celebration) out.push({ type: 'celebration' });

  if (out.length === 0) {
    const keys = Object.keys(content).filter((k) => k.includes('Component'));
    if (keys.length > 0) out.push({ type: 'other', title: keys.join(', ') });
  }

  return out;
}

function safeNumber(v: unknown): number {
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    const n = parseInt(v, 10);
    return isNaN(n) ? 0 : n;
  }
  return 0;
}

function parseShare(share: any, included: any[]): LinkedInPost | null {
  const urn: string = share.urn || share.entityUrn || share.dashEntityUrn || '';
  if (!urn) return null;

  const text: string = share.commentary?.text?.text ?? share.commentary?.text ?? '';
  const ts: number | undefined =
    share.actor?.subDescription?.accessibilityText?.match(/\d+/)?.[0] ||
    share.createdAt ||
    share.publishedAt ||
    undefined;

  // Find social activity by URN — counts are usually in updateMetadata or socialDetail
  let reactions = 0;
  let comments = 0;
  let reposts = 0;
  const reactionsByType: Record<string, number> = {};

  const social = share.socialDetail ?? share.updateMetadata?.socialDetail;
  if (social) {
    reactions = safeNumber(
      social.totalSocialActivityCounts?.numLikes ??
        social.totalSocialActivityCounts?.numReactions ??
        social.likes?.paging?.total ??
        0,
    );
    comments = safeNumber(
      social.totalSocialActivityCounts?.numComments ??
        social.comments?.paging?.total ??
        0,
    );
    reposts = safeNumber(
      social.totalSocialActivityCounts?.numShares ??
        social.totalShares ??
        0,
    );
    const byType =
      social.totalSocialActivityCounts?.reactionTypeCounts ??
      social.reactionTypeCounts ??
      [];
    for (const r of byType) {
      if (r.reactionType && typeof r.count === 'number') {
        reactionsByType[r.reactionType] = r.count;
      }
    }
  }

  // Fall back: check `included` array for matching social detail
  if (reactions === 0 && comments === 0 && reposts === 0) {
    const detail = included.find(
      (x: any) =>
        x?.$type === 'com.linkedin.voyager.feed.SocialDetail' &&
        (x.urn === urn || x.threadUrn === urn || x.entityUrn?.includes(urn)),
    );
    if (detail) {
      reactions = safeNumber(detail.totalSocialActivityCounts?.numLikes ?? 0);
      comments = safeNumber(detail.totalSocialActivityCounts?.numComments ?? 0);
      reposts = safeNumber(detail.totalSocialActivityCounts?.numShares ?? 0);
    }
  }

  // Permalink
  let permalink: string | undefined = share.permalink ?? undefined;
  if (!permalink) {
    const activityId = urn.match(/activity:(\d+)/)?.[1];
    if (activityId) {
      permalink = `https://www.linkedin.com/feed/update/urn:li:activity:${activityId}/`;
    }
  }

  const isRepost = !!(share.resharedUpdate || share.resharedUpdateUrn || share.reshared);
  const originalAuthor: string | undefined =
    share.resharedUpdate?.actor?.name?.text ??
    share.resharedUpdate?.actor?.name ??
    undefined;

  // Build a "content" union from multiple possible shapes
  const content =
    share.content ??
    share.contentUnion ??
    share.componentsUnion ??
    share.components ??
    null;

  const media = classifyMedia(content);

  return {
    urn,
    permalink,
    postedAt: typeof ts === 'string' ? ts : undefined,
    postedAtTimestamp: typeof ts === 'number' ? ts : undefined,
    text,
    textLength: text.length,
    isRepost,
    originalAuthor,
    media,
    hashtags: extractHashtags(text),
    mentions: extractMentions(text),
    engagement: { reactions, comments, reposts, reactionsByType: Object.keys(reactionsByType).length ? reactionsByType : undefined },
  };
}

// ---------- Main ----------

export async function fetchPosts(options?: {
  count?: number;
  rawPath?: string;
}): Promise<PostsResult> {
  const count = Math.max(1, Math.min(options?.count ?? 50, 100));
  const profileUrn = await getOwnProfileUrn();
  if (!profileUrn) throw new Error('Could not resolve own profile URN');

  const headers = await getAuthHeaders();
  const params = new URLSearchParams({
    profileId: profileUrn,
    q: 'memberShareFeed',
    moduleKey: 'member-shares:phone',
    count: String(count),
    includeLongTermHistory: 'true',
  });

  const url = `${BASE}/identity/profileUpdatesV2?${params}`;
  const res = await fetch(url, { headers });

  if (!res.ok) {
    const body = await res.text().then((t) => t.slice(0, 300));
    throw new Error(`profileUpdatesV2 ${res.status}: ${body}`);
  }

  const json = await res.json();

  if (options?.rawPath) {
    writeFileSync(options.rawPath, JSON.stringify(json, null, 2));
  }

  const elements: any[] = json.elements ?? json.data?.elements ?? [];
  const included: any[] = json.included ?? [];

  const posts: LinkedInPost[] = [];
  for (const el of elements) {
    // Some elements wrap the share in a `value` key
    const share =
      el.value?.['com.linkedin.voyager.feed.render.UpdateV2'] ??
      el.value ??
      el;
    const parsed = parseShare(share, included);
    if (parsed) posts.push(parsed);
  }

  return {
    total: posts.length,
    posts,
    fetchedAt: new Date().toISOString(),
  };
}

// ---------- CLI ----------

async function main() {
  const args = process.argv.slice(2);
  let count = 50;
  let rawPath: string | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--count' && args[i + 1]) count = parseInt(args[++i], 10);
    else if (args[i] === '--raw' && args[i + 1]) rawPath = args[++i];
  }

  try {
    const result = await fetchPosts({ count, rawPath });
    console.log(JSON.stringify(result, null, 2));
  } catch (e) {
    console.error('Error:', e instanceof Error ? e.message : e);
    process.exit(1);
  }
}

if (process.argv[1]?.includes('linkedin/fetch-posts')) main();
