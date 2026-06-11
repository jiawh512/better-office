import pytest

def pytest_addoption(parser):
    parser.addoption("--evals-report-file", action="store", default="")
    parser.addoption("--model", action="store", default="demo-model")

@pytest.fixture
def model(pytestconfig):
    return str(pytestconfig.getoption("--model"))
