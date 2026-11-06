"""OpTC dataset preprocessing - create PostgreSQL database from JSON logs.

Parses OpTC provenance JSON files and populates PostgreSQL database with nodes
(subjects, files, netflows) and events (edges) for graph construction.

MIGRATION: vendored from PIDSMaker_newer `dataset_preprocessing/optc/create_database_optc.py`
(the pipeline that produced the original OpTC databases). The `pidsmaker` package
dependencies are inlined here (`OPTC_hostname_map`, `OPTC_datetime_to_timestamp_US`)
or resolved from our own vendored modules (`provnet_utils`, `config`). The parsing
logic itself is verbatim.
"""
import json
import os
import sys
import time
from datetime import datetime
from time import mktime

import pytz
from psycopg2 import extras as ex
from tqdm import tqdm

# MIGRATION: resolve vendored modules both through prepare_data_optc.py and when
# this file is invoked directly for usage guidance.
_DP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DP_DIR not in sys.path:
    sys.path.insert(0, _DP_DIR)

# MIGRATION: our own vendored helpers (same algorithms as pidsmaker's).
from provnet_utils import log, stringtomd5, init_database_connection
from config import rel2id_optc

# MIGRATION: inlined from pidsmaker/utils/dataset_utils.py (verbatim values).
OPTC_hostname_map = {
    "optc_h051": "SysClient0051",
    "optc_h201": "SysClient0201",
    "optc_h501": "SysClient0501",
}


def OPTC_datetime_to_timestamp_US(date):
    """convert OPTC datetime string to timestamp in nanoseconds (verbatim)."""
    date = date.replace("-04:00", "")
    if "." in date:
        date, ms = date.split(".")
    else:
        ms = 0
    tz = pytz.timezone("Etc/GMT+4")
    timeArray = time.strptime(date, "%Y-%m-%dT%H:%M:%S")
    dt = datetime.fromtimestamp(mktime(timeArray))
    timestamp = tz.localize(dt)
    timestamp = timestamp.timestamp()
    timeStamp = timestamp * 1000 + int(ms)
    return int(timeStamp) * 1000000


def get_all_filelist(filepath):
    """get all file paths under the given filepath recursively (verbatim)."""
    file_paths = []
    for root, dirs, files in os.walk(filepath):
        for file in files:
            full_path = os.path.join(root, file)
            abs_path = os.path.abspath(full_path)
            file_paths.append(abs_path)
    return file_paths


def save_nodes(cfg, dataset_dir):
    hostname = OPTC_hostname_map[cfg.dataset.name.lower()]
    all_paths = get_all_filelist(dataset_dir)

    rel2id = rel2id_optc

    subject_uuid2attr = {}
    netflow_uuid2attr = {}
    file_uuid2attr = {}

    for i, file in enumerate(all_paths):
        with open(file, "r") as f:
            for line in tqdm(f, desc=f"Extracting nodes from {i}-th/{len(all_paths)} file."):
                line = line.replace("\\\\", "/")
                temp_dic = json.loads(line.strip())

                if temp_dic["hostname"].split(".")[0] != hostname:
                    continue

                if temp_dic["action"] not in rel2id:
                    continue

                if temp_dic["object"] not in ["FILE", "FLOW", "PROCESS"]:
                    continue

                src_uuid = temp_dic["actorID"]
                dst_uuid = temp_dic["objectID"]

                # Process src_node
                if "image_path" in temp_dic["properties"]:
                    subject_uuid2attr[src_uuid] = (temp_dic["properties"]["image_path"], None)
                else:
                    subject_uuid2attr[src_uuid] = (None, None)

                # Process dst_node
                if temp_dic["object"] == "FILE":
                    if "file_path" in temp_dic["properties"]:
                        file_uuid2attr[dst_uuid] = temp_dic["properties"]["file_path"]
                    else:
                        file_uuid2attr[dst_uuid] = None
                elif temp_dic["object"] == "FLOW":
                    if "src_ip" in temp_dic["properties"]:
                        src_ip = temp_dic["properties"]["src_ip"]
                    else:
                        src_ip = None
                    if "dest_ip" in temp_dic["properties"]:
                        dst_ip = temp_dic["properties"]["dest_ip"]
                    else:
                        dst_ip = None
                    if "src_port" in temp_dic["properties"]:
                        src_port = temp_dic["properties"]["src_port"]
                    else:
                        src_port = None
                    if "dest_port" in temp_dic["properties"]:
                        dst_port = temp_dic["properties"]["dest_port"]
                    else:
                        dst_port = None

                    netflow_uuid2attr[dst_uuid] = (src_ip, src_port, dst_ip, dst_port)
                elif temp_dic["object"] == "PROCESS":
                    if "parent_image_path" in temp_dic["properties"]:
                        path = temp_dic["properties"]["parent_image_path"]
                    else:
                        path = None
                    if "command_line" in temp_dic["properties"]:
                        cmd = temp_dic["properties"]["command_line"]
                    else:
                        cmd = None
                    subject_uuid2attr[dst_uuid] = (path, cmd)

    index_id = 0
    cur, connect = init_database_connection(cfg)
    uuid2index_id = {}

    # Save subject_nodes
    datalist = []
    for sub_uuid, sub_attr in tqdm(
        subject_uuid2attr.items(), desc=f"Processing datalist for subject nodes"
    ):
        temp_data = [sub_uuid, stringtomd5(str(sub_attr)), sub_attr[0], sub_attr[1], index_id]
        datalist.append(temp_data)
        uuid2index_id[sub_uuid] = index_id
        index_id += 1

    log(f"Start saving subject nodes.")
    sql = """insert into subject_node_table
                             values %s
                """
    ex.execute_values(cur, sql, datalist, page_size=10000)
    connect.commit()
    log(f"Finished saving subject nodes.")
    del subject_uuid2attr
    del datalist

    # Save file_nodes
    datalist = []
    for file_uuid, file_attr in tqdm(file_uuid2attr.items(), desc=f"Processing file nodes"):
        temp_data = [file_uuid, stringtomd5(str(file_attr)), file_attr, index_id]
        datalist.append(temp_data)
        uuid2index_id[file_uuid] = index_id
        index_id += 1

    log(f"Start saving file nodes.")
    sql = """insert into file_node_table
                             values %s
                """
    ex.execute_values(cur, sql, datalist, page_size=10000)
    connect.commit()
    log(f"Finished saving file nodes.")
    del file_uuid2attr
    del datalist

    # Save netflow_nodes
    datalist = []
    for net_uuid, net_attr in tqdm(netflow_uuid2attr.items(), desc="Processing net nodes"):
        temp_data = [
            net_uuid,
            stringtomd5(str(net_attr)),
            net_attr[0],
            net_attr[1],
            net_attr[2],
            net_attr[3],
            index_id,
        ]
        datalist.append(temp_data)
        uuid2index_id[net_uuid] = index_id
        index_id += 1

    log(f"Start saving net nodes.")
    sql = """insert into netflow_node_table
                             values %s
                """
    ex.execute_values(cur, sql, datalist, page_size=10000)
    connect.commit()
    log(f"Finished saving net nodes.")
    del netflow_uuid2attr
    del datalist

    return uuid2index_id


