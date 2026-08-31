from mfm.model import Runner, RunnerState


def test_runner_lease_and_release() -> None:
    runner = Runner("m1-01", "macos-15-xcode-16")
    runner.lease("job-123", ttl_seconds=60)
    assert runner.state is RunnerState.LEASED
    assert runner.job_id == "job-123"
    runner.release("job-123", "success")
    assert runner.state is RunnerState.DRAINING
    assert runner.job_id is None


def test_runner_rejects_double_lease() -> None:
    runner = Runner("m1-01", "macos-15-xcode-16")
    runner.lease("job-123")
    try:
        runner.lease("job-456")
    except ValueError as exc:
        assert "not ready" in str(exc)
    else:
        raise AssertionError("double lease should fail")
