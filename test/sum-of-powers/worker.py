""" the worker
"""
# pylint: disable=invalid-name

import numpy as np
import joblib
from constants import GLOBAL_CONFIG_FILE, WORKER_INPUTS_FILE, WORKER_OUTPUTS_FILE


# read the designated global config and iteration parameter files
print("reading in config files...",end="")
global_config = joblib.load(GLOBAL_CONFIG_FILE)
parameters = joblib.load(WORKER_INPUTS_FILE)
print("DONE")

# do the work
print("Doing work...",end="")
np.random.seed(parameters["seed"])
out = sum(
    np.power(np.random.uniform(size=global_config["size"]), global_config["power"])
)
print("DONE")

# write the results to the designated output file
print("Writing outputs...",end="")
joblib.dump(out, WORKER_OUTPUTS_FILE)
print("DONE")
