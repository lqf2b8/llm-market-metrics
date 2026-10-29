"""Add one access entry to a dataset JSON (from `bq show --format=prettyjson`) in place.

Exits 0 if the entry was added, 1 if an equal entry was already there.
"""

import json
import sys
from pathlib import Path

path, entry = sys.argv[1], json.loads(sys.argv[2])
dataset = json.loads(Path(path).read_text())
access = dataset.setdefault("access", [])
if entry in access:
    sys.exit(1)
access.append(entry)
Path(path).write_text(json.dumps(dataset))
