"""Create local PostgreSQL credentials without displaying them."""

import secrets
from pathlib import Path

from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / ".env"
    if not destination.exists():
        destination.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    values = dotenv_values(destination)
    if not values.get("POSTGRES_PASSWORD"):
        set_key(str(destination), "POSTGRES_PASSWORD", secrets.token_urlsafe(32))
    print("Local PostgreSQL credentials ready in .env (password hidden).")


if __name__ == "__main__":
    main()
