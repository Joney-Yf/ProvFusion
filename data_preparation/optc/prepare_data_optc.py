"""OpTC data-preparation entry point: raw OpTC logs -> edge_embeds (TemporalData.simple).

Additive sibling of `data_preparation/prepare_data.py` for the three OpTC hosts
(OPTC_h201 / OPTC_h051 / OPTC_h501). It reuses the SAME stage implementations
(graph construction, word2vec featurization, edge embedding) and the SAME isolation
knobs (--out_suffix / --raw_data_dir / --run_from / --run_to / --skip_build_gt),
differing only in:

  1. the stage-1 ingester (OpTC JSON schema, hostname filtering, READ/inbound reversal)
  2. the relation vocabulary: OpTC's 10 event types (OPEN/READ/CREATE/MESSAGE/MODIFY/
     START/RENAME/DELETE/TERMINATE/WRITE) instead of DARPA TC's EVENT_* types.

Both differences are injected process-locally at startup (see the rel2id patch below);
no TC file is modified, and a TC run in another process is unaffected.

Usage (run from the OpenProvFusion project root):

    # full pipeline, isolated DB + isolated publish dir
    PYTHONHASHSEED=0 python data_preparation/optc/prepare_data_optc.py OPTC_h201 \
        --out_suffix _Test_for_OpenSource --raw_data_dir ../raw_data_opensource

    # resume from a later stage
    PYTHONHASHSEED=0 python data_preparation/optc/prepare_data_optc.py OPTC_h201 \
        --out_suffix _Test_for_OpenSource --raw_data_dir ../raw_data_opensource \
        --run_from graphs

Prerequisites: same as prepare_data.py (Postgres with schema — create the isolated DBs
with `data_preparation/optc/init-create-databases-optc.sh [out_suffix]`; raw JSON dir
set via local_config.json datasets.<NAME>.raw_dir).
"""

import os
import sys
import time

# MIGRATION: make `data_preparation/` the import root (same trick as prepare_data.py).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DP_DIR = os.path.dirname(_THIS_DIR)
if _DP_DIR not in sys.path:
    sys.path.insert(0, _DP_DIR)

import config

# The OpTC relation vocabulary patch. The vendored stage modules do
# `from config import *` and read the module-level `rel2id`; patching it BEFORE those
# imports makes every stage in THIS process speak OpTC's 10 event types. TC runs in
# other processes see the unpatched config — zero cross-contamination.
config.rel2id = config.rel2id_optc

import prepare_data as prep  # noqa: E402  (stage modules inside bind the patched rel2id)
from optc import create_database_optc  # noqa: E402

STAGES = prep.STAGES


def main():
    prep_args, cfg_args = prep.parse_args()
    cfg = config.get_yml_cfg(cfg_args)

    if cfg.dataset.name.lower() not in create_database_optc.OPTC_hostname_map:
        raise ValueError(
            f"prepare_data_optc.py only handles {sorted(create_database_optc.OPTC_hostname_map)}; "
            f"got {cfg.dataset.name}. Use prepare_data.py for DARPA TC datasets."
        )

    prep.apply_out_suffix(cfg, prep_args.out_suffix)

    # mirror prep.main's seeding
    import numpy as np
    import torch
    import random
    if cfg.edge_featurization.embed_nodes.use_seed:
        seed = cfg._seed
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    start = STAGES.index(prep_args.run_from)
    stop = STAGES.index(prep_args.run_to)
    if start > stop:
        raise ValueError(f"--run_from after --run_to in {STAGES}")

    def _selected(stage):
        return start <= STAGES.index(stage) <= stop

    times = {}
    t0 = time.time()

    t = t0
    if _selected("create_db"):
        prep.log("=" * 60)
        prep.log("[stage 1/4] create_db: raw OpTC logs -> Postgres")
        prep._assert_db_ready_and_empty(cfg)
        create_database_optc.main(cfg)
        times["create_db"] = round(time.time() - t, 2)

        # canonical labels for THIS database (same auto-derive as the TC entry point)
        if not prep_args.skip_build_gt:
            repo_root = os.path.dirname(_DP_DIR)
            builder = os.path.join(repo_root, "tools", "build_ground_truth.py")
            tag = "regen" if prep_args.out_suffix else "orig"
            out_prefix = os.path.join(repo_root, "gt_canonical", f"{cfg.dataset.name}_{tag}")
            import subprocess
            r = subprocess.run(
                [sys.executable, builder, cfg.dataset.name, cfg.dataset.database, out_prefix],
                capture_output=True, text=True, cwd=repo_root,
            )
            for ln in (r.stdout + r.stderr).strip().splitlines():
                prep.log(f"[build_gt] {ln}")
            if r.returncode != 0:
                if "KeyError" in r.stderr:
                    prep.log(f"[build_gt] dataset {cfg.dataset.name} has no canonical CSV spec — skipped")
                else:
                    raise RuntimeError("build_ground_truth failed; see [build_gt] log lines above")
            else:
                prep.log(f"[build_gt] labels for database '{cfg.dataset.database}' -> {out_prefix}_*.pt")

    t = time.time()
    if _selected("graphs"):
        prep.log("=" * 60)
        prep.log("[stage 2/4] graphs: Postgres -> per-time-window nx graphs")
        prep.build_orthrus_graphs.main(cfg)
        times["graphs"] = round(time.time() - t, 2)

    t = time.time()
    if _selected("featurization"):
        prep.log("=" * 60)
        prep.log("[stage 3/4] featurization: node msgs -> feature_word2vec.model")
        prep.build_feature_word2vec.main(cfg)
        times["featurization"] = round(time.time() - t, 2)

    t = time.time()
    if _selected("embed"):
        prep.log("=" * 60)
        prep.log("[stage 4/4] embed: graphs + word2vec -> edge_embeds")
        prep.embed_edges_feature_word2vec.main(cfg)
        times["embed"] = round(time.time() - t, 2)

    if _selected("embed"):
        prep.log("=" * 60)
        prep.log("[publish] Exposing edge_embeds as a dataset")
        prep.publish_as_dataset(
            cfg, prep_args.raw_data_dir, prep_args.publish_mode, prep_args.force_publish
        )
    else:
        prep.log("=" * 60)
        prep.log(f"[publish] Skipped: --run_to {prep_args.run_to} stops before the embed stage.")

    times["total"] = round(time.time() - t0, 2)
    prep.log("=" * 60)
    prep.log("Data preparation finished. Time per stage (s):")
    for k, v in times.items():
        prep.log(f"  {k}: {v}")


if __name__ == "__main__":
    main()
