#!/usr/bin/env python3
"""Load the open-source gateway's context instructions (setup/open_source_gateway/context/) onto its MCP servers.

The open-source MCP gateway has no context store like Connect AI's. The closest native feature is a
per-server `instructions` field, which the open-source gateway merges into its MCP initialize response. This
script sets that field from one markdown file per server, through the open-source gateway's management API
(PUT /v1/mcp/server).

Instructions belong to the server, not to a key: every key that reaches these servers gets them.
run_matrix.py appends them to the system prompt for the open_source_gateway condition, and stops if the
gateway's instructions lack the context.

  python3 setup/open_source_gateway/gateway_instructions.py            # show what would change
  python3 setup/open_source_gateway/gateway_instructions.py --apply    # write the instructions
  python3 setup/open_source_gateway/gateway_instructions.py --clear    # remove them again

Reads GATEWAY_URL and GATEWAY_ADMIN_KEY (the open-source gateway's admin key) from this repo's .env, or the admin
key from the open-source gateway's own env file with --gateway-env (LITELLM_MASTER_KEY there). Neither value is
printed.

Servers are found by alias through GET /v1/mcp/server. Some gateway builds return an empty list
there even for the admin key; pass each server's id instead (shown in the admin UI):
  python3 setup/open_source_gateway/gateway_instructions.py --id snowflake=<id> --id salesforce=<id>
"""
import argparse, os, sys

import requests

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)
from core.envutil import load_env

CONTEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "context")
# gateway server alias -> instructions file. The aliases are the tool-name prefixes the models saw
# (warehouse, CRM and ITSM servers). The ITSM server is left out by default: when it returns its own
# initialize instructions, the open-source gateway passes them through, and setting this field would replace
# them. If it can't return instructions, add --map servicenow=itsm.md (with the others).
DEFAULT_MAP = {"snowflake": "warehouse.md", "salesforce": "crm.md"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the instructions")
    ap.add_argument("--clear", action="store_true", help="remove the instructions")
    ap.add_argument("--gateway-env", help="the open-source gateway's own env file, for its admin key")
    ap.add_argument("--map", action="append", metavar="ALIAS=FILE",
                    help="server alias and instructions file, repeatable (default: snowflake, "
                         "salesforce)")
    ap.add_argument("--id", action="append", default=[], metavar="ALIAS=SERVER_ID",
                    help="server id for an alias, when the server list comes back empty")
    args = ap.parse_args()

    load_env(os.path.join(HERE, ".env"))
    if args.gateway_env:
        load_env(args.gateway_env)
    url = os.environ.get("GATEWAY_URL", "").rstrip("/")
    key = os.environ.get("GATEWAY_ADMIN_KEY") or os.environ.get("LITELLM_MASTER_KEY")
    if not url or not key:
        raise SystemExit("!! need GATEWAY_URL and the open-source gateway admin key (GATEWAY_ADMIN_KEY in .env, or --gateway-env)")
    mapping = dict(m.split("=", 1) for m in args.map) if args.map else DEFAULT_MAP
    headers = {"Authorization": f"Bearer {key}"}

    r = requests.get(f"{url}/v1/mcp/server", headers=headers, timeout=30)
    r.raise_for_status()
    servers = {(s.get("alias") or s.get("server_name") or "").lower(): s for s in r.json()}
    for pair in args.id:
        alias, sid = pair.split("=", 1)
        r = requests.get(f"{url}/v1/mcp/server/{sid}", headers=headers, timeout=30)
        if r.status_code >= 400:
            raise SystemExit(f"!! server {sid}: HTTP {r.status_code}: {r.text[:300]}")
        servers[alias.lower()] = r.json()

    for alias, fname in mapping.items():
        s = servers.get(alias.lower())
        if not s:
            raise SystemExit(f"!! no MCP server with alias {alias!r} (found: {', '.join(sorted(servers)) or 'none'})"
                             " -- pass its id with --id ALIAS=SERVER_ID")
        text = None if args.clear else open(os.path.join(CONTEXT_DIR, fname), encoding="utf-8").read().strip()
        before = len(s.get("instructions") or "")
        after = len(text or "")
        action = "clear" if args.clear else f"set from {fname}"
        print(f"{alias:<12} {s['server_id']}  {action}: {before} -> {after} chars")
        if args.apply or args.clear:
            r = requests.put(f"{url}/v1/mcp/server", headers=headers, timeout=30,
                             json={"server_id": s["server_id"], "instructions": text})
            if r.status_code >= 400:
                raise SystemExit(f"!! {alias}: HTTP {r.status_code}: {r.text[:300]}")

    if not (args.apply or args.clear):
        print("\nDry run. Re-run with --apply to write, or --clear to remove.")


if __name__ == "__main__":
    main()
