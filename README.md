# UoW WiFi Sensing

Master's dissertation project: **device-free worker sensing from WiFi
channel data in a simulated human–robot factory cell.**

From one static WiFi CSI snapshot, a small supervised network predicts three
things at once:

- **Presence** — is a worker in the cell? (yes / no)
- **Count** — roughly how many? (0 / 1 / 2+)
- **Safety zone** — which ISO/TS 15066 speed-and-separation ring around the
  robot the nearest worker is in (none / green / yellow / red).

The outputs are deliberately coarse — honest for device-free WiFi and enough
for the safety use case. This is a **simulation study**: it tests whether the
information is present in the CSI, not that a fielded product works.

> **Repo scope.** This repository is the Stage 2 working folder only. Stage 1
> (localisation, paused foundation), the project logs, and the planning
> documents live in the parent project folder and are **not** part of this
> repo.

## Pipeline

Four steps. Steps 1–3 build the simulated cell and turn it into a labelled
dataset; step 4 is the model.

| Step | Notebook | What it does |
|------|----------|--------------|
| 1. Build scene | `scenes/scene_builder_ur10.ipynb` | Generates the UR10 cell (Mitsuba XML + JSON safety-zone contract) into `scenes/hrc_ur10_cell/`. Source of truth. |
| 2. Validate scene | `validate_scene_ur10.ipynb` | Loads the scene in Sionna RT; confirms all links are alive and the zones are well covered. |
| 3. Generate data | `data_generation_ur10.ipynb` | Sweeps worker(s) through the cell, ray-traces the channel, writes the labelled dataset (`.npz`). |
| 4. Model | `csi_multitask_v0.ipynb` | Trains + evaluates the presence / count / zone network. |

Other files:

- `csi_ablation_input.ipynb` — raw-vs-background-subtracted input ablation.
- `csi_multitask_v0_backup_run1.ipynb` — preserved copy of the first trained
  run (kept as a fallback; git now handles versioning).
- `scenes/scene_builder.ipynb`, `scenes/make_industrial_cell.py` — earlier
  scene variants (`robot_cell`, `industrial_cell`), kept as fallbacks.
- `document/` — Word write-ups (git-ignored; binary and regenerated from
  scripts).

## Data (not in the repo)

The datasets (`*.npz`, ~100 MB each) are **git-ignored** — they are large and
fully **regenerable**, because data generation is seeded and deterministic.

To get the data, either:

1. run `data_generation_ur10.ipynb` (produces
   `hrc_ur10_cell_data_v0_robot.npz`), or
2. drop an existing `.npz` beside the notebooks.

The model notebook finds the file automatically (see below) — no path edits.

## Running the notebooks

The notebooks run **unchanged on both Colab and the lab machine**. The setup
cell auto-detects the environment: it searches for the dataset under Colab's
`/content`, the notebook's own folder, and the lab default project folder, and
picks the GPU if available else CPU.

- **Colab:** upload the notebook + `.npz` into `/content`, then Run all.
- **Lab machine:** keep the notebook + `.npz` in the same folder, then Run all.

> **Important — separate runtimes.** Data generation pins `numpy==2.0.2` for
> Sionna, which breaks stock PyTorch. **Never run the data-generation notebook
> and the model notebook in the same runtime.** If `import torch` fails with a
> `METH_CLASS`/`METH_STATIC` error: restart with a fresh runtime, re-upload,
> Run all.

## Environment

- **Data generation** (steps 1–3): Python + Sionna RT (`numpy==2.0.2`), GPU
  recommended (Colab GPU or the lab RTX PRO 5000).
- **Modelling** (step 4): Python + PyTorch + scikit-learn + matplotlib. Runs on
  GPU or CPU; on the lab machine it currently runs on CPU (GPU PyTorch is
  pending an IT whitelist).

A local `.venv` is used on the lab machine and is git-ignored.

## Status

Scene 1 (`hrc_ur10_cell`) is built, validated, and turned into an 8,000-sample
dataset; the multi-task model (`csi_multitask_v0`, ~406k params) is trained.

Headline test results (background-subtracted input):

- **Presence** — accuracy 0.998 (essentially solved).
- **Count** — accuracy 0.774 (0-vs-any perfect; all errors are 1-vs-2).
- **Zone** — balanced accuracy 0.629, red-zone recall 0.597 (the ceiling; a
  single static snapshot bounds how finely the zone can be resolved).

**Next:** the raw-vs-bgsub input ablation, then a robot-vs-no-robot
coverage comparison.
