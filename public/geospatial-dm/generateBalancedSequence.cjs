/* eslint-disable no-console */
/**
 * generateBalancedSequence.cjs
 *
 * Rebuilds the `sequence` block of the geospatial-dm study config so that, for
 * every US Census region a participant sees, the four states shown are distinct
 * AND collectively cover all four task-difficulty levels.
 *
 * ---------------------------------------------------------------------------
 * WHY THE CONFIG ALONE CANNOT DO THIS
 * ---------------------------------------------------------------------------
 * In reVISit, each `latinSquare` block owns an independent Latin square keyed by
 * its structural path (see src/utils/handleRandomSequences.tsx). Sibling blocks
 * cannot coordinate. So the old shape --
 *
 *     region: latinSquare numSamples 4  -> [state blocks]
 *     state:  latinSquare numSamples 1  -> [diff 1..4]
 *
 * -- draws each state's difficulty independently, and difficulties can repeat
 * within a region. `numSamples` also slices BEFORE recursion, so unselected
 * states never pop their square and the per-state cycles drift out of step.
 *
 * ---------------------------------------------------------------------------
 * THE DESIGN
 * ---------------------------------------------------------------------------
 * Move the pairing decision up one level: precompute the legal (state,
 * difficulty) 4-tuples per region and Latin-square over THOSE.
 *
 *   region: latinSquare numSamples 1  -> [row blocks]
 *   row:    fixed                     -> [4 leaf components]
 *
 * Rows come from a 4-COLUMN LATIN RECTANGLE over the region's state pool:
 * four random permutations of the pool used as columns, redrawn until no row
 * contains a duplicate state. Column index == difficulty level. This gives:
 *
 *   - 4 distinct states per row                          (rectangle property)
 *   - all 4 difficulties per row                         (one per column)
 *   - each state exactly once at each difficulty per      (each column is a
 *     rectangle, so K times over K stacked rectangles      permutation)
 *
 * K rectangles are stacked per region, so rows = K * poolSize.
 *
 * Random rectangles are used rather than the first four columns of a cyclic
 * balanced Latin square (e.g. @quentinroy/latin-square). That library's first
 * row is [0, 1, n-1, 2, ...], so its first four columns form the contiguous
 * offset window {-1, 0, 1, 2}: states only ever co-occur within cyclic distance
 * 3. In the 15-state South pool that leaves 60 of 105 pairs structurally unable
 * to co-occur, and shuffling the pool first only relabels which states are
 * neighbours. Random rectangles carry the same balance guarantees with no
 * structural holes.
 *
 * Row blocks are `fixed`, not `latinSquare`, for two reasons: a fixed block
 * registers no Latin-square path (avoiding the uneven-pop drift above), and
 * shuffleSequenceToAvoidConsecutiveRegions re-shuffles all 16 trials at the end
 * anyway, so within-row order is not observable.
 *
 * NOTE: the region block MUST stay `latinSquare`. `fixed` with numSamples 1
 * would slice(0, 1) a fixed list and hand every participant row 0 forever.
 *
 * Usage:  node generateBalancedSequence.cjs [--in FILE] [--out FILE]
 *                                           [--k N] [--seed N] [--num-sequences N]
 */

const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const args = process.argv.slice(2);
const argOf = (flag, fallback) => {
  const i = args.indexOf(flag);
  return i === -1 ? fallback : args[i + 1];
};

const IN_FILE = path.resolve(argOf('--in', path.join(__dirname, 'configWIP.json')));
const OUT_FILE = path.resolve(argOf('--out', path.join(__dirname, 'configLatinRect.json')));
const K = Number(argOf('--k', 4)); // rectangles stacked per region
const SEED = Number(argOf('--seed', 20260810)); // fixed seed => reproducible config
const NUM_SEQUENCES = Number(argOf('--num-sequences', 800));

const DIFFICULTIES = [1, 2, 3, 4];

// ---------------------------------------------------------------------------
// Seeded RNG (mulberry32) - keeps regeneration reproducible
// ---------------------------------------------------------------------------

