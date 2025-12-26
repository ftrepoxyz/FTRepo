# FTRepo

A repository of iOS apps (IPAs) automatically scraped from Telegram channels and hosted for use with Feather/AltStore.

---

## 🚀 Quick Start (For Users)

### Add to Feather/AltStore

1. Open **Feather** or **AltStore** on your iOS device
2. Go to **Sources** (or **Browse** → **Sources** in AltStore)
3. Tap the **+** button to add a new source
4. Choose your preferred format:

   **Standard Format** (for Feather or basic usage):
   ```
   https://ftrepo.xyz/apps.json
   ```

   **Enhanced Format** (for AltStore with unique bundle IDs):
   ```
   https://ftrepo.xyz/altstore.json
   ```

   > 💡 **Tip**: Use `altstore.json` if you want to install multiple tweaked versions of the same app (e.g., Instagram + Instagram (Theta) + Instagram (InstaLRD))

5. Tap **Add** and browse the apps!

---

## 📚 Technical Documentation (For Nerds)

### Features

- Scrapes **configurable number** of .ipa files from specified Telegram channels (default: 5 per channel)
- **Supports forum topics/sub-channels** (automatically detects and scrapes topics containing "IPA" or 👀)
- **Prevents duplicates** by checking existing releases before downloading
- **Keeps only latest version** of each app (automatically removes older versions)
- **AI-powered metadata extraction** (uses OpenRouter API - **REQUIRED**):
  - Intelligently extracts app name, version, tweak name, and bundle ID from descriptions
  - Cleans and formats descriptions automatically
  - 100% AI-based - no fragile regex patterns
  - Automatically detects Twitter/X and uses correct naming ("X" instead of "Twitter")
  - Handles any description format intelligently
- **Stores IPAs in GitHub Releases** (no large files in git repository)
- Runs automatically via GitHub Actions (on-demand or scheduled)
- Generates AltStore-compatible `apps.json`
- **Generates AltStore-compatible `altstore.json`** with unique bundle IDs for tweaked apps
- Extracts app metadata from .ipa files (name, version, bundle ID, etc.)
- **Detailed logging** for easy debugging and monitoring

### Setup

#### 1. Get Telegram API Credentials

1. Go to https://my.telegram.org/apps
2. Log in with your Telegram account
3. Create a new application
4. Copy your `api_id` and `api_hash`

#### 2. Choose Authentication Method

You need one of these authentication methods:

**Option A: Bot Token (Recommended for automation)**
1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Copy the bot token
3. Add your bot to the channels you want to scrape

**Option B: Session String (For user account)**
1. Run this script locally to generate a session string:
```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = YOUR_API_ID
API_HASH = 'YOUR_API_HASH'

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("Session String:", client.session.save())
```
2. Save the session string securely

#### 3. Get OpenRouter API Key (REQUIRED)

The scraper uses AI to intelligently extract **ALL metadata** from Telegram messages. This is **MANDATORY** - the scraper will not run without it.

1. Go to https://openrouter.ai/
2. Sign up for an account
3. Generate an API key
4. Add credits to your account (very cheap - ~$0.05 per 1000 apps)

**What does AI extraction do?**
- Extracts app name, version, tweak name, and bundle ID from Telegram descriptions
- Cleans and formats descriptions (removes excessive emojis, markdown, etc.)
- Maps apps to their official App Store names and bundle IDs
- Automatically handles edge cases (e.g., Twitter → X, various tweak naming patterns)
- No manual regex patterns - AI understands context intelligently

**Why AI is mandatory:**
- Tweaked IPAs often have incorrect bundle IDs (e.g., TikTok LRD shows `org.cocoapods.Illustration` instead of `com.zhiliaoapp.musically`)
- AI automatically maps tweaked apps to their official App Store bundle IDs
- Handles messy Telegram descriptions with inconsistent formatting
- Works for any app, even new ones
- Much more reliable than regex-based extraction (which has been removed)

