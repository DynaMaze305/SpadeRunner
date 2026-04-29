"""
    Helper that creates a fresh numbered run directory under a parent
    folder, named <prefix>_<N>_<timestamp>. Used by any agent that
    groups a batch of output files into its own run.
"""

import os
import datetime


# Creates a new run directory and returns its path and run id
def new_run_dir(parent: str, prefix: str, with_timestamp: bool = True):
    os.makedirs(parent, exist_ok=True)

    # Increments the Folder directory name
    existing_runs = []
    for name in os.listdir(parent):
        full = os.path.join(parent, name)
        if name.startswith(f"{prefix}_") and os.path.isdir(full):
            parts = name.split("_")
            if len(parts) >= 2 and parts[1].isdigit():
                existing_runs.append(int(parts[1]))
    run_id = max(existing_runs, default=-1) + 1

    # creates the name for the subdirectory
    if with_timestamp:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(parent, f"{prefix}_{run_id}_{timestamp}")
    else:
        run_dir = os.path.join(parent, f"{prefix}_{run_id}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir, run_id
