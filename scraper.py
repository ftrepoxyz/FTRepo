import os
import json
import re
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename
import zipfile
from pathlib import Path
import plistlib
import shutil
import subprocess
from urllib.parse import quote
import urllib.request
import urllib.parse

API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
API_HASH = os.getenv('TELEGRAM_API_HASH', '')
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
PHONE = os.getenv('TELEGRAM_PHONE', '')
SESSION_STRING = os.getenv('TELEGRAM_SESSION_STRING', '')
CHANNELS = os.getenv('TELEGRAM_CHANNELS').split(',')
DOWNLOAD_DIR = 'downloads'
ICONS_DIR = 'icons'
REPO_FILE = 'apps.json'
RELEASE_TAG = 'latest'
GITH_TOKEN = os.getenv('GITH_TOKEN', '')
GITHUB_API_URL = os.getenv('GITHUB_API_URL', 'https://api.github.com')
REPO_OWNER = os.getenv('REPO_OWNER', '')
REPO_NAME = os.getenv('REPO_NAME', '')
MAX_DOWNLOADS_PER_CHANNEL = int(os.getenv('MAX_DOWNLOADS_PER_CHANNEL', '5'))
MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', '3'))

# OpenRouter API for AI-based bundle ID extraction
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')  # Lightweight, fast, accurate
OPENROUTER_FALLBACK_MODEL = os.getenv('OPENROUTER_FALLBACK_MODEL', 'openai/gpt-4o')  # Stronger model for difficult cases

# Performance optimizations
APPSTORE_CACHE_FILE = 'appstore_cache.json'
_appstore_cache = {}

# AI bundle ID cache
AI_BUNDLE_CACHE_FILE = 'ai_bundle_cache.json'
_ai_bundle_cache = {}

# Known tweaks list
TWEAKS_LIST_FILE = 'tweaks_list.json'
_known_tweaks = []

def load_appstore_cache():
    """Load App Store lookup cache from disk"""
    global _appstore_cache
    if os.path.exists(APPSTORE_CACHE_FILE):
        try:
            with open(APPSTORE_CACHE_FILE, 'r', encoding='utf-8') as f:
                _appstore_cache = json.load(f)
            print(f"[CACHE] Loaded {len(_appstore_cache)} cached App Store lookups")
        except Exception as e:
            print(f"[CACHE] Failed to load cache: {e}")
            _appstore_cache = {}

def save_appstore_cache():
    """Save App Store lookup cache to disk"""
    try:
        with open(APPSTORE_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_appstore_cache, f, indent=2)
        print(f"[CACHE] Saved {len(_appstore_cache)} App Store lookups to cache")
    except Exception as e:
        print(f"[CACHE] Failed to save cache: {e}")

def load_ai_bundle_cache():
    """Load AI bundle ID cache from disk"""
    global _ai_bundle_cache
    if os.path.exists(AI_BUNDLE_CACHE_FILE):
        try:
            with open(AI_BUNDLE_CACHE_FILE, 'r', encoding='utf-8') as f:
                _ai_bundle_cache = json.load(f)
            print(f"[AI CACHE] Loaded {len(_ai_bundle_cache)} cached AI bundle ID lookups")
        except Exception as e:
            print(f"[AI CACHE] Failed to load cache: {e}")
            _ai_bundle_cache = {}

def save_ai_bundle_cache():
    """Save AI bundle ID cache to disk"""
    try:
        with open(AI_BUNDLE_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_ai_bundle_cache, f, indent=2)
        print(f"[AI CACHE] Saved {len(_ai_bundle_cache)} AI bundle ID lookups to cache")
    except Exception as e:
        print(f"[AI CACHE] Failed to save cache: {e}")

def load_known_tweaks():
    """Load the list of known tweaks from tweaks_list.json"""
    global _known_tweaks
    if os.path.exists(TWEAKS_LIST_FILE):
        try:
            with open(TWEAKS_LIST_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _known_tweaks = data.get('tweaks', [])
            print(f"[TWEAKS] Loaded {len(_known_tweaks)} known tweaks from {TWEAKS_LIST_FILE}")
        except Exception as e:
            print(f"[TWEAKS] Failed to load tweaks list: {e}")
            _known_tweaks = []
    else:
        print(f"[TWEAKS] {TWEAKS_LIST_FILE} not found, AI will not have tweak context")
        _known_tweaks = []

def search_app_store(app_name, bundle_id):
    """
    Search App Store API and return app info (name, icon, bundle ID)
    Returns tuple: (official_name, icon_url, official_bundle_id) or (None, None, None)
    """
    # Check cache first
    cache_key = f"{bundle_id}:{app_name}"
    if cache_key in _appstore_cache:
        cached = _appstore_cache[cache_key]
        print(f"  [CACHE] Using cached result for {app_name or bundle_id}")
        return cached.get('name'), cached.get('icon'), cached.get('bundle_id')

    try:
        # Strategy 1: Search by bundle ID first (most accurate)
        if bundle_id:
            print(f"  [APPSTORE] Searching by bundle ID: {bundle_id}")
            search_query = urllib.parse.quote(bundle_id)
            itunes_url = f"https://itunes.apple.com/search?term={search_query}&entity=software&limit=5"

            try:
                with urllib.request.urlopen(itunes_url, timeout=3) as response:
                    data = json.loads(response.read().decode())
                    results = data.get('results', [])

                    # Look for exact bundle ID match
                    for result in results:
                        result_bundle = result.get('bundleId', '')
                        if result_bundle == bundle_id:
                            official_name = result.get('trackName', '')
                            icon_url = result.get('artworkUrl512') or result.get('artworkUrl100')
                            official_bundle_id = result.get('bundleId', '')
                            print(f"  [APPSTORE] Found by bundle ID: {official_name} ({official_bundle_id})")
                            # Cache the result
                            _appstore_cache[cache_key] = {'name': official_name, 'icon': icon_url, 'bundle_id': official_bundle_id}
                            return official_name, icon_url, official_bundle_id
            except Exception as e:
                print(f"  [APPSTORE] Bundle ID search failed: {e}")

        # Strategy 2: Search by app name
        clean_name = app_name.strip() if app_name else ""

        # If no app name, try to extract from bundle ID
        if not clean_name and bundle_id:
            parts = bundle_id.split('.')
            if len(parts) >= 2:
                clean_name = parts[-2]  # Usually the app name is second to last
                print(f"  [APPSTORE] Extracted name from bundle ID: {clean_name}")

        if clean_name:
            print(f"  [APPSTORE] Searching by name: {clean_name}")
            search_query = urllib.parse.quote(clean_name)
            itunes_url = f"https://itunes.apple.com/search?term={search_query}&entity=software&limit=5"

            try:
                with urllib.request.urlopen(itunes_url, timeout=3) as response:
                    data = json.loads(response.read().decode())
                    results = data.get('results', [])

                    # Try to find best match by name similarity
                    for result in results:
                        result_name = result.get('trackName', '')
                        # Check if name is very similar
                        if result_name.lower() == clean_name.lower():
                            official_name = result.get('trackName', '')
                            icon_url = result.get('artworkUrl512') or result.get('artworkUrl100')
                            official_bundle_id = result.get('bundleId', '')
                            print(f"  [APPSTORE] Found by exact name match: {official_name} ({official_bundle_id})")
                            # Cache the result
                            _appstore_cache[cache_key] = {'name': official_name, 'icon': icon_url, 'bundle_id': official_bundle_id}
                            return official_name, icon_url, official_bundle_id

                    # If no exact match, use first result if available
                    if results:
                        official_name = results[0].get('trackName', '')
                        icon_url = results[0].get('artworkUrl512') or results[0].get('artworkUrl100')
                        official_bundle_id = results[0].get('bundleId', '')
                        print(f"  [APPSTORE] Using first result: {official_name} ({official_bundle_id})")
                        # Cache the result
                        _appstore_cache[cache_key] = {'name': official_name, 'icon': icon_url, 'bundle_id': official_bundle_id}
                        return official_name, icon_url, official_bundle_id
            except Exception as e:
                print(f"  [APPSTORE] Name search failed: {e}")

    except Exception as e:
        print(f"  [APPSTORE] Search failed: {e}")

    # Cache negative results to avoid repeated failures
    _appstore_cache[cache_key] = {'name': None, 'icon': None, 'bundle_id': None}
    return None, None, None

def get_icon_url_from_name(app_name, bundle_id):
    """
    Get app icon URL from external services based on app name.
    Uses multiple strategies:
    1. Try to search iTunes/App Store API for the app
    2. Fallback to Logo.dev for well-known apps
    3. Fallback to UI-Avatars for unknown apps
    """
    try:
        # Try App Store search first
        official_name, icon_url, _ = search_app_store(app_name, bundle_id)
        if icon_url:
            return icon_url

        # Fallback to searching by name only
        clean_name = app_name.strip() if app_name else ""
        if not clean_name and bundle_id:
            parts = bundle_id.split('.')
            if len(parts) >= 2:
                clean_name = parts[-2]

        if not clean_name:
            print(f"  [ICON] No app name available, using fallback")
            return 'https://github.com/khcrysalis/Feather/blob/v1.x/iOS/Resources/Icons/Main/Mac@3x.png?raw=true'

        # Fallback to Logo.dev for well-known apps
        # Logo.dev provides icons for popular brands/apps
        logo_name = clean_name.lower().replace(' ', '')
        logo_url = f"https://img.logo.dev/{logo_name}.com?token=pk_bkELuwmuQhu5ZVrVl3t-iw"
        print(f"  [ICON] Trying Logo.dev: {logo_url}")

        try:
            # Test if logo.dev has this icon
            req = urllib.request.Request(logo_url, method='HEAD')
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    print(f"  [ICON] Found Logo.dev icon")
                    return logo_url
        except:
            pass

        # Final fallback: UI-Avatars (generates text-based avatar)
        print(f"  [ICON] Using UI-Avatars fallback")
        initials = ''.join([word[0].upper() for word in clean_name.split()[:2] if word])
        ui_avatar_url = f"https://ui-avatars.com/api/?name={urllib.parse.quote(clean_name)}&size=512&background=random&bold=true"
        return ui_avatar_url

    except Exception as e:
        print(f"  [ICON] Error getting icon URL: {e}")
        # Ultimate fallback
        return 'https://github.com/khcrysalis/Feather/blob/v1.x/iOS/Resources/Icons/Main/Mac@3x.png?raw=true'

def _extract_with_model(description_text, filename, model_name, known_tweaks_text):
    """
    Internal function to extract metadata using a specific AI model.

    Args:
        description_text: The full Telegram message text/description
        filename: Optional filename for additional context
        model_name: The OpenRouter model to use
        known_tweaks_text: Pre-formatted known tweaks text for the prompt

    Returns:
        Dictionary with extracted metadata or None on failure
    """
    try:
        # Prepare context for AI
        context = f"Description: {description_text}"
        if filename:
            context += f"\nFilename: {filename}"

        # Construct the API request
        api_url = "https://openrouter.ai/api/v1/chat/completions"

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an iOS app metadata extraction expert. Given a Telegram message description "
                        "(and optionally a filename), extract the following information:\n\n"
                        "1. **app_name**: The official App Store name of the base app (NOT the tweak name)\n"
                        "   - Examples: 'Instagram', 'TikTok', 'X' (not 'Twitter'), 'Snapchat', 'YouTube'\n"
                        "   - Use the CURRENT official name (e.g., 'X' not 'Twitter')\n"
                        "   - Remove suffixes like (Pro), (Plus), (Premium), (Subscription Unlocked), (Patched), Plus, +, etc.\n"
                        "   - ONLY include the base app name, NOT any modification status\n"
                        "   - For bilingual descriptions: prefer the ENGLISH app name if available, otherwise use the primary name\n"
                        "   - CRITICAL: If you cannot confidently determine the app name from the description, return null\n"
                        "2. **version**: The app version number (format: X.X.X or similar)\n"
                        "3. **tweak_name**: The tweak/mod name if present\n"
                        "   - CRITICAL: ONLY use tweak names from the KNOWN LEGITIMATE TWEAKS list below\n"
                        "   - If a tweak-like name appears but is NOT in the approved list, set to null\n"
                        "   - IMPORTANT: Only include actual tweak/mod names, NOT developer/uploader names\n"
                        "   - If the description says 'made by X', 'developed by X', 'uploaded by X', X is a developer, NOT a tweak\n"
                        "   - Examples of what NOT to include: Chocolate Fluffy, Blatants, IAppsBest, or any username/developer name\n"
                        "   - Set to null if no tweak is mentioned or if the tweak is not in the approved list\n"
                        + known_tweaks_text +
                        "\n"
                        "4. **bundle_id**: The official App Store bundle identifier for the BASE app\n"
                        "   - Examples: 'com.burbn.instagram', 'com.zhiliaoapp.musically', 'com.atebits.Tweetie2'\n"
                        "   - IMPORTANT: Tweaks do NOT change the bundle ID. Always use the official app's bundle ID.\n"
                        "5. **description**: The original description with ONLY markdown formatting removed\n"
                        "   - Remove markdown syntax: **bold**, [links](url), etc.\n"
                        "   - Keep ALL original text, emojis, and content exactly as-is\n"
                        "   - Do NOT rewrite, rephrase, or summarize the content\n"
                        "   - Only strip markdown formatting characters\n\n"
                        "Common bundle IDs:\n"
                        "- Instagram → com.burbn.instagram\n"
                        "- TikTok → com.zhiliaoapp.musically\n"
                        "- X (Twitter) → com.atebits.Tweetie2\n"
                        "- Snapchat → com.toyopagroup.picaboo\n"
                        "- YouTube → com.google.ios.youtube\n"
                        "- WhatsApp → net.whatsapp.WhatsApp\n"
                        "- Spotify → com.spotify.client\n"
                        "- Reddit → com.reddit.Reddit\n"
                        "- Facebook → com.facebook.Facebook\n"
                        "- Telegram → ph.telegra.Telegraph\n"
                        "- Swiftgram → app.swiftgram.ios (This is a SEPARATE app, NOT Telegram!)\n\n"
                        "IMPORTANT DISTINCTIONS:\n"
                        "- Swiftgram (app.swiftgram.ios) is its OWN standalone app in the App Store\n"
                        "- Swiftgram is NOT a Telegram tweak or mod\n"
                        "- If bundle ID is app.swiftgram.ios, the app_name should be 'Swiftgram', NOT 'Telegram'\n"
                        "- If bundle ID is ph.telegra.Telegraph, the app_name should be 'Telegram'\n"
                        "- Swiftgram WITH TGExtra tweak → app_name: 'Swiftgram', tweak_name: 'TGExtra'\n"
                        "- Telegram WITH TGExtra tweak → app_name: 'Telegram', tweak_name: 'TGExtra'\n\n"
                        "Respond with ONLY a JSON object (no markdown, no explanation):\n"
                        "{\n"
                        '  "app_name": "AppName",\n'
                        '  "version": "X.X.X",\n'
                        '  "tweak_name": "TweakName" or null,\n'
                        '  "bundle_id": "com.company.app",\n'
                        '  "description": "Cleaned description"\n'
                        "}"
                    )
                },
                {
                    "role": "user",
                    "content": context
                }
            ],
            "temperature": 0,  # Deterministic output
            "max_tokens": 500,  # More tokens for JSON response
            "response_format": {"type": "json_object"}  # Force JSON output
        }

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/FTRepo/FTRepo",
            "X-Title": "FTRepo IPA Scraper"
        }

        # Make the API request
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))

        # Extract the metadata from the response
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content'].strip()

            # Parse JSON response
            metadata = json.loads(content)

            # Validate required fields
            required_fields = ['app_name', 'version', 'bundle_id', 'description']
            if all(field in metadata for field in required_fields):
                # Normalize null values (convert string "null" to None)
                # This handles cases where AI returns "null" as a string instead of JSON null
                for field in ['app_name', 'version', 'bundle_id', 'description', 'tweak_name']:
                    if field in metadata and (metadata[field] == 'null' or metadata[field] is None):
                        metadata[field] = None

                return metadata
            else:
                print(f"  [AI] AI response missing required fields: {metadata}")
                return None
        else:
            print(f"  [AI] Unexpected API response format")
            return None

    except Exception as e:
        print(f"  [AI] Error with model {model_name}: {e}")
        return None