**Cost:**
- ~$0.05 per 1000 apps (GPT-4o-mini)
- Even cheaper options: Gemini Flash (~$0.01 per 1000 apps)
- Extremely affordable for automated scraping

#### 4. Configure GitHub Secrets and Variables

In your GitHub repository settings, add the following:

**Secrets:**
- `TELEGRAM_API_ID` - Your Telegram API ID (number)
- `TELEGRAM_API_HASH` - Your Telegram API Hash (string)
- `GITH_TOKEN` - Personal access token for GitHub API (needed to create/update releases)
  - Generate at: Settings → Applications → Generate New Token
  - Required permissions: Repository access
- `OPENROUTER_API_KEY` - **[REQUIRED]** OpenRouter API key for AI metadata extraction
  - Get from: https://openrouter.ai/
  - Enables intelligent extraction of app metadata from Telegram messages
  - **The scraper will not run without this key**
- **ONE OF:**
  - `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather (recommended)
  - `TELEGRAM_SESSION_STRING` - Session string from user account

**Variables:**
- `TELEGRAM_CHANNELS` - Comma-separated list of channels (default: `blatants,binnichtaktivipas`)
- `REPO_BASE_URL` - Base URL where your repo is hosted (e.g., `https://yourdomain.com`)
- `MAX_DOWNLOADS_PER_CHANNEL` - Number of IPAs to scrape per channel including already scraped ones (default: `5`)
  - Set to `10` to download 10 apps per channel
  - Set to `3` to download only 3 apps per channel
  - Applies to each channel/topic individually
- `MAX_CONCURRENT_DOWNLOADS` - Number of IPAs to download at the same time
- `OPENROUTER_MODEL` - **[Optional]** AI model to use (default: `openai/gpt-4o-mini`)
  - Default is recommended for cost/performance balance
  - See https://openrouter.ai/models for other options
- `OPENROUTER_FALLBACK_MODEL` - Fallback model when the above one fails or returns null (default: `openai/gpt-4o`)

#### 4. Enable GitHub Actions

Make sure GitHub Actions is enabled for your repository.

#### 5. Deploy Cloudflare Worker

See **[CLOUDFLARE_SETUP.md](CLOUDFLARE_SETUP.md)** for instructions on deploying the worker to serve apps.json at `https://ftrepo.xyz/apps.json`.

### Manual Run

To run the scraper manually:

```bash
pip install -r requirements.txt
export TELEGRAM_API_ID="your_api_id"
export TELEGRAM_API_HASH="your_api_hash"

# Choose ONE authentication method:
export TELEGRAM_BOT_TOKEN="your_bot_token"  # Option A
# OR
export TELEGRAM_SESSION_STRING="your_session_string"  # Option B

# Optional: Enable AI bundle ID extraction
export OPENROUTER_API_KEY="your_openrouter_api_key"  # Highly recommended!

export TELEGRAM_CHANNELS="blatants,binnichtaktivipas"
export REPO_BASE_URL="https://yourdomain.com"
python scraper.py
```

### How It Works

1. **Scraper** (`scraper.py`):
   - Connects to Telegram using Telethon
   - Checks existing IPAs in the "latest" GitHub release
   - **Detects forum channels** and searches for IPA-related topics (e.g., "👀iPA updates")
   - Downloads **configurable number** of new .ipa files per channel (default: 5)
   - Skips files that already exist in the release
   - Extracts app metadata from Info.plist (bundle ID, version, etc.)
   - **Uses AI to determine correct bundle IDs** for tweaked IPAs (if OpenRouter API key is configured)
   - **Keeps only the latest version** of each app (removes older versions)
   - Uploads .ipa files to GitHub "latest" release
   - Updates `apps.json` with download URLs pointing to release assets

2. **Duplicate Prevention**:
   - Fetches list of files in "latest" release before scraping
   - Skips downloading files that already exist in the release
   - Compares versions for same bundle ID
   - Automatically replaces older versions with newer ones

