import pdb
import os
from os.path import join, expanduser
import datetime
import pathlib
import joblib
from task import task
import super_batch

from constants import (
    GLOBAL_RESOURCE_FILE,
    TASK_RESOURCE_FILE,
    TASK_OUTPUT_FILE,
    LOCAL_RESOURCE_PATTERN,
    LOCAL_OUTPUT_PATTERN,
)

# ------------------------------
# Configure the batch client
# ------------------------------

# The `$name` of our created resources:
NAME = os.environ.get("NAME", "superbatchtest")
IMAGE_NAME = os.environ.get("IMAGE_NAME")
assert IMAGE_NAME is not None

# a local directory where temporary files will be stored:
BATCH_DIRECTORY = expanduser("~/temp/super-batch-test")
pathlib.Path(BATCH_DIRECTORY).mkdir(parents=True, exist_ok=True)

# used to generate unique task names:
_TIMESTAMP = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")

# instantiate the batch helper client:
batch_client = super_batch.Client(
    POOL_ID=NAME,
    JOB_ID=NAME + _TIMESTAMP,
    POOL_VM_SIZE="STANDARD_D1_v2",
    POOL_NODE_COUNT=0,
    POOL_LOW_PRIORITY_NODE_COUNT=2,
    DELETE_POOL_WHEN_DONE=False,
    BLOB_CONTAINER_NAME=NAME,
    BATCH_DIRECTORY=BATCH_DIRECTORY,
    DOCKER_IMAGE=IMAGE_NAME,
    COMMAND_LINE="python /worker.py",
)

# ------------------------------
# build the global parameters
# ------------------------------

# <<< YOUR CODE GOES BELOW >>>
global_parameters = {"power": 3, "size": (10,)}
# <<< YOUR CODE GOES ABOVE >>>

# write the global parameters resource to disk
joblib.dump(global_parameters, join(BATCH_DIRECTORY, GLOBAL_RESOURCE_FILE))

# upload the task resource
global_parameters_resource = batch_client.build_resource_file(
    GLOBAL_RESOURCE_FILE, GLOBAL_RESOURCE_FILE
)


# ------------------------------
# build the batch tasks
# ------------------------------

# <<< YOUR CODE GOES BELOW >>>
SEEDS = (1, 12, 123, 1234)
for i, seed in enumerate(SEEDS):
    task_parameters = {"seed": seed}
    # <<< YOUR CODE GOES ABOVE >>>

    # write the resource to disk
    local_resource_file = LOCAL_RESOURCE_PATTERN.format(i)
    joblib.dump(task_parameters, join(BATCH_DIRECTORY, local_resource_file))

    # upload the task resource
    input_resource = batch_client.build_resource_file(
        local_resource_file, TASK_RESOURCE_FILE
    )

    # create an output resource
    output_resource = batch_client.build_output_file(
        TASK_OUTPUT_FILE, LOCAL_OUTPUT_PATTERN.format(i)
    )

    # create a task
    batch_client.add_task(
        [input_resource, global_parameters_resource], [output_resource]
    )

# ------------------------------
# run the batch job
# ------------------------------

batch_client.run()

# ------------------------------
# aggregate the results
# ------------------------------

task_results = []
for out_file in batch_client.output_files:
    task_result = joblib.load(join(BATCH_DIRECTORY, out_file))
    task_results.append(task_result)

# <<< YOUR CODE GOES BELOW >>>
print(sum(task_results))
# <<< YOUR CODE GOES ABOVE >>>
