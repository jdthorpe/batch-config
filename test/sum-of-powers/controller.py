""" conroller for the example
"""
# pylint: disable=invalid-name
import os
import datetime
import pathlib
import numpy  # pylint: disable=unused-import
import joblib
import super_batch
from constants import (
    GLOBAL_CONFIG_FILE,
    WORKER_INPUTS_FILE,
    WORKER_OUTPUTS_FILE,
    LOCAL_INPUTS_PATTERN,
    LOCAL_OUTPUTS_PATTERN,
)


# --------------------------------------------------
# CONSTANTS
# --------------------------------------------------
_TIMESTAMP: str = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
BATCH_DIRECTORY: str = os.path.expanduser("~/temp/super-batch-test")
NAME: str = "superbatchtest"
pathlib.Path(BATCH_DIRECTORY).mkdir(parents=True, exist_ok=True)

batch_client = super_batch.client(
    POOL_ID=NAME,
    JOB_ID=NAME + _TIMESTAMP,
    POOL_VM_SIZE="STANDARD_A1_v2",
    POOL_NODE_COUNT=0,
    POOL_LOW_PRIORITY_NODE_COUNT=1,
    DELETE_POOL_WHEN_DONE=False,
    BLOB_CONTAINER_NAME=NAME,
    BATCH_DIRECTORY=BATCH_DIRECTORY,
    DOCKER_IMAGE="jdthorpe/super-batch-test-sum-of-powers:v1",
    COMMAND_LINE="python /worker.py",
)


# --------------------------------------------------
# BUILD THE GLOBAL PARAMETER RESOURCE
# --------------------------------------------------
global_parameters = {"power": 3, "size": (10,)}
joblib.dump(global_parameters, os.path.join(BATCH_DIRECTORY, GLOBAL_CONFIG_FILE))
global_parameters_resource = batch_client.build_resource_file(
    GLOBAL_CONFIG_FILE, GLOBAL_CONFIG_FILE
)

# --------------------------------------------------
# BUILD THE BATCH TASKS
# --------------------------------------------------

SEEDS = (1, 12, 123, 1234)
for i, seed in enumerate(SEEDS):
    # CREATE THE ITERATION PAREMTERS RESOURCE
    param_file = LOCAL_INPUTS_PATTERN.format(i)
    joblib.dump({"seed": seed}, os.path.join(BATCH_DIRECTORY, param_file))
    input_resource = batch_client.build_resource_file(param_file, WORKER_INPUTS_FILE)

    # CREATE AN OUTPUT RESOURCE
    output_resource = batch_client.build_output_file(
        WORKER_OUTPUTS_FILE, LOCAL_OUTPUTS_PATTERN.format(i)
    )

    # CREATE A TASK
    batch_client.add_task(
        [input_resource, global_parameters_resource], [output_resource]
    )

# --------------------------------------------------
# RUN THE BATCH JOB
# --------------------------------------------------
batch_client.run()

# --------------------------------------------------
# AGGREGATE INTERMEDIATE STATISTICS
# --------------------------------------------------
out = [None] * len(SEEDS)
for i in range(len(SEEDS)):
    fpath = os.path.join(BATCH_DIRECTORY, LOCAL_OUTPUTS_PATTERN.format(i))
    out[i] = joblib.load(fpath)

print(sum(out))
