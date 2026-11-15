import os
import sys
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
PORT = int(os.getenv("PORT", "8080"))

# Check for common Azure hosting environment variables
IS_AZURE_APP_SERVICE = bool(os.getenv("WEBSITE_SITE_NAME"))
IS_AZURE_CONTAINER_APP = bool(os.getenv("CONTAINER_APP_NAME"))
IS_AZURE = IS_AZURE_APP_SERVICE or IS_AZURE_CONTAINER_APP or bool(os.getenv("AZURE_ENV"))

AZURE_APP_NAME = (
    os.getenv("WEBSITE_SITE_NAME")
    or os.getenv("CONTAINER_APP_NAME")
    or os.getenv("AZURE_APP_NAME")
    or "Local / Unspecified"
)


def validate_config():
    """Verify that required credentials exist before starting."""
    if not DISCORD_TOKEN or DISCORD_TOKEN == "your_discord_bot_token_here":
        print("\n" + "=" * 65)
        print(" [!] ERROR: DISCORD_TOKEN is missing or still set to default.")
        print("=" * 65)
        print(" To fix this:")
        print(" 1. Create a Discord Bot at: https://discord.com/developers/applications")
        print(" 2. Copy your Bot Token under the 'Bot' tab.")
        print(" 3. Create or update your .env file with:")
        print("      DISCORD_TOKEN=your_token_here")
        print("=" * 65 + "\n")
        return False
    return True
