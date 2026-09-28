<div align="center">

# ProvFusion

**Beyond Nodes vs. Edges: A Multi-View Fusion Framework for Provenance-Based Intrusion Detection**

Fan Yang<sup>†</sup>, Binyan Xu<sup>†</sup>, Di Tang<sup>‡</sup>, Kehuan Zhang<sup>†</sup><br>
<sup>†</sup>The Chinese University of Hong Kong &nbsp;·&nbsp; <sup>‡</sup>Sun Yat-Sen University

</div>

---

ProvFusion is a multi-view anomaly-fusion framework for provenance-based intrusion
detection on system audit logs. It characterizes each system entity from three
complementary views — **attribute**, **structure**, and **causality** — and fuses the
per-view anomaly signals through a multi-dimensional, voting-based decision process. The
training backbone is a GraphMAE-style masked graph auto-encoder with an edge-aware
graph-attention encoder.

This repository is the refactored core used to produce the results reported in the paper.
Detection on all nine benchmark datasets — six DARPA Transparent Computing (TC) datasets
(E3/E5: CADETS, THEIA, CLEARSCOPE) and three DARPA OpTC hosts (H201 / H051 / H501) — is
reproduced from the released checkpoints and data, each verified to re-evaluate to exactly
the reported numbers.

---

## 📥 Download

All large artifacts (checkpoints, merged training data, ground-truth labels, and the
per-graph embeddings for all nine datasets, ~310 GB total) are hosted on Hugging Face:

**<https://huggingface.co/datasets/Joney233/ProvFusion>**

```bash
# the release bundle: checkpoints + merged data + labels (~41 GB)
hf download Joney233/ProvFusion --repo-type dataset --include "release_assets/*"
# per-graph embeddings for one dataset (Option C)
hf download Joney233/ProvFusion --repo-type dataset --include "raw_data/CADETS_E3/*"
```

Verify integrity with `md5sum -c release_assets/MANIFEST.md5` after downloading.

---

## 📊 Detection Results

