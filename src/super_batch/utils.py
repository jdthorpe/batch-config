"""
general helper utils
"""
import datetime
from azure.storage.blob.models import ContainerPermissions

# Update the Batch and Storage account credential strings in config.py with values
# unique to your accounts. These are used when constructing connection strings
# for the Batch and Storage client objects.
def build_output_sas_url(config, _blob_client):
    """
    build a sas token for the output container
    """

    sas_token = _blob_client.generate_container_shared_access_signature(
        config.CONTAINER_NAME,
        ContainerPermissions.READ
        + ContainerPermissions.WRITE
        + ContainerPermissions.DELETE
        + ContainerPermissions.LIST,
        datetime.datetime.utcnow()
        + datetime.timedelta(hours=config.STORAGE_ACCESS_DURATION_HRS),
        start=datetime.datetime.utcnow(),
    )

    _sas_url = "https://{}.blob.core.windows.net/{}?{}".format(
        config.STORAGE_ACCOUNT_NAME, config.CONTAINER_NAME, sas_token
    )
    return _sas_url
