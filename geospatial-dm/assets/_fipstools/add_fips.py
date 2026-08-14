#!/usr/bin/env python3
"""Stamp a leading `fips` column onto the VA/MD/MO task CSVs in assets/Data.

Keys each task row back to assets/county_fips_lookup.csv on (county name, moe).
Falls back to name-only ONLY where the name is unique inside its state; a
colliding name with no moe match is a hard failure, never a guess.
Idempotent. Backs originals up to assets/Data_backup_pre_fips/.
"""
import csv, shutil, sys, argparse
from pathlib import Path
from collections import Counter

ASSETS = Path(__file__).resolve().parent.parent
DATA = ASSETS / "Data"
BACKUP = ASSETS / "Data_backup_pre_fips"
STATES = ["VA", "MD", "MO"]


def mkey(v):
    try:
        return f"{round(float(v), 4):g}"
    except (TypeError, ValueError):
        return str(v).strip()


rows = list(csv.DictReader(open(ASSETS / "county_fips_lookup.csv", newline="")))
name_counts = {st: Counter(r["county"] for r in rows if r["state"] == st) for st in STATES}
moe_index = {(r["state"], r["county"], mkey(r["moe"])): r["fips"] for r in rows}
by_name = {(r["state"], r["county"]): r["fips"] for r in rows
           if name_counts[r["state"]][r["county"]] == 1}


def main(dry_run=False):
    if not dry_run:
        BACKUP.mkdir(exist_ok=True)
    failures, fallbacks, total = [], [], 0

    for st in STATES:
        for i in range(1, 5):
            path = DATA / f"{st}Data{i}.csv"
            with open(path, newline="") as fh:
                rdr = csv.DictReader(fh)
                fields, data = rdr.fieldnames, list(rdr)

            if "fips" in fields:
                print(f"  {path.name}: already stamped, skipping")
                continue

            out, seen = [], {}
            for k, r in enumerate(data):
                nm = r["county"].strip()
                fips = moe_index.get((st, nm, mkey(r["moe"])))
                if fips is None:
                    fips = by_name.get((st, nm))
                    if fips is not None:
                        fallbacks.append((path.name, nm))
                if fips is None:
                    failures.append((path.name, k + 2, nm, r["moe"],
                                     "colliding name, no moe match"
                                     if name_counts[st][nm] > 1 else "unknown county"))
                    continue
                if fips in seen:
                    failures.append((path.name, k + 2, nm, r["moe"],
                                     f"fips {fips} already used by row {seen[fips]}"))
                    continue
                seen[fips] = k + 2
                out.append({"fips": fips, **r})
                total += 1

            expect = sum(name_counts[st].values())
            print(f"  {path.name}: {len(out)}/{expect} "
                  f"[{'OK' if len(out) == expect else 'SHORT'}]")

            if not dry_run and len(out) == expect:
                shutil.copy2(path, BACKUP / path.name)
                with open(path, "w", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=["fips"] + fields)
                    w.writeheader()
                    w.writerows(out)

    print(f"\ntotal stamped: {total}")
    if fallbacks:
        print(f"name-only fallback: {len(fallbacks)} rows -> "
              f"{sorted(set(n for _, n in fallbacks))}")
    else:
        print("name-only fallback: not needed (every row matched on moe)")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures[:25]:
            print("  ", f)
        sys.exit(1)
    print("no failures")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(**vars(ap.parse_args()))
