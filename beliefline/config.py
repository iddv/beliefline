"""Configuration from environment variables (read at call time)."""
import os
from pathlib import Path

SETTINGS = {
    "writes.version_check": ("optional", ("optional", "required")),
    "writes.unchanged_set": ("record", ("record", "skip")),
    "retract.allowed_by": ("operator_only", ("operator_only", "operator_and_agent")),
    "display.time_zone": ("local", ("local", "utc")),
    "asof.seq_in_batch": ("whole_batch", ("through_seq", "whole_batch",)),
    "archive.operator_writes": ("allowed", ("allowed", "refused",)),
    "agent.reactivate_keys": ("restored", ("restored", "disabled",)),
    "writes.delete_absent": ("recorded", ("recorded", "refused",)),
}

# Settings whose environment variable is the bare name below. It overrides the stored value everywhere.
OVERRIDE_ENV = {}
OVERRIDE_ENV["asof.seq_in_batch"] = "ASOF_SEQ_IN_BATCH"
OVERRIDE_ENV["archive.operator_writes"] = "ARCHIVE_OPERATOR_WRITES"
OVERRIDE_ENV["agent.reactivate_keys"] = "AGENT_REACTIVATE_KEYS"
OVERRIDE_ENV["writes.delete_absent"] = "WRITES_DELETE_ABSENT"


def setting_env_name(key):
    return "BELIEFLINE_" + key.upper().replace(".", "_")


def data_dir():
    return Path(os.environ.get("BELIEFLINE_DATA_DIR") or "~/.beliefline").expanduser()


def host():
    return os.environ.get("BELIEFLINE_HOST") or "127.0.0.1"


def port():
    return int(os.environ.get("BELIEFLINE_PORT") or 7700)


def url():
    return os.environ.get("BELIEFLINE_URL")


def limit(name, default):
    v = os.environ.get("BELIEFLINE_" + name)
    return int(v) if v else default


def max_batch():
    return limit("MAX_BATCH", 100)


def max_value_bytes():
    return limit("MAX_VALUE_BYTES", 64 * 1024)


def max_reason():
    return limit("MAX_REASON", 2000)


def max_source():
    return limit("MAX_SOURCE", 200)


def max_keys_per_agent():
    return limit("MAX_KEYS", 10)


def max_read_keys():
    return limit("MAX_READ_KEYS", 50)


def explain_depth():
    return limit("EXPLAIN_DEPTH", 10)


def max_body():
    return limit("MAX_BODY", 16 * 1024 * 1024)
