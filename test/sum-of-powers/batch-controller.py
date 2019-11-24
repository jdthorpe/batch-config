"""
"""
from os.path import realpath, join
import batchconfig
import numpy as np
import joblib
from .constnats import (
    WORKER_CONFIG_FILE,
    WORKER_INPUTS_FILE,
    WORKER_OUTPUTS_FILE,
    LOCAL_INPUTS_PATTERN,
    LOCAL_OUTPUTS_PATTERN,
)

BATCH_DIR = "./batch"

# GLOBAL PARAMETERS
POWER = 3
SIZE = (10,)

# DUMP THE GLOBAL CONFIGURATION
joblib.dump({"power": POWER, "size": SIZE}, "global_config.pickle")


# DUMP THE ITERATION OBJECTS
SEEDS = (1, 12, 123, 1234)

for i, seed in enumerate(SEEDS):
    # dump the inputs to file
    inputs = {"seed": seed}
    input_file = LOCAL_INPUTS_PATTERN.format(i)
    joblib.dump(inputs, input_file)
    out[i] = sum(np.power(np.random.uniform(size=SIZE), POWER))


# LOCAL AGGREGATION OF INTERMEDIATE STATISTICS
out = np.zeros((len(SEEDS),))


parameters = joblib.load("inputs.pickle")
parameters["seed"]
{"seed": 123}
joblib.load("inputs.pickle")
