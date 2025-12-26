#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean Duplicates Workflow

This script checks for duplicate app names in apps.json using OpenRouter AI
and removes duplicates that are not in the tweaks list.

Examples:
- "BHInstagram" is in tweaks list -> "Instagram (BHInstagram)" is kept
- "Locket Gold" is NOT in tweaks list -> "Locket (Locket Gold)" is deleted

The script also checks for apps in the Latest Release and removes orphaned IPAs.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
import subprocess

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Configuration
REPO_FILE = 'apps.json'
TWEAKS_LIST_FILE = 'tweaks_list.json'
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
RELEASE_TAG = 'latest'

# Cache for AI duplicate detection
_ai_duplicate_cache = {}


def load_tweaks_list():
    """Load the list of known tweaks from tweaks_list.json"""
    if not os.path.exists(TWEAKS_LIST_FILE):
        print(f"[WARNING] {TWEAKS_LIST_FILE} not found, creating default list...")
        default_tweaks = {
            "description": "List of known tweak names for popular apps",
            "tweaks": [
                "BHInstagram", "BHTikTok", "BHX", "TikTokLRD", "Theta",
                "TwiGalaxy", "NeoFreeBird", "Rocket", "Watusi", "OLED",
                "RXTikTok", "IGFormat", "DLEasy", "TGExtra", "Spotilife", "YouTopia"
            ]
        }
        with open(TWEAKS_LIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_tweaks, f, indent=2)
        return default_tweaks['tweaks']

    try:
        with open(TWEAKS_LIST_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            tweaks = data.get('tweaks', [])
            print(f"[TWEAKS] Loaded {len(tweaks)} known tweaks from {TWEAKS_LIST_FILE}")
            return tweaks
    except Exception as e:
        print(f"[ERROR] Failed to load {TWEAKS_LIST_FILE}: {e}")
        return []


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

            # GitHub uses api.github.com, not github.com/api/v3
            if 'github.com' in base_url:
                api_url = 'https://api.github.com'
            else:
                api_url = f'{base_url}/api/v1'
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
            return {}

        print(f"[RELEASE] Fetching assets from '{RELEASE_TAG}' release...")
        url = f"{api_url}/repos/{owner}/{repo}/releases/tags/{RELEASE_TAG}"

        result = subprocess.run(
            ['curl', '-s', '-H', f'Authorization: token {GITHUB_TOKEN}' if GITHUB_TOKEN else '', url],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0 or not result.stdout:
            print(f"[WARNING] Could not fetch release assets")
            return {}

        try:
            data = json.loads(result.stdout)
            if 'message' in data:  # Error response
                print(f"[WARNING] Release '{RELEASE_TAG}' not found")
                return {}

            assets = {}
            for asset in data.get('assets', []):
                assets[asset['name']] = {
                    'id': asset['id'],
                    'size': asset.get('size', 0),
                    'download_url': asset.get('browser_download_url', '')
                }

            print(f"[RELEASE] Found {len(assets)} assets in release")
            return assets
        except json.JSONDecodeError:
            print(f"[WARNING] Could not parse release data")
            return {}
    except Exception as e:
        print(f"[ERROR] Failed to fetch release assets: {e}")
        return {}


def delete_release_asset(asset_id, asset_name):
    """Delete an asset from the release"""
    try:
        owner, repo, api_url, _ = get_repo_info()
        if not owner or not repo or not api_url:
            print(f"[ERROR] Could not determine repository info")
            return False

        # Get release ID first
        url = f"{api_url}/repos/{owner}/{repo}/releases/tags/{RELEASE_TAG}"
        result = subprocess.run(
            ['curl', '-s', '-H', f'Authorization: token {GITHUB_TOKEN}' if GITHUB_TOKEN else '', url],
            capture_output=True,
            text=True,
            check=False
        )

        data = json.loads(result.stdout)
        release_id = data.get('id')
        if not release_id:
            print(f"[ERROR] Could not get release ID")
            return False

        # Delete the asset
        delete_url = f"{api_url}/repos/{owner}/{repo}/releases/{release_id}/assets/{asset_id}"
        result = subprocess.run(
            ['curl', '-s', '-X', 'DELETE',
             '-H', f'Authorization: token {GITHUB_TOKEN}' if GITHUB_TOKEN else '',
             delete_url],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            print(f"[DELETED] Removed from release: {asset_name}")
            return True
        else:
            print(f"[ERROR] Failed to delete asset: {asset_name}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to delete asset {asset_name}: {e}")
        return False


def check_duplicate_with_ai(name1, name2):
    """
    Use OpenRouter AI to check if two app names are duplicates.

    Returns:
        - 'duplicate': Both names refer to the same app
        - 'different': Names refer to different apps
        - 'unknown': Cannot determine
    """
    if not OPENROUTER_API_KEY:
        print(f"[WARNING] OPENROUTER_API_KEY not set, skipping AI duplicate check")
        return 'unknown'

    # Check cache first
    cache_key = f"{name1}|{name2}"
    reverse_cache_key = f"{name2}|{name1}"

    if cache_key in _ai_duplicate_cache:
        return _ai_duplicate_cache[cache_key]
    if reverse_cache_key in _ai_duplicate_cache:
        return _ai_duplicate_cache[reverse_cache_key]

    try:
        print(f"  [AI] Checking if '{name1}' and '{name2}' are duplicates...")

        api_url = "https://openrouter.ai/api/v1/chat/completions"

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an iOS app duplicate detection expert. Given two app names, "
                        "determine if they refer to the SAME app or DIFFERENT apps.\n\n"
                        "Rules:\n"
                        "1. Names like 'Instagram' and 'Instagram (BHInstagram)' are DUPLICATES "
                        "(one is tweaked version of the other)\n"
                        "2. Names like 'Locket' and 'Locket (Locket Gold)' are DUPLICATES "
                        "(Locket Gold is not a known tweak, it's likely the same app with premium features)\n"
                        "3. Names like 'YouTube' and 'YouTube Music' are DIFFERENT apps\n"
                        "4. Names like 'Telegram' and 'Swiftgram' are DIFFERENT apps (Swiftgram is a separate app)\n"
                        "5. Ignore capitalization, spacing, and special characters\n"
                        "6. Ignore suffixes like 'Pro', 'Plus', 'Premium', 'Gold', etc. - these are duplicates\n"
                        "7. If the base app name is the same (ignoring modifiers), they are duplicates\n\n"
                        "Respond with ONLY a JSON object:\n"
                        "{\n"
                        '  "result": "duplicate" or "different",\n'
                        '  "reason": "brief explanation"\n'
                        "}"
                    )
                },
                {
                    "role": "user",
                    "content": f"App 1: {name1}\nApp 2: {name2}"
                }
            ],
            "temperature": 0,
            "max_tokens": 150,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/FTRepo/FTRepo",
            "X-Title": "FTRepo Duplicate Cleaner"
        }

        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))

        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content'].strip()
            ai_response = json.loads(content)

            result_type = ai_response.get('result', 'unknown')
            reason = ai_response.get('reason', 'No reason provided')

            print(f"  [AI] Result: {result_type} - {reason}")

            # Cache the result
            _ai_duplicate_cache[cache_key] = result_type

            return result_type
        else:
            print(f"  [AI] Unexpected response format")
            return 'unknown'

    except Exception as e:
        print(f"  [AI] Failed to check duplicates: {e}")
        return 'unknown'


