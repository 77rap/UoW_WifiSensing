# Data-generation spec — dynamic-clutter cell (Scene 2)

Status: **draft for implementation** · Author decisions locked 2026-07-26.
Supersedes the fixed-scene assumption for the active task; the Scene 1
dataset (`hrc_ur10_cell_data_v0_robot.npz`) stays as the clean-room anchor.

## 1. Purpose

Test whether a device-free WiFi CSI model can detect and coarsely locate
**humans** in the UR10 cell when the environment also contains **variable
machinery** — mobile robots (AGVs) that appear in different places, in
different numbers, or not at all, each snapshot. The fixed-scene result is
easy partly because the one robot is removed by background subtraction; this
scene makes "detect humans *despite* moving machines" the actual test.

The central difficulty is that a channel change no longer means "a human is
here" — an AGV moving also changes the channel. The model must separate
**human**-induced perturbation from **machine**-induced perturbation, and the
key risk becomes **false alarms** (a machine read as a human).

## 2. Locked design decisions

| # | Decision | Value |
|---|----------|-------|
| 1 | Clutter type | **one AGV class** (metal box). Multiple object types = future work. |
| 2 | Input | **raw = primary**; **static-bgsub = free comparison**; **no oracle**. |
| 3 | AGV count per snapshot | **0–3**, uniform (includes 0 = no clutter). |
| 4 | UR10 | **fixed**; `count` is **humans only**. |

Everything fixed in Scene 1 stays fixed (room, fixtures, UR10, TX, AP, radio
config) so results are directly comparable to the anchor.

## 3. Coordinate frame & fixed scene (from `hrc_ur10_cell.json`)

Metres; +z up; floor z=0; bay centred at origin.

- **Room:** 12 × 10 × 3.5 m (walls concrete, ceiling metal).
- **UR10 (fixed, metal):** 3 boxes near origin (`Robot_base`, `Robot_shoulder`,
  `Robot_arm`). Safety-zone centre = (0, 0), **red r ≤ 1.6 m**, **yellow r ≤
  2.8 m**, else green.
- **Fixed fixtures (metal):** CNC (0, 1.9), Cabinet (−2.5, −0.5), Operator_bench
  (0, −2.2), Pallet (2.2, 0.3). Footprints are the exclusion boxes in the JSON.
- **TX ×4 (fixed):** the four `suggested_tx` positions on existing equipment.
- **AP (fixed):** ceiling at (1.5, −1.2, 3.4), 4 antennas.
- **Legal placement rect (`worker_region`):** x ∈ [−5.5, 5.5], y ∈ [−4.5, 4.5],
  minus the object-footprint exclusion boxes.

## 4. Radio configuration (unchanged from Scene 1)

f = 3.5 GHz · 64 subcarriers · K_TX = 4 · M_AP = 4 · dipole arrays · PathSolver
(max_depth 5, LoS + specular + refraction, `synthetic_array=True`). Bandwidth is
**auto-tuned on the empty cell** exactly as before (Scene 1 chose 40 MHz). Hold
this identical so the clutter effect is the only change vs the anchor.

## 5. Human model (unchanged from Scene 1)

- Count ~ uniform {0, 1, 2}. Rigid dielectric sphere proxy (ε_r ≈ 48, σ ≈ 3),
  radius 0.30 m, torso centre z = 1.0 m. (Refine to a cylinder later — noted.)
- Placement uses the existing **robot-biased sampler** (bias toward the centre
  so red/yellow zones stay populated), min separation 0.7 m between humans,
  rejected if outside the legal rect or inside a fixture footprint.

## 6. AGV clutter model (new)

| Property | Value |
|----------|-------|
| Object | metal box (AGV / mobile robot) |
| Size (L×W×H) | **1.0 × 0.8 × 0.4 m**, centre z = 0.2 m (on floor) |
| Material | metal (same as fixtures) — strong reflector |
| Orientation | axis-aligned in v0 (random yaw = future work) |
| Count per snapshot | uniform {0, 1, 2, 3} |
| Max concurrent | `MAX_AGV = 3` movable objects, parked when unused |

**AGV placement region & constraints.** Sample the AGV centre in the legal rect
shrunk by the AGV bounding radius (~0.64 m) → x ∈ [−4.86, 4.86], y ∈ [−3.86,
3.86]. Reject a candidate if its footprint (axis-aligned 1.0 × 0.8 box):

