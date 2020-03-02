""" The main entry point for the worker task
"""
# pylint: disable=invalid-name

import joblib
from constants import GLOBAL_RESOURCE_FILE, TASK_RESOURCE_FILE, TASK_OUTPUT_FILE
from task import task

# read the designated global config and iteration parameter files
print("reading in config files...", end="")
global_parameters = joblib.load(GLOBAL_RESOURCE_FILE)
task_parameters = joblib.load(TASK_RESOURCE_FILE)
print("DONE")

# do the work
print("Doing work...", end="")
output = task(global_parameters, task_parameters)
print("DONE")

# write the results to the designated output file
print("Writing outputs ({})...".format(output), end="")
joblib.dump(output, TASK_OUTPUT_FILE)
print("DONE")
