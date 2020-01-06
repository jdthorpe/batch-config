# SuperBatch

#### Slightly opinionated convenience wrappers and best practices for Azure
Batch

### TL;DR:

In principal Azure Batch can often speed up your long running for loops by
several orders of magnitude, but rolling your code over requires a good bit
of configuration. This package aims to simplify that process dramatically,
and insitutes some best practices too.

For example, the following code contains a nested for loop with work which
can be spread across multiple workers and orchestrated by Azure Batch:
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
However, to leverage azure batch, we'll need to:
* Set up an Azure Batch instance.
* Bundle the code which does the actual work into it's own component.
* Tell Azure Batch about each of the individual bits of work that need to
	be done (i.e. the `for i, seed in enumerate(SEEDS)` part)
* Collect the results of each task
* Aggregate the intermediate results to produce our final result (i.e the
	`sum(out)` part)

This module aims to make this process as smooth as possible, and will take
some opinions on how to do so in order to reduce the amount or research and
code you need to write to get your job up and running with Azure Batch.  Specifically:
* **The Azure Batch instance will be set up using the 
	[Azure command line tool `az`](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest).**
	This makes setting up the Azure Batch Instance fast and repeatable, and
	allows us to authenticate without having to store credentials anywhere,
	which is a security best practice.
* **The code to be executed by azure batch will be bundled into a docker
	image.**  Using docker ensures that our code can be tested locally and
	then run in Azure Batch in the exact same computing environment without
	having to write custom scripts to configure the VMs which will run our
	code.


## Overview of the solution:

Azure batch is responsible for (1) loading our code into a computing
environment, (2) loading the data that our code requires into the file
system, (3) executing our code, (4) collection the data produced by our
file. 

Therefor, we will need to
1. Bundle our code 
1. Specify where our code will read in required data and write the results
   or it's work
1. Run our code in Azure Batch
1. Collect the results
1. Shut down our Azure Batch Instance

## Step 0: specify the input and output file names

This module contains constants that for the contract between the controller
which tells Azure Batch about the individual tasks that need to be
completed, and the worker which executes an individual task.
```python
# constants.py
GLOBAL_CONFIG_FILE = "config.pickle"
WORKER_INPUTS_FILE = "inputs.pickle"
WORKER_OUTPUTS_FILE = "outputs.pickle"
LOCAL_INPUTS_PATTERN = "iter_{}_inputs.pickle"
LOCAL_OUTPUTS_PATTERN = "iter_{}_outputs.pickle"
```

## Step 1: Write the worker code

First, we'll bundle our worker into a python script which is responsible
for running a single task.  Specifically, it reads in the global and
iteration specific configuration, does the work, and writes the results to
file in the local computing environment.
```python
# worker.py
import numpy as np
import joblib
from constants import GLOBAL_CONFIG_FILE, WORKER_INPUTS_FILE, WORKER_OUTPUTS_FILE

# read the designated global config and iteration parameter files
global_config = joblib.load(GLOBAL_CONFIG_FILE)
parameters = joblib.load(WORKER_INPUTS_FILE)

# DO WORK
np.random.seed(parameters["seed"])
out = sum( np.power(np.random.uniform(size=global_config["size"]), global_config["power"]))

# write the results to the designated output file
joblib.dump(out, WORKER_OUTPUTS_FILE)
```
##### Step 2: Build a docker image with your worker code
Next, we need to bundle this code so that it can be executed by Azure
Batch.  We'll use docker to bundle the code and it's dependencies, which
requires writing a docker file like the following:
```dockerfile
FROM python:3.7
RUN pip install --upgrade pip \
	&& pip install numpy joblib
COPY worker.py .
COPY constants.py .
```
##### Best practice tip:

In the above docker file, we explicitly installed two packages (numpy and
joblib), but if your code requires more packages and you know your code
runs locally, you can call `pip freeze` from the command line and copy the
results of that call to a file called `requirements.txt`.  Then simply copy
the requirements file into the docker image and install the exact versions
of your requirements into the docker image like so:
```dockerfile
FROM python:3.7
COPY requirements.txt .
RUN pip install --upgrade pip \
	&& pip install -r requirements.txt
COPY worker.py .
COPY constants.py .
```
##### Build and publish the docker image

