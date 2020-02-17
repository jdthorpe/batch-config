"""
usage requires these additional modules
"""
# pylint: disable=bad-continuation, invalid-name, protected-access, line-too-long, fixme

from __future__ import print_function
from typing import Tuple, List
import datetime
import os
import pathlib

from azure.storage.blob import (
    BlobServiceClient,
    ContainerClient,
    ContainerSasPermissions,
    BlobSasPermissions,
    generate_container_sas,
    generate_blob_sas,
)
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.batch import BatchServiceClient
from azure.batch.batch_auth import SharedKeyCredentials
import azure.batch.models as models

from .BatchConfig import _BatchConfig, BatchConfig
from .utils import (
    print_batch_exception,
    wait_for_tasks_to_complete,
    read_stream_as_string,
)


# Create a new pool of Linux compute nodes using an Azure Virtual Machines
# Marketplace image. For more information about creating pools of Linux
# nodes, see:
# https://azure.microsoft.com/documentation/articles/batch-linux-nodes/
IMAGE_REF = models.ImageReference(
    publisher="microsoft-azure-batch",
    offer="ubuntu-server-container",
    sku="16-04-lts",
    version="latest",
)


class Client:
    """ convenience class
    """

    config: _BatchConfig
    blob_client: BlobServiceClient
    batch_client: BatchServiceClient
    container_client: ContainerClient
    output_files: List[Tuple[str]]
    tasks: List[models.TaskAddParameter]
    image: models.ImageReference

    @property
    def data(self):
        """ return data for persisting the object
        """
        return {"config": self.config.clean, "output_files": self.output_files}

    @staticmethod
    def from_data(data):
        """ restore the object from the stored data
        """
        out = Client(**data["config"])
        out.output_files = data["output_files"]
        del out.image
        del out.tasks
        return out

    def __init__(self, image=IMAGE_REF, **kwargs):

        self.image = image
        self.config = BatchConfig(**kwargs)
        self.output_files = []
        self.tasks = []

        # --------------------------------------------------
        # BLOB STORAGE CONFIGURATION:
        # --------------------------------------------------

        # Create the blob client, for use in obtaining references to
        # blob storage containers and uploading files to containers.
        self.blob_client = BlobServiceClient.from_connection_string(
            self.config.STORAGE_ACCOUNT_CONNECTION_STRING
        )

        # Use the blob client to create the containers in Azure Storage if they
        # don't yet exist.
        self.container_client = self.blob_client.get_container_client(
            self.config.BLOB_CONTAINER_NAME
        )

        try:
            self.container_client.create_container()
        except ResourceExistsError:
            pass

        # --------------------------------------------------
        # AZURE BATCH CONFIGURATION
        # --------------------------------------------------

        # Create a Batch service client. We'll now be interacting with the Batch
        # service in addition to Storage
        self.batch_client = BatchServiceClient(
            SharedKeyCredentials(
                self.config.BATCH_ACCOUNT_NAME, self.config.BATCH_ACCOUNT_KEY
            ),
            batch_url=self.config.BATCH_ACCOUNT_URL,
        )

    def build_resource_file(
        self, file_path, container_path: str, duration_hours=24
    ):
        """
        Uploads a local file to an Azure Blob storage container.

        :param str file_path: The local path to the file.
        :param str container_path: The path where the file should be placed in the container before executing the task
        :rtype: `azure.batch.models.ResourceFile`
        :return: A ResourceFile initialized with a SAS URL appropriate for Batch
        tasks.
        """
        # print( "Uploading file {} to container [{}]...".format( file_path, self.config.BLOB_CONTAINER_NAME)),
        blob_name = os.path.basename(file_path)
        blob_client = self.container_client.get_blob_client(blob_name)

        try:
            blob_client.delete_blob()
        except ResourceNotFoundError:
            pass

        with open(
            os.path.join(self.config.BATCH_DIRECTORY, file_path), "rb"
        ) as data:
            blob_client.upload_blob(data, blob_type="BlockBlob")

        sas_token = generate_blob_sas(
            blob_client.account_name,
            blob_client.container_name,
            blob_client.blob_name,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.datetime.utcnow()
            + datetime.timedelta(hours=duration_hours),
            account_key=self.config.STORAGE_ACCOUNT_KEY,
        )

        return models.ResourceFile(
            http_url=blob_client.url + "?" + sas_token, file_path=container_path
        )

    def build_output_file(self, output_file, container_path):
        """
        Uploads a local file to an Azure Blob storage container.

        :param str output_file: the name of the file produced as the output by the task
        :param str container_path: the name of the file in the container

        :rtype: `azure.batch.models.ResourceFile`
        :return: A ResourceFile initialized with a SAS URL appropriate for Batch
        tasks.
        """

        # where to store the outputs
        container_sas_url = (
            self.container_client.url
            + "?"
            + generate_container_sas(
                self.container_client.account_name,
                self.container_client.container_name,
                permission=ContainerSasPermissions(
                    read=True, write=True, delete=True, list=True
                ),
                expiry=datetime.datetime.utcnow()
                + datetime.timedelta(
                    hours=self.config.STORAGE_ACCESS_DURATION_HRS
                ),
                account_key=self.config.STORAGE_ACCOUNT_KEY,
            )
        )

        destination = models.OutputFileDestination(
            container=models.OutputFileBlobContainerDestination(
                container_url=container_sas_url, path=container_path
            )
        )

        # Under what conditions should Azure Batch attempt to extract the outputs?
        upload_options = models.OutputFileUploadOptions(
            upload_condition=models.OutputFileUploadCondition.task_success
        )

        # https://docs.microsoft.com/en-us/azure/batch/batch-task-output-files#specify-output-files-for-task-output
        out = models.OutputFile(
            file_pattern=output_file,
            destination=destination,
            upload_options=upload_options,
        )
        self.output_files.append(container_path)

        return out

    def _create_pool(self):
        """
        Creates a pool of compute nodes with the specified OS settings.

        :param batch_service_client: A Batch service client.
        :type batch_service_client: `azure.batch.BatchServiceClient`
        :param str pool_id: An ID for the new pool.
        :param str publisher: Marketplace image publisher
        :param str offer: Marketplace image offer
        :param str sku: Marketplace image sku
        """
        if self.config.REGISTRY_SERVER:
            registry = models.ContainerRegistry(
                user_name=self.config.REGISTRY_USERNAME,
                password=self.config.REGISTRY_PASSWORD,
                registry_server=self.config.REGISTRY_SERVER,
            )
            container_conf = models.ContainerConfiguration(
                container_image_names=[self.config.DOCKER_IMAGE],
                container_registries=[registry],
            )
        else:
            container_conf = models.ContainerConfiguration(
                container_image_names=[self.config.DOCKER_IMAGE]
            )

        new_pool = models.PoolAddParameter(
            id=self.config.POOL_ID,
            virtual_machine_configuration=models.VirtualMachineConfiguration(
                image_reference=IMAGE_REF,
                container_configuration=container_conf,
                node_agent_sku_id="batch.node.ubuntu 16.04",
            ),
            vm_size=self.config.POOL_VM_SIZE,
            target_dedicated_nodes=self.config.POOL_NODE_COUNT,
            target_low_priority_nodes=self.config.POOL_LOW_PRIORITY_NODE_COUNT,
        )

        # Create the pool
        self.batch_client.pool.add(new_pool)

    def _create_job(self):
        """
        Creates a job with the specified ID, associated with the specified pool.
        """
        print("Creating job [{}]...".format(self.config.JOB_ID))

    def add_task(
        self,
        resource_files: List[models.ResourceFile],
        output_files: List[models.OutputFile],
        command_line=None,
    ):
        """
        Adds a task for each input file in the collection to the specified job.

        :param list resource_files: A list of ResouceFile descriptions for the task
        :param list output_files: A list of OutputFile descriptions for the task
        :param str command_line: The command used to for the task.  Optional;
            if missing, defaults to the command_line parameter provided when
            instantiating this object
        """
        self.tasks.append(
            models.TaskAddParameter(
                id="Task_{}".format(len(self.tasks)),
                command_line=self.config.COMMAND_LINE
                if command_line is None
                else command_line,
                resource_files=resource_files,
                output_files=output_files,
                container_settings=models.TaskContainerSettings(
                    image_name=self.config.DOCKER_IMAGE
                ),
            )
        )

    def _download_files(self):
        """
            def _download_files(config, blob_client, out_path, count):
        """

        pathlib.Path(self.config.BATCH_DIRECTORY).mkdir(
            parents=True, exist_ok=True
        )
        blob_names = [b.name for b in self.container_client.list_blobs()]

        for blob_name in self.output_files:
            if not blob_name in blob_names:
                raise RuntimeError(
                    "incomplete blob set: missing blob {}".format(blob_name)
                )

            blob_client = self.container_client.get_blob_client(blob_name)

            download_file_path = os.path.join(
                self.config.BATCH_DIRECTORY, blob_name
            )
            with open(download_file_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())

    def run(self, wait=True, **kwargs) -> None:
        r"""
        :param config: A :class:`BatchConfig` instance with the Azure Batch run parameters
        :type config: :class:BatchConfig

        :param boolean wait: If true, wait for the batch to complete and then
                download the results to file

        :raises BatchErrorException: If raised by the Azure Batch Python SDK
        """
        # replace any missing values in the configuration with environment variables

        if not hasattr(self, "tasks"):
            raise ValueError(
                "Client restored from data cannot be used to run the job"
            )

        try:
            # Create the pool that will contain the compute nodes that will execute the
            # tasks.
            if not (
                self.config.POOL_VM_SIZE
                and (
                    self.config.POOL_NODE_COUNT
                    or self.config.POOL_LOW_PRIORITY_NODE_COUNT
                )
            ):
                print("Using existing pool: ", self.config.POOL_ID)

            else:
                try:
                    self._create_pool()
                    print("Created pool: ", self.config.POOL_ID)
                except models.BatchErrorException:
                    print("Using pool: ", self.config.POOL_ID)

            # Create the job that will run the tasks.
            job_description = models.JobAddParameter(
                id=self.config.JOB_ID,
                pool_info=models.PoolInformation(pool_id=self.config.POOL_ID),
            )
            self.batch_client.job.add(job_description)

            # Add the tasks to the job.
            self.batch_client.task.add_collection(
                self.config.JOB_ID, self.tasks
            )

        except models.BatchErrorException as err:
            print_batch_exception(err)
            raise err

        if wait:
            self.load_results(**kwargs)

    def load_results(self, quiet=False) -> None:
        r"""
        :param config: A :class:`BatchConfig` instance with the Azure Batch run parameters
        :type config: :class:BatchConfig

        :raises BatchErrorException: If raised by the Azure Batch Python SDK
        """
        # pylint: disable=too-many-locals

        # replace any missing values in the configuration with environment variables
        start_time = datetime.datetime.now().replace(microsecond=0)
        if not quiet:
            print(
                "Job: {}\nStart time: {}".format(self.config.JOB_ID, start_time)
            )

        try:
            # Pause execution until tasks reach Completed state.
            wait_for_tasks_to_complete(
                self.batch_client,
                self.config.JOB_ID,
                datetime.timedelta(
                    hours=self.config.STORAGE_ACCESS_DURATION_HRS
                ),
            )
            self._download_files()
        except models.BatchErrorException as err:
            print_batch_exception(err)
            raise err

        # Print out some timing info
        if not quiet:
            end_time = datetime.datetime.now().replace(microsecond=0)
            print("End time: {}".format(end_time))

        # Clean up Batch resources (if the user so chooses).
        if self.config.DELETE_POOL_WHEN_DONE:
            self.batch_client.pool.delete(self.config.POOL_ID)
        if self.config.DELETE_JOB_WHEN_DONE:
            self.batch_client.job.delete(self.config.JOB_ID)
        if self.config.DELETE_CONTAINER_WHEN_DONE:
            self.container_client.delete_container()

    def print_task_output(self, encoding=None):
        """ Utilty method: Prints the stdout.txt file for each task in the job.
        # TODO: not sure if this works any more with jump to version 8 of the batch client
        """

        print("Printing task output...")

        for task in self.batch_client.task.list(self.config.JOB_ID):

            node_id = self.batch_client.task.get(
                self.config.JOB_ID, task.id
            ).node_info.node_id
            print("Task: {}".format(task.id))
            print("Node: {}".format(node_id))

            stream = self.batch_client.file.get_from_task(
                self.config.JOB_ID, task.id, "stdout.txt"
            )
            print("Standard output:")
            print(read_stream_as_string(stream, encoding))