def extract_metadata_with_ai(description_text, filename=None):
    """
    Use OpenRouter AI to extract ALL metadata from Telegram message description and filename.

    This function uses a two-tier approach:
    1. First tries with the primary model (fast and cheap)
    2. If extraction fails or returns insufficient data, retries with a stronger fallback model

    This is the ONLY metadata extraction method - regex extraction has been removed.

    Args:
        description_text: The full Telegram message text/description
        filename: Optional filename for additional context

    Returns:
        Dictionary with extracted metadata:
        {
            'app_name': str|None,   # Official app name (e.g., "Instagram", "TikTok", "X")
            'version': str|None,    # App version (e.g., "404.0.0")
            'tweak_name': str|None, # Tweak name if detected (e.g., "BHX", "Theta", "TikTokLRD")
            'bundle_id': str|None,  # Official App Store bundle ID (e.g., "com.burbn.instagram")
            'description': str      # Cleaned description for display
        }
        Returns None if extraction completely fails
        Raises RuntimeError if no API key is configured
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is required for metadata extraction. "
            "Please set the OPENROUTER_API_KEY environment variable or secret. "
            "Get your API key from https://openrouter.ai/"
        )

    # Create cache key from description + filename
    cache_input = f"{description_text[:100]}|{filename if filename else ''}"
    cache_key = f"metadata:{hash(cache_input)}"

    if cache_key in _ai_bundle_cache:
        cached_result = _ai_bundle_cache[cache_key]
        print(f"  [AI CACHE] Using cached metadata extraction")
        return cached_result

    # Build the known tweaks list for the AI prompt
    known_tweaks_text = ""
    if _known_tweaks:
        known_tweaks_text = (
            f"\n\n**KNOWN LEGITIMATE TWEAKS (use these ONLY):**\n"
            f"The following is the OFFICIAL list of known, legitimate tweak names. "
            f"ONLY use tweak names from this list. If a tweak name appears in the description "
            f"but is NOT in this list, set tweak_name to null.\n\n"
            f"Approved tweaks: {', '.join(_known_tweaks)}\n\n"
            f"If you see any of these exact names in the description or filename, "
            f"extract them as the tweak_name. Otherwise, set tweak_name to null."
        )

    print(f"  [AI] Extracting metadata from description and filename...")

    # Try with primary model first
    metadata = _extract_with_model(description_text, filename, OPENROUTER_MODEL, known_tweaks_text)

    # Check if we need to retry with a stronger model
    # Retry if: extraction failed completely, or critical fields (app_name, bundle_id) are both null
    needs_fallback = False
    if metadata is None:
        needs_fallback = True
        print(f"  [AI] Primary model failed to extract metadata")
    elif metadata.get('app_name') is None and metadata.get('bundle_id') is None:
        needs_fallback = True
        print(f"  [AI] Primary model could not extract app_name or bundle_id")

    # Retry with stronger model if needed and available
    if needs_fallback and OPENROUTER_FALLBACK_MODEL and OPENROUTER_FALLBACK_MODEL != OPENROUTER_MODEL:
        print(f"  [AI FALLBACK] Retrying with stronger model: {OPENROUTER_FALLBACK_MODEL}")
        fallback_metadata = _extract_with_model(description_text, filename, OPENROUTER_FALLBACK_MODEL, known_tweaks_text)

        if fallback_metadata:
            metadata = fallback_metadata
            print(f"  [AI FALLBACK] Successfully extracted with fallback model")
        else:
            print(f"  [AI FALLBACK] Fallback model also failed")

    # Log the final result
    if metadata:
        print(f"  [AI] Extracted metadata:")
        print(f"       App: {metadata.get('app_name', 'None')}")
        print(f"       Version: {metadata.get('version', 'None')}")
        print(f"       Tweak: {metadata.get('tweak_name', 'None')}")
        print(f"       Bundle ID: {metadata.get('bundle_id', 'None')}")

        # Cache the result
        _ai_bundle_cache[cache_key] = metadata

    return metadata


# Deprecated functions removed - AI extraction is now mandatory
# All metadata extraction is done through extract_metadata_with_ai()

def extract_tweak_name(text):
    """
    Extract tweak name from filename or message text.
    Common patterns: BHX, BHInstagram, IGFormat, Rocket, Watusi, TikTokLRD, RXTikTok, Theta, TwiGalaxy, NeoFreeBird, etc.

    Returns the tweak name or None if no tweak detected.
    """
    if not text:
        return None

    # Common tweak prefixes and patterns
    tweak_patterns = [
        r'\b(BHX)\b',                       # BHX (X/Twitter tweak)
        r'\b(BH[A-Z][a-zA-Z]+(?:\+\+)?)',  # BHInstagram, BHTikTok++, etc.
        r'\b(RX[A-Z][a-zA-Z]+)',           # RXTikTok, RXInstagram, etc.
        r'\b(IG[A-Z][a-zA-Z]+)',           # IGFormat, etc.
        r'\b([A-Z][a-zA-Z]+LRD)\b',        # TikTokLRD, SnapchatLRD, etc.
        r'\b(Rocket)\b',                    # Rocket
        r'\b(Watusi)\s*\d*',                # Watusi, Watusi2, etc.
        r'\b(DLEasy)\b',                    # DLEasy
        r'\b(Theta)\b',                     # Theta (Instagram Theta)
        r'\b(TwiGalaxy)\b',                 # TwiGalaxy (Twitter/X tweak)
        r'\b(NeoFreeBird)\b',               # NeoFreeBird (Twitter/X tweak)
        r'\b(No Ads?)\b',                   # NoAds, No Ad
        r'\b(Plus\+?)\b',                   # Plus, Plus+
        r'\b(Pro\+?)\b',                    # Pro, Pro+
        r'\b([A-Z][a-z]+(?:Tweak|Mod|Hack|Plus|Pro))', # CustomTweak, InstaMod, etc.
    ]

    for pattern in tweak_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            tweak = match.group(1).strip()
            # Normalize common variations
            if tweak.lower() in ['plus', 'plus+']:
                return 'Plus'
            elif tweak.lower() in ['pro', 'pro+']:
                return 'Pro'
            return tweak

    return None

# extract_app_info_from_message() removed - use extract_metadata_with_ai() instead

async def extract_ipa_info(ipa_path):
    try:
        print(f"  [INFO] Extracting metadata from: {os.path.basename(ipa_path)}")
        filename = os.path.basename(ipa_path)

        with zipfile.ZipFile(ipa_path, 'r') as zip_ref:
            info_plist_path = None
            for name in zip_ref.namelist():
                # Look for main app Info.plist: Payload/AppName.app/Info.plist
                # Exclude framework/plugin Info.plist files
                if (name.startswith('Payload/') and
                    name.endswith('.app/Info.plist') and
                    '/Frameworks/' not in name and
                    '/PlugIns/' not in name):
                    info_plist_path = name
                    break

            if not info_plist_path:
                print(f"  [WARNING] No Info.plist found in {os.path.basename(ipa_path)}")
                return None

            with zip_ref.open(info_plist_path) as plist_file:
                plist_data = plistlib.load(plist_file)

            # Extract basic info from plist
            name = plist_data.get('CFBundleDisplayName') or plist_data.get('CFBundleName', '')
            version = plist_data.get('CFBundleShortVersionString', '1.0')
            build = plist_data.get('CFBundleVersion', '1')
            min_os = plist_data.get('MinimumOSVersion', '12.0')
            extracted_bundle_id = plist_data.get('CFBundleIdentifier', '')

            # Use the bundle ID from the IPA plist
            bundle_id = extracted_bundle_id
            if bundle_id:
                print(f"  [INFO] Using bundle ID from plist: {bundle_id}")
            else:
                bundle_id = ''
                print(f"  [WARNING] No bundle ID found in plist")

            print(f"  [SUCCESS] Extracted: {name} v{version} (Bundle: {bundle_id})")

            return {
                'bundleIdentifier': bundle_id,
                'name': name,
                'version': version,
                'build': build,
                'minOSVersion': min_os,
                'size': os.path.getsize(ipa_path)
            }
    except Exception as e:
        print(f"  [ERROR] Failed to extract info from {ipa_path}: {e}")
        return None

def get_repo_info():
    """Get repository owner and name from git remote"""
    try:
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'],
            capture_output=True,
            text=True,
            check=True
        )
        remote_url = result.stdout.strip()

        # Parse git@github.com:owner/repo.git or https://github.com/owner/repo.git
        import re
        match = re.search(r'[:/]([^/]+)/([^/]+?)(\.git)?$', remote_url)
        if match:
            owner = match.group(1)
            repo = match.group(2)

            # Extract base URL for API
            if remote_url.startswith('https://'):
                base_url = re.match(r'(https://[^/]+)', remote_url).group(1)
            elif remote_url.startswith('http://'):
                base_url = re.match(r'(http://[^/]+)', remote_url).group(1)
            else:
                # SSH format git@host:owner/repo
                host = remote_url.split('@')[1].split(':')[0]
                base_url = f'https://{host}'

            api_url = f'{base_url}/api/v3'
            return owner, repo, api_url, base_url

        return None, None, None, None
    except Exception as e:
        print(f"[WARNING] Could not parse git remote: {e}")
        return None, None, None, None

def get_release_assets():
    """Get list of assets in the latest release using GitHub API"""
    try:
        owner, repo, api_url, _ = get_repo_info()
        if not owner or not repo or not api_url:
            print(f"[ERROR] Could not determine repository info")
            return set()

        print(f"[RELEASE] Fetching assets from '{RELEASE_TAG}' release...")
        print(f"[INFO] Repository: {owner}/{repo}")
        print(f"[INFO] API URL: {api_url}")

        # GitHub API: GET /repos/{owner}/{repo}/releases/tags/{tag}
        url = f"{api_url}/repos/{owner}/{repo}/releases/tags/{RELEASE_TAG}"
        headers = {}
        if GITH_TOKEN:
            headers['Authorization'] = f'token {GITH_TOKEN}'

        result = subprocess.run(
            ['curl', '-s', '-H', f'Authorization: token {GITH_TOKEN}' if GITH_TOKEN else '', url],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0 or not result.stdout:
            print(f"[RELEASE] Release '{RELEASE_TAG}' not found, will create it")
            return set()

        try:
            data = json.loads(result.stdout)
            if 'message' in data:  # Error response
                print(f"[RELEASE] Release '{RELEASE_TAG}' not found, will create it")
                return set()

            assets = {asset['name'] for asset in data.get('assets', [])}
            ipa_assets = {name for name in assets if name.endswith('.ipa')}
            print(f"[RELEASE] Found {len(ipa_assets)} IPA files in release")
            if ipa_assets:
                print(f"[RELEASE] Existing IPAs: {', '.join(sorted(ipa_assets)[:5])}{'...' if len(ipa_assets) > 5 else ''}")
            return ipa_assets
        except json.JSONDecodeError:
            print(f"[RELEASE] Release '{RELEASE_TAG}' not found, will create it")
            return set()
    except Exception as e:
        print(f"[ERROR] Failed to fetch release assets: {e}")
        return set()

def ensure_release_exists():
    """Ensure the 'latest' release exists using GitHub API"""
    try:
        owner, repo, api_url, _ = get_repo_info()
        if not owner or not repo or not api_url:
            print(f"[ERROR] Could not determine repository info")
            return False

        print(f"[RELEASE] Checking if '{RELEASE_TAG}' release exists...")

        # Check if release exists
        url = f"{api_url}/repos/{owner}/{repo}/releases/tags/{RELEASE_TAG}"
        result = subprocess.run(
            ['curl', '-s', '-H', f'Authorization: token {GITH_TOKEN}' if GITH_TOKEN else '', url],
            capture_output=True,
            text=True,
            check=False
        )

        try:
            data = json.loads(result.stdout)
            if 'id' in data:  # Release exists
                print(f"[RELEASE] Release '{RELEASE_TAG}' already exists")
                return True
        except json.JSONDecodeError:
            pass

        # Create release
        print(f"[RELEASE] Creating '{RELEASE_TAG}' release...")
        create_url = f"{api_url}/repos/{owner}/{repo}/releases"
        payload = {
            "tag_name": RELEASE_TAG,
            "name": "Latest IPAs",
            "body": "Latest scraped IPA files from Telegram channels",
            "draft": False,
            "prerelease": False
        }

        result = subprocess.run(
            ['curl', '-s', '-X', 'POST',
             '-H', 'Content-Type: application/json',
             '-H', f'Authorization: token {GITH_TOKEN}' if GITH_TOKEN else '',
             '-d', json.dumps(payload),
             create_url],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            print(f"[RELEASE] Release '{RELEASE_TAG}' created successfully")
            return True
        else:
            print(f"[ERROR] Failed to create release: {result.stderr}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to ensure release exists: {e}")
        return False

def upload_to_release(file_path, bundle_id=None, tweak_name=None, old_filename=None):
    """Upload a file to the latest release using GitHub API

    Args:
        file_path: Path to the file to upload
        bundle_id: Bundle ID of the app (used to identify old versions)
        tweak_name: Name of the tweak (used to differentiate tweaked versions)
        old_filename: Filename of the old version to delete (if known)
    """
    try:
        owner, repo, api_url, _ = get_repo_info()
        if not owner or not repo or not api_url:
            print(f"[ERROR] Could not determine repository info")
            return False

        filename = os.path.basename(file_path)
        print(f"[UPLOAD] Uploading {filename} to release '{RELEASE_TAG}'...")

        # First, get the release ID
        url = f"{api_url}/repos/{owner}/{repo}/releases/tags/{RELEASE_TAG}"
        result = subprocess.run(
            ['curl', '-s', '-H', f'Authorization: token {GITH_TOKEN}' if GITH_TOKEN else '', url],
            capture_output=True,
            text=True,
            check=False
        )

        data = json.loads(result.stdout)
        release_id = data.get('id')
        if not release_id:
            print(f"[ERROR] Could not get release ID")
            return False

        # Check if asset already exists and delete it
        # This handles two cases:
        # 1. Exact filename match (same version being re-uploaded)
        # 2. Old filename provided (different version being replaced)
        for asset in data.get('assets', []):
            if asset['name'] == filename:
                print(f"[INFO] Deleting existing asset with same filename: {filename}")
                delete_url = f"{api_url}/repos/{owner}/{repo}/releases/{release_id}/assets/{asset['id']}"
                subprocess.run(
                    ['curl', '-s', '-X', 'DELETE',
                     '-H', f'Authorization: token {GITH_TOKEN}' if GITH_TOKEN else '',
                     delete_url],
                    capture_output=True,
                    check=False
                )
            elif old_filename and asset['name'] == old_filename:
                print(f"[INFO] Deleting old version from release: {old_filename}")
                delete_url = f"{api_url}/repos/{owner}/{repo}/releases/{release_id}/assets/{asset['id']}"
                subprocess.run(
                    ['curl', '-s', '-X', 'DELETE',
                     '-H', f'Authorization: token {GITH_TOKEN}' if GITH_TOKEN else '',
                     delete_url],
                    capture_output=True,
                    check=False
                )

        # Upload the file (URL-encode the filename to handle special characters)
        upload_url = f"{api_url}/repos/{owner}/{repo}/releases/{release_id}/assets"
        encoded_filename = quote(filename)
        result = subprocess.run(
            ['curl', '-s', '-X', 'POST',
             '-H', f'Authorization: token {GITH_TOKEN}' if GITH_TOKEN else '',
             '-F', f'attachment=@{file_path}',
             f'{upload_url}?name={encoded_filename}'],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            # Check if the response contains an error message
            try:
                response_data = json.loads(result.stdout)
                if 'message' in response_data and response_data.get('message'):
                    print(f"[ERROR] Failed to upload {filename}: {response_data.get('message')}")
                    return False
            except json.JSONDecodeError:
                pass  # Not JSON, likely success

            print(f"[UPLOAD] Successfully uploaded {filename}")
            return True
        else:
            print(f"[ERROR] Failed to upload {filename}: {result.stderr if result.stderr else result.stdout}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to upload {filename}: {e}")
        return False

async def download_progress_callback(current, total, filename):
    """Callback to show download progress - disabled to reduce log spam"""
    # Don't print progress updates during download
    pass

async def download_single_file(client, message, download_path, filename):
    """Download a single file with error handling"""
    try:
        await client.download_media(
            message,
            download_path,
            progress_callback=lambda c, t: download_progress_callback(c, t, filename)
        )
        file_size_mb = os.path.getsize(download_path) / (1024 * 1024)
        print(f"  [SUCCESS] Download complete: {filename} ({file_size_mb:.2f}MB)")
        return True
    except Exception as e:
        print(f"  [ERROR] Download failed for {filename}: {e}")
        # Clean up partial download
        if os.path.exists(download_path):
            os.remove(download_path)
        return False

async def scrape_channel_or_topic(client, entity, downloaded_files, name, release_assets, source_metadata=None, existing_apps_dict=None):
    print(f"\n[CHANNEL] Starting scrape: {name}")
    print(f"[INFO] Searching for last {MAX_DOWNLOADS_PER_CHANNEL} IPAs total (limit: 200 messages)")
    print(f"[PERF] Parallel downloads: {MAX_CONCURRENT_DOWNLOADS} concurrent")
    if source_metadata is None:
        source_metadata = {}
    if existing_apps_dict is None:
        existing_apps_dict = {}
    try:
        ipa_count = 0
        new_downloads = 0
        messages_scanned = 0
        download_queue = []  # Queue of (message, filename, message_text) tuples to download

        # First pass: scan messages and collect files to download
        async for message in client.iter_messages(entity, limit=200):
            messages_scanned += 1
            if messages_scanned % 50 == 0:
                print(f"[PROGRESS] Scanned {messages_scanned} messages, found {ipa_count} IPAs...")

            if message.document:
                filename = None
                for attr in message.document.attributes:
                    if isinstance(attr, DocumentAttributeFilename):
                        filename = attr.file_name
                        break

                if filename and filename.endswith('.ipa'):
                    ipa_count += 1
                    file_size_mb = message.document.size / (1024 * 1024)
                    print(f"\n[FOUND] IPA #{ipa_count}: {filename} ({file_size_mb:.2f}MB)")

                    # Check if we've processed enough IPAs
                    if ipa_count > MAX_DOWNLOADS_PER_CHANNEL:
                        print(f"[INFO] Reached maximum of {MAX_DOWNLOADS_PER_CHANNEL} IPAs total, stopping scan")
                        break

                    # Capture message text/caption
                    message_text = message.text or message.message or ""
                    if message_text:
                        message_text = message_text.strip()

                    # Check if file is already in the release
                    if filename in release_assets:
                        print(f"  [SKIP] Already exists in '{RELEASE_TAG}' release")
                        continue

                    # *** NEW: Check version against existing apps.json ***
                    # Extract version and bundle ID from message/filename before downloading
                    if existing_apps_dict:
                        # Use AI extraction (mandatory)
                        if message_text:
                            ai_meta = extract_metadata_with_ai(message_text, filename)
                            app_name_msg = ai_meta['app_name']
                            version_msg = ai_meta['version']
                            tweak_msg = ai_meta['tweak_name']
                            bundle_id_from_file = ai_meta['bundle_id']
                        else:
                            # No message text, skip version check
                            app_name_msg = None
                            version_msg = None
                            tweak_msg = None
                            bundle_id_from_file = None

                        # Extract tweak from filename if AI didn't find one
                        tweak_from_file = extract_tweak_name(filename) if not tweak_msg else None
                        tweak = tweak_msg or tweak_from_file

                        # Try to determine version
                        # Parse filename for version if not in message
                        version_from_file = None
                        fname_no_ext = filename.replace('.ipa', '')
                        # Try various version patterns
                        version_patterns = [
                            r'\sv(\d+[\d\._]+)',  # " v1.2.3"
                            r'_v(\d+[\d_]+)',      # "_v1_2_3"
                            r'\s(\d+\.\d+\.\d+)'   # " 1.2.3"
                        ]
                        for pattern in version_patterns:
                            match = re.search(pattern, fname_no_ext, re.IGNORECASE)
                            if match:
                                version_from_file = match.group(1).replace('_', '.')
                                break

                        # Determine version to check
                        version_to_check = version_msg or version_from_file

                        if bundle_id_from_file and version_to_check:
                            # Create unique key (with tweak if present)
                            if tweak:
                                check_key = f"{bundle_id_from_file}:{tweak}"
                            else:
                                check_key = bundle_id_from_file

                            # Check if this app exists in apps.json
                            if check_key in existing_apps_dict:
                                existing_version = existing_apps_dict[check_key]
                                print(f"  [VERSION CHECK] Found in apps.json: {check_key} v{existing_version}")
                                print(f"  [VERSION CHECK] Telegram version: v{version_to_check}")

                                # Compare versions
                                if not compare_versions(version_to_check, existing_version):
                                    # Telegram version is NOT newer (either older or equal)
                                    print(f"  [SKIP] Telegram version v{version_to_check} is not newer than existing v{existing_version}")
                                    continue
                                else:
                                    print(f"  [NEWER] Telegram version v{version_to_check} is newer than existing v{existing_version}, downloading...")
                            else:
                                print(f"  [NEW] App not found in apps.json ({check_key}), will download")
                        else:
                            if not bundle_id_from_file:
                                print(f"  [WARNING] Could not extract bundle ID from filename, skipping version check")
                            if not version_to_check:
                                print(f"  [WARNING] Could not extract version from message/filename, skipping version check")

                    download_path = os.path.join(DOWNLOAD_DIR, filename)

                    if not os.path.exists(download_path):
                        # Add to download queue with message timestamp
                        message_timestamp = message.date.timestamp() if message.date else 0
                        download_queue.append((message, filename, message_text, message_timestamp))
                        print(f"  [QUEUED] Added to download queue")
                    else:
                        print(f"  [INFO] Already in downloads folder, will be processed")
                        message_timestamp = message.date.timestamp() if message.date else 0
                        downloaded_files.append({
                            'filename': filename,
                            'source': source_metadata.get('channel', name),
                            'message': message_text,
                            'timestamp': message_timestamp
                        })
                        new_downloads += 1

        # Second pass: download files in parallel batches
        if download_queue:
            print(f"\n[DOWNLOAD] Starting parallel download of {len(download_queue)} files...")
            print(f"[PERF] Processing in batches of {MAX_CONCURRENT_DOWNLOADS}")

            for i in range(0, len(download_queue), MAX_CONCURRENT_DOWNLOADS):
                batch = download_queue[i:i + MAX_CONCURRENT_DOWNLOADS]
                batch_num = i // MAX_CONCURRENT_DOWNLOADS + 1
                total_batches = (len(download_queue) - 1) // MAX_CONCURRENT_DOWNLOADS + 1

                print(f"\n[BATCH {batch_num}/{total_batches}] Downloading {len(batch)} files in parallel...")

                # Create download tasks for this batch
                tasks = []
                for message, filename, message_text, message_timestamp in batch:
                    download_path = os.path.join(DOWNLOAD_DIR, filename)
                    print(f"  [START] {filename}")
                    task = download_single_file(client, message, download_path, filename)
                    tasks.append((task, filename, message_text, message_timestamp))

                # Wait for all downloads in this batch to complete
                results = await asyncio.gather(*[task for task, _, _, _ in tasks], return_exceptions=True)

                # Process results
                for (_, filename, message_text, message_timestamp), result in zip(tasks, results):
                    if result is True:
                        downloaded_files.append({
                            'filename': filename,
                            'source': source_metadata.get('channel', name),
                            'message': message_text,
                            'timestamp': message_timestamp
                        })
                        new_downloads += 1
                    elif isinstance(result, Exception):
                        print(f"  [ERROR] Exception downloading {filename}: {result}")

                print(f"[BATCH {batch_num}/{total_batches}] Completed - {new_downloads}/{len(download_queue)} successful")

        print(f"\n[CHANNEL] Completed: {name}")
        print(f"[SUMMARY] Scanned {messages_scanned} messages, found {ipa_count} IPAs, downloaded {new_downloads} new files")
    except Exception as e:
        print(f"[ERROR] Failed to scrape {name}: {e}")

async def get_forum_topics_safe(client, entity):
    try:
        from telethon.tl.functions.channels import GetForumTopicsRequest
        result = await client(GetForumTopicsRequest(channel=entity, offset_date=0, offset_id=0, offset_topic=0, limit=100))
        return result.topics if hasattr(result, 'topics') else []
    except Exception as e:
        print(f"  Error getting forum topics: {e}")
        return []

async def download_ipas():
    print("=" * 60)
    print("TELEGRAM IPA SCRAPER - STARTING")
    print("=" * 60)

    # Load existing apps.json to check versions before downloading
    existing_apps_dict = {}  # Maps "bundle_id" or "bundle_id:tweak" to version
    print(f"\n[SETUP] Loading existing {REPO_FILE} to check versions...")
    if os.path.exists(REPO_FILE):
        try:
            with open(REPO_FILE, 'r', encoding='utf-8') as f:
                repo_data = json.load(f)
                existing_apps = repo_data.get('apps', [])
                print(f"[SETUP] Found {len(existing_apps)} existing apps in {REPO_FILE}")

                for app in existing_apps:
                    bundle_id = app.get('bundleIdentifier', '')
                    version = app.get('version', '')
                    app_name = app.get('name', '')

                    # Detect tweak from app name (e.g., "Instagram (BHInstagram)")
                    tweak = None
                    tweak_match = re.search(r'\(([^)]+)\)$', app_name)
                    if tweak_match:
                        tweak = tweak_match.group(1)

                    # Create unique key
                    if tweak:
                        key = f"{bundle_id}:{tweak}"
                    else:
                        key = bundle_id

                    existing_apps_dict[key] = version
                    print(f"  [LOADED] {app_name} v{version} ({key})")

                print(f"[SETUP] Loaded {len(existing_apps_dict)} app versions from {REPO_FILE}")
        except Exception as e:
            print(f"[WARNING] Failed to load {REPO_FILE}: {e}")
    else:
        print(f"[SETUP] No existing {REPO_FILE} found")

    client = TelegramClient('session', API_ID, API_HASH)

    # Authenticate using bot token, phone, or session string
    if BOT_TOKEN:
        print("\n[AUTH] Authenticating with bot token...")
        await client.start(bot_token=BOT_TOKEN)
        print("[AUTH] Successfully authenticated with bot token")
    elif PHONE:
        print(f"\n[AUTH] Authenticating with phone number: {PHONE}")
        await client.start(phone=PHONE)
        print("[AUTH] Successfully authenticated with phone number")
    elif SESSION_STRING:
        print("\n[AUTH] Authenticating with session string...")
        # Session strings require StringSession
        from telethon.sessions import StringSession
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.start()
        print("[AUTH] Successfully authenticated with session string")
    else:
        raise ValueError(
            "No authentication method provided. Please set one of:\n"
            "  - TELEGRAM_BOT_TOKEN (for bot authentication)\n"
            "  - TELEGRAM_PHONE (for user authentication, requires interactive session)\n"
            "  - TELEGRAM_SESSION_STRING (for user authentication with saved session)"
        )

    print(f"\n[SETUP] Creating directories...")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"[SETUP] Download directory: {DOWNLOAD_DIR}")

    print(f"\n[SETUP] Checking existing IPAs in '{RELEASE_TAG}' release...")
    release_assets = get_release_assets()
    print(f"[SETUP] Found {len(release_assets)} existing IPAs in release")
    downloaded_files = []

    # Load existing source tracking
    source_tracking_file = 'source_tracking.json'
    source_tracking = {}
    if os.path.exists(source_tracking_file):
        try:
            with open(source_tracking_file, 'r', encoding='utf-8') as f:
                source_tracking = json.load(f)
            print(f"[SETUP] Loaded source tracking for {len(source_tracking)} files")
        except:
            pass

    print(f"\n[SETUP] Channels to process: {', '.join(CHANNELS)}")
    print("=" * 60)

    for channel_idx, channel in enumerate(CHANNELS, 1):
        channel = channel.strip()
        print(f"\n{'=' * 60}")
        print(f"PROCESSING CHANNEL {channel_idx}/{len(CHANNELS)}: {channel}")
        print("=" * 60)

        try:
            print(f"[INFO] Fetching channel entity...")
            entity = await client.get_entity(channel)
            print(f"[INFO] Channel entity retrieved successfully")

            if hasattr(entity, 'forum') and entity.forum:
                print(f"[FORUM] Channel is a forum, searching for IPA topics...")
                topics = await get_forum_topics_safe(client, entity)
                print(f"[FORUM] Found {len(topics)} topics total")

                ipa_topics = []
                for topic in topics:
                    topic_title = topic.title.lower() if hasattr(topic, 'title') else ''
                    topic_title_original = topic.title if hasattr(topic, 'title') else ''
                    if 'ipa' in topic_title or '👀' in topic_title_original or '📁' in topic_title_original:
                        ipa_topics.append(topic)
                        print(f"[TOPIC] Found IPA topic: {topic.title}")

                print(f"[FORUM] Processing {len(ipa_topics)} IPA topics...")

                for topic_idx, topic in enumerate(ipa_topics, 1):
                    print(f"\n[TOPIC {topic_idx}/{len(ipa_topics)}] {topic.title}")
                    # Use the parallel download function for topics too
                    topic_entity = await client.get_entity(entity.id)
                    # Create a custom iterator for topic messages
                    async def topic_scraper():
                        ipa_count = 0
                        new_downloads = 0
                        messages_scanned = 0
                        download_queue = []

                        print(f"[INFO] Searching for last {MAX_DOWNLOADS_PER_CHANNEL} IPAs total in topic...")
                        print(f"[PERF] Parallel downloads: {MAX_CONCURRENT_DOWNLOADS} concurrent")

                        async for message in client.iter_messages(entity, reply_to=topic.id, limit=200):
                            messages_scanned += 1
                            if messages_scanned % 50 == 0:
                                print(f"[PROGRESS] Scanned {messages_scanned} messages in topic, found {ipa_count} IPAs...")

                            if message.document:
                                filename = None
                                for attr in message.document.attributes:
                                    if isinstance(attr, DocumentAttributeFilename):
                                        filename = attr.file_name
                                        break

                                if filename and filename.endswith('.ipa'):
                                    ipa_count += 1
                                    file_size_mb = message.document.size / (1024 * 1024)
                                    print(f"\n[FOUND] IPA #{ipa_count}: {filename} ({file_size_mb:.2f}MB)")

                                    if ipa_count > MAX_DOWNLOADS_PER_CHANNEL:
                                        print(f"[INFO] Reached maximum of {MAX_DOWNLOADS_PER_CHANNEL} IPAs total for this topic")
                                        break

                                    message_text = message.text or message.message or ""
                                    if message_text:
                                        message_text = message_text.strip()

                                    if filename in release_assets:
                                        print(f"  [SKIP] Already exists in '{RELEASE_TAG}' release")
                                        continue

                                    # *** NEW: Check version against existing apps.json ***
                                    # Extract version and bundle ID from message/filename before downloading
                                    if existing_apps_dict:
                                        # Use AI extraction (mandatory)
                                        if message_text:
                                            ai_meta = extract_metadata_with_ai(message_text, filename)
                                            app_name_msg = ai_meta['app_name']
                                            version_msg = ai_meta['version']
                                            tweak_msg = ai_meta['tweak_name']
                                            bundle_id_from_file = ai_meta['bundle_id']
                                        else:
                                            # No message text, skip version check
                                            app_name_msg = None
                                            version_msg = None
                                            tweak_msg = None
                                            bundle_id_from_file = None

                                        # Extract tweak from filename if AI didn't find one
                                        tweak_from_file = extract_tweak_name(filename) if not tweak_msg else None
                                        tweak = tweak_msg or tweak_from_file

                                        # Try to determine version
                                        # Parse filename for version if not in message
                                        version_from_file = None
                                        fname_no_ext = filename.replace('.ipa', '')
                                        # Try various version patterns
                                        version_patterns = [
                                            r'\sv(\d+[\d\._]+)',  # " v1.2.3"
                                            r'_v(\d+[\d_]+)',      # "_v1_2_3"
                                            r'\s(\d+\.\d+\.\d+)'   # " 1.2.3"
                                        ]
                                        for pattern in version_patterns:
                                            match = re.search(pattern, fname_no_ext, re.IGNORECASE)
                                            if match:
                                                version_from_file = match.group(1).replace('_', '.')
                                                break

                                        # Determine version to check
                                        version_to_check = version_msg or version_from_file

                                        if bundle_id_from_file and version_to_check:
                                            # Create unique key (with tweak if present)
                                            if tweak:
                                                check_key = f"{bundle_id_from_file}:{tweak}"
                                            else:
                                                check_key = bundle_id_from_file

                                            # Check if this app exists in apps.json
                                            if check_key in existing_apps_dict:
                                                existing_version = existing_apps_dict[check_key]
                                                print(f"  [VERSION CHECK] Found in apps.json: {check_key} v{existing_version}")
                                                print(f"  [VERSION CHECK] Telegram version: v{version_to_check}")

                                                # Compare versions
                                                if not compare_versions(version_to_check, existing_version):
                                                    # Telegram version is NOT newer (either older or equal)
                                                    print(f"  [SKIP] Telegram version v{version_to_check} is not newer than existing v{existing_version}")
                                                    continue
                                                else:
                                                    print(f"  [NEWER] Telegram version v{version_to_check} is newer than existing v{existing_version}, downloading...")
                                            else:
                                                print(f"  [NEW] App not found in apps.json ({check_key}), will download")
                                        else:
                                            if not bundle_id_from_file:
                                                print(f"  [WARNING] Could not extract bundle ID from filename, skipping version check")
                                            if not version_to_check:
                                                print(f"  [WARNING] Could not extract version from message/filename, skipping version check")

                                    download_path = os.path.join(DOWNLOAD_DIR, filename)

                                    if not os.path.exists(download_path):
                                        message_timestamp = message.date.timestamp() if message.date else 0
                                        download_queue.append((message, filename, message_text, message_timestamp))
                                        print(f"  [QUEUED] Added to download queue")
                                    else:
                                        print(f"  [INFO] Already in downloads folder, will be processed")
                                        message_timestamp = message.date.timestamp() if message.date else 0
                                        downloaded_files.append({
                                            'filename': filename,
                                            'source': channel,
                                            'message': message_text,
                                            'timestamp': message_timestamp
                                        })
                                        new_downloads += 1

                        # Download in parallel batches
                        if download_queue:
                            print(f"\n[DOWNLOAD] Starting parallel download of {len(download_queue)} files...")

                            for i in range(0, len(download_queue), MAX_CONCURRENT_DOWNLOADS):
                                batch = download_queue[i:i + MAX_CONCURRENT_DOWNLOADS]
                                batch_num = i // MAX_CONCURRENT_DOWNLOADS + 1
                                total_batches = (len(download_queue) - 1) // MAX_CONCURRENT_DOWNLOADS + 1

                                print(f"\n[BATCH {batch_num}/{total_batches}] Downloading {len(batch)} files in parallel...")

                                tasks = []
                                for message, filename, message_text, message_timestamp in batch:
                                    download_path = os.path.join(DOWNLOAD_DIR, filename)
                                    print(f"  [START] {filename}")
                                    task = download_single_file(client, message, download_path, filename)
                                    tasks.append((task, filename, message_text, message_timestamp))

                                results = await asyncio.gather(*[task for task, _, _, _ in tasks], return_exceptions=True)

                                for (_, filename, message_text, message_timestamp), result in zip(tasks, results):
                                    if result is True:
                                        downloaded_files.append({
                                            'filename': filename,
                                            'source': channel,
                                            'message': message_text,
                                            'timestamp': message_timestamp
                                        })
                                        new_downloads += 1
                                    elif isinstance(result, Exception):
                                        print(f"  [ERROR] Exception downloading {filename}: {result}")

                                print(f"[BATCH {batch_num}/{total_batches}] Completed - {new_downloads}/{len(download_queue)} successful")

                        print(f"[TOPIC] Completed: {topic.title} - Scanned {messages_scanned} messages, found {ipa_count} IPAs, downloaded {new_downloads} new files")

                    await topic_scraper()
            else:
                print(f"[INFO] Channel is a regular channel (not a forum)")
                await scrape_channel_or_topic(client, entity, downloaded_files, channel, release_assets, {'channel': channel}, existing_apps_dict)
        except Exception as e:
            print(f"[ERROR] Failed to process {channel}: {e}")
            print(f"[INFO] Attempting fallback method...")
            try:
                await scrape_channel_or_topic(client, channel, downloaded_files, channel, release_assets, {'channel': channel}, existing_apps_dict)
            except Exception as inner_e:
                print(f"[ERROR] Fallback also failed for {channel}: {inner_e}")

    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)
    print(f"[SUMMARY] Total new files downloaded: {len(downloaded_files)}")
    if downloaded_files:
        print(f"[SUMMARY] Downloaded files:")
        for idx, file_info in enumerate(downloaded_files, 1):
            if isinstance(file_info, dict):
                print(f"  {idx}. {file_info['filename']} (from @{file_info['source']})")
                # Update source tracking with source, message, and timestamp
                source_tracking[file_info['filename']] = {
                    'source': file_info['source'],
                    'message': file_info.get('message', ''),
                    'timestamp': file_info.get('timestamp', 0)
                }
            else:
                print(f"  {idx}. {file_info}")

    # Save source tracking
    with open(source_tracking_file, 'w', encoding='utf-8') as f:
        json.dump(source_tracking, f, indent=2, ensure_ascii=False)
    print(f"[SETUP] Saved source tracking for {len(source_tracking)} files")

    print(f"\n[DISCONNECT] Disconnecting from Telegram...")
    await client.disconnect()
    print(f"[DISCONNECT] Disconnected successfully")

    return downloaded_files, source_tracking

def compare_versions(v1, v2, timestamp1=None, timestamp2=None):
    """
    Compare two versions and return True if v1 is newer than v2.

    Args:
        v1: Version string 1
        v2: Version string 2
        timestamp1: Optional timestamp for v1 (used as tiebreaker)
        timestamp2: Optional timestamp for v2 (used as tiebreaker)

    Returns:
        True if v1 is newer than v2, False otherwise
    """
    try:
        v1_parts = [int(x) for x in re.split(r'[.-]', v1.split()[0]) if x.isdigit()]
        v2_parts = [int(x) for x in re.split(r'[.-]', v2.split()[0]) if x.isdigit()]

        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        # If versions are equal and we have timestamps, use the more recent one
        if v1_parts == v2_parts:
            if timestamp1 is not None and timestamp2 is not None:
                # More recent timestamp = newer
                return timestamp1 > timestamp2
            return False  # Versions are equal, no preference

        return v1_parts > v2_parts
    except:
        # Fallback: string comparison, with timestamp tiebreaker
        if str(v1) == str(v2):
            if timestamp1 is not None and timestamp2 is not None:
                return timestamp1 > timestamp2
            return False
        return str(v1) > str(v2)

async def update_repo_json(source_tracking=None):
    print("\n" + "=" * 60)
    print("UPDATING REPOSITORY JSON AND UPLOADING TO RELEASE")
    print("=" * 60)

    if source_tracking is None:
        source_tracking = {}
        # Try to load from file
        if os.path.exists('source_tracking.json'):
            try:
                with open('source_tracking.json', 'r', encoding='utf-8') as f:
                    source_tracking = json.load(f)
            except:
                pass

    # Load App Store cache for performance
    load_appstore_cache()

    # Load AI bundle ID cache
    load_ai_bundle_cache()

    # Load known tweaks list for AI context (if not already loaded)
    if not _known_tweaks:
        load_known_tweaks()

    # Ensure the release exists
    if not ensure_release_exists():
        print(f"[ERROR] Failed to ensure release exists, aborting upload")
        return

    apps_by_bundle = {}

    print(f"\n[SCAN] Scanning downloaded IPAs...")
    ipa_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.ipa')]
    print(f"[SCAN] Found {len(ipa_files)} IPA files to process")

    for idx, filename in enumerate(ipa_files, 1):
        print(f"\n[PROCESSING {idx}/{len(ipa_files)}] {filename}")
        ipa_path = os.path.join(DOWNLOAD_DIR, filename)

        info = await extract_ipa_info(ipa_path)

        # Try to get message text and timestamp from source tracking
        source_data = source_tracking.get(filename, {})
        if isinstance(source_data, dict):
            message_text = source_data.get('message', '')
            message_timestamp = source_data.get('timestamp', 0)
        else:
            message_text = ''
            message_timestamp = 0

        # Extract metadata using AI (mandatory)
        if message_text:
            ai_metadata = extract_metadata_with_ai(message_text, filename)
            if ai_metadata:
                # Extract values and normalize "null" strings to None
                app_name_from_message = ai_metadata.get('app_name')
                version_from_message = ai_metadata.get('version')
                tweak_from_message = ai_metadata.get('tweak_name')
                ai_bundle_id = ai_metadata.get('bundle_id')
                ai_description = ai_metadata.get('description')

                # Additional safeguard: treat string "null" as None
                if app_name_from_message == 'null':
                    app_name_from_message = None
                if version_from_message == 'null':
                    version_from_message = None
                if ai_bundle_id == 'null':
                    ai_bundle_id = None
                if ai_description == 'null':
                    ai_description = None

                print(f"  [AI] Extracted metadata successfully")
            else:
                # AI extraction failed
                print(f"  [AI] AI extraction returned no metadata")
                app_name_from_message = None
                version_from_message = None
                tweak_from_message = None
                ai_bundle_id = None
                ai_description = None

            # IMPORTANT: Post-process to fix common AI misidentifications
            # Swiftgram is a standalone app, NOT Telegram
            if ai_bundle_id == 'app.swiftgram.ios' and app_name_from_message != 'Swiftgram':
                print(f"  [CORRECTION] Bundle ID is app.swiftgram.ios - correcting app name from '{app_name_from_message}' to 'Swiftgram'")
                app_name_from_message = 'Swiftgram'
            elif ai_bundle_id == 'ph.telegra.Telegraph' and app_name_from_message != 'Telegram':
                print(f"  [CORRECTION] Bundle ID is ph.telegra.Telegraph - correcting app name from '{app_name_from_message}' to 'Telegram'")
                app_name_from_message = 'Telegram'
        else:
            # No message text available, will rely on IPA metadata
            print(f"  [WARNING] No message text available for AI extraction")
            app_name_from_message = None
            version_from_message = None
            tweak_from_message = None
            ai_bundle_id = None
            ai_description = None

        # Don't use fallback tweak detection from filename - AI is more accurate
        # The extract_tweak_name function is too aggressive and matches things like "Pro" which aren't tweaks
        tweak_from_filename = None

        # Parse filename for app name and version
        def parse_filename(fname):
            """Extract app name and version from filename"""
            fname_no_ext = fname.replace('.ipa', '')

            # Try to extract version
            # Patterns: "v1.2.3", "v1_2_3", "15.0.16" (without v)
            version_match = None

            # Pattern 1: "v1.2.3" or "v1_2_3" with spaces (e.g., "Instagram v402.0.0")
            # Match digits and separators but don't capture trailing separators
            match = re.search(r'\sv(\d+(?:[\d\._]+\d)?)', fname_no_ext, re.IGNORECASE)
            if match:
                version_match = match.group(1).replace('_', '.')

            # Pattern 2: "_v1_2_3" with underscores (e.g., "App_v9_1_10_Pro")
            # Match digits and underscores but don't capture trailing underscores
            if not version_match:
                match = re.search(r'_v(\d+(?:_\d+)*)', fname_no_ext, re.IGNORECASE)
                if match:
                    version_match = match.group(1).replace('_', '.')

            # Pattern 3: Standalone version like "15.0.16" (e.g., "Notability Plus 15.0.16")
            if not version_match:
                match = re.search(r'\s(\d+\.\d+\.\d+)', fname_no_ext)
                if match:
                    version_match = match.group(1)

            # Extract app name (everything before version or common suffixes)
            name_part = fname_no_ext
            # Remove version patterns
            name_part = re.sub(r'_v\d+[\d_\.]+.*$', '', name_part, flags=re.IGNORECASE)
            name_part = re.sub(r'\sv\d+[\d\.]+.*$', '', name_part, flags=re.IGNORECASE)
            name_part = re.sub(r'\s\d+\.\d+\.\d+.*$', '', name_part)  # Remove standalone version
            # Remove common suffixes
            name_part = re.sub(r'_(Pro_|Plus_|Premium_)?(Subscription_)?Unlocked.*$', '', name_part, flags=re.IGNORECASE)
            name_part = re.sub(r'_blatant.*$', '', name_part, flags=re.IGNORECASE)
            name_part = re.sub(r'_Patched.*$', '', name_part, flags=re.IGNORECASE)
            name_part = re.sub(r'\[tg@.*\]$', '', name_part)
            name_part = re.sub(r'\sLRD.*$', '', name_part)  # Remove "LRD v2.18" type suffixes
            name_part = re.sub(r'\s(Pro|Plus|Premium)$', '', name_part, flags=re.IGNORECASE)
            # Replace underscores and ampersands with spaces, clean up
            name_part = name_part.replace('_', ' ').replace('&', '&').strip()
            # Remove multiple spaces
            name_part = re.sub(r'\s+', ' ', name_part)

            return name_part, version_match

        def clean_app_name(name):
            """Clean up app name by removing exact duplicates, markdown, emojis, and modification suffixes"""
            if not name:
                return name

            # Remove markdown formatting and emojis
            name = name.replace('**', '')  # Remove bold markdown
            name = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', name)  # Remove markdown links
            name = re.sub(r'[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF\U00002700-\U000027BF\U0000FE00-\U0000FE0F\u0600-\u06FF]', '', name)  # Remove emojis

            # Remove modification suffixes like (Pro), (Plus), (Premium), (Unlocked), (Patched), etc.
            # Match parentheses at the end with common modification terms
            suffix_pattern = r'\s*\((Pro|Plus|Premium|Unlocked|Patched|Subscription Unlocked|Mod|Modded|Hacked|Cracked|Full)\)\s*$'
            cleaned = re.sub(suffix_pattern, '', name, flags=re.IGNORECASE)
            if cleaned != name:
                print(f"  [CLEANUP] Removed suffix: '{name}' -> '{cleaned}'")
                name = cleaned

            # Handle duplicated names like "AppAuth AppAuth"
            # Only remove if EXACTLY the same word is repeated
            parts = name.split()

            # Check if first part is exactly repeated (e.g., "AppAuth AppAuth")
            if len(parts) >= 2 and parts[0] == parts[1]:
                name = parts[0]
                print(f"  [CLEANUP] Removed exact duplicate: '{parts[0]} {parts[1]}' -> '{name}'")

            return name.strip()

        app_name_from_file, version_from_file = parse_filename(filename)
        print(f"  [FILENAME] Parsed: name='{app_name_from_file}', version='{version_from_file}'")

        # Priority for app name, version, and tweak depends on source channel
        # Get source channel for this file (already loaded above)
        if isinstance(source_data, dict):
            source_channel = source_data.get('source', '')
        else:
            source_channel = ''

        # For @binnichtaktivsipas: prioritize filename version over message version
        # because their filenames contain accurate version numbers
        if 'binnichtaktiv' in source_channel.lower():
            # Priority: filename > message > IPA metadata
            best_version = version_from_file or version_from_message
            if version_from_file:
                print(f"  [PRIORITY] Using version from filename (@binnichtaktivsipas): '{version_from_file}'")
        else:
            # Priority: message > filename > IPA metadata (default for other channels)
            best_version = version_from_message or version_from_file
            if version_from_message:
                print(f"  [PRIORITY] Using version from message: '{version_from_message}'")

        # App name and tweak: always prefer message over filename
        best_name = app_name_from_message or app_name_from_file
        best_tweak = tweak_from_message or tweak_from_filename

        if app_name_from_message:
            print(f"  [PRIORITY] Using app name from message: '{app_name_from_message}'")
        if best_tweak:
            print(f"  [TWEAK] Detected tweak: '{best_tweak}'")

        # If extraction failed or returned empty data, try to parse filename
        if not info or not info.get('name') or not info.get('bundleIdentifier'):
            print(f"  [WARNING] Metadata extraction failed or incomplete, using filename data...")

            # Clean the app name (prefer message name, then filename)
            cleaned_name = clean_app_name(best_name if best_name else app_name_from_file)

            # Priority for bundle ID: AI > filename > App Store search
            temp_bundle_id = None

            # 1. Use AI-extracted bundle ID if available
            if ai_bundle_id:
                temp_bundle_id = ai_bundle_id
                print(f"  [AI] Using AI-extracted bundle ID: {ai_bundle_id}")
            else:
                # 2. Try App Store search as fallback
                print(f"  [APPSTORE] Attempting early App Store lookup for bundle ID...")
                _, _, official_bundle_id = search_app_store(cleaned_name, None)
                if official_bundle_id:
                    temp_bundle_id = official_bundle_id
                    print(f"  [APPSTORE] Found bundle ID from App Store: {official_bundle_id}")
                else:
                    temp_bundle_id = None

            if not info:
                info = {
                    'bundleIdentifier': temp_bundle_id if temp_bundle_id else f'com.unknown.{cleaned_name.lower().replace(" ", "")}',
                    'name': cleaned_name,
                    'version': best_version or '1.0',
                    'build': '1',
                    'minOSVersion': '12.0',
                    'size': os.path.getsize(ipa_path)
                }
                print(f"  [FALLBACK] Using filename-based metadata")
            else:
                # Update missing fields
                if not info.get('name'):
                    info['name'] = cleaned_name
                    print(f"  [FALLBACK] Updated name from filename: {cleaned_name}")
                if not info.get('bundleIdentifier'):
                    info['bundleIdentifier'] = temp_bundle_id if temp_bundle_id else f'com.unknown.{cleaned_name.lower().replace(" ", "")}'
                    print(f"  [FALLBACK] Generated/found bundle ID: {info['bundleIdentifier']}")
                if best_version and (not info.get('version') or info.get('version') in ['1.0', '0.1.0', '1']):
                    info['version'] = best_version
                    print(f"  [FALLBACK] Updated version from message/filename: {best_version}")
        else:
            # Metadata was extracted successfully, but prefer message data if available
            # Override name with message name if available
            if app_name_from_message:
                info['name'] = clean_app_name(app_name_from_message)
                print(f"  [OVERRIDE] Using app name from message: '{info['name']}'")
            elif info.get('name'):
                # Clean the app name from metadata
                original_name = info['name']
                cleaned_name = clean_app_name(original_name)
                if cleaned_name != original_name:
                    info['name'] = cleaned_name
                    print(f"  [CLEANUP] Cleaned metadata name: '{original_name}' -> '{cleaned_name}'")

            # Override version with message version if available, or filename version if metadata has placeholder version
            if version_from_message:
                info['version'] = version_from_message
                print(f"  [OVERRIDE] Using version from message: {version_from_message}")
            elif version_from_file and info.get('version') in ['1.0', '0.1.0', '1']:
                # Replace placeholder versions with filename version
                info['version'] = version_from_file
                print(f"  [FALLBACK] Updated version from filename: {version_from_file} (metadata had '{info.get('version')}')")

        if info:
            bundle_id = info['bundleIdentifier']
            app_version = info['version']

            # IMPORTANT: Final correction for Swiftgram/Telegram based on bundle ID
            # This ensures consistency even if AI extraction failed
            if bundle_id == 'app.swiftgram.ios' and info.get('name') != 'Swiftgram':
                print(f"  [CORRECTION] Bundle ID is app.swiftgram.ios - correcting app name from '{info.get('name')}' to 'Swiftgram'")
                info['name'] = 'Swiftgram'
            elif bundle_id == 'ph.telegra.Telegraph' and info.get('name') != 'Telegram':
                print(f"  [CORRECTION] Bundle ID is ph.telegra.Telegraph - correcting app name from '{info.get('name')}' to 'Telegram'")
                info['name'] = 'Telegram'

            # Create a unique key that includes tweak name
            # This allows different tweaks of the same app to be tracked separately
            # e.g., "com.instagram.app" vs "com.instagram.app:BHInstagram" vs "com.instagram.app:IGFormat"
            if best_tweak:
                unique_app_key = f"{bundle_id}:{best_tweak}"
                print(f"  [KEY] Using unique key for tweak: {unique_app_key}")
            else:
                unique_app_key = bundle_id
                print(f"  [KEY] Using bundle ID as key: {unique_app_key}")

            if unique_app_key in apps_by_bundle:
                existing_version = apps_by_bundle[unique_app_key]['version']
                existing_timestamp = apps_by_bundle[unique_app_key].get('timestamp', 0)
                print(f"  [VERSION] Comparing: {app_version} vs existing {existing_version}")
                if compare_versions(app_version, existing_version, message_timestamp, existing_timestamp):
                    print(f"  [VERSION] New version is newer (or more recent), replacing...")
                    if app_version == existing_version and message_timestamp > existing_timestamp:
                        new_date = datetime.fromtimestamp(message_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        old_date = datetime.fromtimestamp(existing_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        print(f"  [TIMESTAMP] Using more recent message: {new_date} vs {old_date}")
                    old_filename = apps_by_bundle[unique_app_key]['filename']
                    old_path = os.path.join(DOWNLOAD_DIR, old_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                        print(f"  [REMOVED] Deleted older version: {old_filename}")

                    # Get source data for the new version
                    source_data = source_tracking.get(filename, 'Unknown')
                    if isinstance(source_data, dict):
                        source_channel = source_data.get('source', 'Unknown')
                        source_message = source_data.get('message', '')
                    else:
                        source_channel = source_data
                        source_message = ''

                    apps_by_bundle[unique_app_key] = {
                        'info': info,
                        'filename': filename,
                        'version': app_version,
                        'source': source_channel,
                        'message': source_message,
                        'tweak': best_tweak,
                        'timestamp': message_timestamp,
                        'ai_description': ai_description,
                        'old_filename': old_filename  # Store old filename for release cleanup
                    }
                else:
                    print(f"  [SKIP] Existing version {existing_version} is newer than {app_version}")
                    if app_version == existing_version:
                        new_date = datetime.fromtimestamp(message_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        old_date = datetime.fromtimestamp(existing_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        print(f"  [SKIP] Same version, but existing message is more recent: {old_date} vs {new_date}")
                    continue
            else:
                print(f"  [NEW] First occurrence of app key: {unique_app_key}")
                # Handle both old (string) and new (dict) source_tracking formats
                source_data = source_tracking.get(filename, 'Unknown')
                if isinstance(source_data, dict):
                    source_channel = source_data.get('source', 'Unknown')
                    source_message = source_data.get('message', '')
                else:
                    # Old format (just a string)
                    source_channel = source_data
                    source_message = ''

                apps_by_bundle[unique_app_key] = {
                    'info': info,
                    'filename': filename,
                    'version': app_version,
                    'source': source_channel,
                    'message': source_message,
                    'tweak': best_tweak,
                    'timestamp': message_timestamp,
                    'ai_description': ai_description
                }
    
    print(f"\n[MERGE] Checking existing {REPO_FILE} for apps...")
    if os.path.exists(REPO_FILE):
        print(f"[MERGE] Found existing {REPO_FILE}, merging with new data...")
        with open(REPO_FILE, 'r', encoding='utf-8') as f:
            repo_data = json.load(f)
            existing_apps = repo_data.get('apps', [])
            print(f"[MERGE] Existing repo contains {len(existing_apps)} apps")

            for app in existing_apps:
                bundle_id = app['bundleIdentifier']
                app_version = app['version']
                app_name = app.get('name', '')

                # Try to detect tweak from existing app name
                # e.g., "Instagram (BHInstagram)" -> tweak is "BHInstagram"
                existing_tweak = None
                tweak_in_name_match = re.search(r'\(([^)]+)\)$', app_name)
                if tweak_in_name_match:
                    existing_tweak = tweak_in_name_match.group(1)

                # Create unique key for existing app
                if existing_tweak:
                    unique_app_key = f"{bundle_id}:{existing_tweak}"
                    print(f"[MERGE] Existing app key: {unique_app_key} ('{app_name}' v{app_version})")
                else:
                    unique_app_key = bundle_id
                    print(f"[MERGE] Existing app key: {unique_app_key} ('{app_name}' v{app_version})")

                if unique_app_key in apps_by_bundle:
                    new_version = apps_by_bundle[unique_app_key]['version']
                    print(f"[MERGE] Conflict for {unique_app_key}: existing v{app_version} vs new v{new_version}")
                    if compare_versions(app_version, new_version):
                        print(f"  [MERGE] Keeping existing version (newer)")
                        apps_by_bundle[unique_app_key] = {
                            'info': None,
                            'existing': app,
                            'version': app_version,
                            'tweak': existing_tweak
                        }
                    else:
                        print(f"  [MERGE] Replacing with new version")
                else:
                    print(f"[MERGE] Keeping existing app: {app.get('name', 'Unknown')} ({unique_app_key})")
                    apps_by_bundle[unique_app_key] = {
                        'info': None,
                        'existing': app,
                        'version': app_version,
                        'tweak': existing_tweak
                    }
    else:
        print(f"[MERGE] No existing {REPO_FILE} found, creating new one")

    print(f"\n[BUILD] Building final app list and uploading to release...")
    final_apps = []
    new_apps_count = 0
    existing_apps_count = 0

    # Get the repository URL for constructing download URLs
    owner, repo_name, api_url, base_url = get_repo_info()
    if owner and repo_name and base_url:
        repo_url = f"{base_url}/{owner}/{repo_name}"
        print(f"[INFO] Repository URL: {repo_url}")
    else:
        print(f"[WARNING] Could not get repo URL from git remote")
        repo_url = os.getenv('REPO_BASE_URL', 'https://example.com')

    # Get current release assets to verify existing apps still have their IPAs
    print(f"[VERIFY] Fetching current release assets to verify existing apps...")
    current_release_assets = get_release_assets()
    print(f"[VERIFY] Found {len(current_release_assets)} assets in release")

    for bundle_id, data in apps_by_bundle.items():
        if 'existing' in data:
            # Verify that the IPA file for this existing app still exists in the release
            existing_app = data['existing']
            download_url = existing_app.get('downloadURL', '')

            # Extract filename from download URL (e.g., ".../<filename>.ipa")
            if download_url:
                # URL format: https://example.com/owner/repo/releases/download/latest/filename.ipa
                filename_from_url = download_url.split('/')[-1]
                # URL decode the filename
                filename_from_url = urllib.parse.unquote(filename_from_url)

                if filename_from_url in current_release_assets:
                    print(f"[VERIFY] Existing app IPA found in release: {existing_app.get('name', 'Unknown')} ({filename_from_url})")
                    final_apps.append(existing_app)
                    existing_apps_count += 1
                else:
                    print(f"[VERIFY] Existing app IPA NOT found in release, skipping: {existing_app.get('name', 'Unknown')} ({filename_from_url})")
            else:
                print(f"[WARNING] Existing app has no download URL, skipping: {existing_app.get('name', 'Unknown')}")
        elif data['info']:
            new_apps_count += 1
            info = data['info']
            filename = data['filename']

            src_path = os.path.join(DOWNLOAD_DIR, filename)

            # Get metadata for upload (bundle_id, tweak, old_filename if replacing)
            bundle_id_value = info['bundleIdentifier']
            tweak_value = data.get('tweak')
            old_filename_value = data.get('old_filename')  # Will be None if this is a new app

            # Upload to release
            if upload_to_release(src_path, bundle_id=bundle_id_value, tweak_name=tweak_value, old_filename=old_filename_value):
                # Construct download URL from release (URL-encode the filename)
                encoded_filename = quote(filename)
                download_url = f"{repo_url}/releases/download/{RELEASE_TAG}/{encoded_filename}"

                # Search App Store for official name, icon, and bundle ID
                # Only search if we have com.unknown or if cache check suggests we need to
                current_bundle_id = info['bundleIdentifier']
                cache_key = f"{current_bundle_id}:{info['name']}"

                # Skip App Store lookup if we have valid bundle ID and it's not in cache
                # This avoids lookups for apps we've never seen before with valid IDs
                if 'com.unknown' in current_bundle_id:
                    print(f"[APPSTORE] Found fallback bundle ID, searching App Store for correct one...")
                    official_name, icon_url, official_bundle_id = search_app_store(info['name'], current_bundle_id)
                elif cache_key in _appstore_cache:
                    # Use cached result if available
                    print(f"[APPSTORE] Looking up app: {info['name']} ({current_bundle_id})")
                    official_name, icon_url, official_bundle_id = search_app_store(info['name'], current_bundle_id)
                else:
                    # Skip lookup for known-good bundle IDs on first run
                    print(f"[SKIP] Skipping App Store lookup for {info['name']} (valid bundle ID)")
                    official_name, icon_url, official_bundle_id = None, None, None

                # Use official App Store name if found, otherwise use extracted name
                base_name = official_name if official_name else info['name']

                # Final cleanup: ensure no markdown or emojis slip through
                if not official_name and base_name:
                    # Clean the extracted name as a fallback
                    base_name = base_name.replace('**', '')  # Remove bold markdown
                    base_name = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', base_name)  # Remove markdown links
                    base_name = re.sub(r'[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF\U00002700-\U000027BF\U0000FE00-\U0000FE0F\u0600-\u06FF]', '', base_name)  # Remove emojis
                    base_name = base_name.strip()

                # Special name mappings to ensure correct App Store icon lookup
                # Twitter was rebranded to X, so ensure we use "X" for proper icon matching
                bundle_id_name_overrides = {
                    'com.atebits.Tweetie2': 'X',  # Twitter bundle ID should show as "X"
                }

                final_bundle_id_for_check = official_bundle_id if official_bundle_id else info['bundleIdentifier']
                if final_bundle_id_for_check in bundle_id_name_overrides:
                    base_name = bundle_id_name_overrides[final_bundle_id_for_check]
                    print(f"[MAPPING] Using name override for {final_bundle_id_for_check}: '{base_name}'")

                if official_name and official_name != info['name']:
                    print(f"[APPSTORE] Using official name: '{info['name']}' -> '{official_name}'")

                # If this is a tweaked app, append tweak name to distinguish it
                tweak_name = data.get('tweak')
                if tweak_name:
                    final_name = f"{base_name} ({tweak_name})"
                    print(f"[TWEAK] Adding tweak to app name: '{base_name}' -> '{final_name}'")
                else:
                    final_name = base_name

                # ALWAYS use official App Store bundle ID if found, especially for com.unknown cases
                final_bundle_id = official_bundle_id if official_bundle_id else info['bundleIdentifier']
                if official_bundle_id and official_bundle_id != info['bundleIdentifier']:
                    print(f"[APPSTORE] Using official bundle ID: '{info['bundleIdentifier']}' -> '{official_bundle_id}'")
                elif 'com.unknown' in final_bundle_id and not official_bundle_id:
                    print(f"[WARNING] Could not find official bundle ID for {info['name']}, using fallback: {final_bundle_id}")

                # If no icon from App Store, try other methods
                if not icon_url:
                    print(f"[ICON] App Store lookup failed, trying fallback methods")
                    icon_url = get_icon_url_from_name(info['name'], info['bundleIdentifier'])

                # Format date as ISO 8601 with Z suffix (Feather/AltStore format)
                current_date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

                # Get source channel and message for description and developer
                source_channel = data.get('source', 'Unknown')
                source_message = data.get('message', '')
                ai_desc = data.get('ai_description', None)

                # Build description with source and formatted message
                # Priority: AI-cleaned description > manual cleaning
                if ai_desc:
                    # Use AI-cleaned description with source header
                    if source_channel != 'Unknown':
                        header = f"from @{source_channel} |"
                        separator = "-" * len(header)
                        description = f"{header}\n{separator}\n{ai_desc}"
                        print(f"  [AI] Using AI-cleaned description")
                    else:
                        description = ai_desc
                elif source_channel != 'Unknown':
                    # Fallback: manual cleaning
                    header = f"from @{source_channel} |"
                    separator = "-" * len(header)
                    description = f"{header}\n{separator}"

                    if source_message:
                        # Clean up message (remove markdown formatting and links but keep link text)
                        clean_message = source_message.replace('**', '')
                        # Remove markdown links: [text](url) -> text
                        clean_message = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_message)
                        description += f"\n{clean_message}"
                else:
                    description = final_name

                developer_name = f"@{source_channel}" if source_channel != 'Unknown' else 'Unknown'

                app_entry = {
                    'name': final_name,
                    'bundleIdentifier': final_bundle_id,
                    'developerName': developer_name,
                    'iconURL': icon_url,
                    'localizedDescription': description,
                    'versions': [
                        {
                            'version': info['version'],
                            'date': current_date,
                            'size': info['size'],
                            'downloadURL': download_url
                        }
                    ],
                    'appPermissions': {},
                    'version': info['version'],
                    'versionDate': current_date,
                    'size': info['size'],
                    'downloadURL': download_url
                }

                final_apps.append(app_entry)
                print(f"[BUILD] Added new app: {final_name} v{info['version']}")
            else:
                print(f"[ERROR] Failed to upload {filename}, skipping from {REPO_FILE}")

    print(f"\n[BUILD] Final app list: {len(final_apps)} total apps")
    print(f"[BUILD] - New apps: {new_apps_count}")
    print(f"[BUILD] - Existing apps: {existing_apps_count}")
    
    print(f"\n[JSON] Creating repository JSON structure...")
    repo_data = {
        'name': 'FTRepo',
        'identifier': 'xyz.ftrepo',
        'apps': final_apps
    }

    print(f"[JSON] Writing to {REPO_FILE}...")
    with open(REPO_FILE, 'w', encoding='utf-8') as f:
        json.dump(repo_data, f, indent=2, ensure_ascii=False)

    # Save App Store cache for future runs
    save_appstore_cache()

    # Save AI bundle ID cache
    save_ai_bundle_cache()

    print(f"[SUCCESS] Updated {REPO_FILE} with {len(repo_data['apps'])} apps")
    print("=" * 60)

async def main():
    print("\n" + "=" * 60)
    print("TELEGRAM IPA SCRAPER")
    print("=" * 60)
    print(f"[START] Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check for required OpenRouter API key
    if not OPENROUTER_API_KEY:
        print("\n" + "=" * 60)
        print("ERROR: OPENROUTER_API_KEY is required!")
        print("=" * 60)
        print("This scraper uses AI for metadata extraction.")
        print("Please set the OPENROUTER_API_KEY environment variable or secret.")
        print("\nGet your API key from: https://openrouter.ai/")
        print("Cost: ~$0.05 per 1000 apps (very cheap!)")
        print("=" * 60 + "\n")
        raise RuntimeError("OPENROUTER_API_KEY is required but not configured")

    print(f"[CONFIG] OpenRouter API Key: {'*' * 8}{OPENROUTER_API_KEY[-4:]}")
    print(f"[CONFIG] OpenRouter Model: {OPENROUTER_MODEL}")

    # Load known tweaks list for AI context
    print(f"\n[SETUP] Loading known tweaks list...")
    load_known_tweaks()
    if _known_tweaks:
        print(f"[TWEAKS] AI will use these approved tweaks: {', '.join(_known_tweaks[:5])}{'...' if len(_known_tweaks) > 5 else ''}")
    else:
        print(f"[TWEAKS] No tweaks list found - AI will use default behavior")

    print("\n[PHASE 1] Downloading IPAs from Telegram channels...")
    downloaded_files, source_tracking = await download_ipas()

    print("\n[PHASE 2] Updating repository JSON...")
    await update_repo_json(source_tracking)

    print("\n" + "=" * 60)
    print("ALL OPERATIONS COMPLETE")
    print("=" * 60)
    print(f"[FINISH] Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[STATS] Total new downloads: {len(downloaded_files)}")
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
