from os.path import join, expanduser
import datetime
import pathlib
import joblib
import super_batch

from constants import (
    GLOBAL_CONFIG_FILE,
    TASK_RESOURCE_FILE,
    TASK_OUTPUT_FILE,
    LOCAL_RESOURCE_PATTERN,
    LOCAL_OUTPUT_PATTERN,
)

# ------------------------------
# DEFINE CONSTANTS
# ------------------------------

# The `$name` of our created resources:
NAME = "superbatchtest"

# a local directory where temporary files will be stored:
BATCH_DIRECTORY = expanduser("~/temp/super-batch-test")
pathlib.Path(BATCH_DIRECTORY).mkdir(parents=True, exist_ok=True)

# CONSTANTS:
# used to generate unique task names:
_TIMESTAMP = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")

# INSTANTIATE THE BATCH HELPER CLIENT:
batch_client = super_batch.client(
    POOL_ID=NAME,
    JOB_ID=NAME + _TIMESTAMP,
    POOL_VM_SIZE="STANDARD_A1_v2",
    POOL_NODE_COUNT=0,
    POOL_LOW_PRIORITY_NODE_COUNT=2,
    DELETE_POOL_WHEN_DONE=False,
    BLOB_CONTAINER_NAME=NAME,
    BATCH_DIRECTORY=BATCH_DIRECTORY,
    DOCKER_IMAGE="myusername/sum-of-powers:v1",
    COMMAND_LINE="python /worker.py",
)

# ------------------------------
# BUILD THE GLOBAL PARAMETERS
# ------------------------------

# <<< Your code goes below >>>
global_parameters = {"power": 3, "size": (10,)}
# <<< Your code goes above >>>

# WRITE THE GLOBAL PARAMETERS RESOURCE TO DISK
joblib.dump(global_parameters, join(BATCH_DIRECTORY, GLOBAL_CONFIG_FILE))

# UPLOAD THE TASK RESOURCE
global_parameters_resource = batch_client.build_resource_file(
    GLOBAL_CONFIG_FILE, GLOBAL_CONFIG_FILE
)

# ------------------------------
# BUILD THE BATCH TASKS
# ------------------------------

# <<< Your code goes below >>>
SEEDS = (1, 12, 123, 1234)
for i, seed in enumerate(SEEDS):
    parameters = {"seed": seed}
    # <<< Your code goes above >>>

    # WRITE THE RESOURCE TO DISK
    local_resource_file = LOCAL_RESOURCE_PATTERN.format(i)
    joblib.dump(parameters, join(BATCH_DIRECTORY, local_resource_file))

    # UPLOAD THE TASK RESOURCE
    input_resource = batch_client.build_resource_file(
        local_resource_file, TASK_RESOURCE_FILE
    )

    # CREATE AN OUTPUT RESOURCE
    output_resource = batch_client.build_output_file(
        LOCAL_OUTPUT_FILE, LOCAL_OUTPUT_PATTERN.format(i)
    )

    # CREATE A TASK
    batch_client.add_task(
        [input_resource, global_parameters_resource], [output_resource]
    )

# ------------------------------
# RUN THE BATCH JOB
# ------------------------------

batch_client.run()

# ------------------------------
# AGGREGATE THE RESULTS
# ------------------------------

task_results = []
for task in batch_client.tasks:
    task_results.append(joblib.load(task.something))

# <<< Your code goes below >>>
print(sum(task_results))
# <<< Your code goes above >>>
