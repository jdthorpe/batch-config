"""
usage requires these additional modules

pip install azure-batch azure-storage-blob jsonschema pyyaml && pip install git+https://github.com/microsoft/SparseSC.git@ad4bf27edb28f517508f6934f21eb65d17fb6543 && scgrad start


usage:

from SparseSC import fit, aggregate_batch_results
from SparseSC.utils.azure_batch_client import BatchConfig, run

_TIMESTAMP = datetime.utcnow().strftime("%Y%m%d%H%M%S")

BATCH_DIR= "path/to/my/batch_config/"

fit(x=x,..., batchDir=BATCH_DIR)

my_config = BatchConfig(
    BATCH_ACCOUNT_NAME="MySecret",
    BATCH_ACCOUNT_KEY="MySecret",
    BATCH_ACCOUNT_URL="MySecret",
    STORAGE_ACCOUNT_NAME="MySecret",
    STORAGE_ACCOUNT_KEY="MySecret",
    POOL_ID="my-compute-pool",
    POOL_NODE_COUNT=0,
    POOL_LOW_PRIORITY_NODE_COUNT=20,
    POOL_VM_SIZE="STANDARD_A1_v2",
    DELETE_POOL_WHEN_DONE=False,
    JOB_ID="my-job" + _TIMESTAMP,
    DELETE_JOB_WHEN_DONE=False,
    CONTAINER_NAME="my-blob-container",
    BATCH_DIRECTORY=BATCH_DIR,
)

run(my_config)

fitted_model = aggregate_batch_results("path/to/my/batch_config")

"""
from __future__ import print_function
from typing import Tuple, List
import datetime
import os
import pathlib
import pdb

# -- from azure.storage.blob.blockblobservice import BlockBlobService, BlobPermissions
from azure.storage.blob import (
    BlobServiceClient,
    ContainerClient,
    ContainerSasPermissions,
    BlobSasPermissions,
    generate_container_sas,
    generate_blob_sas,
)
from azure.core.exceptions import ResourceExistsError,ResourceNotFoundError
from azure.batch import BatchServiceClient
from azure.batch.batch_auth import SharedKeyCredentials
import azure.batch.models as models


from .BatchConfig import _BatchConfig, BatchConfig
from .utils import (
    print_batch_exception,
    wait_for_tasks_to_complete,
    read_stream_as_string,
)


# pylint: disable=bad-continuation, invalid-name, protected-access, line-too-long, fixme

# -- sys.path.append(".")
# -- sys.path.append("..")
_STANDARD_OUT_FILE_NAME = "stdout.txt"

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