def extract_base_name_and_tweak(app_name):
    """
    Extract base app name and tweak name from full app name.

    Examples:
        "Instagram (BHInstagram)" -> ("Instagram", "BHInstagram")
        "Locket (Locket Gold)" -> ("Locket", "Locket Gold")
        "YouTube" -> ("YouTube", None)

    Returns:
        tuple: (base_name, tweak_name or None)
    """
    # Pattern: AppName (TweakName) or AppName (Modifier)
    match = re.search(r'^(.+?)\s*\(([^)]+)\)$', app_name)
    if match:
        base_name = match.group(1).strip()
        tweak_name = match.group(2).strip()
        return base_name, tweak_name
    else:
        return app_name, None


def extract_tweak_from_filename(filename, known_tweaks):
    """
    Extract tweak name from filename by searching for known tweak names anywhere in the filename.

    This handles filenames where tweaks are embedded in the middle, like:
    - "Instagram v405.1.0 Theta v4.0 blatant Patched.ipa" -> "Theta"
    - "Instagram v405.1.0 BHInsta v1.2 blatant Patched.ipa" -> "BHInsta"
    - "TikTok v42.0.0.ipa" -> None

    Args:
        filename: The filename to search
        known_tweaks: List of known tweak names from tweaks_list.json

    Returns:
        The tweak name if found, None otherwise
    """
    if not known_tweaks:
        return None

    # Search for each known tweak as a word boundary in the filename
    for tweak in known_tweaks:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(tweak) + r'\b'
        if re.search(pattern, filename, re.IGNORECASE):
            return tweak

    return None


def is_tweak_in_list(tweak_name, known_tweaks):
    """
    Check if a tweak name is in the known tweaks list (case-insensitive).

    Args:
        tweak_name: The tweak name to check
        known_tweaks: List of known tweak names

    Returns:
        True if the tweak is in the list (case-insensitive), False otherwise
    """
    if not tweak_name or not known_tweaks:
        return False

    # Case-insensitive comparison
    tweak_lower = tweak_name.lower()
    return any(known.lower() == tweak_lower for known in known_tweaks)


