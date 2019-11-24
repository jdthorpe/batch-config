"""
"""
import numpy as np


# global parameters
POWER = 3
SIZE = (10,)
SEEDS = (1, 12, 123, 1234)

# LOCAL AGGREGATION OF INTERMEDIATE STATISTICS
out = np.zeros((len(SEEDS),))

for i, seed in enumerate(SEEDS):
    np.random.seed(seed)
    out[i] = sum(np.power(np.random.uniform(size=SIZE), POWER))

parameters = joblib.load("inputs.pickle")
parameters["seed"]
{"seed": 123}
joblib.load("inputs.pickle")
