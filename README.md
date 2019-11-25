# SuperBatch

#### Convenience wrappers and best practices

### TL;DR:

In principal Azure Batch can often speed up your long running for loops by
orders of magnitude, but rolling your code over requires a good bit of
configuration. This package aims to simplify that process dramatically, and
insitutes some best practices too.

For example, this:

```python
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
```

Is split into a worker which is responsible for a single task:

```python
# worker.py
import numpy as np
import joblib
from constants import GLOBAL_CONFIG_FILE, WORKER_INPUTS_FILE, WORKER_OUTPUTS_FILE

# read the designated global config and iteration parameter files
global_config = joblib.load(GLOBAL_CONFIG_FILE)
parameters = joblib.load(WORKER_INPUTS_FILE)

# do work
np.random.seed(parameters["seed"])
out = sum( np.power(np.random.uniform(size=global_config["size"]), global_config["power"]))

# write the results to the designated output file
joblib.dump(out, WORKER_OUTPUTS_FILE)
```

A controller to send tasks to azure batch:

```python
# controller.py
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

# CONSTANTS
_TIMESTAMP: str = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
BATCH_DIRECTORY: str = os.path.expanduser("~/temp/super-batch-test")
NAME: str = "superbatchtest"
pathlib.Path(BATCH_DIRECTORY).mkdir(parents=True, exist_ok=True)

batch_client = super_batch.client(
    POOL_ID=NAME,
    JOB_ID=NAME + _TIMESTAMP,
    POOL_VM_SIZE="STANDARD_A1_v2",
    POOL_NODE_COUNT=0,
    POOL_LOW_PRIORITY_NODE_COUNT=2,
    DELETE_POOL_WHEN_DONE=False,
    BLOB_CONTAINER_NAME=NAME,
    BATCH_DIRECTORY=BATCH_DIRECTORY,
    DOCKER_IMAGE="jdthorpe/super-batch-test-sum-of-powers:v1",
    COMMAND_LINE="python /worker.py",
)


# BUILD THE GLOBAL PARAMETER RESOURCE
global_parameters = {"power": 3, "size": (10,)}
joblib.dump( global_parameters, os.path.join(BATCH_DIRECTORY, GLOBAL_CONFIG_FILE))
global_parameters_resource = batch_client.build_resource_file(
    GLOBAL_CONFIG_FILE, GLOBAL_CONFIG_FILE
)

# BUILD THE BATCH TASKS
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

# RUN THE BATCH JOB
batch_client.run()

# AGGREGATE INTERMEDIATE STATISTICS
out = [None] * len(SEEDS)
for i in range(len(SEEDS)):
    fpath = os.path.join(BATCH_DIRECTORY, LOCAL_OUTPUTS_PATTERN.format(i))
    out[i] = joblib.load(fpath)
print(sum(out))
```

Some constants shared between the worker and the controller:

```python
# constants.py
GLOBAL_CONFIG_FILE = "config.pickle"
WORKER_INPUTS_FILE = "inputs.pickle"
WORKER_OUTPUTS_FILE = "outputs.pickle"
LOCAL_INPUTS_PATTERN = "iter_{}_inputs.pickle"
LOCAL_OUTPUTS_PATTERN = "iter_{}_outputs.pickle"
```

with the following `Dockerfile`:

```dockerfile
# docker build -t jdthorpe/super-batch-test-sum-of-powers:v1 .
# docker push jdthorpe/super-batch-test-sum-of-powers:v1
FROM python:3.7
RUN pip install --upgrade pip \
	&& pip install numpy joblib
COPY worker.py .
COPY constants.py .
```

# Setup

### Create the Required Azure resources

