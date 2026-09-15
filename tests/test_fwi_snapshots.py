import json
from types import SimpleNamespace

import pytest

from geoworld_open.studio_fwi_snapshots import latest_snapshot


def test_snapshot_poll_retries_without_advancing_scientific_progress():
    from geoworld_open.studio_fwi_snapshots import should_check_snapshot
    assert not should_check_snapshot(0,None,0,None)
    assert should_check_snapshot(50,49,10,9)
    assert not should_check_snapshot(50,50,12,10)
    assert should_check_snapshot(50,50,15,10)


def api(values):
    return SimpleNamespace(get_artifact=lambda *_:json.dumps(values).encode())


def test_only_completed_snapshots_are_shown():
    client=api([dict(completed=50,figure_file='snapshot_0050.png'),
                dict(completed=100,figure_file='snapshot_0100.png')])
    assert latest_snapshot(client,'job',49) is None
    assert latest_snapshot(client,'job',73)==(50,'fwi/snapshot_0050.png')
    assert latest_snapshot(client,'job',100)==(100,'fwi/snapshot_0100.png')


@pytest.mark.parametrize('entry',[dict(completed=True,figure_file='snapshot_0001.png'),
    dict(completed=1000,figure_file='snapshot_1000.png'),dict(completed=50,figure_file='../../secret'),
    dict(completed=50,figure_file='https://example.test/pixel'),dict(completed=50,figure_file='trace.json')])
def test_snapshot_index_cannot_select_arbitrary_artifacts(entry):
    with pytest.raises(ValueError):
        latest_snapshot(api([entry]),'job',100)
