#!/usr/bin/env python3
"""
Convert apps.json to AltStore-compatible altstore.json with unique bundle IDs.
Apps with tweaks listed in tweaks_list.json get modified bundle IDs.
"""

import json
import re
import sys
from pathlib import Path


def load_json_file(filepath):
    """Load and parse a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {filepath} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing {filepath}: {e}")
        sys.exit(1)


def extract_tweak_from_name(app_name, known_tweaks):
    """
    Extract tweak name from app name if it's in parentheses.
    Returns (base_name, tweak_name) or (app_name, None) if no tweak found.
    """
    # Pattern to match tweaks in parentheses
    pattern = r'^(.+?)\s*\(([^)]+)\)\s*$'
    match = re.match(pattern, app_name)

    if match:
        base_name = match.group(1).strip()
        potential_tweak = match.group(2).strip()

        # Check if the extracted name matches a known tweak
        for tweak in known_tweaks:
            if tweak.lower() == potential_tweak.lower():
                return base_name, tweak

    return app_name, None


def create_unique_bundle_id(original_bundle_id, tweak_name):
    """
    Create a unique bundle ID by appending the tweak name.
    Example: com.burbn.instagram + Theta -> com.burbn.instagram.theta
    """
    if not tweak_name:
        return original_bundle_id

    # Convert tweak name to lowercase for bundle ID
    tweak_suffix = tweak_name.lower()

    # Append the tweak name to the bundle ID
    return f"{original_bundle_id}.{tweak_suffix}"


def convert_app_to_altstore_format(app, known_tweaks):
    """
    Convert a single app from apps.json format to AltStore format.
    Modifies bundle ID if the app has a known tweak.
    """
    app_name = app.get('name', '')
    base_name, tweak_name = extract_tweak_from_name(app_name, known_tweaks)

    # Get original bundle ID
    original_bundle_id = app.get('bundleIdentifier', '')

    # Create unique bundle ID if there's a tweak
    bundle_id = create_unique_bundle_id(original_bundle_id, tweak_name)

    # Convert versions array
    altstore_versions = []
    for version in app.get('versions', []):
        altstore_version = {
            'version': version.get('version', ''),
            'date': version.get('date', ''),
            'size': version.get('size', 0),
            'downloadURL': version.get('downloadURL', '')
        }

        # Add buildVersion if available (some sources use 'buildVersion')
        # If not available, use version as buildVersion
        altstore_version['buildVersion'] = version.get('buildVersion', version.get('version', ''))

        # Add localizedDescription if available
        if 'localizedDescription' in version:
            altstore_version['localizedDescription'] = version['localizedDescription']

        # Add minOSVersion if available
        if 'minOSVersion' in version:
            altstore_version['minOSVersion'] = version['minOSVersion']

        altstore_versions.append(altstore_version)

    # Build the AltStore app object
    altstore_app = {
        'name': app_name,  # Keep the full name with tweak in parentheses
        'bundleIdentifier': bundle_id,
        'developerName': app.get('developerName', ''),
        'localizedDescription': app.get('localizedDescription', ''),
        'iconURL': app.get('iconURL', ''),
        'versions': altstore_versions,
        'appPermissions': app.get('appPermissions', {})
    }

    # Add optional fields if they exist
    optional_fields = ['subtitle', 'tintColor', 'category', 'screenshots']
    for field in optional_fields:
        if field in app:
            altstore_app[field] = app[field]

    return altstore_app


def convert_to_altstore(apps_data, tweaks_data):
    """
    Convert apps.json to AltStore format with unique bundle IDs.
    """
    known_tweaks = tweaks_data.get('tweaks', [])

    # Build AltStore source structure
    altstore_source = {
        'name': apps_data.get('name', 'FTRepo'),
        'identifier': apps_data.get('identifier', 'xyz.ftrepo'),
    }

    # Add optional source fields if they exist
    optional_source_fields = ['subtitle', 'description', 'iconURL', 'headerURL',
                              'website', 'tintColor', 'featuredApps']
    for field in optional_source_fields:
        if field in apps_data:
            altstore_source[field] = apps_data[field]

    # Convert apps
    altstore_apps = []
    for app in apps_data.get('apps', []):
        altstore_app = convert_app_to_altstore_format(app, known_tweaks)
        altstore_apps.append(altstore_app)

    altstore_source['apps'] = altstore_apps

    # Add news array (empty for now, can be populated if needed)
    altstore_source['news'] = apps_data.get('news', [])

    return altstore_source


def main():
    """Main conversion function."""
    # Load input files
    print("Loading apps.json...")
    apps_data = load_json_file('apps.json')

    print("Loading tweaks_list.json...")
    tweaks_data = load_json_file('tweaks_list.json')

    print("Converting to AltStore format...")
    altstore_data = convert_to_altstore(apps_data, tweaks_data)

    # Write output
    output_file = 'altstore.json'
    print(f"Writing to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(altstore_data, f, indent=2, ensure_ascii=False)

    print(f"[OK] Successfully created {output_file}")
    print(f"  Total apps: {len(altstore_data['apps'])}")

    # Count how many apps have modified bundle IDs
    modified_count = 0
    for app in altstore_data['apps']:
        app_name = app['name']
        _, tweak_name = extract_tweak_from_name(app_name, tweaks_data.get('tweaks', []))
        if tweak_name:
            modified_count += 1

    print(f"  Apps with unique bundle IDs (tweaked): {modified_count}")


if __name__ == '__main__':
    main()
