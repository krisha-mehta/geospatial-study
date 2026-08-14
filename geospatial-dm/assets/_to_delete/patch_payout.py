#!/usr/bin/env python3
"""Add a fips column to top3_counties.csv (VA/MD/MO rows) and key payout
scoring on it, so Baltimore city stops matching Baltimore County selections.

Rows for other states keep a blank fips and continue to score by name.
Idempotent. Backs originals up alongside with .pre_fips.bak.
"""
import csv, re, shutil, sys
from pathlib import Path
from collections import Counter

ASSETS = Path(__file__).resolve().parent.parent
STATES = ["VA", "MD", "MO"]
MARKER = "/* __fips_scoring__ */"


def mkey(v):
    try:
        return f"{round(float(v), 4):g}"
    except (TypeError, ValueError):
        return str(v).strip()


rows = list(csv.DictReader(open(ASSETS / "county_fips_lookup.csv", newline="")))
counts = {st: Counter(r["county"] for r in rows if r["state"] == st) for st in STATES}
moe_index = {(r["state"], r["county"], mkey(r["moe"])): r["fips"] for r in rows}

# ---- 1. top3_counties.csv -------------------------------------------------
top3 = ASSETS / "top3_counties.csv"
with open(top3, newline="") as fh:
    rdr = csv.DictReader(fh)
    fields, data = rdr.fieldnames, list(rdr)

if "fips" in fields:
    print("top3_counties.csv: already has fips, skipping")
else:
    stamped, missed = 0, []
    out = []
    for r in data:
        sf = (r.get("state_file") or "").strip()
        st = sf[:2]
        fips = ""
        if st in STATES:
            nm = (r.get("county") or "").strip()
            got = moe_index.get((st, nm, mkey(r.get("moe"))))
            if got is None and counts[st][nm] == 1:
                got = next((x["fips"] for x in rows
                            if x["state"] == st and x["county"] == nm), None)
            if got is None:
                missed.append((sf, nm, r.get("moe")))
            else:
                fips, _ = got, stamped
                stamped += 1
        out.append({**r, "fips": fips})

    if missed:
        print(f"FAIL: {len(missed)} VA/MD/MO top3 rows unresolved: {missed[:10]}")
        sys.exit(1)

    shutil.copy2(top3, top3.with_suffix(".csv.pre_fips.bak"))
    with open(top3, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields + ["fips"])
        w.writeheader()
        w.writerows(out)
    print(f"top3_counties.csv: stamped {stamped} rows (VA/MD/MO), "
          f"{len(out) - stamped} left blank for name scoring")

# ---- 2. payout.html ------------------------------------------------------
payout = ASSETS / "payout.html"
src = payout.read_text()
if MARKER in src:
    print("payout.html: already patched")
else:
    old_build = """      if (!top3Map[key]) top3Map[key] = new Set();
      top3Map[key].add(normCounty(row.county || ''));"""
    new_build = ("      " + MARKER + """
      if (!top3Map[key]) top3Map[key] = { fips: new Set(), name: new Set() };
      const __f = String(row.fips ?? '').trim();
      if (__f) top3Map[key].fips.add(__f.padStart(5, '0'));
      else top3Map[key].name.add(normCounty(row.county || ''));""")

    old_empty = "const correctSet = top3Map[stateFile] || new Set();"
    new_empty = ("const correctSet = top3Map[stateFile] "
                 "|| { fips: new Set(), name: new Set() };")

    old_score = """    for (const county of selected) {
      if (correctSet.has(normCounty(county))) correctCount++;
    }"""
    new_score = """    for (const entry of selected) {
      const __nm = (typeof entry === 'string') ? entry : (entry && entry.name) || '';
      const __fp = (typeof entry === 'string') ? null : (entry && entry.fips) || null;
      if (__fp && correctSet.fips.has(String(__fp).padStart(5, '0'))) { correctCount++; continue; }
      if (correctSet.name.has(normCounty(__nm))) correctCount++;
    }"""

    for old in (old_build, old_empty, old_score):
        if old not in src:
            print(f"FAIL: payout.html anchor not found:\n{old}")
            sys.exit(1)

    shutil.copy2(payout, payout.with_suffix(".html.pre_fips.bak"))
    src = src.replace(old_build, new_build).replace(old_empty, new_empty).replace(old_score, new_score)
    payout.write_text(src)
    print("payout.html: scoring keyed on fips with name fallback")

# ---- 3. saveTrialToSession ----------------------------------------------
old_save = ("sessionStorage.setItem('trial_' + trialId, JSON.stringify(counties));")
new_save = ("sessionStorage.setItem('trial_' + trialId, JSON.stringify(\n"
            "      counties.map(c => ({ name: c, fips: __labelToFips.get(c) ?? null }))));")

n = 0
for p in sorted(ASSETS.rglob("*.html")):
    t = p.read_text()
    if "function saveTrialToSession" not in t or old_save not in t:
        continue
    shutil.copy2(p, p.with_suffix(".html.pre_save.bak"))
    p.write_text(t.replace(old_save, new_save))
    n += 1
print(f"saveTrialToSession: patched {n} files to store {{name, fips}}")