Then to create a docker image in locally, navigate to the project directory and
call: 
```bash
docker build -t myusername/sum-of-powers:v1 .
```
The tag name includes (`myusername/sum-of-powers:v1`) the
username and image name as well as a version.

At this point, the docker image needs to be uploaded to someplace where
accessible to Azure Batch.  If you own that user name at hub.docker.com
(`myusername` in this case) and are logged in, you can push your code to a
**publicly available** image like so:
```bash
docker push myusername/sum-of-powers:v1
```
However, if you wish to keep your code private, you'll need a private
registry such as Azure Container Registry which can be created at the
command line via [`az acr create`](https://docs.microsoft.com/en-us/cli/azure/acr?view=azure-cli-latest#az-acr-create) 
or via the [web portal](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-get-started-portal).

Once your private Azure Container Registry has been created, you can build,
tag, and upload your image like so: 

```bash
# build the image locally
docker build -t sum-of-powers:v1 .
# login to Azure and the container registry
az login
az acr login --name sparsescinternal
# tag the local image
docker tag sum-of-powers:v4 sparsescinternal.azurecr.io/sum-of-powers:v4
# push the image to the private registry
docker push sparsescinternal.azurecr.io/sum-of-powers:v4
```

## Step 3: Write the controller

We need to tell azure batch about our tasks, run the tasks, wait for their
completion, download the results.  The following script leverages a helper
provided by `super_batch` to do this.  While this is one of the longer
scripts, it's is mostly boiler plate, and you'll most likely just need to
update it with your preferences (e.g. vm size, node counts, etc) as well as
you docker image name and version. 
```python
# controller.py
import os
import datetime
import pathlib
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
    DOCKER_IMAGE="myusername/sum-of-powers:v1",
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
## Step 4: Create the Required Azure resources

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

**Best Practice Tip**: Use a dedicated resource group for your Azure Batch
resources.  This ensures that you can delete all the azure resources when
you are done with a single command ([az rg delete](https://docs.microsoft.com/en-us/cli/azure/group?view=azure-cli-latest#az-group-delete) or via the [portal](https://docs.microsoft.com/en-us/azure/azure-resource-manager/management/manage-resources-portal#delete-resources)) in order to avoid
unnecessary charges to your Azure subscription when you have finished with your
batch jobs.

###### Powershell
```ps1
# parameters
$name = "azurebatchtest"
$location = "westus2"
# create the resources
az group create -l $location -n $name
az storage account create -n $name -g $name
az batch account create -l $location -n $name -g $name --storage-account $name
```

###### Bash
```bash
# parameters
name="azurebatchtest"
location="westus2"
# create the resources
az group create -l $location -n $name
az storage account create -n $name -g $name
az batch account create -l $location -n $name -g $name --storage-account $name
```

###### CMD
```bash
REM parameters
set name=azurebatchtest
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

# Step 5:  Executing the Batch Job

In the following Python script, a Batch configuration is created and the batch
job is executed with Azure Batch. Note that the Batch Account and Storage
Account details can be provided directly to the BatchConfig, with default
values taken from the system environment.
```sh
python controller.py
```
**Note that** the pool configuration will only be used to create a new pool if
no pool with the id specified by the `POOL_ID` exists. If a pool with that id already
exists, these parameters are ignored and will **not** update the pool
configuration.  Changing pool attrributes such as type or quantity of nodes
can be done through the [Azure Portal](https://portal.azure.com/), [Azure
Batch Explorer](https://azure.github.io/BatchExplorer/) or the [Azure
CLI](https://docs.microsoft.com/en-us/cli/azure/batch/pool?view=azure-cli-latest).

**Note that** if there is an error in your worker code, you can update your
worker by incrementing the version portion of the tag (e.g `v1` to `v2`),
and then rebuild, publish your docker image (Step x), and updating the
`DOCKER_IMAGE` name in  your controller.py script.

## Cleaning Up

In order to prevent unexpected charges, the resource group, including all the
resources it contains, such as the storge account and batch pools, can be
removed with the following command:

###### Powershell and Bash

```ps1
az group delete -n $name
```

###### CMD

```bat
az group delete -n %name%
```
