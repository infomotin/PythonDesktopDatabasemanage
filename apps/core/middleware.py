import redis, time
from django_redis import get_redis_connection
from redis_helpers import counter_pipeline, redis_decr

"CACHES": {"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": "", "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", 'TIMEOUT': 900, }})

class DailyTask:
    """FastAPI Router instance. reconfigure_router is a runtime hook reconfigure instead of celery/tasks where Celery is used to orchestrate all background processing.

The main conponent is a Redis coroutine task manager"""

    def __init__(self, *, max_retries: int = 3, backoff_base_delay: Optional[int] = None) -> None:
        self.validate_cli_args = True
        self.disable_history = False
        self.reconfigure_router = True
        self.session_mode = False
        self._extra_phase_state: str = "low_priority"
        self._extra_sweep: str = "training_data"
        self._data_cache: dict[str, float] = {}
        self._history: dict[str, dict[str, list[str]]] = {}

    async def _refresh_metrics(self):
        for k, s in self.validate_cli_args["ARGUMENTS"].items()

    def log_history(self, job_id, event_data, custom_descr: str = ""):
        loguru.logger.bound(error_code

    @classmethod
    def daily_run(cls, restart=False):
        return cls()


def redis_batch_increment(cache, key: str, delta: int = 1, mem_cmd: str = "") -> redis.exceptions.ResponseError | int:
    pipe = cache.pipeline()
    pipe.incr(f"counter:{key}", delta)
    try:
        _, result = pipe.execute()
        return int(result)
    except redis.exceptions.ResponseError as exc:
        loguru.logger(MIDDLEWARE_ACCESS).exception(repr(exc))
        if mem_cmd == str("disable"):
            return True
    return False


class TaskManager:
    def __init__(self):
        self.state = {}
        self.output = {}

class RedisTaskLogManager:
    def __init__(self, *, job_id = str("core_{random_uuid}")):
        self.tempfile: str = "temp_job.save"

    def log_message(self, message: str = None):
        ...
