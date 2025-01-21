from contextlib import contextmanager

import pytest
from cdktf import LocalBackend, Testing

from .stacks import AwsS3StateStack


@pytest.fixture(scope="module")
def stack():
    @contextmanager
    def _stack(stack_class):
        assert issubclass(stack_class, AwsS3StateStack)

        monkeypatch = pytest.MonkeyPatch()

        # Ensure we do not have an active AWS CLI session
        for name in ("AWS_PROFILE", "AWS_DEFAULT_PROJECT"):
            monkeypatch.delenv(name, raising=False)

        # Patch S3Backend to be a LocalBackend to avoid AWS API activity
        monkeypatch.setattr(
            stack_class, "register_backend", lambda self: LocalBackend(self)
        )

        # Initialise our stack with the monkey patching in place
        stack = stack_class(Testing.app(context={"name": "app"}), "stack")
        try:
            yield stack
        finally:
            monkeypatch.undo()

    return _stack


@pytest.fixture(scope="module")
def synthesized(stack):
    @contextmanager
    def _synthesized(stack_class):
        nonlocal stack
        with stack(stack_class) as stack:
            yield Testing.synth(stack)

    return _synthesized


@pytest.fixture(scope="module")
def fully_synthesized(stack):
    @contextmanager
    def _fully_synthesized(stack_class):
        nonlocal stack
        with stack(stack_class) as stack:
            yield Testing.full_synth(stack)

    return _fully_synthesized
