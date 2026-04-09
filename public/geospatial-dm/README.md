# geospatial-dm — Study Directory README

**Study:** Uncertainty Visualizations for Geospatial Decision-Making
**Authors:** Krisha Mehta, Julia Koschinsky, Alex Kale (University of Chicago)
**Platform:** [reVISit](https://revisit.dev/)

---

## Directory Structure

```
geospatial-dm/
├── config.json              # Minimal pilot config (3 states, no practice/survey)
├── configNoCT.json          # Same as config.json but excludes Connecticut
├── configNoDiff.json        # Variant without differentiated uncertainty display
├── configWIP.json           # Full study design (376 trials per condition, all 50 states, Latin square)
└── assets/
    ├── d3-pixel.html        # Main pixel map stimulus
    ├── d3-hop.html          # Main HOP (Hypothetical Outcome Plot) map stimulus
    ├── pixel-practice-trial.html   # Pixel practice with feedback
    ├── hop-practice-trial.html     # HOP practice with feedback
    ├── pixel-survey.html    # Post-task survey (pixel condition)
    ├── hop-survey.html      # Post-task survey (HOP condition)
    ├── pixel.html           # Legacy prototype (SVG-based, unused)
    ├── hop.html             # Legacy prototype (SVG-based, unused)
    ├── bar-chart.html       # Bar chart visualization (unused/exploratory)
    ├── introduction.md      # Introductory text shown to participants
    ├── consent.md           # IRB consent form
    ├── help.md              # Help text shown in UI sidebar
    ├── pixel-intro.md       # Condition intro shown before pixel trials
    ├── hop-intro.md         # Condition intro shown before HOP trials
    ├── pixel.md             # Notes/documentation on pixel design
    ├── NMData.csv           # New Mexico county data (root-level copy)
    ├── AZData.csv           # Arizona county data (root-level copy)
    ├── Connecticut_Planning_Region_WGS84_fast.geojson     # CT planning regions
    ├── Connecticut_Planning_Region_WGS84_simple.geojson   # Simplified variant
    ├── Connecticut_Planning_Region_WGS84.geojson          # Full-resolution variant
    ├── Data/                # Per-state CSV files (named <ST>Data<N>.csv)
    └── OldData/             # Previous CSV format (superseded)
```

---

## File Descriptions

### `config.json`
The primary reVISit study configuration. Defines:
- Study metadata (title, authors, version `pilot`, date `2025-08-29`)
- UI config: Prolific ID capture, progress bar, contact email
- Two base components: `pixel-map-d3` (→ `d3-pixel.html`) and `hom-map-d3` (→ `d3-hop.html`)
- Six main trial components: `d3-pixel-1/2/3` and `d3-hom-1/2/3` using New Mexico (FIPS 35), Arizona (FIPS 04), and Illinois (FIPS 17)
- Fixed sequence: introduction → consent → pixel trials → HOP trials

**Issue:** The base component is named `hom-map-d3` (HOM) but references `d3-hop.html` (HOP). The naming is inconsistent — HOM (Hypothetical Outcome Map) vs HOP (Hypothetical Outcome Plot) are used interchangeably throughout the project.

**Issue:** CSV path prefixes are inconsistent. `d3-pixel-1` and `d3-hom-1` pass `"NMData.csv"` (no prefix), while `d3-pixel-3` and `d3-hom-3` pass `"Data/ILData.csv"` (with prefix). The `d3-pixel.html` file uses the path as-is, so correctness depends entirely on how the dev server resolves the base URL. This will silently fail if the working directory assumption is wrong.

### `configNoCT.json`
Identical structure to `config.json` but excludes Connecticut from the trial set. Used when CT's planning-region data or special-case rendering is causing issues.

### `configNoDiff.json`
Variant config that appears to remove the differentiated uncertainty display. Likely used for a control condition or A/B comparison baseline.

### `configWIP.json`
The **full study design** — 5,708 lines, the largest file in the project (~355 KB). This is the active work-in-progress config intended for the actual Prolific deployment.

**What it adds over `config.json`:**
- **376 pixel components + 376 HOP components** (752 total trials), covering all 50 states with 4 dataset variants per state per condition (e.g., `pix_NE_CT_1` through `pix_NE_CT_4`, `hom_NE_CT_1` through `hom_NE_CT_4`)
- **4 geographic regions** used to organize the trial sequence: Northeast, South, Midwest, West
- **Practice trials** (`pixel-trial`, `hop-trial`) wired to `pixel-practice-trial.html` and `hop-practice-trial.html` with the full task instruction text
- **Post-task surveys** (`pixel-survey`, `hop-survey`) wired to the survey HTML files
- **Condition intro pages** (`pixel-intro`, `hop-intro`) referencing `pixel-intro.md` and `hop-intro.md` (note: these `.md` files are referenced in the config but **not present** in `assets/` — this will cause a 404 at runtime)
- **Latin square counterbalancing** (`"order": "latinSquare"`) within each region and state group, with `"numSamples": 1` to select one dataset variant per participant
- **Hidden reactive responses** — the `selectedCounty` response uses `"hidden": true` (unlike `config.json` where it is visible), keeping the answer field out of the reVISit UI

**Issue:** Component naming switches between `hom_` prefix (e.g., `hom_NE_CT_1`) and the HOP terminology used in filenames. See the naming inconsistency noted under `config.json`.

---

### `assets/d3-pixel.html`
The primary **pixel map** stimulus. Renders a county-level choropleth using a pixel/grain technique to encode uncertainty.

**How it works:**
- Loads US TopoJSON from CDN + a state-specific CSV
- Projects counties using `d3.geoEquirectangular()`, fit to a 400×400 SVG viewport
- Draws a 3px-grid pixel canvas over each county. Each pixel samples a value from `Normal(estimate, MOE/1.645)` using the Mulberry32 PRNG seeded per-county (`hashStr` of county FIPS)
- Color encodes sampled value via `d3.interpolateYlOrRd` over domain [0, 50] (percent poverty)
- Continuous vertical gradient legend (140×400 SVG) labeled "Poverty"
- Participants select exactly 3 counties by clicking; selected counties appear as chips below the map
- **Special case:** Connecticut (FIPS `09`) uses `Connecticut_Planning_Region_WGS84_fast.geojson` and `d3.geoIdentity().reflectY(true)` instead of standard counties + equirectangular projection

**Key constants (inline, not in a config object):**
| Constant | Value | Meaning |
|----------|-------|---------|
| `PIXEL` | 3 | Pixel grid cell size in SVG units |
| `MOE_Z` | 1.645 | Z-score for 90% CI margin of error |
| `VALUE_MIN` | 0 | Min of color scale (poverty %) |
| `VALUE_MAX` | 50 | Max of color scale (poverty %) |
| `MAX_SELECTIONS` | 3 | Max counties selectable |
| `REQUIRED_SELECTIONS` | 3 | Selections needed to post answer |

**Issue:** There is no validation of `stateFips` or `csvFile` before calling `renderState()`. If reVISit passes malformed parameters, the function will crash without a meaningful user-facing message (contrast with `d3-hop.html` which validates first).

**Issue:** Constants are scattered as bare `const` declarations rather than grouped in a config object (as `d3-hop.html` does). This makes it harder to compare settings across conditions at a glance.

---

### `assets/d3-hop.html`
The primary **HOP (Hypothetical Outcome Plot) map** stimulus. Renders an animated binary county map where each frame is a plausible realization drawn from the uncertainty distribution.

**How it works:**
- Same data pipeline as `d3-pixel.html` (TopoJSON + state CSV)
- For each county and frame, computes `P(poverty > 15%)` using `normalCdf`, then Bernoulli-samples to get a binary on/off for that frame
- Animates 50 frames at 2.5 FPS (one full cycle = 20 seconds), looping continuously
- Counties colored binary: `#800000` (maroon = above threshold) or `#e9e9e9` (gray = below)
- Progress bar shows animation cycle progress
- Same 3-county selection mechanic as pixel
- Same Connecticut special case with planning regions

**Key constants (grouped in `CONFIG` object):**
| Constant | Value | Meaning |
|----------|-------|---------|
| `THRESHOLD` | 15 | Poverty % threshold for binary classification |
| `MOE_Z` | 1.645 | Z-score for 90% CI margin of error |
| `N_FRAMES` | 50 | Animation frames per cycle |
| `FPS` | 2.5 | Frames per second |
| `MAX_SELECTIONS` | 3 | Max counties selectable |
| `REQUIRED_SELECTIONS` | 3 | Selections needed to post answer |
| `RNG_SEED` | 42 | Base seed for Mulberry32 PRNG |

**Issue:** The animation loop (`requestAnimationFrame(loop)`) never stops. Once `startLoopOnce()` is called, `loop()` schedules itself indefinitely via `requestAnimationFrame`. If reVISit re-triggers `onDataReceive` for a new trial, `loadData()` is called again but a second animation loop is NOT started (guarded by `loopStarted`). However, the existing loop continues running against the old frame data until `state.draws` is replaced. There is a brief window of visual inconsistency, and CPU is consumed continuously for the entire session.

**Issue:** No input validation counterpart for the `renderState` call path if called directly (validation only exists in `onDataReceive`).

---

### `assets/pixel-practice-trial.html`
Interactive practice trial for the pixel condition with immediate correctness feedback. Hardcoded to Alaska (FIPS `02`, `Data/AKData4.csv`). After participants select 3 counties, it compares to a hardcoded answer key (`['Kusilvak Census Area', 'Bethel Census Area', 'Yukon-Koyukuk Census Area']`) and shows color-coded feedback.

**Issue:** Uses `d3.geoAlbers()` projection — different from the `d3.geoEquirectangular()` used in the main `d3-pixel.html`. See the [Viewing Conditions Comparison](#stimuli-viewing-conditions-d3-pixelhtml-vs-d3-hophtml) section for implications.

**Issue:** No Connecticut special-case handling. If the practice state were ever changed to CT, it would fail.

---

### `assets/hop-practice-trial.html`
Interactive practice trial for the HOP condition, analogous to `pixel-practice-trial.html`. Same hardcoded Alaska data and answer key. Renders the animated HOP visualization with feedback after selection.

**Issue:** Same `d3.geoAlbers()` projection inconsistency as `pixel-practice-trial.html`.

**Issue:** The `loopStarted` flag is a module-level closure variable that is never reset. If the page re-initializes (e.g., in a single-page app context), a second animation loop cannot be started.

---

### `assets/pixel-survey.html`
Post-task survey for participants in the pixel condition. Contains a mix of Likert-scale questions about confidence and task difficulty, plus a static pixel map for reference. Uses `d3.geoEquirectangular()` (consistent with main trial).

---

### `assets/hop-survey.html`
Post-task survey for the HOP condition. Same structure as `pixel-survey.html`. Uses `d3.geoEquirectangular()` (consistent with main trial).

---

### `assets/pixel.html`
**Legacy prototype — not used in the current study.** An earlier approach that loaded pre-rendered SVG files and applied D3 event listeners. Uses `Revisit.onDataReceive` with `data['svgFile']` (no CSV). This approach was superseded by `d3-pixel.html`.

This file appears functionally correct (`d3.select(this)` used properly on click).

---

### `assets/hop.html`
**Legacy prototype — not used in the current study.** Same era as `pixel.html`, loads SVG files.

**Bug (line 44):** Uses `d3.selectAll(this)` instead of `d3.select(this)` in the click handler. `d3.selectAll` does not accept a DOM node as a selector in this context; the behavior is undefined/broken. Since this file is unused, it poses no active risk but should be fixed or deleted to avoid confusion.

---

### `assets/bar-chart.html`
A simple bar chart visualization. Appears to be an exploratory or alternative stimulus that is not referenced in any config file. Status: unused/in-progress.

---

### `assets/Data/`
Contains the current per-state CSV files used by the main trials. Named `<ST>Data<N>.csv` (e.g., `AKData1.csv`, `ILData1.csv`). The `<N>` suffix (currently all `1`) presumably allows multiple dataset variants per state. Each CSV contains county-level poverty estimates and margins of error.

### `assets/OldData/`
Superseded CSV files from a previous data format. Named without the numeric suffix (e.g., `AKData.csv`). These are not referenced by any current config and can be archived or deleted.

### GeoJSON files (`Connecticut_Planning_Region_WGS84*.geojson`)
Three variants of the same Connecticut planning region boundaries at different resolutions:
- `_fast` — simplified geometry for performance (used by `d3-pixel.html` and `d3-hop.html`)
- `_simple` — moderately simplified
- (full) — highest fidelity

Only the `_fast` variant is actively referenced.

---

## Stimuli Viewing Conditions: `d3-pixel.html` vs `d3-hop.html`

The two conditions are designed to test the same underlying task (identify the 3 counties with highest poverty) under different uncertainty representations. Most viewing conditions are matched, but there are meaningful differences.

### Matched conditions

| Parameter | Pixel | HOP |
|-----------|-------|-----|
| Body dimensions | 650×550 px | 650×550 px |
| Map SVG viewBox | 400×400 | 400×400 |
| Legend SVG max-width | 140 px | 140 px |
| Wrap div height | 400 px | 400 px |
| Map margin-top | none (0) | 20 px |
| Geographic projection | `d3.geoEquirectangular()` | `d3.geoEquirectangular()` |
| TopoJSON source | `us-atlas@3/counties-10m.json` (CDN) | same |
| MOE interpretation | Z = 1.645 (90% CI) | Z = 1.645 (90% CI) |
| Selections required | 3 counties | 3 counties |
| Max selections | 3 | 3 |
| Font | Inter | Inter |
| County border color | stroke inherited | `#777`, width 0.8 |
| State outline | `#595959`, width 1 | `#222`, width 1.2 |
| Connecticut handling | Planning regions + `geoIdentity` | Planning regions + `geoIdentity` |

**Minor discrepancy:** HOP has a `margin-top: 20px` on `.wrap` that pixel does not. This shifts the map 20px lower in the HOP condition, making the layout slightly different.

**Minor discrepancy:** State outline stroke color differs (`#595959` in pixel vs `#222` in HOP) and stroke-width differs (1 vs 1.2). These are small but visible.

### Differing conditions

| Parameter | Pixel | HOP | Notes |
|-----------|-------|-----|-------|
| **Uncertainty encoding** | Color (continuous) | Animation (binary, temporal) | Fundamental design difference |
| **Color scale** | `d3.interpolateYlOrRd`, domain [0, 50] | Binary: `#800000` / `#e9e9e9` | Different visual channel |
| **Data range shown** | Continuous 0–50% poverty | Binary above/below 15% | Pixel shows full distribution; HOP shows a threshold decision |
| **Threshold** | Implicit (encoded in color) | Explicit: 15% poverty | HOP requires participants to understand what threshold means |
| **Time to perceive** | Immediate (static) | ~20 seconds minimum for one full cycle | HOP requires sustained attention over time |
| **Animation** | None | 50 frames at 2.5 FPS | |
| **PRNG mechanism** | `mulberry32` seeded by `hashStr(fips)` per county | `mulberry32` seeded by `CONFIG.RNG_SEED + frame*1000 + countyHash` | Different seeding strategies |
| **Legend type** | Continuous gradient bar | Two categorical swatches | |
| **Legend content** | Gradient 0–50 labeled "Poverty" | "≥ 15% poverty" / "< 15% poverty" | |
| **D3 chromatic library** | `d3-scale-chromatic.v3.min.js` loaded | Not loaded | Pixel needs it for `interpolateYlOrRd`; HOP uses only hex colors |
| **Progress bar** | None | Present (shows animation cycle progress) | HOP has extra UI element |
| **`loopStarted` guard** | N/A | Module-level boolean, never resets | |

### Practice trial projection mismatch

Both `pixel-practice-trial.html` and `hop-practice-trial.html` use `d3.geoAlbers()`, while the main trials use `d3.geoEquirectangular()`. This means:

- The practice maps use an equal-area conic projection (Albers), which preserves area ratios and produces the familiar "standard" US map shape
- The main trial maps use a simple rectangular lat/lon projection, which distorts areas (especially at high/low latitudes) and stretches the map differently

Alaska (used for practice) is particularly sensitive to this: Albers places Alaska in the lower-left inset; equirectangular places it at its true geographic latitude far north, often off-screen or extremely compressed. **This means participants may experience a visually very different map for the practice vs. main trials**, which could confuse them or prevent the practice from being effective as training.

---

## Bugs and Issues Summary

### Bugs

| Severity | File | Line | Description |
|----------|------|------|-------------|
| Low | [hop.html](assets/hop.html#L44) | 44 | `d3.selectAll(this)` should be `d3.select(this)` — legacy file, unused |

### Design Issues and Inconsistencies

| Issue | Files Affected |
|-------|---------------|
| **No input validation** before `renderState()` — crashes silently on bad params | [d3-pixel.html](assets/d3-pixel.html#L628) |
| **Animation loop never stops** — `requestAnimationFrame(loop)` runs forever; no cleanup on state change | [d3-hop.html](assets/d3-hop.html#L685), [hop-practice-trial.html](assets/hop-practice-trial.html) |
| **Inconsistent projection** — practice trials use `geoAlbers`, main trials use `geoEquirectangular` | [pixel-practice-trial.html](assets/pixel-practice-trial.html#L297), [hop-practice-trial.html](assets/hop-practice-trial.html#L431) |
| **Inconsistent CSV path prefixes** — some configs pass `NMData.csv`, others `Data/ILData.csv` | [config.json](config.json#L69), [config.json](config.json#L89) |
| **Inconsistent naming** — `hom-map-d3` / HOM used in configs, `d3-hop.html` / HOP used in filenames | [config.json](config.json#L41), all configs |
| **Constants not grouped** — pixel uses bare `const` globals; HOP uses a `CONFIG` object | [d3-pixel.html](assets/d3-pixel.html#L136) |
| **Duplicate utility functions** — `mulberry32`, `randnFactory`, `norm`, `stripTypeSuffix` defined in every file | All HTML files |
| **Map top margin differs** — HOP `.wrap` has `margin-top: 20px`, pixel has none | [d3-hop.html](assets/d3-hop.html#L29) |
| **State outline style differs** — stroke color `#595959` vs `#222`, width 1 vs 1.2 | [d3-pixel.html](assets/d3-pixel.html), [d3-hop.html](assets/d3-hop.html) |
| **`OldData/` directory** — superseded CSV files still present alongside `Data/` | [assets/OldData/](assets/OldData/) |
| **Three GeoJSON variants** for Connecticut but only `_fast` is used | [assets/](assets/) |
| **`bar-chart.html`** not referenced in any config | [assets/bar-chart.html](assets/bar-chart.html) |
