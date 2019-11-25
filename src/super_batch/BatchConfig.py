# pylint: disable=invalid-name
"""
configuration for azure batch
"""

import os
from typing import NamedTuple, Optional
from jsonschema import validate

# ------------------------------
# Fail Faster
# ------------------------------
CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "BATCH_ACCOUNT_NAME": {"type": "string"},
        "BATCH_ACCOUNT_KEY": {"type": "string"},
        "BATCH_ACCOUNT_URL": {"type": "string"},
        "STORAGE_ACCOUNT_NAME": {"type": "string"},
        "STORAGE_ACCOUNT_KEY": {"type": "string"},
        "STORAGE_ACCOUNT_CONNECTION_STRING": {"type": "string"},
        "STORAGE_ACCESS_DURATION_HRS": {"type": "number", "minimum": 0, "default": 24},
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
    # to do: missing required properties
}


class _BatchConfig(NamedTuple):
    """
    A convenience class for typing the config object
    """

    # pylint: disable=too-few-public-methods
    POOL_ID: str
    JOB_ID: str
    POOL_VM_SIZE: str
    BLOB_CONTAINER_NAME: str
    BATCH_DIRECTORY: str
    DOCKER_IMAGE: str
    POOL_NODE_COUNT: int = 0
    POOL_LOW_PRIORITY_NODE_COUNT: int = 0
    DELETE_POOL_WHEN_DONE: bool = False
    DELETE_JOB_WHEN_DONE: bool = False
    DELETE_CONTAINER_WHEN_DONE: bool = False
    BATCH_ACCOUNT_NAME: Optional[str] = None
    BATCH_ACCOUNT_KEY: Optional[str] = None
    BATCH_ACCOUNT_URL: Optional[str] = None
    STORAGE_ACCOUNT_KEY: Optional[str] = None
    STORAGE_ACCOUNT_CONNECTION_STRING: Optional[str] = None
    STORAGE_ACCESS_DURATION_HRS: int = 24
    REGISTRY_SERVER: Optional[str] = None
    REGISTRY_USERNAME: Optional[str] = None
    REGISTRY_PASSWORD: Optional[str] = None
    COMMAND_LINE: Optional[str] = None


def BatchConfig(**kwargs):
    """ Azure Batch Configuration
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
    validate(__env_config, CONFIG_SCHEMA)
    return _BatchConfig(**__env_config)


SERVICE_KEYS = (
    "BATCH_ACCOUNT_NAME",
    "BATCH_ACCOUNT_KEY",
    "BATCH_ACCOUNT_URL",
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
