"""Imports every module that registers jobs, so the worker and the API know all of them."""

from chorus import dev_jobs  # noqa: F401
from chorus.jobs import celery_app

__all__ = ["celery_app"]
