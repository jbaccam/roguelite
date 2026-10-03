"""Chest pacing simulator for RARITY_GODLY_ARMOR.md (2026-09-28).

Mirrors ChestConfig's rules: fixed item count per chest, whole + fractional Rare/Epic counts,
Legendary/Godly chances with pity, all copies of one rarity on one item (1-3 until 2026-10-03).
A simulated player spends every emerald on one chest type and upgrades greedily.

INCOME IS A GUESS (emeralds per hour played, incl. 200 daily per ~1.5 h session). Replace it
with real run data when available. Run: python chest_pace_sim.py
"""
import random, statistics as st

POOL = {'Common': 12, 'Rare': 12, 'Epic': 5, 'Legendary': 7, 'Godly': 6}
UP = {'Common': [2, 6, 15], 'Rare': [2, 4, 8], 'Epic': [1, 2, 4], 'Legendary': [1, 2, 3], 'Godly': [1, 1, 2]}
# price, items, rare, epic, legendary, godly   (Wooden has no pity)
CH = {'Wooden': (60, 3, .25, .02, .002, 0), 'Silver': (160, 6, 1, .08, .008, .0005),
      'Gold': (300, 10, 2, .25, .03, .002), 'Magical': (700, 18, 4, 1, .1, .006)}
LEGENDARY_PITY, GODLY_PITY = 50, 150


def income(hours):
    return (200 if hours < 4 else 450 if hours < 15 else 900 if hours < 40 else 1500) + 200 / 1.5


def stacks(c): return 0 if c <= 0 else 1


def group(rarity, copies, tally):
    ids = [f'{rarity}{i}' for i in range(POOL[rarity])]
    n = min(stacks(copies), len(ids))
    if not n: return
    picked = random.sample(ids, n); shares = [1] * n
    for _ in range(copies - n):
        i = 0 if random.random() < .55 else random.randrange(n); shares[i] += 1
    shares.sort(reverse=True)
    for i, wid in enumerate(picked): tally[wid] = tally.get(wid, 0) + shares[i]


def chance(x): return int(x) + (1 if random.random() < x % 1 else 0)


def open_chest(kind, lpity, gpity):
    _, items, r, e, l, g = CH[kind]; pity = kind != 'Wooden'
    rare, epic = chance(r), chance(e)
    leg = 1 if (pity and lpity >= LEGENDARY_PITY - 1) or random.random() < l else 0
    god = 1 if (pity and gpity >= GODLY_PITY - 1) or random.random() < g else 0
    t = {}
    group('Common', items - rare - epic - leg - god, t); group('Rare', rare, t)
    group('Epic', epic, t); group('Legendary', leg, t); group('Godly', god, t)
    return t, leg, god


def tier(rarity, have):
    if have <= 0: return 0
    left, t = have - 1, 1
    for cost in UP[rarity]:
        if left >= cost: left -= cost; t += 1
        else: break
    return t


def run(kind, trials=150, cap=600):
    keys = ['starter T2', 'first Epic', 'first Legendary', 'first T4', 'first Godly', 'all Legendaries', 'all non-Godly T4']
    out = {k: [] for k in keys}
    ids = [f'{r}{i}' for r in POOL if r != 'Godly' for i in range(POOL[r])]
    for _ in range(trials):
        have = {'Common0': 1}; lp = gp = 0; h = bank = 0.0; got = {}
        while h < cap and len(got) < len(keys):
            bank += income(h) * .1; h += .1
            while bank >= CH[kind][0]:
                bank -= CH[kind][0]; t, l, g = open_chest(kind, lp, gp)
                lp = 0 if l else lp + 1; gp = 0 if g else gp + 1
                for k, v in t.items(): have[k] = have.get(k, 0) + v
            T = lambda i: tier(i.rstrip('0123456789'), have.get(i, 0))
            checks = {'starter T2': T('Common0') >= 2,
                      'first Epic': any(k.startswith('Epic') for k in have),
                      'first Legendary': any(k.startswith('Legendary') for k in have),
                      'first T4': any(T(i) >= 4 for i in ids),
                      'first Godly': any(k.startswith('Godly') for k in have),
                      'all Legendaries': all(have.get(f'Legendary{i}', 0) for i in range(POOL['Legendary'])),
                      'all non-Godly T4': all(T(i) >= 4 for i in ids)}
            for k, v in checks.items():
                if v and k not in got: got[k] = h
        for k in keys: out[k].append(got.get(k, cap))
    return {k: round(st.median(v), 1) for k, v in out.items()}


if __name__ == '__main__':
    random.seed(5)
    for kind in ['Wooden', 'Gold', 'Magical']:
        print(kind, 'median hours:', run(kind))
