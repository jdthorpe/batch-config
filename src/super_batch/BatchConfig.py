import os
from typing import NamedTuple, Optional
from jsonschema import validate

# ------------------------------
# Fail Faster
# ------------------------------
_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "BATCH_ACCOUNT_NAME": {"type": "string"},
        "BATCH_ACCOUNT_KEY": {"type": "string"},
        "BATCH_ACCOUNT_ENDPOINT": {"type": "string"},
        "STORAGE_ACCOUNT_NAME": {"type": "string"},
        "STORAGE_ACCOUNT_KEY": {"type": "string"},
        "STORAGE_ACCOUNT_CONNECTION_STRING": {"type": "string"},
        "STORAGE_ACCESS_DURATION_HRS": {"type": "number", "minimum": 0, "default": 24,},
        "REGISTRY_SERVER": {"type": "string"},
        "REGISTRY_USERNAME": {"type": "string"},
        "REGISTRY_PASSWORD": {"type": "string"},
        "POOL_ID": {"type": "string"},
        "POOL_NODE_COUNT": {"type": "number", "minimum": 0},
        "POOL_LOW_PRIORITY_NODE_COUNT": {"type": "number", "minimum": 0},
        "POOL_VM_SIZE": {"type": "string"},
        "JOB_ID": {"type": "string"},
        "DELETE_POOL_WHEN_DONE": {"type": "boolean"},
        "DELETE_JOB_WHEN_DONE": {"type": "boolean"},
        "DELETE_CONTAINER_WHEN_DONE": {"type": "boolean"},
        "BLOB_CONTAINER_NAME": {
            "type": "string",
            "pattern": "^[a-z0-9](-?[a-z0-9]+)$",
            "maxLength": 63,
            "minLength": 3,
        },
        "BATCH_DIRECTORY": {"type": "string"},
        "DOCKER_IMAGE": {"type": "string"},
    },
    "required": [
        "POOL_ID",
        "JOB_ID",
        "BLOB_CONTAINER_NAME",
        "BATCH_DIRECTORY",
        "DOCKER_IMAGE",
        "BATCH_ACCOUNT_NAME",
        "BATCH_ACCOUNT_KEY",
        "BATCH_ACCOUNT_ENDPOINT",
        "STORAGE_ACCOUNT_KEY",
        "STORAGE_ACCOUNT_CONNECTION_STRING",
        "STORAGE_ACCESS_DURATION_HRS",
    ],
    "dependencies": {
        "REGISTRY_USERNAME": ["REGISTRY_SERVER", "REGISTRY_PASSWORD"],
        "REGISTRY_PASSWORD": ["REGISTRY_SERVER", "REGISTRY_USERNAME"],
        "REGISTRY_SERVER": ["REGISTRY_USERNAME", "REGISTRY_PASSWORD"],
    }
    # to do: missing required properties
}


class _BatchConfig(NamedTuple):
    """
    A convenience class for typing the config object
    """

    # pylint: disable=too-few-public-methods
    POOL_ID: str
    JOB_ID: str
    BLOB_CONTAINER_NAME: str
    BATCH_DIRECTORY: str
    DOCKER_IMAGE: str
    POOL_VM_SIZE: Optional[str]
    POOL_NODE_COUNT: Optional[int] = 0
    POOL_LOW_PRIORITY_NODE_COUNT: Optional[int] = 0
    DELETE_POOL_WHEN_DONE: bool = False
    DELETE_JOB_WHEN_DONE: bool = False
    DELETE_CONTAINER_WHEN_DONE: bool = False
    BATCH_ACCOUNT_NAME: Optional[str] = None
    BATCH_ACCOUNT_KEY: Optional[str] = None
    BATCH_ACCOUNT_ENDPOINT: Optional[str] = None
    STORAGE_ACCOUNT_KEY: Optional[str] = None
    STORAGE_ACCOUNT_CONNECTION_STRING: Optional[str] = None
    STORAGE_ACCESS_DURATION_HRS: int = 24
    REGISTRY_SERVER: Optional[str] = None
    REGISTRY_USERNAME: Optional[str] = None
    REGISTRY_PASSWORD: Optional[str] = None
    COMMAND_LINE: Optional[str] = None

    @property
    def clean(self):
        """
        get the attributes from this object which don't contain permissions
        """
        out = {}
        for k in _clean_keys:
            try:
                v = getattr(self, k)
            except AttributeError:
                pass
            else:
                out[k] = v

        return out

    @property
    def BATCH_ACCOUNT_URL(self):
        return "https://{}".format(self.BATCH_ACCOUNT_ENDPOINT)


