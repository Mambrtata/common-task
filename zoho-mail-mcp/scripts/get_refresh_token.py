#!/usr/bin/env python3
"""Jednorazové získanie refresh tokenu pre Zoho Mail (Self Client).

Postup:
  1. Otvor https://api-console.zoho.<dc> a vytvor klienta typu **Self Client**.
  2. Na karte „Generate Code" zadaj scope:
         ZohoMail.accounts.READ,ZohoMail.folders.READ,ZohoMail.messages.READ
     Time Duration daj 10 minút, Scope Description čokoľvek.
  3. Skopírovaný kód vlož sem:
         python3 scripts/get_refresh_token.py --dc eu --client-id ... \
             --client-secret ... --code ...

Vypísaný refresh token vlož do ZOHO_REFRESH_TOKEN. Access token si server
obnovuje sám a nikam ho neukladá.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Import až po úprave cesty, nech skript funguje aj bez inštalácie balíčka.
from zoho_mail_mcp.config import DATA_CENTERS, SCOPE_STRING
from zoho_mail_mcp.envfile import parse_env_text, update_env_text


def exchange_code(
    dc: str, client_id: str, client_secret: str, code: str, redirect_uri: str | None
) -> dict:
    _, accounts_base = DATA_CENTERS[dc]
    params = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "scope": SCOPE_STRING,
    }
    if redirect_uri:
        params["redirect_uri"] = redirect_uri

    request = urllib.request.Request(
        f"{accounts_base}/oauth/v2/token",
        data=urllib.parse.urlencode(params).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dc", choices=sorted(DATA_CENTERS), help="dátové centrum účtu")
    parser.add_argument("--client-id")
    parser.add_argument("--client-secret")
    parser.add_argument("--code", required=True, help="kód z Self Client → Generate Code")
    parser.add_argument("--redirect-uri", default=None, help="len ak si použil Server-based Application")
    parser.add_argument(
        "--from-env",
        metavar="SÚBOR",
        help="prečíta ZOHO_DC, CLIENT_ID a CLIENT_SECRET z konfigurácie, nech ich netreba prepisovať",
    )
    parser.add_argument(
        "--write-env",
        metavar="SÚBOR",
        help="zapíše získaný refresh token rovno do konfigurácie",
    )
    args = parser.parse_args()

    dc, client_id, client_secret = args.dc, args.client_id, args.client_secret

    if args.from_env:
        try:
            stored = parse_env_text(Path(args.from_env).read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"Nepodarilo sa prečítať {args.from_env}: {exc}", file=sys.stderr)
            return 1
        dc = dc or stored.get("ZOHO_DC")
        client_id = client_id or stored.get("ZOHO_CLIENT_ID")
        client_secret = client_secret or stored.get("ZOHO_CLIENT_SECRET")

    missing = [
        name
        for name, value in (
            ("--dc", dc), ("--client-id", client_id), ("--client-secret", client_secret)
        )
        if not value
    ]
    if missing:
        print(
            "Chýba: " + ", ".join(missing) + ". Zadaj ich prepínačmi alebo použi --from-env.",
            file=sys.stderr,
        )
        return 1
    if dc not in DATA_CENTERS:
        print(f"Neznáme dátové centrum {dc!r}.", file=sys.stderr)
        return 1

    payload = exchange_code(dc, client_id, client_secret, args.code, args.redirect_uri)

    if "error" in payload:
        print(f"Zoho vrátilo chybu: {payload['error']}", file=sys.stderr)
        print(f"Celá odpoveď: {json.dumps(payload, ensure_ascii=False)}", file=sys.stderr)
        if payload["error"] == "invalid_code":
            print("Kód je jednorazový a rýchlo expiruje – vygeneruj nový.", file=sys.stderr)
        if payload["error"] in ("invalid_client", "general_error"):
            print(
                f"Skontroluj, či Self Client naozaj žije v dátovom centre {dc} "
                f"(konzola na api-console.zoho.{'com' if dc == 'us' else dc}) "
                "a či sú Client ID a Secret z tej istej aplikácie.",
                file=sys.stderr,
            )
        return 1

    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        print(
            "Odpoveď neobsahuje refresh_token. Pri Self Clientovi ho Zoho vydá "
            "len raz – ak si kód použil druhýkrát, vygeneruj nový.",
            file=sys.stderr,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    if args.write_env:
        target = Path(args.write_env)
        try:
            original = target.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Nepodarilo sa prečítať {target}: {exc}", file=sys.stderr)
            return 1
        updated = update_env_text(
            original,
            {
                "ZOHO_DC": dc,
                "ZOHO_CLIENT_ID": client_id,
                "ZOHO_CLIENT_SECRET": client_secret,
                "ZOHO_REFRESH_TOKEN": refresh_token,
            },
        )
        target.write_text(updated, encoding="utf-8")
        print(f"Refresh token som zapísal do {target}.")
        print("Token sa nikde nevypisuje, nič neprepisuj ručne.\n")
        print("Reštartuj službu:")
        print("    sudo systemctl restart zoho-mail-mcp")
        return 0

    print("Hotovo.\n")
    print("Ak konektor beží ako systemd služba, otvor /etc/zoho-mail-mcp.env")
    print("a doplň tieto riadky – bez slova 'export' a bez úvodzoviek:\n")
    print(f"ZOHO_DC={dc}")
    print(f"ZOHO_CLIENT_ID={client_id}")
    print(f"ZOHO_CLIENT_SECRET={client_secret}")
    print(f"ZOHO_REFRESH_TOKEN={refresh_token}")
    print("\nPotom službu reštartuj:")
    print("    sudo systemctl restart zoho-mail-mcp\n")
    print("V stdio režime sú to tie isté hodnoty ako premenné prostredia,")
    print("tam sa pred ne 'export' píše.\n")
    print("Refresh token je heslo do schránky – nekomituj ho do gitu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
