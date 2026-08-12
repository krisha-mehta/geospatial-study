import csv
import random
from collections import Counter
from itertools import combinations


CENSUS_REGIONS = {
    "Northeast": ["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"],
    "Midwest":   ["IL", "IN", "IA", "KS", "MI", "MN",
                  "MO", "NE", "ND", "OH", "SD", "WI"],
    "South":     ["AL", "AR", "FL", "GA", "KY", "LA", "MD", "MS",
                  "NC", "OK", "SC", "TN", "TX", "VA", "WV"],
    "West":      ["AZ", "CA", "CO", "ID", "MT", "NV",
                  "NM", "OR", "UT", "WA", "WY"],
}


N_LEVELS = 4   # difficulty levels

def _random_row(n, used_in_column, rng, max_repairs=2000):
    row = list(range(n))
    rng.shuffle(row)

    for _ in range(max_repairs):
        conflicts = [j for j in range(n) if row[j] in used_in_column[j]]
        if not conflicts:
            return row
        j = rng.choice(conflicts)
        k = rng.randrange(n)
        row[j], row[k] = row[k], row[j]

    return None


def _random_latin_rectangle(n, rng, max_attempts=200):
    
    if n < N_LEVELS:
        raise ValueError(f"region has {n} states; need at least {N_LEVELS}")

    for _ in range(max_attempts):
        rows = []
        used_in_column = [set() for _ in range(n)]
        ok = True

        for _ in range(N_LEVELS):
            row = _random_row(n, used_in_column, rng)
            if row is None:
                ok = False
                break
            rows.append(row)
            for j, s in enumerate(row):
                used_in_column[j].add(s)

        if ok:
            return rows

    raise RuntimeError(f"failed to build a Latin rectangle for n={n}")


def _pair_counts(blocks):
    counts = Counter()
    for block in blocks:
        for pair in combinations(sorted(block), 2):
            counts[pair] += 1
    return counts


def _score(blocks, n):
    counts = _pair_counts(blocks)
    observed = [counts.get(p, 0) for p in combinations(range(n), 2)]
    zeros = sum(1 for v in observed if v == 0)
    return (zeros, sum(v * v for v in observed))


def generate_region_blocks(states, seed=0, n_candidates=500, k=1):
    n = len(states)
    rng = random.Random(seed)

    best_blocks, best_score = None, None
    for _ in range(n_candidates):
        blocks = []
        seen = set()
        for _ in range(k):
           
            for _attempt in range(200):
                rows = _random_latin_rectangle(n, rng)
                cand = [tuple(rows[r][j] for r in range(N_LEVELS))
                        for j in range(n)]
                if not any(b in seen for b in cand) and len(set(cand)) == n:
                    seen.update(cand)
                    blocks.extend(cand)
                    break
            else:
                raise RuntimeError(f"could not place rectangle without duplicates (n={n}, k={k})")

        score = _score(blocks, n)
        if best_score is None or score < best_score:
            best_blocks, best_score = blocks, score

    return [tuple(states[i] for i in block) for block in best_blocks]

def verify(blocks, states, k=1):
    n = len(states)
    level_counts = Counter()
    for block in blocks:
        assert len(set(block)) == N_LEVELS, "block repeats a state"
        for level, state in enumerate(block, start=1):
            level_counts[(state, level)] += 1

    per_cell = {level_counts.get((s, l), 0)
                for s in states for l in range(1, N_LEVELS + 1)}

    pair_counts = Counter()
    for block in blocks:
        for pair in combinations(sorted(block), 2):
            pair_counts[pair] += 1
    observed = [pair_counts.get(p, 0) for p in combinations(sorted(states), 2)]

    return {
        "n_states": n,
        "n_blocks": len(blocks),
        "balanced": per_cell == {k},         # each state k times at each level
        "appearances_per_state": N_LEVELS * k,
        "pair_cooccurrence_range": (min(observed), max(observed)),
    }

def write_csv(all_blocks, path="blocks.csv"):
    """One row per block: region, block index, and the four states by level."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "block_id", "level_1", "level_2",
                    "level_3", "level_4"])
        for region, blocks in all_blocks.items():
            for i, block in enumerate(blocks):
                w.writerow([region, f"{region}_{i:02d}", *block])


def main(seed=1, out="blocks.csv", k=1):
    all_blocks = {}
    print(f"seed = {seed}   k = {k}\n")
    for region, states in CENSUS_REGIONS.items():
        blocks = generate_region_blocks(states, seed=seed, k=k)
        all_blocks[region] = blocks
        v = verify(blocks, states, k=k)
        assert v["balanced"], f"{region} failed verification"
        print(f"{region:<10} {v['n_states']:>2} states -> "
              f"{v['n_blocks']:>2} blocks | each state {k}x per level | "
              f"pair co-occurrence {v['pair_cooccurrence_range']}")

    write_csv(all_blocks, out)
    total = sum(len(b) for b in all_blocks.values())
    print(f"\n{total} blocks ({total * N_LEVELS} trials) written to {out}")
    return all_blocks


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--out", default="blocks.csv")
    a = ap.parse_args()
    main(seed=a.seed, out=a.out, k=a.k)