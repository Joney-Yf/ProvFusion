# OpTC data preparation

Additive OpTC sibling of the TC pipeline (`../prepare_data.py`). Raw OpTC JSON logs
(DARPA OpTC, host-filtered per dataset) → Postgres → per-day graphs → Word2Vec
featurization → edge embeddings (`*.TemporalData.simple`), published as
`../raw_data*/OPTC_h{201,051,501}`.

The OpTC integration is **additive**. The stage-1 ingester and the OpTC relation
vocabulary (10 event types: OPEN, READ, CREATE, MESSAGE, MODIFY, START, RENAME, DELETE,
TERMINATE, WRITE) live in this directory and in additive entries in `../config.py`
(`rel2id_optc`, `OPTC_DATASETS`, and three `OPTC_h*` dataset configurations). Shared TC
configuration and ground-truth files gain OpTC entries, but TC stage implementations and
behavior are unchanged. Graph construction, featurization, and edge embedding are reused
unchanged; `prepare_data_optc.py` patches `rel2id` **process-locally at startup**, so TC
runs in other processes are unaffected.

The ingester (`create_database_optc.py`) is vendored from the pipeline that produced the
original OpTC databases; its `pidsmaker` dependencies are inlined or resolved from our
vendored modules (marked `# MIGRATION`).

## Prerequisites

Run all commands from the repository root in the project Python environment.

1. **Raw logs.** Obtain DARPA OpTC through its official distribution channel and extract
   the host archives. Raw logs are not redistributed in this repository. Each configured
   directory must contain that host's JSON files (nested directories are supported):
   - `OPTC_h201` → the extracted `h201/` directory
   - `OPTC_h051` → the extracted `h051/` directory
   - `OPTC_h501` → the extracted `h501/` directory
2. **Local configuration.** Copy `data_preparation/local_config.example.json` to
   `data_preparation/local_config.json`, set the Postgres credentials, and set each host's
   `datasets.<DATASET>.raw_dir`. This file is gitignored; do not commit local paths or
   credentials.
3. **Postgres.** Start Postgres and initialize the isolated databases (once):

   ```bash
   data_preparation/optc/init-create-databases-optc.sh _Test_for_OpenSource
   ```

   The target database must be **empty**. Stage 1 only inserts and aborts if tables already
   contain data; it never drops or truncates an existing database. For an already-ingested
   isolated database, resume with `--run_from graphs` instead of ingesting again.

## Generate embeddings

```bash
# Full pipeline for one host
PYTHONHASHSEED=0 python data_preparation/optc/prepare_data_optc.py OPTC_h201 \
    --out_suffix _Test_for_OpenSource --raw_data_dir ../raw_data_opensource

# Repeat for OPTC_h051 or OPTC_h501. Resume from a later stage when appropriate:
PYTHONHASHSEED=0 python data_preparation/optc/prepare_data_optc.py OPTC_h201 \
    --out_suffix _Test_for_OpenSource --raw_data_dir ../raw_data_opensource \
    --run_from graphs
```

The four stages are `create_db` → `graphs` → `featurization` → `embed`. The final publish
step creates `../raw_data_opensource/OPTC_h201/{train,val,test}` as a symlink to the new
`*.TemporalData.simple` embeddings. The isolation flags only affect the database name and
the publish parent directory; the dataset name remains canonical for training.

## Canonical ground truth

Attack nodes are recorded by UUID in `Ground_Truth_csv/OPTC-h*/`. Stage 1 automatically
resolves them against the newly ingested database and writes:

```
gt_canonical/OPTC_h201_regen_ground_truth_nids.pt
gt_canonical/OPTC_h201_regen_attack_to_nids.pt
```

When resuming with `--run_from graphs`, stage 1 is skipped; if labels have not yet been
built, build them explicitly (the database name is lowercase):

```bash
python tools/build_ground_truth.py OPTC_h201 optc_h201_test_for_opensource \
    gt_canonical/OPTC_h201_regen
```

Never reuse original-database labels with regenerated data: node indices depend on the
ingestion. The evaluation attack map must likewise be the matching `_regen_` file.

## Merge and train

Use a new merged-data filename for every fresh embedding draw. `preprocess.py` skips an
existing output, and the trainer reuses an existing `--data_path` without rebuilding it.

```bash
# Convert the newly published per-graph embeddings
python preprocess.py --dataset OPTC_h201 \
    --raw_data_dir ../raw_data_opensource --output_dir .
mv optc_h201_merge_edge_normalized.pt optc_h201_my_regen.pt

# Evaluation reads this map from the current working directory
ln -sf gt_canonical/OPTC_h201_regen_attack_to_nids.pt OPTC_h201_attack_to_nids.pt

# OPTC_h201 paper configuration (training is stochastic even with seed 1)
CUDA_VISIBLE_DEVICES=0 python main_transductive.py --device 0 \
    --dataset OPTC_h201 \
    --data_path optc_h201_my_regen.pt \
    --ground_truth_path gt_canonical/OPTC_h201_regen_ground_truth_nids.pt \
    --raw_data_dir ../raw_data_opensource \
    --encoder gatedge --decoder gat --num_hidden 64 --num_heads 2 --mask_rate 0.5 \
    --num_layers 2 --lr 0.0015 --weight_decay 0.0001 --lr_f 0.001 --weight_decay_f 0.000002 \
    --max_epoch 500 --max_epoch_f 10 --in_drop 0.2 --attn_drop 0.1 --drop_edge_rate 0.0 \
    --loss_fn sce --optimizer adam --alpha_l 3 --replace_rate 0.0 --activation prelu \
    --norm layernorm --linear_prob --scheduler --seeds 1 --normalization_method percentile
```

For h051/h501, substitute the dataset, paths, attack map, and hyperparameters from the root
README's Best Hyperparameters table (`lr_f=0.0005` for both). Training saves a middle result
and evaluates it automatically.

## Exact replay versus fresh regeneration

The root README lists the selected OpTC Option-D checkpoints, their pinned merged data,
and matching regenerated labels. **Replay those exact artifacts with Option A to reproduce
the listed TP/FP values.** Fresh regeneration and retraining are stochastic: Word2Vec
creates a new embedding draw, and the shuffled multi-worker edge-reconstruction head makes
training non-bit-reproducible even with a fixed seed. The selected rows are observed draws,
not guaranteed or necessarily typical single-run outcomes.
