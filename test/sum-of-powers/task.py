import numpy as np


def task(global_parameters, task_parameters):
    # extract parameters
    size = global_parameters["size"]
    power = global_parameters["power"]
    seed = task_parameters["seed"]

    # do work
    np.random.seed(seed)
    return sum(np.power(np.random.uniform(size=size), power))
