"""
"""
import numpy as np
from task import task

# SET GLOBAL PARAMETERS
global_parameters = {"power": 3, "size": (10,)}

results = []
SEEDS = (1, 12, 123, 1234)
for seed in SEEDS:
    task_parameters = {"seed": seed}

    # DO WORK
    results.append(task(global_parameters, task_parameters))

# AGGREGATE INTERMEDIATE STATISTICS
print(sum(results))
