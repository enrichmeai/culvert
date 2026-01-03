import pytest
import sys
from pathlib import Path

# Add tests directory to path for fixture imports
tests_dir = Path(__file__).parent.parent.parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

from fixtures.test_data_factory import (
    ApplicationFactory,
    CustomerFactory,
    BranchFactory,
    CollateralFactory
)

@pytest.fixture(scope="function")
def application_factory():
    return ApplicationFactory()

@pytest.fixture(scope="function")
def customer_factory():
    return CustomerFactory()

@pytest.fixture(scope="function")
def branch_factory():
    return BranchFactory()

@pytest.fixture(scope="function")
def collateral_factory():
    return CollateralFactory()

@pytest.fixture(scope="function")
def sample_applications(application_factory):
    return application_factory.create_batch(10)

@pytest.fixture(scope="function")
def sample_customers(customer_factory):
    return customer_factory.create_batch(10)

@pytest.fixture(scope="function")
def sample_branches(branch_factory):
    return branch_factory.create_batch(10)

@pytest.fixture(scope="function")
def sample_collateral(collateral_factory):
    return collateral_factory.create_batch(10)
