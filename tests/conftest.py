from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def scenarios():
    from memhalflife.scenarios import load_all

    return load_all(ROOT / "scenarios")


@pytest.fixture(scope="session")
def synth_dir(tmp_path_factory, scenarios):
    from memhalflife.synthetic import generate

    d = tmp_path_factory.mktemp("synth")
    generate(d, scenarios, reps=8, seed=3)
    return d
