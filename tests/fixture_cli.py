import argparse
import json
import sys
import time


parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=("echo", "json", "fail", "sleep", "flood"))
parser.add_argument("value", nargs="?", default="")
args = parser.parse_args()

if args.mode == "echo":
    print(args.value or sys.stdin.read(), end="")
elif args.mode == "json":
    print(json.dumps({"ok": True, "value": args.value}, sort_keys=True))
elif args.mode == "fail":
    print(args.value, file=sys.stderr)
    raise SystemExit(7)
elif args.mode == "sleep":
    time.sleep(float(args.value))
elif args.mode == "flood":
    print("x" * int(args.value), end="")