3. **Release Management**:
   - Creates "latest" release if it doesn't exist
   - Uploads IPAs to release using GitHub API
   - Replaces existing files with `--clobber` functionality
   - Download URLs: `{repo_url}/releases/download/latest/{filename}.ipa`

4. **Cloudflare Worker** (`cloudflare-worker.js`):
    - Fetches `apps.json` from GitHub
   - Serves it with correct `Content-Type: application/json` header
   - Adds CORS headers for compatibility
   - Caches responses for 5 minutes

5. **GitHub Actions** (`.github/workflows/scrape.yml`):
   - Runs on workflow_dispatch (manual trigger)
   - Sets up Python environment
   - Runs the scraper
   - Commits and pushes only `apps.json` (IPAs stored in release)

6. **AltStore Repository** (`apps.json`):
   - Contains metadata for all scraped apps
   - Compatible with AltStore source format
   - Only includes latest version of each app
    - Download URLs point to GitHub release assets

7. **AltStore Format Converter** (`convert_to_altstore.py`):
   - Automatically converts `apps.json` to AltStore-compatible `altstore.json`
   - Creates **unique bundle IDs** for apps with tweaks listed in `tweaks_list.json`
   - Example: "Instagram (Theta)" → bundle ID `com.burbn.instagram.theta`
   - Detects tweak names in parentheses and modifies bundle IDs accordingly
   - Runs automatically via workflow whenever `apps.json` or `tweaks_list.json` changes
   - Ensures all tweaked versions of apps can be installed simultaneously
    - See `.github/workflows/scrape.yml` for automation details

8. **AI Metadata Extraction** (Mandatory):
   - **The Problem**:
     - Telegram messages have inconsistent formatting (emojis, markdown, weird spacing)
     - Tweaked IPAs often contain incorrect bundle IDs in their Info.plist
     - Regex patterns are fragile and break with new formats
     - Example: TikTok LRD shows `org.cocoapods.Illustration` instead of `com.zhiliaoapp.musically`
     - Example: Twitter with tweaks shows `grok.Grok.resources` instead of `com.atebits.Tweetie2`

   - **The Solution**: AI intelligently extracts ALL metadata from descriptions
     - Sends full Telegram description + filename to OpenRouter API (GPT-4o-mini)
     - AI extracts: app name, version, tweak name, bundle ID, and cleaned description
     - AI understands context (e.g., knows "Twitter" should be "X" now)
     - Result is cached to avoid duplicate API calls

   - **How It Works**:
     1. Input: Telegram message with description and filename
        ```
        Description: "**Instagram** v404.0.0 | **Theta** v1.2 🔥
        Download the best Instagram mod!
        [Link](https://example.com)"
        Filename: "Instagram_v404.0.0_Theta.ipa"
        ```
     2. AI extracts structured metadata:
        ```json
        {
          "app_name": "Instagram",
          "version": "404.0.0",
          "tweak_name": "Theta",
          "bundle_id": "com.burbn.instagram",
          "description": "Instagram v404.0.0 | Theta v1.2 - Download the best Instagram mod!"
        }
        ```
     3. Use AI-extracted data for apps.json (perfect formatting, correct bundle ID)

   - **Supported Tweaks**: BHX, BHInstagram, BHTikTok, TikTokLRD, Theta, TwiGalaxy, NeoFreeBird, Rocket, Watusi, and many more
   - **Special Handling**:
     - Twitter/X tweaks (BHX, TwiGalaxy, NeoFreeBird) automatically show as "X" not "Twitter"
     - AI cleans excessive emojis, markdown, and formatting
     - Descriptions are formatted consistently
   - **Required**: The scraper will fail if `OPENROUTER_API_KEY` is not configured
   - **Cost**: ~$0.00005 per app, ~$0.05 per 1000 apps (extremely cheap)
   - **Performance**: ~500ms per request, but cached after first lookup
   - **Caching**: Results saved to `ai_bundle_cache.json` for instant reuse

### Directory Structure

