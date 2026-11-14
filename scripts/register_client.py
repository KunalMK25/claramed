"""Register an integration client. Prints the API key and webhook secret ONCE.

Example:
  python scripts/register_client.py --name jeevacare \
      --webhook-url https://jeevacare.example/api/webhook/claramed-callback \
      --allowed-host res.cloudinary.com
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database.connection import get_db_context  # noqa: E402
from backend.services.client_registry import register_client  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--webhook-url", required=True)
    p.add_argument("--allowed-host", action="append", required=True, dest="hosts",
                   help="hostname ClaraMed may download files from (repeatable; '*.example.com' allowed)")
    p.add_argument("--callback-token", help="optional bearer token sent to the client's webhook")
    p.add_argument("--description")
    args = p.parse_args()
    try:
        with get_db_context() as db:
            reg = register_client(
                db, name=args.name, webhook_url=args.webhook_url, allowed_file_hosts=args.hosts,
                description=args.description, callback_auth_token=args.callback_token,
            )
            print(f"Registered client: {reg.client.client_name}")
            print(f"API key (shown once):        {reg.api_key}")
            print(f"Webhook secret (shown once): {reg.webhook_secret}")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
