"""
LOA Common - Test Data Factory

Factory pattern fixtures for generating realistic test data for all 4 entity types.
Creates sample records for Applications, Customers, Branches, and Collateral that
can be used across all test suites with builder pattern support.

Used by: All test suites for consistent test data generation
"""

from faker import Faker
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytest
import random
from string import ascii_uppercase, digits


class ApplicationFactory:
    """Factory for generating realistic application test records."""

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize ApplicationFactory.

        Args:
            seed: Optional seed for reproducibility
        """
        self.faker = Faker()
        if seed:
            Faker.seed(seed)
            random.seed(seed)

        # Builder state
        self._ssn = None
        self._loan_amount = None
        self._loan_type = None
        self._status = None

    def create_single(self, **overrides) -> Dict[str, Any]:
        """
        Create a single application record.

        Args:
            **overrides: Override default values for specific fields

        Returns:
            Dictionary representing one application record
        """
        applicant_name = self.faker.name().upper()
        application_id = f"APP{self.faker.numerify(text='##########')}"
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        record = {
            "run_id": run_id,
            "processed_timestamp": datetime.utcnow().isoformat() + "Z",
            "source_file": f"APP_EXTRACT_{datetime.now().strftime('%Y%m%d')}.txt",
            "application_id": application_id,
            "ssn": self._ssn or self._generate_valid_ssn(),
            "applicant_name": applicant_name,
            "loan_amount": self._loan_amount or random.randint(10000, 1000000),
            "loan_type": self._loan_type or random.choice(["MORTGAGE", "PERSONAL", "AUTO", "HOME_EQUITY"]),
            "application_date": (datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d"),
            "branch_code": random.choice(["BRANCH001", "BRANCH002", "BRANCH003", "BRANCH004", "BRANCH005"]),
        }

        # Apply overrides
        record.update(overrides)

        # Reset builder state
        self._ssn = None
        self._loan_amount = None
        self._loan_type = None
        self._status = None

        return record

    def create_batch(self, count: int, **overrides) -> List[Dict[str, Any]]:
        """
        Create multiple application records.

        Args:
            count: Number of records to create
            **overrides: Override default values for all records

        Returns:
            List of application records
        """
        return [self.create_single(**overrides) for _ in range(count)]

    def with_ssn(self, ssn: str) -> 'ApplicationFactory':
        """Builder: Set SSN."""
        self._ssn = ssn
        return self

    def with_loan_amount(self, amount: int) -> 'ApplicationFactory':
        """Builder: Set loan amount."""
        self._loan_amount = amount
        return self

    def with_loan_type(self, loan_type: str) -> 'ApplicationFactory':
        """Builder: Set loan type."""
        self._loan_type = loan_type
        return self

    @staticmethod
    def _generate_valid_ssn() -> str:
        """Generate valid SSN format (XXX-XX-XXXX)."""
        return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"


class CustomerFactory:
    """Factory for generating realistic customer profile records."""

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize CustomerFactory.

        Args:
            seed: Optional seed for reproducibility
        """
        self.faker = Faker()
        if seed:
            Faker.seed(seed)
            random.seed(seed)

        # Builder state
        self._credit_score = None
        self._branch_code = None
        self._vip = False

    def create_single(self, **overrides) -> Dict[str, Any]:
        """
        Create a single customer record.

        Args:
            **overrides: Override default values for specific fields

        Returns:
            Dictionary representing one customer record
        """
        customer_name = self.faker.name().upper()
        customer_id = f"CUST{self.faker.numerify(text='########')}"
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # VIP customers have higher credit scores
        if self._vip:
            credit_score = random.randint(750, 850)
        else:
            credit_score = self._credit_score or random.randint(300, 850)

        record = {
            "run_id": run_id,
            "processed_timestamp": datetime.utcnow().isoformat() + "Z",
            "source_file": f"CUST_MASTER_{datetime.now().strftime('%Y%m%d')}.txt",
            "customer_id": customer_id,
            "ssn": ApplicationFactory._generate_valid_ssn(),
            "customer_name": customer_name,
            "account_number": str(self.faker.numerify(text='#########')),
            "email": self.faker.email(),
            "phone": f"{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}",
            "credit_score": credit_score,
            "customer_since": (datetime.now() - timedelta(days=random.randint(365, 3650))).strftime("%Y-%m-%d"),
            "branch_code": self._branch_code or random.choice(["BRANCH001", "BRANCH002", "BRANCH003", "BRANCH004", "BRANCH005"]),
        }

        # Apply overrides
        record.update(overrides)

        # Reset builder state
        self._credit_score = None
        self._branch_code = None
        self._vip = False

        return record

    def create_batch(self, count: int, **overrides) -> List[Dict[str, Any]]:
        """
        Create multiple customer records.

        Args:
            count: Number of records to create
            **overrides: Override default values for all records

        Returns:
            List of customer records
        """
        return [self.create_single(**overrides) for _ in range(count)]

    def with_credit_score(self, score: int) -> 'CustomerFactory':
        """Builder: Set credit score."""
        self._credit_score = score
        return self

    def with_branch(self, branch_code: str) -> 'CustomerFactory':
        """Builder: Set branch code."""
        self._branch_code = branch_code
        return self

    def vip(self) -> 'CustomerFactory':
        """Builder: Create VIP customer (credit score > 750)."""
        self._vip = True
        return self


