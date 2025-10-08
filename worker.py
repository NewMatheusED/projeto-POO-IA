import os
import platform
import sys

from app.tasks.celery_config import celery_app
from worker_factory import create_worker_app

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


flask_app = create_worker_app()
celery_app.flask_app = flask_app

if __name__ == "__main__":
    import sys

    worker_args = sys.argv[1:]
    if platform.system() == "Windows":
        if "--pool" not in worker_args:
            worker_args.extend(["--pool=threads"])
        if "--concurrency" not in worker_args:
            worker_args.extend(["--concurrency=1"])
    celery_app.worker_main(worker_args)
