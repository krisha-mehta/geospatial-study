#!/usr/bin/env python3
"""Make the 8 map renderers join CSV rows to polygons on FIPS.

Only the baseComponent renderers in configLatinRect.json are patched -- they are
the only files that receive a variable csvFile. Every other map page hardcodes
COData4 (08) or AKData4 (02), neither of which has a colliding county name.

One hunk per file. Prefers the csv's fips column; falls back to the existing
name lookup when the column is absent; refuses to guess (and says so) when the
name occurs twice in the state and there is no fips column.

Idempotent via the __fips_join__ marker. Backs up to *.pre_fips.bak.
"""
import re, shutil, sys, argparse
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent
MARKER = "/* __fips_join__ */"

TARGETS = [
    "pixel/d3-pixel.html",
    "hops/d3-hop.html",
    "animatedPixel/d3-animated-pixel-map.html",
    "pixelSorted/d3-pixel-sorted.html",
    "thresholdPixel/d3-threshold-pixel.html",
    "thresholdPixelSorted/d3-threshold-pixel-sorted.html",
    "exceedance/d3-exceedance.html",
    "svsup/d3-svsup.html",
]

LOOKUP_RE = re.compile(
    r"^([ \t]*)const fips = (nameToFipsMap|nameToFips)\.get\(key\);[ \t]*$", re.M)


def replacement(m):
    i, mapvar = m.group(1), m.group(2)
    return (
        f"{i}{MARKER}\n"
        f"{i}const __csvFips = (r.fips === undefined || r.fips === null || String(r.fips).trim() === '')\n"
        f"{i}  ? null : String(r.fips).trim().padStart(5, '0');\n"
        f"{i}const __dupName = __csvFips ? false\n"
        f"{i}  : csv.filter(x => String(x.county ?? x.NAME ?? '').trim() === rawName).length > 1;\n"
        f"{i}if (__dupName) console.error('[fips-join] \"' + rawName + '\" occurs more than once in '\n"
        f"{i}  + 'this state and the data file has no fips column - refusing to guess.');\n"
        f"{i}const fips = __csvFips || (__dupName ? undefined : {mapvar}.get(key));")


def main(dry_run=False, revert=False):
    done = 0
    for rel in TARGETS:
        p = ASSETS / rel
        bak = p.with_suffix(".html.pre_fips.bak")
        if revert:
            if bak.exists():
                shutil.move(str(bak), str(p)); done += 1; print(f"  reverted  {rel}")
            else:
                print(f"  no backup {rel}")
            continue

        src = p.read_text()
        if MARKER in src:
            print(f"  skip      {rel} (already patched)")
            continue
        out, n = LOOKUP_RE.subn(replacement, src, count=1)
        if n != 1:
            print(f"  FAIL      {rel}: anchor 'const fips = nameToFips*.get(key);' not found")
            sys.exit(1)
        print(f"  {'dry  ' if dry_run else 'patch'}     {rel}")
        if not dry_run:
            shutil.copy2(p, bak)
            p.write_text(out)
            done += 1
    print(f"\n{'reverted' if revert else 'patched'} {done} of {len(TARGETS)} renderers")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    main(**vars(ap.parse_args()))
