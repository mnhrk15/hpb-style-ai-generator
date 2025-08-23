import pytest


def test_generate_hairstyle_async_sends_effect_type_to_celery(mocker):
    from app.services import task_service as ts

    # Arrange: fake celery app with send_task spy
    class FakeCelery:
        def __init__(self):
            self.send_task = mocker.Mock()

    fake_celery = FakeCelery()
    service = ts.TaskService(celery_app=fake_celery)

    # Act
    effect_type = "bright_bg"
    service.generate_hairstyle_async(
        user_id="u1",
        file_path="app/static/uploads/a.jpg",
        japanese_prompt="テスト",
        original_filename="a.jpg",
        task_id="tid-123",
        mode="kontext",
        mask_data=None,
        effect_type=effect_type,
    )

    # Assert: effect_type is included in args
    assert fake_celery.send_task.called
    _, kwargs = fake_celery.send_task.call_args
    args = kwargs["args"]
    # args order defined in implementation
    assert args[-1] == effect_type


def test_sync_generation_passes_effect_type_to_execute(mocker):
    from app.services import task_service as ts

    # Arrange: service without celery -> sync path
    service = ts.TaskService(celery_app=None)
    spy_execute = mocker.spy(ts.TaskService, "_execute_single_generation")

    # Act
    effect_type = "glossy_hair"
    service.generate_hairstyle_async(
        user_id="u2",
        file_path="app/static/uploads/b.jpg",
        japanese_prompt="プロンプト",
        original_filename="b.jpg",
        task_id="tid-456",
        mode="kontext",
        mask_data=None,
        effect_type=effect_type,
    )

    # Assert: effect_type forwarded (keyword or positional)
    assert spy_execute.called
    ca = spy_execute.call_args
    forwarded = ca.kwargs.get("effect_type") if hasattr(ca, "kwargs") else None
    if forwarded is None:
        forwarded = ca[0][-1]
    assert forwarded == effect_type


