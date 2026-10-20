#!/usr/bin/env python3
"""Print local routing identifiers; never connects to WeChat."""

import argparse
import hashlib
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="+", help="Exact, unambiguous chat display names")
    parser.add_argument("--platform-id", default="mimicwx-wechat")
    args = parser.parse_args()
    for name in args.names:
        gid = "wxg_" + hashlib.sha256(name.encode()).hexdigest()[:24]
        print(
            json.dumps(
                {"group_id": gid, "unified_msg_origin": f"{args.platform_id}:GroupMessage:{gid}"},
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
