import numpy as np

from geoworld_open.engine import SeedManager
from geoworld_open.science import run_structural_workflow


def test_seed_manager_is_stable_and_namespace_order_independent() -> None:
    first = SeedManager(41)
    a_before_b = first.generator("a").normal(size=8)
    b_after_a = first.generator("b").normal(size=8)
    second = SeedManager(41)
    b_before_a = second.generator("b").normal(size=8)
    a_after_b = second.generator("a").normal(size=8)
    np.testing.assert_array_equal(a_before_b, a_after_b)
    np.testing.assert_array_equal(b_after_a, b_before_a)


def test_seed_and_realization_identity_change_random_draws() -> None:
    first = SeedManager(41).generator("operator", realization=2).normal(size=8)
    changed_seed = SeedManager(42).generator("operator", realization=2).normal(size=8)
    changed_realization = SeedManager(41).generator("operator", realization=3).normal(size=8)
    assert not np.array_equal(first, changed_seed)
    assert not np.array_equal(first, changed_realization)


def test_seed_lineage_is_stable() -> None:
    first = SeedManager(77).lineage("geology", realization=4)
    second = SeedManager(77).lineage("geology", realization=4)
    assert first == second
    assert first["root_entropy"] == 77
    assert first["realization"] == 4


def test_structural_workflow_does_not_mutate_global_numpy_rng(structural_v2_scenario) -> None:
    np.random.seed(12345)
    expected = np.random.random(5)
    np.random.seed(12345)
    run_structural_workflow(structural_v2_scenario)
    actual = np.random.random(5)
    np.testing.assert_array_equal(actual, expected)