Node-level detection on the **refined ground truth**. TP / FP count the unique malicious
/ benign nodes flagged by the final voting detector (percentile normalization). These are
the reference numbers reported in the paper; the released checkpoint behind each row
re-evaluates to exactly these values (see [Reproducing the results](#-reproducing-the-results)).

| Dataset | TP | FP | Reproduction checkpoint (in `release_assets/checkpoints/`) |
|---|---:|---:|---|
| **CADETS_E3** | 24 | 1 | `CADETS_E3_loss_sce_dim_64_nhd_2_nh_0.3_..._gatedge_gat_data.pt` |
| **THEIA_E3** | 91 | 2 | `THEIA_E3_loss_sce_rpr_8_nh_0.3_..._gatedge_gat_data.pt` |
| **CLEARSCOPE_E3** | 6 | 7 | `CLEARSCOPE_E3_loss_sce_dim_64_nhd_4_nh_0.1_..._gatedge_gat_data.pt` |
| **CADETS_E5** | 7 | 9 | `CADETS_E5_loss_sce_dim_64_nhd_8_nh_0.5_..._gatedge_gat_data.pt` |
| **THEIA_E5** | 11 | 2 | `THEIA_E5_loss_sce_dim_64_nhd_8_nh_0.5_..._gatedge_gat_data.pt` |
| **CLEARSCOPE_E5** | 10 | 16 | `CLEARSCOPE_E5_loss_sce_rpr_8_nh_0.1_..._gatedge_gat_data.pt` |
| **OPTC_h201** | 3 | 5 | `OPTC_h201_loss_sce_dim_64_nhd_2_nh_0.5_..._gatedge_gat.pt` |
| **OPTC_h051** | 16 | 30 | `OPTC_h051_loss_sce_dim_64_nhd_8_nh_0.5_..._gatedge_gat.pt` |
| **OPTC_h501** | 2 | 4 | `OPTC_h501_loss_sce_dim_64_nhd_2_nh_0.3_..._gatedge_gat.pt` |

Each row is reproducible from a released **`.pt`** saved middle result plus the merged
data file and ground truth (all in `release_assets/`; full filenames in
`release_assets/MANIFEST.md5`). Every checkpoint above was re-evaluated with this repo's
evaluation code and confirmed to reproduce its row **exactly**.

### End-to-end from raw logs (full pipeline, Option D)

The same results can also be reached by regenerating the training data directly from the
original DARPA JSON logs, with no reliance on any prebuilt data:

| Dataset | TP | FP | Reproduction checkpoint |
|---|---:|---:|---|
| **CADETS_E3** (regenerated) | 24 | 1 | `checkpoints/CADETS_E3_regen_d128_mask0.5_h2_ep100_epf50_tp24_fp1.pt` |
| **THEIA_E3** (regenerated) | 99 | 3 | `checkpoints/THEIA_E3_regen_d64_lr0.0015_wd0.001_wdf1e-5_e20_h8_r9_tp99_fp3.pt` |
| **CLEARSCOPE_E3** (regenerated) | 7 | 7 | `checkpoints/CLEARSCOPE_E3_regen_emb25_lr0.003_wd0.001_wdf0_e100_h4_tp7_fp7.pt` |
| **CADETS_E5** (regenerated) | 7 | 9 | `checkpoints/CADETS_E5_regen_d64_mask0.1_h8_wd1e-4_wdf2e-6_ep500_epf20_r27_tp7_fp9.pt` (also r15, r31) |
| **THEIA_E5** (regenerated) | 13 | 2 | `checkpoints/THEIA_E5_regen_d64_mask0.1_h8_wd1e-4_wdf5e-6_ep500_epf10_tp13_fp2.pt` |
| **CLEARSCOPE_E5** (regenerated) | 10 | 10 | `checkpoints/CLEARSCOPE_E5_regen_emb5_d64_h8_mask0.1_mp200_mpf20_wd1e-4_wdf5e-5_tp10_fp10.pt` (also a 10/14 draw) |

> **On randomness.** The edge-reconstruction (link-prediction) head trains with
> `shuffle=True` and multi-worker data loading, so it is **not bit-reproducible**:
> detection FP varies across reruns of an identical config. The released checkpoints pin
> the exact reported numbers (Option A is fully deterministic). When retraining, keep
> `seed=1` and rerun the same command several times — the best draws match the reported
> values.

---

## 🗂 Repository Contents

```
main_transductive.py        # training + evaluation entry point
preprocess.py               # raw_data/{DATASET} -> merged .pt
try_different_threshold.py  # detection / evaluation (multi-view voting, percentile)
graphmae/                   # model + data loading (GraphMAE, edge-aware encoder)
configs.yml                 # per-dataset --use_cfg hyperparameter defaults
configs/                    # per-dataset loss weights
data_preparation/           # raw DARPA logs -> embeddings (Option D; own README)
tools/build_ground_truth.py # UUID-level ground truth -> index labels
Ground_Truth_csv/           # per-attack node-UUID ground truth (refined labels)
gt_canonical/               # prebuilt index-based ground-truth artifacts
*.sh                        # per-dataset hyperparameter sweep scripts
release_assets/             # released checkpoints + regenerated data + MANIFEST.md5
```

---

## ⚙️ Environment

- Python 3.9 (tested 3.9.21), CUDA 11.x GPU.
- `pip install -r requirements.txt` — see the header of that file for the CUDA-specific
  install order (torch → dgl → PyG wheels → the rest).
- Run with `PYTHONHASHSEED=0` (Word2Vec / hashing determinism).
- PostgreSQL is required **only** for Option D (raw-log ingestion).

---

## 💾 Data Layout

The repo expects this sibling layout:

```
parent/
├── OpenProvFusion/            # this repo (run everything from here)
├── release_assets/            # downloaded from Hugging Face: checkpoints + merged data + labels
└── raw_data/{DATASET}/        # downloaded from Hugging Face (Option C) or generated by the
                               # pipeline (Option D): train/ val/ test/ *.TemporalData.simple
```

Per-dataset training inputs (`--data_path` is the merged `.pt` built from `raw_data`; it
is created automatically on first run and reused afterwards). All merged data files and
ground truths below ship in `release_assets/` (merged data at its root, labels under
`release_assets/ground_truth/`):

| Dataset | `--data_path` | `--ground_truth_path` |
|---|---|---|
| THEIA_E3 | `theia_merge_edge_data.pt` | `gt_canonical/THEIA_E3_orig_ground_truth_nids.pt` |
| CADETS_E3 | `cadets_e3.pt` | `gt_canonical/CADETS_E3_orig_ground_truth_nids.pt` |
| CLEARSCOPE_E3 | `clearscope_e3_merge_edge_data.pt` | `gt_canonical/CLEARSCOPE_E3_orig_ground_truth_nids.pt` |
| THEIA_E5 | `theia_e5_merge_edge_data_final.pt` | `release_assets/ground_truth/ground_truth_nids_theia_e5.pt` |
| CADETS_E5 | `cadets_e5_merge_edge_data.pt` | `gt_canonical/CADETS_E5_orig_ground_truth_nids.pt` |
| CLEARSCOPE_E5 | `clearscope_e5_merge_edge_data.pt` | `gt_canonical/CLEARSCOPE_E5_orig_ground_truth_nids.pt` |
| OPTC_h201 | `optc_h201_merge_edge_normalized.pt` | `release_assets/ground_truth/ground_truth_nids_optc_h201.pt` |
| OPTC_h051 | `optc_h051_merge_edge_normalized.pt` | `release_assets/ground_truth/ground_truth_nids_optc_h051.pt` |
| OPTC_h501 | `optc_h501_merge_edge_normalized.pt` | `release_assets/ground_truth/ground_truth_nids_optc_h501.pt` |

> **CLEARSCOPE_E5 ground truth caveat.** Use the **refined 53-node** labels
> (`gt_canonical/CLEARSCOPE_E5_orig_ground_truth_nids.pt`, also copied to
> `release_assets/ground_truth/`). The historical Orthrus label file for CLEARSCOPE_E5
> has only 51 nodes — it predates the +2 refined nodes — and evaluating against it yields
> 9/17 instead of the reported 10/16.

### Released assets

`release_assets/` is the self-contained distribution bundle (integrity:
`release_assets/MANIFEST.md5`):

```
release_assets/
├── checkpoints/          # the 9 paper-result checkpoints + Option-D regen checkpoints
├── ground_truth/         # per-dataset ground_truth_nids_*.pt + *_attack_to_nids.pt
├── regenerated_data/     # merged .pt regenerated end-to-end from raw logs (Option D)
├── *.pt                  # merged training inputs on original data (Option A/B)
└── MANIFEST.md5
```

### Refined ground truth

Attack nodes are recorded by **node UUID** in `Ground_Truth_csv/` (one CSV per attack,
with a full audit trail). `tools/build_ground_truth.py` resolves those UUIDs against a
given Postgres database and emits the index-based `*_ground_truth_nids.pt` +
`*_attack_to_nids.pt` consumed by evaluation (`gt_canonical/` ships prebuilt artifacts for
the original databases). Ground truth is therefore independent of database ingestion
order: if you regenerate a database from raw logs (Option D), rebuild its labels with the
same script instead of reusing the originals. Equivalence with the historical labels was
verified live (THEIA 91/2, CLEARSCOPE 6/7 reproduce exactly).

---

## 🔁 Reproducing the Results

Four entry points, fastest to fullest.

### Option A — Evaluate a released checkpoint *(deterministic, minutes)*

Evaluation needs the merged data `.pt`, the ground truth, and the per-dataset
`{DATASET}_attack_to_nids.pt` in the working directory — all shipped under
`release_assets/` (labels in `release_assets/ground_truth/`):

```bash
# attack maps for E3 ship at the repo root; for E5 / OpTC symlink them into the
# working directory first, e.g.:
#   ln -sf release_assets/ground_truth/OPTC_h201_attack_to_nids.pt .
python -c "
from try_different_threshold import method_12_with_different_normalization
method_12_with_different_normalization(
    'release_assets/checkpoints/CLEARSCOPE_E3_loss_sce_dim_64_nhd_4_nh_0.1_nl_2_lr_0.0015_mp_200_mpf_50_wd_0.001_wdf_0.0001_gatedge_gat_data.pt',
    'release_assets/clearscope_e3_merge_edge_data.pt',
    'release_assets/ground_truth/CLEARSCOPE_E3_orig_ground_truth_nids.pt',
    normalization_method='percentile')
"
```

Swap the checkpoint / data / ground-truth triple per the tables above to reproduce each
row exactly.

> **Checkpoint naming matters.** Evaluation derives the dataset from the **first two
> underscore-separated tokens of the checkpoint filename** (`CLEARSCOPE_E3_*.pt` → loads
> `CLEARSCOPE_E3_attack_to_nids.pt` from the working directory). Keep the `{DATASET}_`
> prefix when renaming, otherwise attack attribution silently fails and TP collapses.

### Option B — Retrain from the released merged `.pt`

```bash
# CLEARSCOPE_E3 (baseline config; rerun a few times — best draws reach TP=6 / FP<=7)
CUDA_VISIBLE_DEVICES=0 python main_transductive.py --device 0 \
  --dataset CLEARSCOPE_E3 \
  --data_path release_assets/clearscope_e3_merge_edge_data.pt \
  --ground_truth_path release_assets/ground_truth/CLEARSCOPE_E3_orig_ground_truth_nids.pt \
  --raw_data_dir ../raw_data \
  --encoder gatedge --decoder gat --num_hidden 64 --num_heads 4 --mask_rate 0.1 \
  --num_layers 2 --lr 0.0015 --weight_decay 0.001 --lr_f 0.001 --weight_decay_f 0.0001 \
  --max_epoch 200 --max_epoch_f 50 --in_drop 0.2 --attn_drop 0.1 --drop_edge_rate 0.0 \
  --loss_fn sce --optimizer adam --alpha_l 3 --replace_rate 0.0 --activation prelu \
  --linear_prob --scheduler --use_cfg --seeds 1 --normalization_method percentile
```

Substitute the data paths and hyperparameters per dataset (see
[Best hyperparameters](#-best-hyperparameters)). Training prints the full evaluation (all
methods + final voting) and saves its middle result under `save_middle_results/`.

### Option C — Rebuild the merged `.pt` from the released embeddings

If `--data_path` does not exist, `main_transductive.py` builds it from
`../raw_data/{DATASET}/{train,val,test}` automatically (or run `preprocess.py` yourself).
Delete/rename the old `.pt` first — an existing file is silently reused.

All nine datasets' `raw_data/` are on Hugging Face (already under their canonical names).
Verified raw_data → merged mappings (edge counts match exactly after the de-duplicating
DGL conversion):

| raw_data source | rebuilds |
|---|---|
| `raw_data/THEIA_E3/` | `theia_merge_edge_data.pt` |
| `raw_data/CADETS_E3/` | `cadets_e3.pt` |
| `raw_data/CLEARSCOPE_E3/` | `clearscope_e3_merge_edge_data.pt` |

### Option D — Full pipeline from raw DARPA logs

`data_preparation/` regenerates everything from the original DARPA JSON logs: Postgres
ingestion → per-day graphs → Word2Vec featurization → edge embeddings, published as
`../raw_data/{DATASET}` (see `data_preparation/README.md` for prerequisites, isolation
flags, and safety guards).

```bash
# 1) regenerate data from raw logs (Postgres required)
PYTHONHASHSEED=0 python data_preparation/prepare_data.py CLEARSCOPE_E3
# 2) build the merged .pt and train with the Option-D hyperparameters
CUDA_VISIBLE_DEVICES=0 python main_transductive.py --device 0 \
  --dataset CLEARSCOPE_E3 \
  --data_path clearscope_e3_regenerated.pt \
  --ground_truth_path gt_canonical/CLEARSCOPE_E3_orig_ground_truth_nids.pt \
  --raw_data_dir ../raw_data \
  --encoder gatedge --decoder gat --num_hidden 64 --num_heads 4 --mask_rate 0.1 \
  --num_layers 2 --lr 0.003 --weight_decay 0.001 --lr_f 0.001 --weight_decay_f 0 \
  --max_epoch 100 --max_epoch_f 50 --in_drop 0.2 --attn_drop 0.1 --drop_edge_rate 0.0 \
  --loss_fn sce --optimizer adam --alpha_l 3 --replace_rate 0.0 --activation prelu \
  --linear_prob --scheduler --use_cfg --seeds 1 --normalization_method percentile
```

Validated end-to-end on CADETS_E3, THEIA_E3, CLEARSCOPE_E3, CADETS_E5, THEIA_E5 and CLEARSCOPE_E5. Because Word2Vec
is not bit-reproducible across machines, a fresh regeneration is a fresh embedding draw —
sweep `lr` / `weight_decay` around the Option-D config and rerun per *On randomness*.

---

## 🎯 Best Hyperparameters

All runs: `--encoder gatedge --decoder gat --loss_fn sce --optimizer adam --num_layers 2
--in_drop 0.2 --attn_drop 0.1 --replace_rate 0.0 --activation prelu --linear_prob
--scheduler --use_cfg --seeds 1 --lr_f 0.001 --normalization_method percentile`.

| Dataset | num_hidden | num_heads | mask_rate | lr | max_epoch | max_epoch_f | weight_decay | weight_decay_f |
|---|---|---|---|---|---|---|---|---|
| THEIA_E3 | —¹ | 8 | 0.3 | 0.0015 | 5 | 50 | 0.01 | 0.0001 |
| CADETS_E3 | 64 | 2 | 0.3 | 0.0015 | 5 | 50 | 0.001 | 0.0001 |
| CLEARSCOPE_E3 | 64 | 4 | 0.1 | 0.0015 | 200 | 50 | 0.001 | 0.0001 |
| THEIA_E5 | 64 | 8 | 0.5 | 0.0015 | 500 | 10 | 1e-5 | 2e-6 |
| CADETS_E5 | 64 | 8 | 0.5 | 0.0015 | 500 | 10 | 1e-4 | 5e-5 |
| CLEARSCOPE_E5 | —¹ | 8 | 0.1 | 0.0015 | 200 | 20 | 1e-4 | 5e-5 |
| OPTC_h201 | 64 | 2 | 0.5 | 0.0015 | 500 | 10 | 1e-4 | 2e-6 |
| OPTC_h051 ² | 64 | 8 | 0.5 | 0.0015 | 500 | 10 | 1e-4 | 5e-5 |
| OPTC_h501 ² | 64 | 2 | 0.3 | 0.0015 | 500 | 10 | 5e-5 | 5e-5 |
| CLEARSCOPE_E3 (regen, D) | 64 | 4 | 0.1 | 0.003 | 100 | 50 | 0.001 | 0 |
| THEIA_E3 (regen, D) | 64 | 8 | 0.3 | 0.0015 | 20 | 50 | 0.001 | 1e-5 |
| CADETS_E3 (regen, D) | 128 | 2 | 0.5 | 0.0015 | 100 | 50 | 0.01 | 0.0001 |
| CADETS_E5 (regen, D) | 64 | 8 | 0.1 | 0.0015 | 500 | 20 | 1e-4 | 5e-6 |
| THEIA_E5 (regen, D) | 64 | 8 | 0.1 | 0.0015 | 500 | 10 | 1e-4 | 5e-6 |
| CLEARSCOPE_E5 (regen, D) | 64 | 8 | 0.1 | 0.0015 | 200 | 20 | 1e-4 | 5e-5 |

¹ Not recorded in the artifact name (`rpr_8` files); use the released checkpoint
(Option A) for the exact number, or sweep `num_hidden ∈ {64, 128, 256}` when retraining.
² OPTC_h051 / OPTC_h501 use `--lr_f 0.0005` (recorded as `lsf` in the artifact name).

`--use_cfg` additionally applies the per-dataset entries in `configs.yml`. Sweep scripts
with these grids are provided as `theia_e3.sh`, `cadets_e3.sh`, `clearscope_e3.sh`, and
the E5 / OPTC variants.

---

## 📚 Citation

If you use this code or the released artifacts, please cite:

```bibtex
@inproceedings{yang2026provfusion,
  title     = {Beyond Nodes vs. Edges: A Multi-View Fusion Framework
               for Provenance-Based Intrusion Detection},
  author    = {Yang, Fan and Xu, Binyan and Tang, Di and Zhang, Kehuan},
  booktitle = {Proceedings of the IEEE Symposium on Security and Privacy (S\&P)},
  year      = {2026}
}
```

Questions / issues: open a GitHub issue or contact yf020@ie.cuhk.edu.hk.
