# Cloudflare Worker Setup for ftrepo.xyz

This guide will help you deploy a Cloudflare Worker to serve `repo.json` at `https://ftrepo.xyz/repo.json` with the correct `Content-Type: application/json` header.

## Why?

GitHub serves `.json` files with `Content-Type: text/plain`, which causes Feather to reject the repository. The Cloudflare Worker fixes this by:
1. Fetching `repo.json` from GitHub
2. Serving it with `Content-Type: application/json`
3. Adding CORS headers for compatibility
4. Caching for 5 minutes to reduce load

## Prerequisites

- Cloudflare account (free tier works fine)
- Domain `ftrepo.xyz` added to Cloudflare

## Deployment Steps

### Option 1: Using Cloudflare Dashboard (Easiest)

1. **Go to Cloudflare Dashboard**
   - Navigate to https://dash.cloudflare.com/
   - Select your account

2. **Create Worker**
   - Click **Workers & Pages** in the left sidebar
   - Click **Create application**
   - Click **Create Worker**
   - Name it: `ftrepo-json-proxy`
   - Click **Deploy**

3. **Edit Worker Code**
   - Click **Edit code**
   - Delete the default code
   - Copy and paste the content from `cloudflare-worker.js`
   - Click **Save and Deploy**

4. **Add Route**
   - Go back to the worker overview
   - Click **Triggers** tab
   - Under **Routes**, click **Add route**
   - **Route:** `ftrepo.xyz/repo.json`
   - **Zone:** Select `ftrepo.xyz`
   - Click **Add route**

5. **Test**
   - Visit `https://ftrepo.xyz/repo.json`
   - Verify it returns JSON with correct Content-Type
   - Check headers: `Content-Type: application/json; charset=utf-8`

### Option 2: Using Wrangler CLI (Advanced)

1. **Install Wrangler**
   ```bash
   npm install -g wrangler
   ```

2. **Login to Cloudflare**
   ```bash
   wrangler login
   ```

3. **Create wrangler.toml**
   Create a file `wrangler.toml` in your project:
   ```toml
   name = "ftrepo-json-proxy"
   main = "cloudflare-worker.js"
   compatibility_date = "2024-01-01"

   [[routes]]
   pattern = "ftrepo.xyz/repo.json"
   zone_name = "ftrepo.xyz"
   ```

4. **Deploy**
   ```bash
   wrangler deploy
   ```

## Usage

Once deployed, use this URL in Feather/AltStore:
```
https://ftrepo.xyz/repo.json
```

## Features

✅ **Correct Content-Type**: Serves `application/json` instead of `text/plain`
✅ **CORS Support**: Allows cross-origin requests
✅ **Caching**: 5-minute cache to reduce GitHub load
✅ **Fast**: Cloudflare's global CDN
✅ **Free**: Works on Cloudflare free tier

## Troubleshooting

### Worker not responding
- Check the route is correctly configured: `ftrepo.xyz/repo.json`
- Make sure the worker is deployed and active

### Getting 404
- Verify the route pattern matches exactly: `ftrepo.xyz/repo.json`
- Try accessing with full URL: `https://ftrepo.xyz/repo.json`

### Stale content
- Cache is 5 minutes by default
- Purge cache: Cloudflare Dashboard → Caching → Purge Everything
- Or update `CACHE_TTL` in the worker code

### GitHub fetch fails
- Check `GITHUB_BASE_URL` in worker code is correct
- Verify GitHub is accessible from Cloudflare's network
- Check worker logs: Dashboard → Workers → ftrepo-json-proxy → Logs

## Updating the Worker

To update the worker code:
1. Edit `cloudflare-worker.js`
2. Go to Cloudflare Dashboard → Workers → ftrepo-json-proxy
3. Click **Quick edit**
4. Paste updated code
5. Click **Save and Deploy**

Or with Wrangler:
```bash
wrangler deploy
```

## Cache Invalidation

The worker caches for 5 minutes. To force immediate update:
- **Option 1**: Purge Cloudflare cache (affects entire site)
- **Option 2**: Add `?v=timestamp` to worker requests temporarily
- **Option 3**: Reduce `CACHE_TTL` to `60` (1 minute) during testing
