import io
import time
import sys
import datetime
from collections import defaultdict
from azure.storage.blob import (
    generate_container_sas,
    ContainerSasPermissions,
    generate_blob_sas,
    BlobSasPermissions,
)
from azure.batch.models import TaskState
from .print_progress import _print_progress

# pylint: disable=bad-continuation, line-too-long, invalid-name


def _print_batch_exception(batch_exception):
    """
    Prints the contents of the specified Batch exception.
    :param batch_exception:
    """
    print("-------------------------------------------")
    print("Exception encountered:")
    if (
        batch_exception.error
        and batch_exception.error.message
        and batch_exception.error.message.value
    ):
        print(batch_exception.error.message.value)
        if batch_exception.error.values:
            print()
            for mesg in batch_exception.error.values:
                print("{}:\t{}".format(mesg.key, mesg.value))
    print("-------------------------------------------")


def _wait_for_tasks_to_complete(batch_service_client, job_id, timeout):
    """
    Returns when all tasks in the specified job reach the Completed state.

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str job_id: The id of the job whose tasks should be to monitored.
    :param timedelta timeout: The duration to wait for task completion. If all
    tasks in the specified job do not reach Completed state within this time
    period, an exception will be raised.
    """

    _start_time = datetime.datetime.now()
    timeout_expiration = _start_time + timeout

    # print( "Monitoring all tasks for 'Completed' state, timeout in {}...".format(timeout), end="",)

    while datetime.datetime.now() < timeout_expiration:
        sys.stdout.flush()
        tasks = [t for t in batch_service_client.task.list(job_id)]

        incomplete_tasks = [task for task in tasks if task.state != TaskState.completed]

        hours, remainder = divmod((datetime.datetime.now() - _start_time).seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        _print_progress(
            len(tasks) - len(incomplete_tasks),
            len(tasks),
            prefix="Time elapsed {:02}:{:02}:{:02}".format(
                int(hours), int(minutes), int(seconds)
            ),
            decimals=1,
            bar_length=min(len(tasks), 50),
        )

        error_codes = [
            "   Task {} exited with code {}".format(i, t.execution_info.exit_code)
            for i, t in enumerate(tasks)
            if t.execution_info and t.execution_info.exit_code
        ]
        if len(error_codes):
            raise RuntimeError(
                "\nSome tasks have exited with a non-zero exit code including:\n"
                + "\n".join(error_codes)
            )
        if not incomplete_tasks:
            print()
            return True
        time.sleep(1)

    print()
    raise RuntimeError(
        "ERROR: Tasks did not reach 'Completed' state within "
        "timeout period of " + str(timeout)
    )


def _read_stream_as_string(stream, encoding):
    """Read stream as string
    :param stream: input stream generator
    :param str encoding: The encoding of the file. The default is utf-8.
    :return: The file content.
    :rtype: str
    """
    output = io.BytesIO()
    try:
        for data in stream:
            output.write(data)
        if encoding is None:
            encoding = "utf-8"
        return output.getvalue().decode(encoding)
    finally:
        output.close()
    raise RuntimeError("could not write data to stream or decode bytes")
