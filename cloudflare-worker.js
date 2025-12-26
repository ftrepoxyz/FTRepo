/**
 * Cloudflare Worker to serve apps.json and altstore.json with correct Content-Type
 *
 * Deploy this to ftrepo.xyz
 *
 * This worker fetches the latest JSON files from GitHub and serves them with
 * Content-Type: application/json (instead of GitHub's text/plain for raw files)
 */

const GITHUB_BASE_URL = 'https://raw.githubusercontent.com/ftrepoxyz/FTRepo/main';
const APPS_JSON_URL = `${GITHUB_BASE_URL}/apps.json`;
const ALTSTORE_JSON_URL = `${GITHUB_BASE_URL}/altstore.json`;

// Cache TTL in seconds (5 minutes)
const CACHE_TTL = 300;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Determine which file to serve
    let githubUrl;
    if (url.pathname === '/apps.json' || url.pathname === '/repo.json') {
      githubUrl = APPS_JSON_URL;
    } else if (url.pathname === '/altstore.json') {
      githubUrl = ALTSTORE_JSON_URL;
    } else {
      return new Response('Not Found', { status: 404 });
    }

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return handleCORS();
    }

    try {
      // Check cache first
      const cache = caches.default;
      let response = await cache.match(request);

      if (!response) {
        // Fetch from GitHub
        console.log(`Cache miss, fetching from GitHub: ${githubUrl}`);
        const githubResponse = await fetch(githubUrl);

        if (!githubResponse.ok) {
          return new Response(`Failed to fetch ${url.pathname} from GitHub`, {
            status: 502,
            headers: {
              'Content-Type': 'text/plain',
            },
          });
        }

        // Get the JSON content
        const jsonContent = await githubResponse.text();

        // Create response with correct headers
        response = new Response(jsonContent, {
          status: 200,
          headers: {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Cache-Control': `public, max-age=${CACHE_TTL}`,
            'X-Content-Source': 'GitHub via Cloudflare Worker',
          },
        });

        // Store in cache
        ctx.waitUntil(cache.put(request, response.clone()));
      } else {
        console.log('Cache hit!');
      }

      return response;
    } catch (error) {
      console.error('Worker error:', error);
      return new Response(`Error: ${error.message}`, {
        status: 500,
        headers: {
          'Content-Type': 'text/plain',
        },
      });
    }
  },
};

function handleCORS() {
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400',
    },
  });
}
