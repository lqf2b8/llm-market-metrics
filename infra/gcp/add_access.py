"""Add one access entry to a dataset JSON (from `bq show --format=prettyjson`) in place.

Exits 0 if the entry was added, 1 if an equal entry was already there.
"""

import json
import sys

path, entry = sys.argv[1], json.loads(sys.argv[2])
dataset = json.load(open(path))
access = dataset.setdefault("access", [])
if entry in access:
    sys.exit(1)
access.append(entry)
json.dump(dataset, open(path, "w"))