```
.
├── .github/
│   └── workflows/
│       ├── scrape.yml             # Main scraping workflow
│       └── reset.yml              # Reset workflow
├── downloads/                     # Temporary downloads (gitignored)
├── scraper.py                     # Main scraper script
├── convert_to_altstore.py         # AltStore format converter
├── clean_duplicates.py            # Duplicate app cleaner
├── cloudflare-worker.js          # CDN proxy worker
├── wrangler.toml                  # Cloudflare worker config
├── apps.json                      # App metadata (committed)
├── altstore.json                  # AltStore-compatible format (committed)
├── tweaks_list.json               # List of known tweaks (committed)
├── appstore_cache.json           # App Store API cache (gitignored)
├── ai_bundle_cache.json          # AI bundle ID cache (gitignored)
├── source_tracking.json          # Telegram source metadata (gitignored)
└── README.md
```

**Note:** IPA files are stored in the "latest" GitHub release, not in the repository itself.

### AltStore Format with Unique Bundle IDs

The repository automatically generates two formats:

1. **`apps.json`** - Standard format for Feather and basic AltStore usage
2. **`altstore.json`** - Enhanced AltStore format with unique bundle IDs for tweaked apps

#### Why Unique Bundle IDs?

AltStore cannot install multiple apps with the same bundle ID. For example:
- Standard Instagram: `com.burbn.instagram`
- Instagram with Theta tweak: `com.burbn.instagram` ❌ **CONFLICT!**

Our converter solves this by creating unique bundle IDs:
- Standard Instagram: `com.burbn.instagram`
- Instagram (Theta): `com.burbn.instagram.theta` ✅ **No conflict!**

#### How It Works

The `convert_to_altstore.py` script:
1. Reads `apps.json` and `tweaks_list.json`
2. Detects apps with tweak names in parentheses (e.g., "Instagram (Theta)")
3. Checks if the tweak is in the known tweaks list
4. Modifies the bundle ID by appending the lowercase tweak name
5. Outputs `altstore.json` with all unique bundle IDs

#### Examples of Bundle ID Modifications

| App Name | Original Bundle ID | New Bundle ID |
|----------|-------------------|---------------|
| Instagram (Theta) | `com.burbn.instagram` | `com.burbn.instagram.theta` |
| Instagram (InstaLRD) | `com.burbn.instagram` | `com.burbn.instagram.instalrd` |
| TikTok (BHTikTok) | `com.zhiliaoapp.musically` | `com.zhiliaoapp.musically.bhtiktok` |
| WhatsApp (Watusi) | `net.whatsapp.WhatsApp` | `net.whatsapp.WhatsApp.watusi` |
| X (NeoFreeBird) | `com.atebits.Tweetie2` | `com.atebits.Tweetie2.neofreebird` |
| YouTube (OLED) | `com.google.ios.youtube` | `com.google.ios.youtube.oled` |

#### Supported Tweaks

The following tweaks are automatically detected and get unique bundle IDs:
- BHInsta, BHTikTok, BHX
- TikTokLRD, VibeTok, RXTikTok
- Theta, InstaLRD, IGFormat
- TWIGalaxy, NeoFreeBird, Rocket
- Watusi, TGExtra
- OLED, Spotilife, EveeSpotify
- YouTopia, Glow, DLEasy, Preview

See `tweaks_list.json` for the complete list.

#### Using altstore.json

To use the enhanced format with unique bundle IDs:

1. Add this URL to AltStore:
   ```
   https://ftrepo.xyz/altstore.json
   ```

2. Now you can install multiple versions of the same app:
   - Regular Instagram + Instagram (Theta) + Instagram (InstaLRD) ✅
   - Regular TikTok + TikTok (BHTikTok) + TikTok (VibeTok) ✅
   - Regular WhatsApp + WhatsApp (Watusi) ✅

#### Workflow Automation

The conversion runs automatically via `.github/workflows/scrape.yml`:
- Triggers when `apps.json` or `tweaks_list.json` changes
- Runs every 6 hours (30 minutes after the scraper)
- Can be triggered manually via workflow dispatch
- Commits and pushes `altstore.json` automatically