def compare_versions(v1, v2):
    """
    Compare two version strings and return True if v1 is newer than v2.

    Args:
        v1: First version string
        v2: Second version string

    Returns:
        True if v1 > v2, False otherwise
    """
    try:
        # Extract numeric parts from version strings
        v1_parts = [int(x) for x in re.split(r'[.-]', str(v1)) if x.isdigit()]
        v2_parts = [int(x) for x in re.split(r'[.-]', str(v2)) if x.isdigit()]

        # Pad with zeros to make them equal length
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        return v1_parts > v2_parts
    except:
        # Fallback to string comparison
        return str(v1) > str(v2)


def check_all_release_assets_with_ai(filenames, known_tweaks=None):
    """
    Use OpenRouter AI to check ALL IPA filenames at once for duplicates.
    Much more efficient than pairwise comparison.

    Args:
        filenames: List of IPA filenames
        known_tweaks: List of known tweak names for validation

    Returns:
        List of dicts with:
            - 'keep': str - Filename to keep (newest version)
            - 'delete': list - List of filenames to delete (older versions)
            - 'reason': str - Explanation
    """
    if not OPENROUTER_API_KEY:
        print(f"[WARNING] OPENROUTER_API_KEY not set, skipping AI asset check")
        return []

    if len(filenames) < 2:
        print(f"[INFO] Not enough files to compare")
        return []

    # If we have too many files, process in chunks to avoid token limits
    CHUNK_SIZE = 50  # Process 50 files at a time
    if len(filenames) > CHUNK_SIZE:
        print(f"  [INFO] Processing {len(filenames)} files in chunks of {CHUNK_SIZE}")
        all_duplicate_groups = []
        for i in range(0, len(filenames), CHUNK_SIZE):
            chunk = filenames[i:i + CHUNK_SIZE]
            print(f"  [CHUNK] Processing files {i+1}-{min(i+CHUNK_SIZE, len(filenames))}")
            chunk_groups = check_all_release_assets_with_ai(chunk, known_tweaks)
            all_duplicate_groups.extend(chunk_groups)
        return all_duplicate_groups

    # Check cache first
    cache_key = f"assets_batch:{hash(tuple(sorted(filenames)))}"
    if cache_key in _ai_duplicate_cache:
        print(f"  [AI CACHE] Using cached batch result")
        return _ai_duplicate_cache[cache_key]

    try:
        print(f"  [AI] Analyzing {len(filenames)} IPA files for duplicates...")

        api_url = "https://openrouter.ai/api/v1/chat/completions"

        # Build the filenames list for the prompt
        filenames_text = "\n".join([f"{i+1}. {name}" for i, name in enumerate(filenames)])

        # Build known tweaks text for the prompt
        tweaks_text = ""
        if known_tweaks:
            tweaks_text = f"\n\nKNOWN TWEAK NAMES (These are DISTINCT tweaks - NEVER treat them as duplicates):\n{', '.join(known_tweaks)}\n\n"

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an iOS IPA filename analyzer. Given a list of IPA filenames, identify groups of duplicates.\n\n"
                        "A duplicate group is:\n"
                        "- Same base app name (ignore case, spacing, underscores, dashes)\n"
                        "- Same modifiers (Pro, Unlocked, Patched, etc.) - these are NOT version differences\n"
                        "- Same EXACT tweak name (can appear anywhere in filename as a standalone word)\n"
                        "- Different version numbers (v1.0, v2.0, v2.19, v2.20, v2.21, etc.)\n\n"
                        f"{tweaks_text}"
                        "TWEAK IDENTIFICATION:\n"
                        "- Tweaks can appear ANYWHERE in the filename as standalone words\n"
                        "- Examples: 'Instagram v405.1.0 BHInsta v1.2 Patched.ipa' → tweak is 'BHInsta'\n"
                        "- Examples: 'Instagram v405.1.0 Theta v4.0 Patched.ipa' → tweak is 'Theta'\n"
                        "- Match tweak names from the KNOWN TWEAKS list above\n"
                        "- BHInsta and Theta are DIFFERENT tweaks - NEVER group them together!\n\n"
                        "VERSION EXTRACTION RULES:\n"
                        "- Version can be anywhere in the filename: 'App v2.19.ipa', 'App_v2_19.ipa', 'App 2.19.ipa'\n"
                        "- Common patterns: v2.19, v2_19, 2.19, 404.0, 42.3.0\n"
                        "- Version format: major.minor.patch (e.g., 2.21 > 2.20 > 2.19)\n"
                        "- App version vs Tweak version: 'Instagram v405.1.0 BHInsta v1.2' has both - compare app versions\n"
                        "- IGNORE words like 'Pro', 'Unlocked', 'Patched', 'Premium', 'blatant' - these are modifiers, not versions\n\n"
                        "EXAMPLES:\n"
                        "✅ DUPLICATES:\n"
                        "- 'Instagram v405.1.0 BHInsta v1.2 blatant Patched.ipa' and 'Instagram v404.0.0 BHInsta v1.2 blatant Patched.ipa'\n"
                        "  → Same app (Instagram), SAME tweak (BHInsta), different app versions (405.1.0 vs 404.0.0)\n"
                        "  → KEEP v405.1.0, DELETE v404.0.0\n"
                        "- 'Instagram v405.1.0 Theta v4.0 blatant Patched.ipa' and 'Instagram v404.0.0 Theta v3.9 blatant Patched.ipa'\n"
                        "  → Same app (Instagram), SAME tweak (Theta), different app versions (405.1.0 vs 404.0.0)\n"
                        "  → KEEP v405.1.0, DELETE v404.0.0\n"
                        "- 'Coconote - AI Note Taker v2.19 Pro Unlocked blatant Patched.ipa'\n"
                        "  'Coconote - AI Note Taker v2.20 Pro Unlocked blatant Patched.ipa'\n"
                        "  'Coconote - AI Note Taker v2.21 Pro Unlocked blatant Patched.ipa'\n"
                        "  → Same app, same modifiers, no tweaks, different versions (2.19, 2.20, 2.21)\n"
                        "  → KEEP v2.21, DELETE v2.19 and v2.20\n\n"
                        "❌ NOT DUPLICATES:\n"
                        "- 'Instagram v405.1.0 BHInsta v1.2 blatant Patched.ipa' and 'Instagram v405.1.0 Theta v4.0 blatant Patched.ipa'\n"
                        "  → DIFFERENT tweaks (BHInsta vs Theta) - NEVER treat different tweaks as duplicates!\n"
                        "  → Even though they have the same app version, they are DIFFERENT files!\n"
                        "- 'Instagram v405.1.0 BHInsta v1.2.ipa' and 'Instagram v404.0.0 Theta v4.0.ipa'\n"
                        "  → DIFFERENT tweaks - even if BHInsta has newer version, they are NOT duplicates!\n"
                        "- 'YouTube.ipa' and 'YouTube Music.ipa'\n"
                        "  → Different apps (YouTube vs YouTube Music)\n\n"
                        "CRITICAL RULES:\n"
                        "- ONLY group files as duplicates if they have the EXACT SAME tweak name (or both have NO tweak)\n"
                        "- Different tweaks are NEVER EVER duplicates, even if one has a newer version number\n"
                        "- BHInsta, Theta, TikTokLRD, VibeTok, etc. are all DIFFERENT tweaks - keep them separate!\n"
                        "- Focus on VERSION NUMBERS WITHIN the same tweak only\n"
                        "- Ignore modifiers like Pro, Unlocked, Patched, Premium, blatant - these are NOT versions!\n"
                        "- If filenames are identical except for version numbers AND have the same tweak, they are duplicates\n"
                        "- Keep the file with the HIGHEST app version number within each tweak group\n\n"
                        "Respond with ONLY a JSON object with a 'groups' array:\n"
                        "{\n"
                        '  "groups": [\n'
                        "    {\n"
                        '      "app_name": "App Name",\n'
                        '      "tweak_name": "Tweak Name or null",\n'
                        '      "keep": "filename with newest version",\n'
                        '      "delete": ["older filename 1", "older filename 2"],\n'
                        '      "reason": "brief explanation with versions"\n'
                        "    }\n"
                        "  ]\n"
                        "}\n\n"
                        "If no duplicates found, return: {\"groups\": []}"
                    )
                },
                {
                    "role": "user",
                    "content": f"Analyze these IPA files:\n\n{filenames_text}"
                }
            ],
            "temperature": 0,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/FTRepo/FTRepo",
            "X-Title": "FTRepo Duplicate Cleaner"
        }

        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=60) as response:  # Increased timeout for large batches
            result = json.loads(response.read().decode('utf-8'))

        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content'].strip()

            # Debug: Print the raw response to see what went wrong
            print(f"  [DEBUG] Raw AI response length: {len(content)} chars")

            # Try to fix common JSON issues
            try:
                ai_response = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"  [ERROR] Failed to parse AI response: {e}")
                print(f"  [DEBUG] Response around error position:")
                # Show context around the error
                start = max(0, e.pos - 100)
                end = min(len(content), e.pos + 100)
                print(f"  {content[start:end]}")
                print(f"  {'~' * (e.pos - start)}^")

                # Try to salvage the response by extracting JSON from markdown code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    print(f"  [RECOVERY] Found JSON in markdown code block, trying again...")
                    content = json_match.group(1).strip()
                    ai_response = json.loads(content)
                else:
                    # Last resort: try to find any JSON object in the content
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        print(f"  [RECOVERY] Found JSON object, trying again...")
                        content = json_match.group(0).strip()
                        ai_response = json.loads(content)
                    else:
                        print(f"  [ERROR] Could not parse or recover AI response")
                        print(f"  [INFO] Returning empty list to prevent crashes")
                        return []

            # Handle both array and object responses
            if isinstance(ai_response, dict):
                # Check if there's a 'duplicates' or 'groups' key
                duplicate_groups = ai_response.get('duplicates', ai_response.get('groups', []))
            else:
                duplicate_groups = ai_response

            # Check if response was truncated
            if result.get('usage', {}).get('completion_tokens', 0) >= 2000:
                print(f"  [WARNING] AI response may have been truncated (hit max_tokens)")
                print(f"  [INFO] Consider reducing CHUNK_SIZE or increasing max_tokens")

            print(f"  [AI] Found {len(duplicate_groups)} duplicate group(s)")

            # Validate AI decisions against known tweaks list
            if known_tweaks and duplicate_groups:
                validated_groups = []
                for group in duplicate_groups:
                    tweak_name = group.get('tweak_name')
                    keep_file = group.get('keep', '')
                    delete_files = group.get('delete', [])

                    # Extract tweak names from filenames using the known_tweaks list
                    # This works with tweaks embedded anywhere in the filename
                    keep_tweak = extract_tweak_from_filename(keep_file, known_tweaks)

                    # Validate that all files in the group have the same tweak
                    all_tweaks_match = True
                    for delete_file in delete_files:
                        delete_tweak = extract_tweak_from_filename(delete_file, known_tweaks)

                        # Normalize for comparison (case-insensitive)
                        keep_tweak_normalized = keep_tweak.lower() if keep_tweak else None
                        delete_tweak_normalized = delete_tweak.lower() if delete_tweak else None

                        if keep_tweak_normalized != delete_tweak_normalized:
                            print(f"  [VALIDATION ERROR] AI tried to group different tweaks:")
                            print(f"    Keep: {keep_file} (tweak: {keep_tweak or 'None'})")
                            print(f"    Delete: {delete_file} (tweak: {delete_tweak or 'None'})")
                            print(f"    → REJECTING this group to prevent incorrect deletion")
                            all_tweaks_match = False
                            break

                    if all_tweaks_match:
                        validated_groups.append(group)
                    else:
                        print(f"  [VALIDATION] Skipped invalid group")

                print(f"  [VALIDATION] {len(validated_groups)}/{len(duplicate_groups)} groups passed validation")
                duplicate_groups = validated_groups

            # Cache the result
            _ai_duplicate_cache[cache_key] = duplicate_groups

            return duplicate_groups
        else:
            print(f"  [AI] Unexpected response format")
            return []

    except Exception as e:
        print(f"  [AI] Failed to analyze assets: {e}")
        import traceback
        traceback.print_exc()
        return []


