"""Extract English glosses from CC-CEDICT -> build/cedict-defs.json.

Usage:
    python scripts/build/defs.py [BUILD_DIR]
"""
import json
import re
import sys
from pathlib import Path

build = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent.parent / "build"
dset = build / "dset"

defs: dict[str, str] = {}
with (dset / "cedict_ts.u8").open(encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\S+)\s+(\S+)\s+\[[^\]]*\]\s+/(.*)/$", line)
        if not m:
            continue
        trad, simp, gloss = m.group(1), m.group(2), m.group(3)
        gloss = re.sub(r"/", "; ", gloss).strip()
        if not gloss:
            continue
        defs.setdefault(simp, gloss)
        if trad != simp:
            defs.setdefault(trad, gloss)

out = build / "cedict-defs.json"
out.write_text(json.dumps(defs, ensure_ascii=False), encoding="utf-8")
print(f"wrote {out} ({len(defs)} keys)")
