"""Chest pacing simulator for RARITY_GODLY_ARMOR.md (2026-09-28; chest rules 2026-10-03).

Mirrors ChestConfig. NEW (2026-10-03): each chest is a few items, each a rarity roll with a
stack of copies by rarity, pity putting a Legendary/Godly on an item. OLD (for comparison): the
morning of 2026-10-03, a fixed copy count spread over every rarity, one item per rarity.
A simulated player spends every emerald on one chest type and upgrades greedily.

INCOME IS A GUESS (emeralds per hour played, incl. 200 daily per ~1.5 h session). Replace it
with real run data when available. Run: python chest_pace_sim.py
"""
import random, statistics as st

POOL = {'Common': 16, 'Rare': 20, 'Epic': 13, 'Legendary': 11, 'Godly': 10}  # weapons + armor pieces
UP = {'Common': [2, 6, 15], 'Rare': [2, 4, 8], 'Epic': [1, 2, 4], 'Legendary': [1, 2, 3], 'Godly': [1, 1, 2]}
RAR = ['Common', 'Rare', 'Epic', 'Legendary', 'Godly']
# NEW: price, items (1.5 = one plus a 50% chance of a second), odds per roll, stack by rarity
CH = {'Silver': (160, 1, [.6, .35, .04, .0095, .0005], [4, 2, 1, 1, 1]),
      'Gold': (300, 1.5, [.45, .42, .11, .019, .001], [6, 3, 1, 1, 1]),
      'Magical': (700, 2, [.2, .4, .35, .047, .003], [8, 4, 2, 1, 1])}
# OLD: price, copies, rare, epic, legendary, godly
CH_OLD = {'Silver': (160, 6, 1, .08, .008, .0005), 'Gold': (300, 10, 2, .25, .03, .002),
          'Magical': (700, 18, 4, 1, .1, .006)}
MODEL = 'new'
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


def open_old(kind, lpity, gpity):
    _, items, r, e, l, g = CH_OLD[kind]
    rare, epic = chance(r), chance(e)
    leg = 1 if lpity >= LEGENDARY_PITY - 1 or random.random() < l else 0
    god = 1 if gpity >= GODLY_PITY - 1 or random.random() < g else 0
    t = {}
    group('Common', items - rare - epic - leg - god, t); group('Rare', rare, t)
    group('Epic', epic, t); group('Legendary', leg, t); group('Godly', god, t)
    return t, leg, god


def open_new(kind, lpity, gpity):
    _, items, odds, stack = CH[kind]
    rolls = []
    for _ in range(chance(items)):
        x, pick = random.random(), RAR[0]
        for r, q in zip(RAR, odds):
            if x < q: pick = r; break
            x -= q
        rolls.append(pick)
    if gpity >= GODLY_PITY - 1 and 'Godly' not in rolls: rolls[0] = 'Godly'
    if lpity >= LEGENDARY_PITY - 1 and 'Legendary' not in rolls:
        for i, r in enumerate(rolls):
            if r != 'Godly': rolls[i] = 'Legendary'; break
    t = {}
    for r in rolls:
        ids = [f'{r}{i}' for i in range(POOL[r]) if f'{r}{i}' not in t]
        t[random.choice(ids)] = stack[RAR.index(r)]
    return t, int('Legendary' in rolls), int('Godly' in rolls)


def open_chest(kind, lpity, gpity):
    return (open_new if MODEL == 'new' else open_old)(kind, lpity, gpity)


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
    chests = items = copies = 0
    ids = [f'{r}{i}' for r in POOL if r != 'Godly' for i in range(POOL[r])]
    for _ in range(trials):
        have = {'Common0': 1}; lp = gp = 0; h = bank = 0.0; got = {}
        while h < cap and len(got) < len(keys):
            bank += income(h) * .1; h += .1
            while bank >= CH[kind][0]:
                bank -= CH[kind][0]; t, l, g = open_chest(kind, lp, gp)
                chests += 1; items += len(t); copies += sum(t.values())
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
    res = {k: round(st.median(v), 1) for k, v in out.items()}
    res['items/chest'] = round(items / max(1, chests), 2); res['copies/chest'] = round(copies / max(1, chests), 2)
    return res


if __name__ == '__main__':
    import sys
    for MODEL in (['old', 'new'] if '--compare' in sys.argv else ['new']):
        random.seed(5)
        for kind in ['Silver', 'Gold', 'Magical']:
            print(MODEL, kind, 'median hours:', run(kind))