def save_events(cfg, uuid2index_id, dataset_dir):
    hostname = OPTC_hostname_map[cfg.dataset.name.lower()]
    all_paths = get_all_filelist(dataset_dir)

    rel2id = rel2id_optc

    cur, connect = init_database_connection(cfg)

    for i, file in enumerate(all_paths):
        with open(file, "r") as f:
            datalist = []
            for line in tqdm(f, desc=f"Extracting events from {i}-th/{len(all_paths)} file."):
                line = line.replace("\\\\", "/")
                temp_dic = json.loads(line.strip())

                reverse_flag = False

                if temp_dic["hostname"].split(".")[0] != hostname:
                    continue

                operation = temp_dic["action"]
                if operation not in rel2id:
                    continue

                if operation in ["READ"]:
                    reverse_flag = True

                src_uuid = temp_dic["actorID"]
                dst_uuid = temp_dic["objectID"]
                if (src_uuid not in uuid2index_id) or (dst_uuid not in uuid2index_id):
                    continue
                else:
                    src_index_id = uuid2index_id[src_uuid]
                    dst_index_id = uuid2index_id[dst_uuid]

                event_uuid = temp_dic["id"]

                if (temp_dic["object"] == "FLOW") and ("direction" in temp_dic["properties"]):
                    if temp_dic["properties"]["direction"] == "inbound":
                        reverse_flag = True

                timestr = temp_dic["timestamp"]
                timestamp = OPTC_datetime_to_timestamp_US(timestr)

                if reverse_flag:
                    temp_data = [
                        dst_uuid,
                        dst_index_id,
                        operation,
                        src_uuid,
                        src_index_id,
                        event_uuid,
                        timestamp,
                    ]
                else:
                    temp_data = [
                        src_uuid,
                        src_index_id,
                        operation,
                        dst_uuid,
                        dst_index_id,
                        event_uuid,
                        timestamp,
                    ]

                datalist.append(temp_data)

            log(f"Start saving events for {i}-th/{len(all_paths)} file.")
            sql = """insert into event_table
                                        values %s
                        """
            ex.execute_values(cur, sql, datalist, page_size=50000)
            connect.commit()
            log(f"Finish saving events for {i}-th/{len(all_paths)} file.")


def main(cfg):
    dataset_name = cfg.dataset.name  # e.g. OPTC_h201 (trainer-style name)
    raw_dir = cfg.dataset.raw_dir
    if not os.path.isdir(raw_dir):
        raise RuntimeError(
            f"OpTC raw_dir not found: {raw_dir}\n"
            f"Set it via data_preparation/local_config.json "
            f"(datasets.{dataset_name}.raw_dir — see local_config.example.json)."
        )

    uuid2index_id = save_nodes(cfg, raw_dir)
    log(f"Finished saving nodes.")

    save_events(cfg, uuid2index_id, raw_dir)
    log(f"Finished saving events.")


if __name__ == "__main__":
    raise SystemExit(
        "Direct ingestion is disabled to preserve the empty-database and isolation guards. "
        "Run `python data_preparation/optc/prepare_data_optc.py --help` from the repository root."
    )
