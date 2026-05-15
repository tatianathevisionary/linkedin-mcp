import sqlite3 from 'sqlite3';
import { domainMatch, pathMatch } from 'tough-cookie';
import keytar from 'keytar';
import crypto from 'crypto';
import fs from 'fs';

const KEYLENGTH = 16;
const SALT = 'saltysalt';
const ITERATIONS = 1003; // macOS

interface Cookie {
  host_key: string;
  path: string;
  is_secure: number;
  expires_utc: string;
  name: string;
  value: string;
  encrypted_value: string;
  creation_utc: string;
  is_httponly: number;
  has_expires: number;
}

function decrypt(key: Buffer, encryptedData: Buffer): string {
  const iv = Buffer.from(new Array(KEYLENGTH + 1).join(' '), 'binary');
  const decipher = crypto.createDecipheriv('aes-128-cbc', key, iv);
  decipher.setAutoPadding(false);

  encryptedData = encryptedData.slice(3);

  const decoded = decipher.update(encryptedData);
  const final = decipher.final();
  final.copy(decoded, decoded.length - 1);

  const padding = decoded[decoded.length - 1];
  if (padding) {
    return decoded.slice(32, decoded.length - padding).toString('utf8');
  }
  return decoded.toString('utf8');
}

function getDerivedKey(): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    keytar
      .getPassword('Chrome Safe Storage', 'Chrome')
      .then((pw: string | null) => {
        if (!pw) return reject(new Error('Could not get Chrome password from Keychain'));
        crypto.pbkdf2(pw, SALT, ITERATIONS, KEYLENGTH, 'sha1', (err, key) => {
          if (err) return reject(err);
          resolve(key);
        });
      })
      .catch(reject);
  });
}

function extractDomain(targetUrl: string): string | null {
  try {
    const { hostname } = new URL(targetUrl);
    const parts = hostname.split('.');
    if (parts.length >= 2) {
      return parts.slice(-2).join('.');
    }
    return hostname;
  } catch {
    return null;
  }
}

export async function getCookieHeader(targetUrl: string): Promise<string> {
  const dbPath = process.env.HOME + '/Library/Application Support/Google/Chrome/Default/Cookies';

  if (!fs.existsSync(dbPath)) {
    throw new Error('Chrome cookie DB not found at: ' + dbPath);
  }

  const derivedKey = await getDerivedKey();
  const db = new sqlite3.Database(dbPath);

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(targetUrl);
  } catch {
    db.close();
    throw new Error('Invalid URL: ' + targetUrl);
  }

  const domain = extractDomain(targetUrl);
  if (!domain) {
    db.close();
    throw new Error('Could not parse domain from: ' + targetUrl);
  }

  return new Promise<string>((resolve, reject) => {
    const cookies: Cookie[] = [];
    let hasError = false;

    db.each(
      `SELECT host_key, path, is_secure, expires_utc, name, value, hex(encrypted_value) as encrypted_value, creation_utc, is_httponly, has_expires
       FROM cookies
       WHERE host_key LIKE ?
       ORDER BY LENGTH(path) DESC, creation_utc ASC`,
      [`%${domain}`],
      (err: Error | null, cookie: Cookie) => {
        if (err) {
          hasError = true;
          return true; // stop iteration
        }
        if (cookie.value === '' && cookie.encrypted_value.length > 0) {
          cookie.value = decrypt(derivedKey, Buffer.from(cookie.encrypted_value, 'hex'));
          delete (cookie as any).encrypted_value;
        }
        cookies.push(cookie);
      },
      (err: Error | null) => {
        if (hasError || err) {
          db.close(() => reject(err || new Error('Failed to read cookies')));
          return;
        }
        const host = parsedUrl.hostname;
        const path = parsedUrl.pathname || '/';
        const isSecure = parsedUrl.protocol === 'https:';
        const nowSeconds = Math.floor(Date.now() / 1000);

        const valid = cookies.filter((c) => {
          if (c.is_secure && !isSecure) return false;
          if (!domainMatch(host, c.host_key, true)) return false;
          if (!pathMatch(path, c.path)) return false;
          if (c.has_expires && parseInt(c.expires_utc, 10) < nowSeconds) return false;
          return true;
        });

        const seen: Record<string, boolean> = {};
        const deduped: Cookie[] = [];
        valid.reverse().forEach((c) => {
          if (!seen[c.name]) {
            deduped.push(c);
            seen[c.name] = true;
          }
        });

        const header = deduped
          .reverse()
          .map((c) => `${c.name}=${c.value}`)
          .join('; ');

        db.close(() => resolve(header));
      },
    );
  });
}

export async function authenticatedFetch<T = any>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const cookieHeader = await getCookieHeader(url);

  const res = await fetch(url, {
    ...options,
    method: options?.method || 'GET',
    headers: {
      Cookie: cookieHeader,
      Accept: 'application/json',
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${url}`);
  }

  return res.json() as Promise<T>;
}