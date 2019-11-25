"""
"""
import numpy as np

# SET GLOBAL PARAMETERS
POWER = 3
SIZE = (10,)
SEEDS = (1, 12, 123, 1234)

out = np.zeros((len(SEEDS),))
for i, seed in enumerate(SEEDS): # DEFINE LOOPING PARAMETERS
    # DO WORK
    np.random.seed(seed)
    tmp = np.random.uniform(size=SIZE)
    out[i] = sum(np.power(tmp, POWER))

# AGGREGATE INTERMEDIATE STATISTICS
print(sum(out))
