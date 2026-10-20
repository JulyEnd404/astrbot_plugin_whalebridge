#!/usr/bin/env python3
"""Read ONLY status/listener counts; never drains messages or sends anything."""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import settings_from  # noqa: E402


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-env", default="MIMICWX_API_TOKEN")
    args = parser.parse_args()
    try:
        settings = settings_from(
            dict(
                id="read-only-check",
                api_url=args.url,
                api_token_env=args.token_env,
                risk_acknowledged=True,
                groups=["synthetic-validation-only"],
                self_name="synthetic",
                mention_names=["synthetic"],
            )
        )
        opener = build_opener(NoRedirect(), ProxyHandler({}))
        results = {}
        for endpoint in ["/status", "/listen"]:
            req = Request(
                settings.api_url + endpoint,
                headers={"Authorization": "Bearer " + settings.api_token},
            )
            with opener.open(req, timeout=10) as response:
                body = response.read(4 * 1024 * 1024 + 1)
                if len(body) > 4 * 1024 * 1024:
                    raise ValueError("response_too_large")
                results[endpoint] = json.loads(body)
        status, listeners = results["/status"], results["/listen"]
        if not isinstance(status, dict) or not isinstance(listeners, list):
            raise ValueError("incompatible_response_shape")
        print(
            json.dumps(
                {
                    "logged_in": status.get("status") == "已登录",
                    "listener_count": len(listeners),
                    "read_only": True,
                }
            )
        )
        return 0
    except (HTTPError, URLError, ValueError, OSError) as error:
        # Exception strings can include URLs or response bodies. Do not print them.
        print(
            "Check failed: "
            + type(error).__name__
            + "; check private configuration without publishing credentials.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
