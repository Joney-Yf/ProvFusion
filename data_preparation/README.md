# data_preparation — raw logs → `edge_embeds` (a new dataset)

This package migrates the **front-end** of the original `orthrus_for_data_prepration`
project (the PIDSMaker/Orthrus framework) into OpenProvFusion. It produces the per-edge
embedded graphs (`edge_embeds`) that the current training pipeline consumes — closing the
one gap in the refactored project: *how to turn raw DARPA system logs into the framework's
data format.*

Only the four stages that build `edge_embeds` were migrated. The detection /
attack_reconstruction stages of the original project were **not** migrated.

## What it does

```
1. create_db       raw JSON logs        -> Postgres database  (create_database/)
2. graphs          Postgres database    -> per-time-window networkx graphs  (graph_construction/)
3. featurization   Postgres node msgs   -> feature_word2vec.model  (edge_featurization/)
4. embed           graphs + word2vec    -> edge_embeds/{train,val,test}/*.TemporalData.simple
```

The stage-4 output is **byte-compatible** with what the trainer already expects: each
`*.TemporalData.simple` is a PyG `TemporalData` whose `.msg` is
`[node_type(3) | src_vec(128) | edge_type(10) | node_type(3) | dst_vec(128)]` = 272 dims —
exactly the layout sliced by `graphmae/datasets/data_util.py::convert_to_dgl_data`.

## How it connects to the existing trainer (two modes preserved)

- **Mode A (unchanged default):** if `../raw_data/{DATASET}/{train,val,test}` already
  exists, `main_transductive.py` → `preprocess.py` → `Custimized` loads it as today. This
  package changes nothing on that path.
- **Mode B (new):** run this package first to *generate* `edge_embeds` from raw logs and
  publish it as `../raw_data/{DATASET}`. Then train exactly as before.

The final "publish" step exposes the produced `edge_embeds` dir as `../raw_data/{DATASET}`
(default: a **symlink**, no data duplication), so the existing loader finds it with zero
code changes.

For the three DARPA OpTC hosts (`OPTC_h201`, `OPTC_h051`, `OPTC_h501`), use the additive
OpTC entry point and its host-specific ingester; see `optc/README.md` for the complete
raw-log → labels → merged data → training sequence. The TC commands below are unchanged.

## Usage (run from the OpenProvFusion project root, inside the `orthrus` conda env)

```bash
# Full pipeline from raw logs, then publish as ../raw_data/CLEARSCOPE_E3
PYTHONHASHSEED=0 python data_preparation/prepare_data.py CLEARSCOPE_E3

# Resume from a later stage (e.g. DB already built):
PYTHONHASHSEED=0 python data_preparation/prepare_data.py CLEARSCOPE_E3 --run_from graphs

# Run a SINGLE stage (step-by-step verification): e.g. only create_db
PYTHONHASHSEED=0 python data_preparation/prepare_data.py CLEARSCOPE_E3 \
    --run_from create_db --run_to create_db

# Override any orthrus.yml param via the original dotted CLI syntax:
PYTHONHASHSEED=0 python data_preparation/prepare_data.py CLEARSCOPE_E3 \
    --graph_construction.build_graphs.time_window_size=1.0

# Validate WITHOUT touching the original DB or the original dataset folder (dev):
data_preparation/postgres/init-create-databases.sh _Test_for_OpenSource   # build the isolated DB first
PYTHONHASHSEED=0 python data_preparation/prepare_data.py CLEARSCOPE_E3 \
    --out_suffix _Test_for_OpenSource --raw_data_dir ../raw_data_opensource
# -> ingests into DB clearscope_e3_test_for_opensource (original DB untouched)
#    publishes ../raw_data_opensource/CLEARSCOPE_E3 (folder name kept; original untouched)
# then train with the SAME dataset name (configs.yml / DATASET_WEIGHTS keep matching):
#   python main_transductive.py --dataset CLEARSCOPE_E3 \
#       --raw_data_dir ../raw_data_opensource --data_path clearscope_e3_opensource.pt ...
# Drop --out_suffix / --raw_data_dir (defaults) for the clean release run on originals.
```

Flags added by this package (everything else is the original config parser):