- overlaps any **fixed-fixture** exclusion box (axis-aligned box–box test), or
- is inside the **robot standoff** — centre distance from origin < red radius
  (1.6 m) — see below, or
- comes within clearance of a **human** (centre distance < ~1.0 m), or
- comes within `AGV_MIN_SEP` (~1.4 m) of **another AGV**.

**AGVs are excluded from the red zone.** The red ring is the robot's own
stop/operating envelope (UR10 reach 1.3 m); routing a mobile robot into it is
physically unrealistic (collision, no free floor). AGVs keep a standoff of
`AGV_ROBOT_STANDOFF = red_radius` (1.6 m) from the origin — allowed in **yellow
and green**, never **red**. The confounders that matter remain: an AGV in
yellow/green misread as a human, or an AGV **occluding** a human.

## 7. Per-snapshot generation procedure

For snapshot *i* (all sampling seeded → deterministic → resumable):

1. Draw `human_count ~ U{0,1,2}`; place humans with the biased sampler
   (§5). Record `positions[i]` (NaN for absent).
2. Draw `agv_count ~ U{0,1,2,3}`; place AGVs (§6) avoiding humans, fixtures,
   UR10, and each other (K attempts each; reduce `agv_count` if a slot can't be
   filled). Record `agv_positions[i]` (NaN for absent).
3. Position the human + AGV SceneObjects; **park** all unused ones far outside
   the sealed room (no RF effect).
4. Trace → `csi_raw[i]` (shape [M_AP, K_TX, N_sub]).

## 8. Reference trace (single, static)

Before the sweep, park **all** humans and **all** AGVs and trace once →
`csi_empty` = room + fixtures + UR10 only. This is the **one** extra trace (the
fixed background is fixed, so no per-snapshot reference — this is what makes
static-bgsub free, unlike the rejected oracle). Then:

```
csi_bgsub = csi_raw - csi_empty      # removes fixed background; leaves AGV + human
```

Note the **changed semantics**: unlike Scene 1, `csi_bgsub` now contains *both*
clutter and human perturbations (only the fixed room is removed). Document this
clearly — the model's `INPUT='raw'|'bgsub'` switch is the §2 ablation.

## 9. Labels (humans only) + evaluation subsets

Computed from **human** positions only; AGVs never contribute to a label.

- `presence` ∈ {0,1} — any human present.
- `count` ∈ {0,1,2} — number of humans.
- `zone` ∈ {0,1,2,3} = none / green / yellow / red — most-severe ring any human
  occupies (distance from origin vs r=1.6 / 2.8).

**False-alarm set (new, important):** the subset `count==0 & agv_count≥1` —
no human but clutter present. This is where false alarms are measured; the
design produces it naturally (~1/3 of samples have 0 humans, most with ≥1 AGV).

## 10. Stored npz schema

Keeps Scene 1 keys (so the existing model + EDA notebooks work unchanged) and
adds AGV metadata.

| Key | Shape | Dtype | Meaning |
|-----|-------|-------|---------|
| `csi_raw` | [N, 4, 4, 64] | complex64 | channel with clutter + humans |
| `csi_bgsub` | [N, 4, 4, 64] | complex64 | `csi_raw − csi_empty` (clutter + human) |
| `csi_empty` | [4, 4, 64] | complex64 | static reference (no AGV, no human) |
| `presence` | [N] | int8 | human present |
| `count` | [N] | int8 | human count 0/1/2 |
| `zone` | [N] | int8 | 0/1/2/3 |
| `positions` | [N, 2, 2] | float32 | human x,y (NaN if absent) |
| `agv_count` | [N] | int8 | 0–3 |
| `agv_positions` | [N, 3, 2] | float32 | AGV x,y (NaN if absent) |
| `split` | [N] | \<U5 | train/val/test (random, §11) |
| meta scalars | — | — | `freq_hz`, `num_subcarriers`, `subcarrier_spacing_hz`, `k_tx`, `m_ap`, `human_z`, `human_scale`, `agv_size` [3], `agv_z`, `max_agv`, `variant='dynamic'`, `zone_center` [2], `red_radius`, `yellow_radius`, `zone_labels` [4] |

## 11. Splits

- **Core (default `split`):** stratified random by human `count`, 70/15/15.
  Answers "can the model sense humans under clutter at all?" (in-distribution).
- **Generalisation (derived in the model notebook, not stored):** **clutter
  hold-out** — train on `agv_count ≤ 2`, test on `agv_count == 3`. Answers "does
  it handle *more* clutter than it trained on?" All metadata is stored, so this
  split (and a spatial human hold-out, if wanted) is derivable without
  regenerating.

