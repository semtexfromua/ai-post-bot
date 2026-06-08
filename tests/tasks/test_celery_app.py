from app.tasks.celery_app import celery_app


def test_serialization_and_utc():
    conf = celery_app.conf
    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert "json" in conf.accept_content
    assert conf.timezone == "UTC"
    assert conf.enable_utc is True


def test_reliability_flags():
    conf = celery_app.conf
    assert conf.task_ignore_result is True
    assert conf.task_acks_late is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.broker_connection_retry_on_startup is True


def test_time_limits_and_visibility_timeout():
    conf = celery_app.conf
    assert conf.task_soft_time_limit == 120
    assert conf.task_time_limit == 150
    vis = conf.broker_transport_options["visibility_timeout"]
    # invariant: visibility_timeout > longest hard time limit
    assert vis > conf.task_time_limit
    assert vis == 3600


def test_default_queue_is_default():
    assert celery_app.conf.task_default_queue == "default"


def test_publish_post_routed_to_tg_queue():
    routes = celery_app.conf.task_routes
    assert routes["app.tasks.pipeline.publish_post"] == {"queue": "tg"}


def test_beat_schedule_every_30_minutes():
    sched = celery_app.conf.beat_schedule
    entry = sched["collect"]
    assert entry["task"] == "app.tasks.pipeline.collect_sources"
    crontab = entry["schedule"]
    assert crontab.minute == {0, 30}
    assert "app.tasks.pipeline" in set(celery_app.conf.include)
