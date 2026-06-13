import json, sys
from pathlib import Path
from common import parse_chr

build = Path(sys.argv[1])
dset = build / "dset"
chr_path = dset / "SUBTLEX-CH-CHR"
clist = "".join(parse_chr(str(chr_path)))
build.mkdir(parents=True, exist_ok=True)
with (build / "freqs.json").open("w", encoding="utf-8") as f:
    json.dump(clist, f, ensure_ascii=False)
print(f"freqs: {len(clist)} chars")