## 12. Dataset size & sim cost

- **N = 8,000** for v0 (matches the anchor; fast; bump to ~16k later only if a
  learning curve justifies it — the extra clutter axis may want more data).
- Cost: 3 extra metal boxes make each solve heavier. Expect roughly **1.5–2×**
  the Scene 1 rate (~6/s → ~3–4/s) → **~35–45 min** on Colab GPU. Reuse the
  existing timing-calibration cell (projects the run before committing) and
  checkpoint/resume every 1,000 (optionally to Drive for safety).

## 13. Determinism & reproducibility

Single seeded RNG drives human counts/positions **and** AGV counts/positions, in
a fixed order, so a resumed run is bit-identical. Store every position so splits
can be redefined at load time without regenerating.

## 14. Post-generation validation (sanity cells)

- **0 NaNs** in `csi_raw`.
- Human `count` ≈ 1/3 each; `zone` has a usable share of yellow + red.
- `agv_count` ≈ 1/4 each; **false-alarm subset** (`count==0 & agv≥1`) has a
  few hundred+ samples.
- **New EDA — condition on clutter.** In Scene 1, mean |bgsub| was ~0 for
  count-0. Here count-0 samples with AGVs have **non-zero** bgsub (clutter
  shows up). So group the magnitude summary by **(human count × agv count)**
  and check: (0 human, 0 AGV) ≈ 0; (0 human, ≥1 AGV) > 0 = the confound;
  (≥1 human, 0 AGV) > 0 = the human signal. This is the picture the model must
  disentangle.
- Position scatter: humans (by zone) + AGV footprints.

## 15. Downstream compatibility

- **Model notebook** (`csi_multitask_v0.ipynb`): change `DATA_NAME` to the new
  file; the `raw|bgsub` input switch, the three heads, and the metrics all work
  unchanged. Add the **false-alarm** and **robustness-vs-AGV-count** evaluations,
  and the clutter-hold-out split.
- **Pandas EDA** (already added): reads the same keys; gains `agv_count` and
  `agv_positions` columns for the per-sample DataFrame. Add the
  (human × agv) conditional magnitude check.

## 16. Deliverables

Edit in place — no new versioned copies (the folder is under git; git holds the
history). Minimum repeated information.

- **`data_generation_ur10.ipynb` — edited in place.** Adds AGV objects +
  placement, agv sampling, agv metadata in the npz, and the (human × agv) sanity
  cell. Clutter is behind a flag (`MAX_AGV`): **set it > 0 for the dynamic
  dataset, 0 to reproduce the Scene 1 anchor** — one notebook makes both, no
  duplicated code. The output filename keys off the mode so the anchor `.npz` is
  never clobbered.
- **`csi_multitask_v0.ipynb` — edited in place** later: repoint `DATA_NAME`, add
  the false-alarm / robustness-vs-AGV eval + clutter-hold-out split.
- `hrc_ur10_dynamic_clutter_v0.npz` — the dataset (git-ignored; regenerable).

## 17. Parameters (defaults)

| Name | Default | Name | Default |
|------|---------|------|---------|
| `N_SAMPLES` | 8000 | `MAX_AGV` | 3 |
| `MAX_WORKERS` | 2 | `AGV_SIZE` | (1.0, 0.8, 0.4) |
| `HUMAN_Z` | 1.0 | `AGV_Z` | 0.2 |
| `HUMAN_SCALE` | 0.30 | `AGV_MIN_SEP` | 1.4 |
| `MIN_SEP` (human) | 0.7 | `AGV_HUMAN_CLEAR` | 1.0 |
| `BIAS_P` (human) | 0.55 | `AGV_COUNT_MAX` | 3 |
| `AGV_ROBOT_STANDOFF` | 1.6 (=red_radius) | AGV in red? | **no** |
| `RNG_SEED` | 0 | `agv_count` dist | uniform 0–3 |

## 18. Out of scope / future work

- Multiple clutter classes (pallets, carts, forklifts) and random AGV yaw.
- Cylinder/articulated human proxy.
- Moving/temporal clutter (needs a time dimension — outside the static-snapshot
  scope).
- Spatial human hold-out and full cross-scene (different room) generalisation.
- The physics-integration ladder (delay/angle representation, etc.) evaluated on
  the robustness / clutter-hold-out splits.
