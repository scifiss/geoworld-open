import pytest

from geoworld_open.client.intermediate_results import IntermediateResultPolicy


@pytest.mark.parametrize('total,expected', [(1,[1]), (10,[10]), (20,[20]),
    (21,[5,10,15,20,21]), (100,[20,40,60,80,100]), (250,[50,100,150,200,250]),
    (251,[100,200,251])])
def test_auto(total,expected):
    assert IntermediateResultPolicy().resolve(total)==expected


def test_scientific_boundaries_override_short_run_default():
    assert IntermediateResultPolicy().resolve(10,stage_boundaries=(2,4,6,8,10))==[2,4,6,8,10]


def test_bounded_advanced_overrides():
    assert IntermediateResultPolicy(mode='interval',interval=100).resolve(250)==[100,200,250]
    assert IntermediateResultPolicy(mode='schedule',schedule=[1,100]).resolve(250)==[1,100,250]
    assert IntermediateResultPolicy(mode='final').resolve(250)==[250]
    with pytest.raises(ValueError):
        IntermediateResultPolicy(mode='interval',interval=1).resolve(250)


@pytest.mark.parametrize('values', [dict(interval=2),dict(mode='interval'),dict(mode='schedule'),
    dict(schedule=[1]),dict(mode='schedule',schedule=[2,1]),dict(mode='schedule',schedule=[0]),
    dict(mode='schedule',schedule=[1,1])])
def test_invalid_policy(values):
    with pytest.raises(ValueError):
        IntermediateResultPolicy(**values)