function makeRng(seed) {
  let a = seed >>> 0;
  return function rng() {
    a += 0x6D2B79F5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rng = makeRng(SEED);

function shuffled(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------------------------------------------------------------------------
// 4-column Latin rectangle
// ---------------------------------------------------------------------------

/**
 * Build a poolSize x 4 array. Each column is a permutation of the pool; no row
 * repeats a state. Columns are drawn one at a time and redrawn on conflict --
 * far cheaper than rejecting whole rectangles (the 4th column accepts with
 * probability ~e^-3, so ~20 draws).
 */
function latinRectangle(pool) {
  const n = pool.length;
  if (n < 4) throw new Error(`pool too small for a 4-column rectangle: ${n}`);

  const columns = [];
  for (let c = 0; c < 4; c += 1) {
    let candidate = null;
    for (let attempt = 0; attempt < 10000 && candidate === null; attempt += 1) {
      const perm = shuffled(pool);
      const clash = perm.some((v, row) => columns.some((col) => col[row] === v));
      if (!clash) candidate = perm;
    }
    if (candidate === null) throw new Error(`could not place column ${c} for pool size ${n}`);
    columns.push(candidate);
  }

  return Array.from({ length: n }, (_, row) => columns.map((col) => col[row]));
}

/**
 * K stacked rectangles => K * poolSize rows of 4 states, with no row repeated.
 *
 * Stacking independent rectangles occasionally repeats a row by chance (36 rows
 * drawn against 9*8*7*6 = 3024 possible NE tuples gives ~0.2 collisions per
 * region). A duplicated row is drawn twice as often as its neighbours and costs
 * a distinct combination, so a rectangle that collides is redrawn whole --
 * individual rows cannot be swapped out without breaking the column-permutation
 * property that the balance guarantee rests on.
 */
function stackRectangles(pool, k) {
  const rows = [];
  const seen = new Set();

  for (let i = 0; i < k; i += 1) {
    let placed = false;
    for (let attempt = 0; attempt < 200 && !placed; attempt += 1) {
      const rect = latinRectangle(pool);
      const keys = rect.map((r) => r.join('|'));
      if (keys.some((key) => seen.has(key)) || new Set(keys).size !== keys.length) continue;
      keys.forEach((key) => seen.add(key));
      rows.push(...rect);
      placed = true;
    }
    if (!placed) throw new Error(`could not place rectangle ${i} without duplicate rows (pool ${pool.length})`);
  }

  return rows;
}

/**
 * Score a candidate row set by how evenly states are paired up.
 *
 * Every candidate already has identical state x difficulty balance (each state
 * exactly K times at each difficulty), so that is not what we are choosing on.
 * What varies is which states share a row. With K=4 the South pool gets 60 rows
 * covering 60*6=360 pair-slots against C(15,2)=105 possible pairs -- roughly 3.4
 * per pair -- so a handful of pairs land on zero purely by chance (~3% each).
 * Returns [numberOfPairsNeverCoOccurring, spread] and we minimise both.
 */
function pairScore(pool, rows) {
  // Canonical key so initialisation and counting share one key space.
  const pk = (a, b) => (a < b ? `${a}|${b}` : `${b}|${a}`);

  const counts = new Map();
  pool.forEach((a, i) => pool.slice(i + 1).forEach((b) => counts.set(pk(a, b), 0)));

  rows.forEach((row) => {
    for (let a = 0; a < row.length; a += 1) {
      for (let b = a + 1; b < row.length; b += 1) {
        const key = pk(row[a], row[b]);
        if (!counts.has(key)) throw new Error(`pair key outside pool: ${key}`);
        counts.set(key, counts.get(key) + 1);
      }
    }
  });

  const values = [...counts.values()];
  const zeros = values.filter((v) => v === 0).length;
  const spread = Math.max(...values) - Math.min(...values);
  return [zeros, spread];
}

/**
 * Draw several candidate row sets and keep the best-paired one. Cheap: the
 * balance guarantees hold for every candidate, so this only trades a little
 * generation time for tighter co-occurrence.
 */
function buildRows(pool, k, attempts = 400) {
  let best = null;
  let bestScore = [Infinity, Infinity];

  for (let i = 0; i < attempts; i += 1) {
    const candidate = stackRectangles(pool, k);
    const score = pairScore(pool, candidate);
    if (score[0] < bestScore[0] || (score[0] === bestScore[0] && score[1] < bestScore[1])) {
      best = candidate;
      bestScore = score;
    }
    if (bestScore[0] === 0 && bestScore[1] <= 2) break; // good enough, stop early
  }

  return { rows: best, score: bestScore };
}

// ---------------------------------------------------------------------------
// Read the existing structure so nothing is hard-coded
// ---------------------------------------------------------------------------

const config = JSON.parse(fs.readFileSync(IN_FILE, 'utf8'));

const LEAF_RE = /^([a-z]+)_([A-Z]{2})_([A-Z]{2})_([1-4])$/;

/** Walk a condition block and pull out its prefix, region order and state pools. */
function describeCondition(conditionBlock) {
  const trialBlocks = conditionBlock.components.filter((c) => typeof c !== 'string');
  if (trialBlocks.length !== 1) {
    throw new Error(`expected exactly one trial block per condition, found ${trialBlocks.length}`);
  }
  const regionContainer = trialBlocks[0];

  let prefix = null;
  const regions = regionContainer.components.map((regionBlock) => {
    let regionCode = null;
    const pool = regionBlock.components.map((stateBlock) => {
      const leaf = stateBlock.components[0];
      const m = LEAF_RE.exec(leaf);
      if (!m) throw new Error(`unrecognised leaf component name: ${leaf}`);
      const [, pfx, reg, state] = m;
      if (prefix === null) prefix = pfx;
      else if (prefix !== pfx) throw new Error(`mixed prefixes in one condition: ${prefix} vs ${pfx}`);
      if (regionCode === null) regionCode = reg;
      else if (regionCode !== reg) throw new Error(`mixed regions in one block: ${regionCode} vs ${reg}`);
      return state;
    });
    return { regionCode, pool };
  });

  return { prefix, regions, regionContainer };
}

// ---------------------------------------------------------------------------
// Rebuild
// ---------------------------------------------------------------------------

const topBlock = config.sequence.components.find(
  (c) => typeof c !== 'string' && c.order === 'latinSquare',
);
if (!topBlock) throw new Error('could not locate the top-level condition block');

const described = topBlock.components.map(describeCondition);

// All conditions must expose the same regions in the same order with the same
// state pools -- otherwise a shared row set cannot be reused across them.
const signature = (d) => JSON.stringify(d.regions.map((r) => [r.regionCode, r.pool]));
const baseline = signature(described[0]);
described.forEach((d, i) => {
  if (signature(d) !== baseline) {
    throw new Error(`condition ${i} (${d.prefix}) has a different region/state structure`);
  }
});

/*
 * One row set per region, SHARED across all 8 conditions (only the component
 * prefix differs). Condition is the between-subjects manipulation, so holding
 * the stimulus pool identical means a performance difference between, say, HOPs
 * and pixel cannot be attributed to one group drawing a different mix of
 * state/difficulty combinations. Independent per-condition sets would leave that
 * resting on matched marginals alone, which is a weaker guarantee.
 *
 * Note this is set-level matching, not participant-level: each condition's
 * region block owns its own Latin square and pops independently, so participant
 * i in one condition does not line up with participant i in another.
 */
const report = [];
const sharedRows = new Map();

described[0].regions.forEach(({ regionCode, pool }) => {
  const { rows, score } = buildRows(pool, K);
  sharedRows.set(regionCode, rows);
  report.push({
    region: regionCode,
    poolSize: pool.length,
    rows: rows.length,
    zeroPairs: score[0],
    pairSpread: score[1],
  });
});

described.forEach(({ prefix, regions, regionContainer }) => {
  regionContainer.components = regions.map(({ regionCode }) => ({
    order: 'latinSquare',
    numSamples: 1,
    components: sharedRows.get(regionCode).map((states) => ({
      order: 'fixed',
      components: states.map(
        (state, i) => `${prefix}_${regionCode}_${state}_${DIFFICULTIES[i]}`,
      ),
    })),
  }));
});

config.uiConfig.numSequences = NUM_SEQUENCES;

// ---------------------------------------------------------------------------
// Sanity checks before writing (the standalone verifier does the deeper pass)
// ---------------------------------------------------------------------------

const defined = new Set(Object.keys(config.components));
const missing = [];
topBlock.components.forEach((conditionBlock) => {
  conditionBlock.components
    .filter((c) => typeof c !== 'string')
    .forEach((regionContainer) => {
      regionContainer.components.forEach((regionBlock) => {
        regionBlock.components.forEach((row) => {
          row.components.forEach((leaf) => {
            if (!defined.has(leaf)) missing.push(leaf);
          });
        });
      });
    });
});
if (missing.length) throw new Error(`undefined component references: ${missing.slice(0, 5).join(', ')}`);

fs.writeFileSync(OUT_FILE, `${JSON.stringify(config, null, 2)}\n`);

console.log(`seed=${SEED}  k=${K}  numSequences=${NUM_SEQUENCES}`);
console.log(`conditions=${topBlock.components.length}`);
console.log('row sets are shared across all conditions (prefix swapped only)');
report.forEach((r) => {
  console.log(
    `  ${r.region}: pool=${r.poolSize} rows=${r.rows} (${K} rectangles)`
    + `  pairs-never-together=${r.zeroPairs} pair-spread=${r.pairSpread}`,
  );
});
console.log(`wrote ${OUT_FILE}`);
