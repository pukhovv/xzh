import json, re, sys
from collections import Counter

corpus = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "output.json"

with open(corpus, 'r', encoding='utf-8') as f:
    text = f.read()

chars = re.findall(r'[\u4e00-\u9fff]', text)
freq = Counter(chars)
sorted_chars = sorted(freq.items(), key=lambda x: x[1], reverse=True)
char_string = ''.join([char for char, _ in sorted_chars])

with open(out, 'w', encoding='utf-8') as f:
    json.dump(char_string, f, ensure_ascii=False)

print(f"chars: {len(chars)} unique: {len(sorted_chars)} -> {out}")
