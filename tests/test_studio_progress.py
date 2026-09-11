import pytest
from geoworld_open.client.job_progress import JobProgress
from geoworld_open.client.models import JobStatusResponse
from geoworld_open.studio_progress import progress_labels


def detail(**kwargs):
    values = dict(phase="rtm_batches", completed=2, total=39, elapsed_s=100., eta_s=1850., updated_unix_s=1000.)
    values.update(kwargs)
    return JobProgress(**values)


def test_real_units_and_eta_scope():
    fraction, label, caption = progress_labels(detail(), now=1010.)
    assert fraction == 2/39 and "2/39" in label
    assert "1m 50s" in caption and "remaining batches" in caption
    assert "saving/validation is additional" in caption


def test_eta_not_fake_zero_and_finalizing_not_job_success():
    _, _, caption = progress_labels(detail(), now=3000.)
    assert "Taking longer" in caption
    _, _, caption = progress_labels(detail(completed=1, eta_s=None), now=1000.)
    assert "after two" in caption
    fraction, _, caption = progress_labels(detail(completed=39, eta_s=None, phase="finalizing"), now=1000.)
    assert fraction == 1 and "still need to finish" in caption


def test_older_jobs_remain_readable():
    job = JobStatusResponse(job_id="old", status="running", progress="Executing unchanged upstream rtm")
    assert job.progress_detail is None


@pytest.mark.parametrize("changes", [{"completed":40}, {"eta_s":float("nan")}, {"completed":0}, {"total":0}])
def test_invalid_progress_rejected(changes):
    with pytest.raises(ValueError):
        detail(**changes)


def test_real_poll_function_uses_counts_and_waits_for_job_success():
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    source = Path(__file__).parents[1] / "apps/studio_streamlit.py"
    tree = ast.parse(source.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "poll_job")
    values = []
    class Slot:
        def empty(self): pass
        def info(self, text): pass
        def caption(self, text): pass
        def success(self, text): values.append("success")
        def progress(self, value, text=""): values.append(value)
    jobs = iter([
        JobStatusResponse(job_id="test", status="running", progress="batch", progress_detail=detail()),
        JobStatusResponse(job_id="test", status="running", progress="saving", progress_detail=detail(completed=39, eta_s=None, phase="finalizing")),
        JobStatusResponse(job_id="test", status="succeeded", progress="complete"),
    ])
    namespace = {"st": SimpleNamespace(empty=Slot), "time": SimpleNamespace(sleep=lambda _: None),
                 "GeoWorldBackendClient": object, "GeoWorldClientError": RuntimeError}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    result = namespace["poll_job"](SimpleNamespace(get_job=lambda _: next(jobs)), "test", actual_stages=True, reference=True)
    assert result.status == "succeeded"
    assert values == [2/39, 1., 100, "success"]