_clean_keys = (
    "POOL_ID",
    "JOB_ID",
    "POOL_VM_SIZE",
    "BLOB_CONTAINER_NAME",
    "BATCH_DIRECTORY",
    "DOCKER_IMAGE",
    "POOL_NODE_COUNT",
    "POOL_LOW_PRIORITY_NODE_COUNT",
    "DELETE_POOL_WHEN_DONE",
    "DELETE_JOB_WHEN_DONE",
    "DELETE_CONTAINER_WHEN_DONE",
    "BATCH_ACCOUNT_NAME",
    "BATCH_ACCOUNT_ENDPOINT",
    "STORAGE_ACCOUNT_CONNECTION_STRING",
    "STORAGE_ACCESS_DURATION_HRS",
    "REGISTRY_SERVER",
    "COMMAND_LINE",
)


def BatchConfig(**kwargs):
    """
    Provides an interface for preparing, running, and pulling down data from an Azure Batch job

    Args:
        BATCH_DIRECTORY (string): Local directory in which input and output files should be placed
        BATCH_ACCOUNT_NAME (string): Batch account name. Taken from the environment when not provided
        BATCH_ACCOUNT_KEY (string): Batch account key. Taken from the environment when not provided
        BATCH_ACCOUNT_ENDPOINT (string): Batch account endpoint. Taken from the environment when not provided
        JOB_ID (string): Name for the Batch Job
        STORAGE_ACCOUNT_NAME (string): Storage Account name
        STORAGE_ACCOUNT_KEY (string): Stoarge account key. Taken from the environment when not provided
        STORAGE_ACCOUNT_CONNECTION_STRING (string): Storage account access connection string. Taken from the environment when not provided
        STORAGE_ACCESS_DURATION_HRS (int): Time in hours that the generated the storage access token will be valid for
        BLOB_CONTAINER_NAME (string): Name for the blob storage container
        POOL_ID (string): Pool Id
        POOL_NODE_COUNT (int): Count for normal priority nodes in the batch pool. Only used when createing a pool.  **Ignored if the pool already exists**
        POOL_LOW_PRIORITY_NODE_COUNT (int): Count for low priority nodes in the batch pool.    **Ignored if the pool already exists**
        POOL_VM_SIZE (string): VM name (See the FAQ for details)
        DOCKER_IMAGE (string): name of the docker image
        REGISTRY_SERVER (string, optional): Used when the docker image is hosted on a private repository. Taken from the environment when not provided
        REGISTRY_USERNAME (string, optional): Used when the docker image is hosted on a private repository. Taken from the environment when not provided
        REGISTRY_PASSWORD (string, optional): Used when the docker image is hosted on a private repository. Taken from the environment when not provided
        DELETE_POOL_WHEN_DONE (boolean): Should the batch pool be deleted when the job has been completed? Default `False`
        DELETE_JOB_WHEN_DONE (boolean): Should the batch job be deleted when the job has been completed? Default `False`
        DELETE_CONTAINER_WHEN_DONE (boolean): should the blob storage container be deleted when the job has been completed? Default `False`
    """
    return _validate(_BatchConfig(**kwargs))


def _validate(x):
    """
    validate the batch configuration object
    """
    _config = x._asdict()
    for _key in SERVICE_KEYS:
        if not _config[_key]:
            del _config[_key]
    __env_config = _ENV_CONFIG.copy()
    __env_config.update(_config)
    validate(__env_config, _CONFIG_SCHEMA)
    return _BatchConfig(**__env_config)


SERVICE_KEYS = (
    "BATCH_ACCOUNT_NAME",
    "BATCH_ACCOUNT_KEY",
    "BATCH_ACCOUNT_ENDPOINT",
    "STORAGE_ACCOUNT_KEY",
    "STORAGE_ACCOUNT_CONNECTION_STRING",
    "REGISTRY_SERVER",
    "REGISTRY_USERNAME",
    "REGISTRY_PASSWORD",
)

_ENV_CONFIG = {}
for key in SERVICE_KEYS:
    val = os.getenv(key, None)
    if val:
        _ENV_CONFIG[key] = val.strip('"')