To manually run the converter:
```bash
python convert_to_altstore.py
```

### Customization

#### Change Channels

Set the `TELEGRAM_CHANNELS` variable in GitHub repository settings:
```
channel1,channel2,channel3
```

**Note:** The scraper automatically detects forum channels (like @binnichtaktivipas) and searches for topics containing "IPA" or 👀 emoji. For the @binnichtaktivipas channel, it will automatically find and scrape the "👀iPA updates" topic.

#### Adjust Download Limit

Set the `MAX_DOWNLOADS_PER_CHANNEL` variable in GitHub repository settings:
- Default: `5` (downloads 5 new IPAs per channel)
- Example: Set to `10` to download 10 new IPAs per channel
- Example: Set to `3` to download only 3 new IPAs per channel

**Note:** This limit applies to each channel/topic individually. If you have 2 channels and set the limit to 5, you'll get up to 10 new IPAs total (5 per channel).

#### Change Schedule

Currently configured for manual trigger only. To enable automatic scheduling, edit `.github/workflows/scrape.yml`:
```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:        # Keep this for manual trigger
```

#### Customize apps.json

Edit the `update_repo_json()` function in `scraper.py` to customize:
- Repository name and description
- Icon and header URLs
- App metadata fields

### Troubleshooting

#### General Issues
- **EOFError: EOF when reading a line**: You need to set up authentication. Add either `TELEGRAM_BOT_TOKEN` or `TELEGRAM_SESSION_STRING` to your secrets.
- **Authentication Error**: Make sure your Telegram API credentials are correct
- **No IPAs Found**: Check if the channels are public and contain .ipa files. If using a bot, make sure it's added to the channels.
- **[ERROR] Failed to ensure release exists**: You need to add `GITH_TOKEN` secret. Generate a personal access token in GitHub settings.
- **Release not created**: Verify the `GITH_TOKEN` has repository access permissions
- **Action Fails**: Check the GitHub Actions logs for detailed error messages
- **AltStore Not Showing Apps**: Verify the download URLs in `apps.json` are accessible. They should point to `{repo_url}/releases/download/latest/{filename}.ipa`
- **Feather Not Loading Repository**: Make sure the Cloudflare Worker is deployed and `https://ftrepo.xyz/apps.json` returns JSON with `Content-Type: application/json`
- **Files re-downloading**: The scraper checks the "latest" release for existing files. Make sure files are being uploaded successfully.

#### AI Metadata Extraction Issues
- **`ERROR: OPENROUTER_API_KEY is required!`**: The scraper requires an OpenRouter API key to function. Set the `OPENROUTER_API_KEY` secret in your GitHub repository settings. Get your key from https://openrouter.ai/
- **`[AI] Failed to extract metadata with AI`**: Check that your `OPENROUTER_API_KEY` is correct and you have credits in your OpenRouter account.
- **Incorrect metadata in apps.json**:
   - Check the GitHub Actions logs for AI responses. Look for `[AI] Extracted metadata:` lines.
  - The AI should handle most cases, but weird description formats might confuse it.
  - Try increasing the model quality: set `OPENROUTER_MODEL=openai/gpt-4o` (more expensive but more reliable).
- **AI returning wrong data**: The AI model (GPT-4o-mini) is highly accurate. If you need more accuracy, set `OPENROUTER_MODEL=openai/gpt-4o` (more expensive but more reliable).
- **High OpenRouter costs**: The default model (GPT-4o-mini) is very cheap (~$0.05 per 1000 apps). Check your usage at https://openrouter.ai/activity. For even cheaper, try `OPENROUTER_MODEL=google/gemini-flash-1.5` (~$0.01 per 1000 apps).
- **AI cache not working**: The cache is stored in `ai_bundle_cache.json`. Make sure this file is being created and preserved between runs (it's in .gitignore, so it's only cached on the runner).

## License

MIT
