# -*- coding: utf-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
This module contains the methods for gathering various debug information
for incident reporting using presto-admin
"""

import logging
import json
import shutil
import tarfile

import requests
from fabric.contrib.files import exists
from fabric.operations import os, get
from fabric.tasks import execute
from fabric.api import env, runs_once, task
from fabric.utils import abort, warn

from prestoadmin.topology import requires_topology
import prestoadmin.util.fabricapi as fabricapi

from util.constants import REMOTE_PRESTO_LOG_DIR, PRESTOADMIN_LOG_DIR


TMP_PRESTO_DEBUG = '/tmp/presto-debug/'
OUTPUT_FILENAME = '/tmp/presto-debug-logs.tar.bz2'
PRESTOADMIN_LOG_NAME = 'presto-admin.log'
_LOGGER = logging.getLogger(__name__)
QUERY_REQUEST_URL = "http://localhost:8080/v1/query/"

__all__ = ['logs', 'query_info']


@task
@runs_once
def logs():
    """
    Gather all the server logs and presto-admin log and create a tar file.
    """

    _LOGGER.debug("LOG directory to be archived: " + REMOTE_PRESTO_LOG_DIR)

    if not os.path.exists(TMP_PRESTO_DEBUG):
        os.mkdir(TMP_PRESTO_DEBUG)

    print 'Downloading logs from all the nodes'
    execute(file_get, REMOTE_PRESTO_LOG_DIR, TMP_PRESTO_DEBUG, roles=env.roles)

    copy_admin_log()

    make_tarfile(OUTPUT_FILENAME, TMP_PRESTO_DEBUG)
    print 'logs archive created : ' + OUTPUT_FILENAME


def copy_admin_log():
    shutil.copy(os.path.join(PRESTOADMIN_LOG_DIR, PRESTOADMIN_LOG_NAME),
                TMP_PRESTO_DEBUG)


def make_tarfile(output_filename, source_dir):
    tar = tarfile.open(output_filename, "w:bz2")

    try:
        tar.add(source_dir, arcname=os.path.basename(source_dir))
    finally:
        tar.close()


def file_get(remote_path, local_path):
    if exists(remote_path, True):
        get(remote_path, local_path + '%(host)s', True)
    else:
        warn("remote path " + remote_path + " not found on " + env.host)


@task
@requires_topology
def query_info(query_id=None):
    """
    Gather information about the query identified by the given
    query_id and store that in a JSON file.
    """

    if env.host not in fabricapi.get_coordinator_role():
        return

    if query_id is None:
        abort("Missing argument query_id")

    req = requests.get(QUERY_REQUEST_URL + query_id)

    if not req.status_code == requests.codes.ok:
        abort("Unable to retrieve information. "
              "Please check that the query_id is correct, or check that "
              "server is up with command server status")

    query_info_file_name = os.path.join(TMP_PRESTO_DEBUG,
                                        "query_info_" + query_id + ".json")

    if not os.path.exists(TMP_PRESTO_DEBUG):
        os.mkdir(TMP_PRESTO_DEBUG)

    with open(query_info_file_name, "w") as out_file:
        out_file.write(json.dumps(req.json(), indent=4))

    print("Gathered query information in file : " + query_info_file_name)