class client:
    """ convenience class
    """

    config: _BatchConfig
    _container_sas_url: str
    _blob_client: BlobServiceClient
    _batch_client: BatchServiceClient
    container_client: ContainerClient
    _output_files: List[Tuple[str]]
    tasks: List[models.TaskAddParameter]

    def __init__(self, **kwargs):
        self.config = BatchConfig(**kwargs)

        # Create the blob client, for use in obtaining references to
        # blob storage containers and uploading files to containers.
        self._blob_client = BlobServiceClient.from_connection_string(
            self.config.STORAGE_ACCOUNT_CONNECTION_STRING
        )

        # Use the blob client to create the containers in Azure Storage if they
        # don't yet exist.
        self.container_client = self._blob_client.get_container_client(
            self.config.CONTAINER_NAME
        )
        try:
            self.container_client.create_container()
        except ResourceExistsError:
            pass

        self._container_sas_url = (
            self.container_client.url
            + "?"
            + generate_container_sas(
                self.container_client.account_name,
                self.container_client.container_name,
                permission=ContainerSasPermissions(
                    read=True, write=True, delete=True, list=True
                ),
                expiry=datetime.datetime.utcnow()
                + datetime.timedelta(hours=self.config.STORAGE_ACCESS_DURATION_HRS),
                account_key=self.config.STORAGE_ACCOUNT_KEY,
            )
        )

        # Create a Batch service client. We'll now be interacting with the Batch
        # service in addition to Storage
        self._batch_client = BatchServiceClient(
            SharedKeyCredentials(
                self.config.BATCH_ACCOUNT_NAME, self.config.BATCH_ACCOUNT_KEY
            ),
            batch_url=self.config.BATCH_ACCOUNT_URL,
        )

        # initialize the output containers
        self._output_files = []
        self.tasks = []

    def build_resource_file(self, file_path, container_path: str, duration_hours=24):
        """
        Uploads a local file to an Azure Blob storage container.

        :param str file_path: The local path to the file.
        :param str container_path: The path where the file should be placed in the container before executing the task
        :rtype: `azure.batch.models.ResourceFile`
        :return: A ResourceFile initialized with a SAS URL appropriate for Batch
        tasks.
        """
        # print( "Uploading file {} to container [{}]...".format( file_path, self.config.CONTAINER_NAME)),
        blob_name = os.path.basename(file_path)
        blob_client = self.container_client.get_blob_client(blob_name)

        try:
            blob_client.delete_blob()
        except ResourceNotFoundError:
            pass

        with open(os.path.join(self.config.BATCH_DIRECTORY, file_path), "rb") as data:
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

        self._output_files.append((container_path))

        # where to store the outputs
        container_dest = models.OutputFileBlobContainerDestination(
            container_url=self._container_sas_url, path=container_path
        )
        dest = models.OutputFileDestination(container=container_dest)

        # Under what conditions should Azure Batch attempt to extract the outputs?
        upload_options = models.OutputFileUploadOptions(
            upload_condition=models.OutputFileUploadCondition.task_success
        )

        # https://docs.microsoft.com/en-us/azure/batch/batch-task-output-files#specify-output-files-for-task-output
        return models.OutputFile(
            file_pattern=output_file, destination=dest, upload_options=upload_options
        )

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
        if self.config.REGISTRY_USERNAME:
            registry = models.ContainerRegistry(
                user_name=self.config.REGISTRY_USERNAME,
                password=self.config.REGISTRY_PASSWORD,
                registry_server=self.config.REGISTRY_SERVER,
            )
            container_conf = models.ContainerConfiguration(
                container_image_names=[self.config.DOCKER_CONTAINER],
                container_registries=[registry],
            )
        else:
            container_conf = models.ContainerConfiguration(
                container_image_names=[self.config.DOCKER_CONTAINER]
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
        self._batch_client.pool.add(new_pool)

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

        :param batch_service_client: A Batch service client.
        :type batch_service_client: `azure.batch.BatchServiceClient`
        :param str job_id: The ID of the job to which to add the tasks.
        :param list resource_files: The input files
        :param output_container_sas_token: A SAS token granting write access to
        the specified Azure Blob storage container.
        """

        # output_file = build_output_file(_container_sas_url, fold_number)
        # command_line = '/bin/bash -c \'echo "Hello World" && echo "hello: world" > output.yaml\''
        # command_line = "/bin/bash -c 'stt {} {} {}'".format( _CONTAINER_INPUT_FILE, _CONTAINER_OUTPUT_FILE, fold_number)

        task_container_settings = models.TaskContainerSettings(
            image_name=self.config.DOCKER_CONTAINER
        )

        self.tasks.append(
            models.TaskAddParameter(
                id="Task_{}".format(len(self.tasks)),
                command_line=self.config.COMMAND_LINE
                if command_line is None
                else command_line,
                resource_files=resource_files,
                output_files=output_files,
                container_settings=task_container_settings,
            )
        )

        # self._batch_client.task.add_collection(job_id, tasks)

    def _download_files(self):
        """
            def _download_files(config, _blob_client, out_path, count):
        """

        pathlib.Path(self.config.BATCH_DIRECTORY).mkdir(parents=True, exist_ok=True)
        blob_names = [ b.name for b in self.container_client.list_blobs() ]

        for blob_name in self._output_files:
            if not blob_name in blob_names:
                raise RuntimeError(
                    "incomplete blob set: missing blob {}".format(blob_name)
                )

            blob_client = self.container_client.get_blob_client(blob_name)

            download_file_path = os.path.join(self.config.BATCH_DIRECTORY, blob_name)
            with open(download_file_path, "wb") as download_file: download_file.write(blob_client.download_blob().readall())

    def run(self, wait=True) -> None:
        r"""
        :param config: A :class:`BatchConfig` instance with the Azure Batch run parameters
        :type config: :class:BatchConfig

        :param boolean wait: If true, wait for the batch to complete and then
                download the results to file

        :raises BatchErrorException: If raised by the Azure Batch Python SDK
        """
        # replace any missing values in the configuration with environment variables

        try:
            # Create the pool that will contain the compute nodes that will execute the
            # tasks.
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
            self._batch_client.job.add(job_description)

            # Add the tasks to the job.
            self._batch_client.task.add_collection(self.config.JOB_ID, self.tasks)

        except models.BatchErrorException as err:
            print_batch_exception(err)
            raise err

        if wait:
            self.load_results()

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
                'Loading result for job "{}" start time: {}\n'.format(
                    self.config.JOB_ID, start_time
                )
            )

        try:

            # Pause execution until tasks reach Completed state.
            wait_for_tasks_to_complete(
                self._batch_client,
                self.config.JOB_ID,
                datetime.timedelta(hours=self.config.STORAGE_ACCESS_DURATION_HRS),
            )

            self._download_files()

        except models.BatchErrorException as err:
            print_batch_exception(err)
            raise err

        # Clean up storage resources
        # TODO: re-enable this and delete the output container too
        # --     print("Deleting container [{}]...".format(input_container_name))
        # --     _blob_client.delete_container(input_container_name)

        # Print out some timing info
        if not quiet:
            end_time = datetime.datetime.now().replace(microsecond=0)
            print(
                "\nSample end: {}\nElapsed time: {}\n".format(
                    end_time, end_time - start_time
                )
            )

        # Clean up Batch resources (if the user so chooses).
        if self.config.DELETE_POOL_WHEN_DONE:
            self._batch_client.pool.delete(self.config.POOL_ID)
        if self.config.DELETE_JOB_WHEN_DONE:
            self._batch_client.job.delete(self.config.JOB_ID)

    def print_task_output(self, encoding=None):
        """ Utilty method: Prints the stdout.txt file for each task in the job.

        """

        print("Printing task output...")

        tasks = self._batch_client.task.list(self.config.JOB_ID)

        for task in tasks:

            node_id = self._batch_client.task.get(
                self.config.JOB_ID, task.id
            ).node_info.node_id
            print("Task: {}".format(task.id))
            print("Node: {}".format(node_id))

            stream = self._batch_client.file.get_from_task(
                self.config.JOB_ID, task.id, _STANDARD_OUT_FILE_NAME
            )

            file_text = read_stream_as_string(stream, encoding)
            print("Standard output:")
            print(file_text)
