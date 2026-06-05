import json, sys
import matplotlib.pyplot as plt

anki_deck = sys.argv[1]
freq_file = sys.argv[2]

def extract_hanzi(path):
    chars, singles = set(), set()
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip() or line[0] == '#':
                continue
            c = line.split('[')[0].strip()
            chars.update(c)
            if len(c) == 1:
                singles.add(c)
    return chars, singles

deck_chars, deck_singles = extract_hanzi(anki_deck)
freq = json.load(open(freq_file, 'r', encoding='utf-8'))

def coverage_plot(freq, deck, limit=3000):
    found = [sum(1 for j in range(i+1) if freq[j] in deck) for i in range(min(limit, len(freq)))]
    total = len(found)
    plt.figure(figsize=(12, 8))
    plt.plot(range(total), found, 'b-', linewidth=2)
    plt.plot([0, total], [0, total], 'r--', alpha=0.5, label='perfect')
    for ratio, color in [(1.0, 'green'), (0.98, 'red'), (0.95, 'purple'), (0.9, 'orange')]:
        for i in range(total):
            if found[i] / (i + 1) < ratio:
                plt.axvline(x=i, color=color, linewidth=2, label=f'<{ratio*100:.0f}% at {i}')
                break
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()

coverage_plot(freq, deck_chars, 3000)

total = len(freq)
in_deck = sum(1 for c in freq if c in deck_chars)
missing = sorted(set(freq[:in_deck + 500]) - deck_chars, key=lambda c: freq.index(c))
rare = sorted(deck_chars - set(freq))

print(f"deck chars: {len(deck_chars)}  singles: {len(deck_singles)}")
print(f"freq list: {total}  in deck: {in_deck}  coverage: {in_deck/total*100:.1f}%")
if missing:
    print(f"next {min(500, len(missing))} missing: {''.join(missing[:500])}")
if rare:
    print(f"rare (in deck, not in freq): {''.join(rare[:50])}")