class BranchFactory:
    """Factory for generating realistic branch master data."""

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize BranchFactory.

        Args:
            seed: Optional seed for reproducibility
        """
        self.faker = Faker()
        if seed:
            Faker.seed(seed)
            random.seed(seed)

        # Builder state
        self._state = None
        self._region = None
        self._manager_name = None
        self._closed = False

    def create_single(self, **overrides) -> Dict[str, Any]:
        """
        Create a single branch record.

        Args:
            **overrides: Override default values for specific fields

        Returns:
            Dictionary representing one branch record
        """
        branch_code = f"BRANCH{str(random.randint(1, 999)).zfill(3)}"
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        valid_states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
                       "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                       "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                       "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                       "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"]

        regions = ["Northeast", "Southeast", "Midwest", "Southwest", "West"]

        state = self._state or random.choice(valid_states)
        region = self._region or random.choice(regions)

        record = {
            "run_id": run_id,
            "processed_timestamp": datetime.utcnow().isoformat() + "Z",
            "source_file": f"BRANCH_MASTER_{datetime.now().strftime('%Y%m%d')}.txt",
            "branch_code": branch_code,
            "branch_name": f"{self.faker.city()} BRANCH".upper(),
            "region": region,
            "state": state,
            "city": self.faker.city(),
            "zip_code": self.faker.zipcode(),
            "manager_name": self._manager_name or self.faker.name().upper(),
            "opened_date": (datetime.now() - timedelta(days=random.randint(365, 10950))).strftime("%Y-%m-%d"),
            "employee_count": random.randint(5, 100),
        }

        # Apply overrides
        record.update(overrides)

        # Reset builder state
        self._state = None
        self._region = None
        self._manager_name = None
        self._closed = False

        return record

    def create_batch(self, count: int, **overrides) -> List[Dict[str, Any]]:
        """
        Create multiple branch records.

        Args:
            count: Number of records to create
            **overrides: Override default values for all records

        Returns:
            List of branch records
        """
        return [self.create_single(**overrides) for _ in range(count)]

    def with_state(self, state: str) -> 'BranchFactory':
        """Builder: Set state code."""
        self._state = state
        return self

    def with_region(self, region: str) -> 'BranchFactory':
        """Builder: Set region."""
        self._region = region
        return self

    def with_manager(self, manager_name: str) -> 'BranchFactory':
        """Builder: Set manager name."""
        self._manager_name = manager_name
        return self


class CollateralFactory:
    """Factory for generating realistic collateral asset records."""

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize CollateralFactory.

        Args:
            seed: Optional seed for reproducibility
        """
        self.faker = Faker()
        if seed:
            Faker.seed(seed)
            random.seed(seed)

        # Builder state
        self._application_id = None
        self._collateral_type = None

    def create_single(self, **overrides) -> Dict[str, Any]:
        """
        Create a single collateral record.

        Args:
            **overrides: Override default values for specific fields

        Returns:
            Dictionary representing one collateral record
        """
        collateral_id = f"COLL{self.faker.numerify(text='##########')}"
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        collateral_type = self._collateral_type or random.choice(["PROPERTY", "VEHICLE", "SECURITIES"])

        # Value depends on type
        if collateral_type == "PROPERTY":
            value = random.randint(100000, 500000)
        elif collateral_type == "VEHICLE":
            value = random.randint(15000, 60000)
        else:  # SECURITIES
            value = random.randint(10000, 200000)

        record = {
            "run_id": run_id,
            "processed_timestamp": datetime.utcnow().isoformat() + "Z",
            "source_file": f"COLL_EXTRACT_{datetime.now().strftime('%Y%m%d')}.txt",
            "collateral_id": collateral_id,
            "application_id": self._application_id or f"APP{self.faker.numerify(text='##########')}",
            "collateral_type": collateral_type,
            "collateral_value": value,
            "appraisal_date": (datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d"),
            "appraiser_name": f"{self.faker.company()} APPRAISALS".upper(),
            "account_number": str(self.faker.numerify(text='#########')),
            "branch_code": random.choice(["BRANCH001", "BRANCH002", "BRANCH003", "BRANCH004", "BRANCH005"]),
        }

        # Apply overrides
        record.update(overrides)

        # Reset builder state
        self._application_id = None
        self._collateral_type = None

        return record

    def create_batch(self, count: int, **overrides) -> List[Dict[str, Any]]:
        """
        Create multiple collateral records.

        Args:
            count: Number of records to create
            **overrides: Override default values for all records

        Returns:
            List of collateral records
        """
        return [self.create_single(**overrides) for _ in range(count)]

    def for_application(self, app_id: str) -> 'CollateralFactory':
        """Builder: Link to application."""
        self._application_id = app_id
        return self

    def property(self) -> 'CollateralFactory':
        """Builder: Create property collateral."""
        self._collateral_type = "PROPERTY"
        return self

    def vehicle(self) -> 'CollateralFactory':
        """Builder: Create vehicle collateral."""
        self._collateral_type = "VEHICLE"
        return self

    def securities(self) -> 'CollateralFactory':
        """Builder: Create securities collateral."""
        self._collateral_type = "SECURITIES"
        return self


# ============================================================================
# PYTEST FIXTURES
# ============================================================================

@pytest.fixture
def application_factory():
    """Factory for creating application test records."""
    return ApplicationFactory()


@pytest.fixture
def customer_factory():
    """Factory for creating customer test records."""
    return CustomerFactory()


@pytest.fixture
def branch_factory():
    """Factory for creating branch test records."""
    return BranchFactory()


@pytest.fixture
def collateral_factory():
    """Factory for creating collateral test records."""
    return CollateralFactory()


@pytest.fixture
def sample_applications(application_factory):
    """Fixture providing 10 sample applications."""
    return application_factory.create_batch(10)


@pytest.fixture
def sample_customers(customer_factory):
    """Fixture providing 10 sample customers."""
    return customer_factory.create_batch(10)


@pytest.fixture
def sample_branches(branch_factory):
    """Fixture providing 5 sample branches."""
    return branch_factory.create_batch(5)


@pytest.fixture
def sample_collateral(collateral_factory):
    """Fixture providing 10 sample collateral records."""
    return collateral_factory.create_batch(10)

