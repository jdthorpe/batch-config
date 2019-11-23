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
        "STORAGE_ACCESS_DURATION_HRS": {"type": "number", "minimum": 0, "default": 24},
        "REGISTRY_SERVER": {"type": "string"},
        "REGISTRY_USERNAME": {"type": "string"},
        "REGISTRY_PASSWORD": {"type": "string"},
        "POOL_ID": {"type": "string"},
        "POOL_NODE_COUNT": {"type": "number", "minimum": 0},
        "POOL_LOW_PRIORITY_NODE_COUNT": {"type": "number", "minimum": 0},
        "POOL_VM_SIZE": {"type": "string"},
        "DELETE_POOL_WHEN_DONE": {"type": "boolean"},
        "JOB_ID": {"type": "string"},
        "DELETE_JOB_WHEN_DONE": {"type": "boolean"},
        "CONTAINER_NAME": {
            "type": "string",
            "pattern": "^[a-z0-9](-?[a-z0-9]+)$",
            "maxLength": 63,
            "minLength": 3,
        },
        "BATCH_DIRECTORY": {"type": "string"},
        "DOCKER_CONTAINER": {"type": "string"},
    },
    # TODO: missing required properties
}


class _BatchConfig(NamedTuple):
    """
    A convenience class for typing the config object
    """

    # pylint: disable=too-few-public-methods
    POOL_ID: str
    JOB_ID: str
    POOL_VM_SIZE: str
    CONTAINER_NAME: str
    BATCH_DIRECTORY: str
    DOCKER_CONTAINER: str
    POOL_NODE_COUNT: int = 0
    POOL_LOW_PRIORITY_NODE_COUNT: int = 0
    DELETE_POOL_WHEN_DONE: bool = False
    DELETE_JOB_WHEN_DONE: bool = False
    BATCH_ACCOUNT_NAME: Optional[str] = None
    BATCH_ACCOUNT_KEY: Optional[str] = None
    BATCH_ACCOUNT_URL: Optional[str] = None
    STORAGE_ACCOUNT_NAME: Optional[str] = None
    STORAGE_ACCOUNT_KEY: Optional[str] = None
    STORAGE_ACCESS_DURATION_HRS: int = 24
    REGISTRY_SERVER: Optional[str] = None
    REGISTRY_USERNAME: Optional[str] = None
    REGISTRY_PASSWORD: Optional[str] = None


class BatchConfig:
    """ Azure Batch Configuration
    """

    def __init__(self, **kwargs):
        self.data = _BatchConfig(**kwargs)
        self.validate()

    def validate(self):
        """
        validate the batch configuration object
        """
        _config = self.data._asdict()
        for _key in SERVICE_KEYS:
            if not _config[_key]:
                del _config[_key]

        __env_config = _ENV_CONFIG.copy()
        __env_config.update(_config)
        validate(__env_config, CONFIG_SCHEMA)
        self.data = _BatchConfig(**__env_config)

    def __repr__(self):
        return self.data.__repr__()

    def __str__(self):
        return self.data.__str__()

    def __getattribute__(self, name):
        return self.data.__getattribute__(name)


SERVICE_KEYS = (
    "BATCH_ACCOUNT_NAME",
    "BATCH_ACCOUNT_KEY",
    "BATCH_ACCOUNT_URL",
    "STORAGE_ACCOUNT_NAME",
    "STORAGE_ACCOUNT_KEY",
    "REGISTRY_SERVER",
    "REGISTRY_USERNAME",
    "REGISTRY_PASSWORD",
)

_ENV_CONFIG = {}
for key in SERVICE_KEYS:
    val = os.getenv(key, None)
    if val:
        _ENV_CONFIG[key] = val.strip('"')
