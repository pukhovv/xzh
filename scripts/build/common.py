"""Shared constants and utilities for build scripts."""
from __future__ import annotations

TRANS = set("斯尔尼卡莉艾莱蒂瑞娜妮玛莎琳弗乔迪奥洛"
            "曼伯佩詹森埃塔卢兹逊翰娅姬茜黛柯沃伊姆"
            "萨芭啡芬冈狄杜罕穆韦丘芙朱梅")

def parse_chr(path: str, encoding: str = "gb2312") -> list[str]:
    chars: list[str] = []
    with open(path, "r", encoding=encoding, errors="replace") as f:
        for i, line in enumerate(f):
            if i < 3:
                continue
            parts = line.strip().split("\t")
            if parts and parts[0]:
                c = parts[0].strip()
                if c and len(c) == 1 and '\ufffd' not in c:
                    chars.append(c)
    return chars
