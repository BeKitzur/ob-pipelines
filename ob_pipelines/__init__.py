import logging
import os
import traceback
from datetime import datetime

import luigi

import ob_pipelines
from ob_pipelines.batch import TaskWrapper
from ob_pipelines.entities.persistence import create_task, get_task_by_key, update_task
from ob_pipelines.entities.task import Task

logger = logging.getLogger(__name__)

# Create the format
formatter = logging.Formatter('%(asctime)s - %(message)s')

# Add a console handler
ch = logging.StreamHandler()
ch.setLevel(os.environ.get('LOGGING_LEVEL') or logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)


@TaskWrapper.event_handler(luigi.event.Event.START)
def luigi_task_start(luigi_task: TaskWrapper):
    task: Task = Task()
    task.name = luigi_task.task_id_str
    task.status = 'running'
    task.started_at = datetime.utcnow()
    luigi_task.task_id = create_task(task).key


@TaskWrapper.event_handler(luigi.event.Event.SUCCESS)
def luigi_task_success(luigi_task: TaskWrapper):
    task = get_task_by_key(luigi_task.task_id)
    task.completed_at = datetime.utcnow()
    task.status = 'completed'
    update_task(task)


@TaskWrapper.event_handler(luigi.event.Event.FAILURE)
def luigi_task_failure(luigi_task: TaskWrapper):
    task = get_task_by_key(luigi_task.task_id)
    task.completed_at = datetime.utcnow()
    task.status = 'failed'
    task.exception = traceback.format_exc()
    update_task(task)