def check_release_assets_with_ai(filename1, filename2):
    """
    Use OpenRouter AI to check if two IPA filenames are duplicates (same app, different versions).

    Args:
        filename1: First filename
        filename2: Second filename

    Returns:
        dict with:
            - 'duplicate': bool - True if same app, different versions
            - 'newer_file': str - Which file has the newer version (filename1 or filename2)
            - 'reason': str - Explanation
    """
    if not OPENROUTER_API_KEY:
        print(f"[WARNING] OPENROUTER_API_KEY not set, skipping AI asset check")
        return {'duplicate': False, 'newer_file': None, 'reason': 'No API key'}

    # Check cache first
    cache_key = f"assets:{filename1}|{filename2}"
    reverse_cache_key = f"assets:{filename2}|{filename1}"

    if cache_key in _ai_duplicate_cache:
        return _ai_duplicate_cache[cache_key]
    if reverse_cache_key in _ai_duplicate_cache:
        # Reverse the result
        cached = _ai_duplicate_cache[reverse_cache_key]
        if cached['duplicate']:
            return {
                'duplicate': True,
                'newer_file': filename1 if cached['newer_file'] == filename2 else filename2,
                'reason': cached['reason']
            }
        return cached

    try:
        print(f"  [AI] Comparing release assets: '{filename1}' vs '{filename2}'")

        api_url = "https://openrouter.ai/api/v1/chat/completions"

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an iOS IPA filename analyzer. Given two IPA filenames, determine:\n"
                        "1. Are they the SAME app (possibly with different versions)?\n"
                        "2. If yes, which version is NEWER?\n\n"
                        "Rules:\n"
                        "- Extract app name, version, and tweak name from filenames\n"
                        "- Compare app names (ignore case, spacing, underscores)\n"
                        "- If app names match, compare versions (e.g., v42.3.0 > v42.0.0)\n"
                        "- Consider tweaks: 'Instagram (BHInstagram) v404.0' and 'Instagram (Theta) v404.0' are DIFFERENT\n"
                        "- Consider tweaks: 'Instagram (BHInstagram) v404.0' and 'Instagram (BHInstagram) v402.0' are SAME (different versions)\n\n"
                        "Respond with ONLY a JSON object:\n"
                        "{\n"
                        '  "same_app": true or false,\n'
                        '  "newer_file": "file1" or "file2" (only if same_app is true),\n'
                        '  "app_name": "extracted app name",\n'
                        '  "version1": "extracted version from file1",\n'
                        '  "version2": "extracted version from file2",\n'
                        '  "tweak1": "extracted tweak from file1 or null",\n'
                        '  "tweak2": "extracted tweak from file2 or null",\n'
                        '  "reason": "brief explanation"\n'
                        "}"
                    )
                },
                {
                    "role": "user",
                    "content": f"File 1: {filename1}\nFile 2: {filename2}"
                }
            ],
            "temperature": 0,
            "max_tokens": 300,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/FTRepo/FTRepo",
            "X-Title": "FTRepo Duplicate Cleaner"
        }

        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))

        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content'].strip()
            ai_response = json.loads(content)

            same_app = ai_response.get('same_app', False)
            newer_file_indicator = ai_response.get('newer_file', None)
            reason = ai_response.get('reason', 'No reason provided')

            # Map 'file1'/'file2' to actual filenames
            newer_file = None
            if same_app and newer_file_indicator:
                if newer_file_indicator.lower() == 'file1':
                    newer_file = filename1
                elif newer_file_indicator.lower() == 'file2':
                    newer_file = filename2

            result_dict = {
                'duplicate': same_app,
                'newer_file': newer_file,
                'reason': reason,
                'details': ai_response
            }

            print(f"  [AI] Result: {result_dict}")

            # Cache the result
            _ai_duplicate_cache[cache_key] = result_dict

            return result_dict
        else:
            print(f"  [AI] Unexpected response format")
            return {'duplicate': False, 'newer_file': None, 'reason': 'Unexpected response'}

    except Exception as e:
        print(f"  [AI] Failed to compare assets: {e}")
        return {'duplicate': False, 'newer_file': None, 'reason': f'Error: {e}'}