Using Azure batch requires an azure account, and we'll demonstrate how to run
this module using the [azure command line tool](https://docs.microsoft.com/en-us/cli/azure/).

After logging into the console with `az login` (and potentially setting the default
subscription with `az account set -s <subscription>`), you'll need to create an azure
resource group into which the batch account is created. In addition, the
azure batch service requires a storage account which is used to keep track of
details of the jobs and tasks.

Although the resource group, storage account and batch account could have
different names, for sake of exposition, we'll give them all the same name and
locate them in the US West 2 region, like so:

###### Powershell

```ps1
# parameters
$name = "sparsesctest"
$location = "westus2"
# create the resources
az group create -l $location -n $name
az storage account create -n $name -g $name
az batch account create -l $location -n $name -g $name --storage-account $name
```

###### Bash

```bash
# parameters
name="sparsesctest"
location="westus2"
# create the resources
az group create -l $location -n $name
az storage account create -n $name -g $name
az batch account create -l $location -n $name -g $name --storage-account $name
```

###### CMD

```bash
REM parameters
set name=sparsesctest
set location=westus2
REM create the resources
az group create -l %location% -n %name%
az storage account create -n %name% -g %name%
az batch account create -l %location% -n %name% -g %name% --storage-account %name%
```

_(Aside: since we're using the `name` for parameter for the resource group
storage account and batch account, it must consist of 3-24 lower case
letters and be unique across all of azure)_

### Gather Resource Credentials

We'll need some information about the batch and storage accounts in order
to create and run batch jobs. We can create bash variables that contain the
information that the SparseSC azure batch client will require, with the
following:

###### Powershell

```ps1
$BATCH_ACCOUNT_NAME = $name
$BATCH_ACCOUNT_KEY =  az batch account keys list -n $name -g $name --query primary
$BATCH_ACCOUNT_URL = "https://$name.$location.batch.azure.com"
$STORAGE_ACCOUNT_KEY = az storage account keys list -n $name --query [0].value
$STORAGE_ACCOUNT_CONNECTION_STRING= az storage account show-connection-string --name $name --query connectionString
```

###### Bash

```bash
export BATCH_ACCOUNT_NAME=$name
export BATCH_ACCOUNT_KEY=$(az batch account keys list -n $name -g $name --query primary)
export BATCH_ACCOUNT_URL="https://$name.$location.batch.azure.com"
export STORAGE_ACCOUNT_KEY=$(az storage account keys list -n $name --query [0].value)
export STORAGE_ACCOUNT_CONNECTION_STRING=$(az storage account show-connection-string --name $name --query connectionString)
```

###### CMD

Replace `%i` with `%%i` below if used from a bat file.

```bash
set BATCH_ACCOUNT_NAME=%name%
set BATCH_ACCOUNT_URL=https://%name%.%location%.batch.azure.com
for /f %i in ('az batch account keys list -n %name% -g %name% --query primary') do @set BATCH_ACCOUNT_KEY=%i
for /f %i in ('az storage account keys list -n %name% --query [0].value') do @set STORAGE_ACCOUNT_KEY=%i
for /f %i in ('az storage account show-connection-string --name $name --query connectionString') do @set STORAGE_ACCOUNT_CONNECTION_STRING=%i
```

We could of course echo these to the console and copy/paste the values into the
BatchConfig object below. However we don't need to do that if we run python
from within the same environment (terminal session), as these environment
variables will be used by the `azure_batch_client` if they are not provided
explicitly.

## Executing the Batch Job

In the following Python script, a Batch configuration is created and the batch
job is executed with Azure Batch. Note that the Batch Account and Storage
Account details can be provided directly to the BatchConfig, with default
values taken from the system environment.

```sh
python controller.py
```

Note that the pool configuration will only be used to create a new pool if no pool
by the id `POOL_ID` exists. If the pool already exists, these parameters are
ignored and will _not_ update the pool configuration. Changing pool attrributes
such as type or quantity of nodes can be done through the [Azure Portal](https://portal.azure.com/), [Azure Batch Explorer](https://azure.github.io/BatchExplorer/) or any of the APIs.

## Cleaning Up

In order to prevent unexpected charges, the resource group, including all the
resources it contains, such as the storge account and batch pools, can be
removed with the following command.

###### Powershell and Bash

```ps1
az group delete -n $name
```

###### CMD

```bat
az group delete -n %name%
```
