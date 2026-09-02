import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("name")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()

if args.json:
    print(json.dumps({"greeting": f"Hello, {args.name}!"}))
else:
    print(f"Hello, {args.name}!")
