#!/usr/bin/env python3
"""
Run this script ONCE locally to obtain a Gmail OAuth2 refresh token.
The refresh token never expires unless you revoke access, so you only need to do this once.

Prerequisites:
    1. Go to https://console.cloud.google.com/
    2. Create a project (or select an existing one)
    3. Enable the Gmail API:  APIs & Services > Enable APIs > search "Gmail API" > Enable
    4. Create OAuth 2.0 credentials:
         APIs & Services > Credentials > Create Credentials > OAuth client ID
         Application type: Desktop app
         Download or copy the Client ID and Client Secret
    5. Add your Gmail address as a Test User:
         APIs & Services > OAuth consent screen > Test users > Add users

Usage:
    pip install google-auth-oauthlib
    python scripts/get_gmail_refresh_token.py --client-id YOUR_ID --client-secret YOUR_SECRET

Then copy the printed values into your .env and Render environment variables.
"""

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Obtain a Gmail OAuth2 refresh token for use with MAIL_PROVIDER=gmail"
    )
    parser.add_argument(
        "--client-id", required=True, help="OAuth2 Client ID from Google Cloud Console"
    )
    parser.add_argument(
        "--client-secret",
        required=True,
        help="OAuth2 Client Secret from Google Cloud Console",
    )
    args = parser.parse_args()

    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # Opens a browser window for you to sign in and grant permission
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    print("\n" + "=" * 60)
    print("SUCCESS — add these to your .env and Render environment:")
    print("=" * 60)
    print(f"MAIL_PROVIDER=gmail")
    print(f"MAIL_FROM=your.gmail@gmail.com")
    print(f"MAIL_FROM_NAME=Lux")
    print(f"GMAIL_CLIENT_ID={args.client_id}")
    print(f"GMAIL_CLIENT_SECRET={args.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
