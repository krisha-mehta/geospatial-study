import argparse
import csv
import json
import re
from collections import defaultdict

from generate_blocks import CENSUS_REGIONS, N_LEVELS, verify

REGION_CODE = {"Northeast": "NE", "Midwest": "MW", "South": "SO", "West": "WE"}
LEAF = re.compile(r"^([a-z]+)_([A-Z]{2})_([A-Z]{2})_([1-4])$")


def describe_condition(condition_block):
    """Pull the prefix, region order and state pools out of an existing condition."""
    containers = [c for c in condition_block["components"] if not isinstance(c, str)]
    if len(containers) != 1:
        raise ValueError(f"expected one trial container, found {len(containers)}")
    container = containers[0]

    prefix = None
    regions = []
    for region_block in container["components"]:
        codes = set()
        for entry in region_block["components"]:
            names = entry["components"] if isinstance(entry, dict) else [entry]
            for name in names:
                m = LEAF.match(name)
                if not m:
                    raise ValueError(f"unrecognised component name: {name}")
                prefix = prefix or m.group(1)
                codes.add(m.group(2))
        if len(codes) != 1:
            raise ValueError(f"region block mixes regions: {codes}")
        regions.append(codes.pop())

    return prefix, regions, container


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="configWIP.json")
    ap.add_argument("--out", dest="dst", default="configLatinRect.json")
    ap.add_argument("--blocks", default="blocks.csv",
                    help="block set produced by generate_blocks.py")
    ap.add_argument("--num-sequences", type=int, default=None,
                    help="override uiConfig.numSequences; omitted = leave the input value alone")
    args = ap.parse_args()

    config = json.load(open(args.src))
    defined = set(config["components"])

    top = next(c for c in config["sequence"]["components"]
               if not isinstance(c, str) and c["order"] == "latinSquare")

    described = [describe_condition(c) for c in top["components"]]
    baseline = described[0][1]
    for prefix, regions, _ in described:
        if regions != baseline:
            raise ValueError(f"condition {prefix} has a different region order: {regions}")

    # Read the block set. One set per region, shared by every condition.
    by_region_name = defaultdict(list)
    with open(args.blocks) as f:
        for row in csv.DictReader(f):
            by_region_name[row["region"]].append(
                tuple(row[f"level_{i}"] for i in range(1, N_LEVELS + 1)))

    if set(by_region_name) != set(CENSUS_REGIONS):
        raise RuntimeError(
            f"{args.blocks} covers {sorted(by_region_name)}, expected "
            f"{sorted(CENSUS_REGIONS)}")

    blocks_by_region = {}
    print(f"blocks: {args.blocks}")
    for region_name, states in CENSUS_REGIONS.items():
        blocks = by_region_name[region_name]

        seen_states = {s for b in blocks for s in b}
        if seen_states != set(states):
            raise RuntimeError(
                f"{region_name}: CSV uses states {sorted(seen_states)}, "
                f"CENSUS_REGIONS declares {sorted(states)}")

        k, rem = divmod(len(blocks), len(states))
        if rem:
            raise RuntimeError(
                f"{region_name}: {len(blocks)} blocks is not a multiple of "
                f"{len(states)} states, so it cannot be balanced")

        # Re-verify the CSV rather than trusting it: it may have been hand-edited,
        # or produced by a different version or seed of generate_blocks.py.
        v = verify(blocks, states, k=k)
        if not v["balanced"]:
            raise RuntimeError(
                f"{region_name}: block set is NOT balanced -- some state does not "
                f"appear exactly {k}x at every difficulty level")

        blocks_by_region[REGION_CODE[region_name]] = blocks
        print(f"  {region_name:<10} {v['n_states']:>2} states -> {v['n_blocks']:>3} blocks | "
              f"k={k} | each state {k}x per level | "
              f"pair co-occurrence {v['pair_cooccurrence_range']}")

    # Emit the sequence, one region block per condition.
    missing = []
    for prefix, regions, container in described:
        container["components"] = []
        for code in regions:
            entries = []
            for block in blocks_by_region[code]:
                names = [f"{prefix}_{code}_{state}_{lvl}"
                         for lvl, state in enumerate(block, start=1)]
                missing += [n for n in names if n not in defined]
                entries.append({"order": "fixed", "components": names})
            container["components"].append(
                {"order": "latinSquare", "numSamples": 1, "components": entries})

    if missing:
        raise RuntimeError(
            f"{len(missing)} component references do not exist in {args.src}, "
            f"e.g. {sorted(set(missing))[:5]}. Check CENSUS_REGIONS against the "
            f"states that actually have stimuli.")

    if args.num_sequences is not None:
        config["uiConfig"]["numSequences"] = args.num_sequences

    n_seq = config["uiConfig"]["numSequences"]
    n_cond = len(described)
    per_condition = n_seq / n_cond
    biggest = max(len(b) for b in blocks_by_region.values())

    print()
    if n_seq % n_cond:
        print(f"  WARNING  numSequences={n_seq} is not a multiple of {n_cond} conditions; "
              f"conditions will be unevenly sampled.")
    if per_condition < 2 * biggest:
        print(f"  WARNING  numSequences={n_seq} gives {per_condition:.0f} sequences per condition, "
              f"but the largest block set has {biggest} blocks. Fewer than 2 complete sweeps: "
              f"exposure will not balance, and below 1 sweep some (state, level) cells reach "
              f"zero participants. Want roughly {2 * biggest * n_cond} or more.")
    else:
        print(f"  numSequences = {n_seq}  ->  {per_condition:.0f} per condition, "
              f"{per_condition / biggest:.1f} sweeps of the largest block set ({biggest})")

    with open(args.dst, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    total = sum(len(b) for b in blocks_by_region.values())
    print(f"{total} blocks x {len(described)} conditions = {total * len(described)} block entries "
          f"({total * len(described) * N_LEVELS} component references)")
    print(f"wrote {args.dst}")


if __name__ == "__main__":
    main()