def clean_duplicates():
    """Main function to clean duplicate apps from apps.json"""
    print("\n" + "=" * 60)
    print("DUPLICATE CLEANER")
    print("=" * 60)
    print(f"[START] Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check for required API key
    if not OPENROUTER_API_KEY:
        print("\n[WARNING] OPENROUTER_API_KEY not set!")
        print("AI duplicate detection will be skipped. Set the API key for better accuracy.")
        print("Get your API key from: https://openrouter.ai/\n")

    # Load tweaks list
    known_tweaks = load_tweaks_list()
    print(f"[TWEAKS] Known tweaks: {', '.join(known_tweaks)}")

    # Load apps.json
    if not os.path.exists(REPO_FILE):
        print(f"[ERROR] {REPO_FILE} not found!")
        return

    print(f"\n[LOAD] Loading {REPO_FILE}...")
    with open(REPO_FILE, 'r', encoding='utf-8') as f:
        repo_data = json.load(f)

    apps = repo_data.get('apps', [])
    print(f"[LOAD] Found {len(apps)} apps in {REPO_FILE}")

    # Get release assets
    release_assets = get_release_assets()

    # Group apps by bundle ID to find potential duplicates
    apps_by_bundle = {}
    for app in apps:
        bundle_id = app.get('bundleIdentifier', '')
        if bundle_id:
            if bundle_id not in apps_by_bundle:
                apps_by_bundle[bundle_id] = []
            apps_by_bundle[bundle_id].append(app)

    print(f"\n[SCAN] Scanning for duplicates...")

    duplicates_found = []
    apps_to_remove = []
    ipas_to_delete = []

    # Find duplicates within same bundle ID
    # NEW STRATEGY: Only look for TRUE duplicates (same app, same or no tweak, different versions)
    for bundle_id, bundle_apps in apps_by_bundle.items():
        if len(bundle_apps) <= 1:
            continue

        print(f"\n[BUNDLE] Found {len(bundle_apps)} apps with bundle ID: {bundle_id}")

        # Group by exact app name pattern (base + tweak)
        app_groups = {}
        for app in bundle_apps:
            app_name = app.get('name', '')
            base_name, tweak_name = extract_base_name_and_tweak(app_name)

            # Create a key that includes tweak (normalized)
            # This ensures "Instagram (BHInstagram)" and "Instagram (Theta)" are different groups
            if tweak_name:
                # Normalize the tweak name for grouping (case-insensitive)
                group_key = f"{base_name}|{tweak_name.lower()}"
            else:
                group_key = f"{base_name}|NO_TWEAK"

            if group_key not in app_groups:
                app_groups[group_key] = []
            app_groups[group_key].append(app)

        # Now check each group for version duplicates
        for group_key, apps_in_group in app_groups.items():
            if len(apps_in_group) <= 1:
                # Only one app in this group, no duplicates
                app = apps_in_group[0]
                app_name = app.get('name', '')
                base_name, tweak_name = extract_base_name_and_tweak(app_name)
                print(f"  [UNIQUE] {app_name}")
                print(f"           Base: {base_name}, Tweak: {tweak_name or 'None'}")

                if tweak_name:
                    if is_tweak_in_list(tweak_name, known_tweaks):
                        print(f"           [OK] Tweak '{tweak_name}' is in tweaks list")
                    else:
                        print(f"           [WARNING] Tweak '{tweak_name}' is NOT in tweaks list")
                        print(f"           [INFO] Consider adding to tweaks_list.json or investigating")
                continue

            # Multiple versions of the same app (with same tweak or no tweak)
            print(f"  [VERSIONS] Found {len(apps_in_group)} versions of same app:")

            # Sort by version (newest first) using proper version comparison
            from functools import cmp_to_key
            apps_in_group_sorted = sorted(
                apps_in_group,
                key=cmp_to_key(lambda a, b: 1 if compare_versions(a.get('version', '0.0.0'), b.get('version', '0.0.0')) else -1),
                reverse=True
            )

            for idx, app in enumerate(apps_in_group_sorted):
                app_name = app.get('name', '')
                version = app.get('version', 'unknown')
                print(f"    [{idx+1}] {app_name} v{version}")

            # Keep the newest, mark others for removal
            newest_app = apps_in_group_sorted[0]
            older_apps = apps_in_group_sorted[1:]

            newest_name = newest_app.get('name')
            newest_version = newest_app.get('version')
            newest_base, newest_tweak = extract_base_name_and_tweak(newest_name)

            print(f"  [KEEP] Keeping newest: {newest_name} v{newest_version}")
            print(f"         Tweak: {newest_tweak or 'None (stock app)'}")

            for old_app in older_apps:
                old_name = old_app.get('name', '')
                old_version = old_app.get('version', 'unknown')
                old_base, old_tweak = extract_base_name_and_tweak(old_name)

                # Safety check: ensure tweaks match
                tweak_match = (newest_tweak or '').lower() == (old_tweak or '').lower()
                if not tweak_match:
                    print(f"  [ERROR] Tweak mismatch detected! This should not happen.")
                    print(f"          Newest: {newest_tweak or 'None'} vs Old: {old_tweak or 'None'}")
                    continue

                print(f"  [REMOVE] Removing older version: {old_name} v{old_version}")
                print(f"           Tweak: {old_tweak or 'None (stock app)'}")

                duplicates_found.append({
                    'name': old_name,
                    'bundle_id': bundle_id,
                    'base_name': old_base,
                    'tweak_name': old_tweak,
                    'reason': f"Older version (v{old_version}) superseded by v{newest_version} (same tweak: {old_tweak or 'stock'})"
                })
                apps_to_remove.append(old_app)

                # Mark IPA for deletion from release
                download_url = old_app.get('downloadURL', '')
                if download_url:
                    filename = download_url.split('/')[-1]
                    filename = urllib.parse.unquote(filename)

                    if filename in release_assets:
                        ipas_to_delete.append({
                            'filename': filename,
                            'asset_id': release_assets[filename]['id'],
                            'app_name': old_name
                        })

    # Skip cross-bundle duplicate check for now
    # Different bundle IDs usually mean legitimately different apps
    # (e.g., official vs sideloaded versions, different forks, etc.)
    print(f"\n[INFO] Skipping cross-bundle duplicate check (different bundle IDs = different apps)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"[FOUND] {len(duplicates_found)} duplicate(s) detected")

    if duplicates_found:
        print("\nDuplicates to be removed:")
        for dup in duplicates_found:
            print(f"  [X] {dup['name']}")
            print(f"      Bundle ID: {dup['bundle_id']}")
            print(f"      Reason: {dup['reason']}")

    if apps_to_remove:
        print(f"\n[ACTION] Removing {len(apps_to_remove)} duplicate app(s) from {REPO_FILE}...")

        # Remove duplicates from apps list
        cleaned_apps = [app for app in apps if app not in apps_to_remove]

        # Update repo data
        repo_data['apps'] = cleaned_apps

        # Backup original file
        backup_file = f"{REPO_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"[BACKUP] Creating backup: {backup_file}")
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump({"apps": apps}, f, indent=2, ensure_ascii=False)

        # Write cleaned data
        print(f"[WRITE] Saving cleaned {REPO_FILE}...")
        with open(REPO_FILE, 'w', encoding='utf-8') as f:
            json.dump(repo_data, f, indent=2, ensure_ascii=False)

        print(f"[SUCCESS] Removed {len(apps_to_remove)} duplicate(s)")
        print(f"[INFO] Apps remaining: {len(cleaned_apps)}")

    if ipas_to_delete:
        print(f"\n[ACTION] Deleting {len(ipas_to_delete)} IPA(s) from release...")

        deleted_count = 0
        for ipa in ipas_to_delete:
            print(f"  Deleting: {ipa['filename']} (for {ipa['app_name']})")
            if delete_release_asset(ipa['asset_id'], ipa['filename']):
                deleted_count += 1

        print(f"[SUCCESS] Deleted {deleted_count}/{len(ipas_to_delete)} IPA(s) from release")

    if not duplicates_found:
        print("\n[OK] No duplicates found in apps.json!")

    # ========== STEP 2: Check Release Assets for Duplicate IPAs ==========
    print("\n" + "=" * 60)
    print("STEP 2: CHECKING RELEASE ASSETS FOR DUPLICATES")
    print("=" * 60)

    if not release_assets:
        print("[INFO] No release assets to check")
    else:
        print(f"[SCAN] Checking {len(release_assets)} release assets for duplicate IPAs...")

        # Get list of IPA files only
        ipa_assets = {name: data for name, data in release_assets.items() if name.endswith('.ipa')}
        print(f"[SCAN] Found {len(ipa_assets)} IPA files in release")

        if len(ipa_assets) < 2:
            print("[INFO] Not enough IPA files to compare")
        else:
            # Use AI to analyze ALL filenames at once (much more efficient!)
            asset_filenames = list(ipa_assets.keys())
            duplicate_groups = check_all_release_assets_with_ai(asset_filenames, known_tweaks)

            if duplicate_groups:
                print(f"\n[DUPLICATES] Found {len(duplicate_groups)} duplicate group(s)")

                # Collect all files to delete
                files_to_delete = []
                for group in duplicate_groups:
                    keep_file = group.get('keep')
                    delete_files = group.get('delete', [])
                    reason = group.get('reason', 'No reason provided')
                    app_name = group.get('app_name', 'Unknown')
                    tweak_name = group.get('tweak_name')

                    # Extract tweak info from filenames for detailed logging
                    keep_base, keep_tweak = extract_base_name_and_tweak(keep_file)

                    print(f"\n[GROUP] {app_name}" + (f" ({tweak_name})" if tweak_name else ""))
                    print(f"  Base Name: {keep_base}")
                    print(f"  Tweak: {keep_tweak or 'None (stock app)'}")
                    print(f"  [KEEP] {keep_file}")
                    print(f"  [DELETE] {len(delete_files)} older version(s)")
                    for old_file in delete_files:
                        delete_base, delete_tweak = extract_base_name_and_tweak(old_file)
                        # Double-check that tweaks match (safety check)
                        tweak_match_indicator = "✓" if (keep_tweak or '').lower() == (delete_tweak or '').lower() else "⚠ MISMATCH"
                        print(f"    - {old_file} [{tweak_match_indicator}]")
                        if old_file in ipa_assets:
                            files_to_delete.append({
                                'filename': old_file,
                                'asset_id': ipa_assets[old_file]['id'],
                                'kept_file': keep_file,
                                'reason': reason,
                                'base_name': delete_base,
                                'tweak_name': delete_tweak
                            })
                    print(f"  Reason: {reason}")

                # Delete older asset files
                if files_to_delete:
                    print(f"\n[ACTION] Deleting {len(files_to_delete)} older IPA(s) from release...")

                    deleted_count = 0
                    for file_info in files_to_delete:
                        print(f"  [DELETE] {file_info['filename']} (superseded by {file_info['kept_file']})")
                        if delete_release_asset(file_info['asset_id'], file_info['filename']):
                            deleted_count += 1

                    print(f"[SUCCESS] Deleted {deleted_count}/{len(files_to_delete)} older IPA(s)")
                else:
                    print("\n[WARNING] Duplicate groups found but no valid files to delete")
            else:
                print("\n[OK] No duplicate IPAs found in release assets!")

    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE")
    print("=" * 60)
    print(f"[FINISH] Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    clean_duplicates()