| flag | default | meaning |
|------|---------|---------|
| `--run_from {create_db,graphs,featurization,embed}` | `create_db` | first stage to run (resume support) |
| `--run_to {create_db,graphs,featurization,embed}` | `embed` | last stage to run, inclusive. `--run_from X --run_to X` runs a single stage; publish runs only when `embed` is included |
| `--out_suffix STR` | `""` | **database** isolation suffix: appended (lowercased) to the Postgres DB names so all stages hit a separate DB and the original is never ingested into. Does **not** rename the published folder (keeps `--dataset` NAME valid for configs.yml/weights). Empty = original DB names |
| `--raw_data_dir PATH` | `../raw_data` | where to publish the dataset (matches the trainer's loader). Point at a separate parent dir to isolate the published **data** without renaming the folder |
| `--publish_mode {symlink,copy,none}` | `symlink` | how to expose `edge_embeds` as `{raw_data_dir}/{DATASET}` |
| `--force_publish` | off | allow publish to delete an existing **real** (non-symlink) `{raw_data_dir}/{DATASET}` |

Unknown arguments (e.g. a typo'd dotted override) abort with an error, same as the
original `orthrus.py` entry point.

> **Reproducibility:** always export `PYTHONHASHSEED=0`. The original project relies on it
> so Gensim's Word2Vec produces deterministic vectors (see the original README).

## Prerequisites (server environment — unchanged from the original project)

1. **Postgres running** and reachable with `DATABASE_DEFAULT_CONFIG` in `config.py`
   (defaults: host=localhost, user=postgres, port=5432). The DB password and the
   per-dataset `raw_dir` paths are placeholders in the repo; copy
   `data_preparation/local_config.example.json` to `data_preparation/local_config.json`
   (gitignored) and fill in your own — it is applied automatically.
2. **Schema created.** The stage-1 scripts `INSERT` into pre-existing tables; they do **not**
   create them. Create the databases + tables first using the vendored
   `postgres/init-create-databases.sh [out_suffix]` (the full-schema variant —
   `init-create-empty-databases.sh` only creates empty databases). It builds `event_table`,
   `file_node_table`, `netflow_node_table`, `subject_node_table` for each dataset. Pass the
   same string you give `--out_suffix` to build isolated DBs (e.g.
   `init-create-databases.sh _Test_for_OpenSource`) instead of the originals.
3. **Raw JSON logs** present at the `raw_dir` path for each dataset. The repo ships
   placeholder paths in `DATASET_DEFAULT_CONFIG`; set your real paths via
   `data_preparation/local_config.json` (see point 1).
4. **Empty database.** Stage 1 aborts if any of the four tables already contains rows:
   the INSERT scripts have no TRUNCATE/upsert logic (re-running would crash on duplicate
   keys), and — more subtly — a from-scratch re-ingestion can assign **different
   `index_id`s** (file enumeration order is filesystem-dependent). The existing
   `Ground_Truth/ground_truth_nids_*.pt` files are valid **only for the DB ingestion they
   were generated against**; rebuilding the DB silently invalidates them. To reuse an
   already-populated database, resume with `--run_from graphs`. If you really rebuild,
   TRUNCATE the four tables first and regenerate the ground-truth nids afterwards.

## Notes / deliberate decisions (`# MIGRATION` / `# TODO` markers in code)

- **Mimicry injection is DISABLED.** The original `build_orthrus_graphs.py` hardcoded
  `mimicry_edge_num = 1000`, which injected ~3000 synthetic "attack-mimicry" edges into every
  graph and required the `Ground_Truth/darpa` CSVs. For clean data preparation it is set to
  `0` (see the `# MIGRATION` comment in `graph_construction/build_orthrus_graphs.py`):
  `gen_mimicry_edges()` is never called and all mimicry code paths become no-ops. `mimicry.py`
  is still vendored so the `import` resolves; set the value `>0` (and provide `Ground_Truth/darpa`)
  to re-enable.
- **Vendored verbatim** from `orthrus_for_data_prepration/src/`: `config.py`, `provnet_utils.py`,
  `create_database/`, `graph_construction/`, `edge_featurization/`, `mimicry.py`, plus
  `config/orthrus.yml` and `postgres/`. Only `config.py` was adapted (path-depth fixes, marked
  `# MIGRATION`) because it moved from `src/` to `data_preparation/` (which is itself the import
  root). The algorithm code is unchanged.
- **DB password and `raw_dir` paths** are placeholders in the repo; real values live in
  the gitignored `data_preparation/local_config.json` (see `local_config.example.json`).
- The vendored `orthrus.yml` still contains `detection` / `attack_reconstruction` sections
  (the config validator requires them), but those stages are never imported or run here.

## Keeping the originals safe (DB vs data are isolated separately)

The pipeline starts (stage 1) by **ingesting into Postgres**, and by default targets the
original database name (`clearscope_e3`, …) and publishes to the original
`../raw_data/{DATASET}`. No code path drops/recreates/truncates anything — stage 1 only
`INSERT`s, and the guards below refuse to clobber a populated DB or a real dataset folder —
but the *names* it touches are the originals. Two independent knobs isolate the two risks:

- **Database → `--out_suffix`.** Appended (lowercased) to the Postgres DB names so every
  stage reads/writes a separate DB (`clearscope_e3_<suffix>`); the original DB is never
  ingested into. It deliberately does **not** rename the published dataset folder.
- **Published data → `--raw_data_dir`.** The folder name stays `cfg.dataset.name` (e.g.
  `CLEARSCOPE_E3`) on purpose: training keys `configs.yml` best-configs and `DATASET_WEIGHTS`
  by the `--dataset` NAME, so renaming the folder would force a new name and break those
  lookups. To avoid clobbering the original `../raw_data/{DATASET}`, publish into a separate
  parent dir (`--raw_data_dir ../raw_data_opensource`) — same folder name, new location —
  then train with the **unchanged** `--dataset CLEARSCOPE_E3` plus a fresh `--data_path`.
- Intermediate artifacts already live under `data_preparation/artifacts/` (keyed by dataset
  *name* + config hash, independent of the DB name), so they never collide regardless.
- Recommended for validation; for the release run omit both (defaults) to produce the clean
  original DB name + original `../raw_data/{DATASET}`.

## Publishing safety / re-run gotchas

- **Publish never deletes a real dataset by default.** The publish step only replaces a
  previous *symlink* publication. If `../raw_data/{DATASET}` exists and is a real
  directory/file (e.g. a pre-existing Mode-A dataset), publish aborts with an error;
  pass `--force_publish` to overwrite, or use `--raw_data_dir` / `--publish_mode none`.
  Note: a previous `--publish_mode copy` publication is a real directory too, so
  re-publishing over it also needs `--force_publish`.
- **Stale merged `.pt`.** `preprocess.py` skips regeneration when its output file already
  exists. After publishing a *new* dataset, delete/rename the old merged `.pt` (the file
  passed to the trainer as `--data_path`, e.g. `clearscope_e3.pt`) — otherwise training
  silently keeps using the old data.
