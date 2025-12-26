#!/usr/bin/env python3
"""
Helper script to generate a Telegram session string for use in automated environments.
This allows you to authenticate once locally and then use the session string in CI/CD.
"""

import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

def main():
    print("Telegram Session String Generator")
    print("=" * 50)
    print()

    # Get API credentials
    api_id = input("Enter your TELEGRAM_API_ID: ").strip()
    api_hash = input("Enter your TELEGRAM_API_HASH: ").strip()

    if not api_id or not api_hash:
        print("Error: API ID and Hash are required!")
        return

    try:
        api_id = int(api_id)
    except ValueError:
        print("Error: API ID must be a number!")
        return

    print()
    print("Connecting to Telegram...")
    print("You will be prompted to enter your phone number and verification code.")
    print()

    try:
        with TelegramClient(StringSession(), api_id, api_hash) as client:
            session_string = client.session.save()

            print()
            print("=" * 50)
            print("Success! Your session string:")
            print()
            print(session_string)
            print()
            print("=" * 50)
            print()
            print("Add this to your GitHub repository secrets as:")
            print("TELEGRAM_SESSION_STRING")
            print()
            print("IMPORTANT: Keep this string secure! It provides access to your account.")
            print()
    except Exception as e:
        print(f"Error: {e}")
        return

if __name__ == '__main__':
    main()
