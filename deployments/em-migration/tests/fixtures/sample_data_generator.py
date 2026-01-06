"""
Test Data Generator for LOA Pipelines

Generates realistic test data for unit, integration, and functional testing.
Supports all LOA entity types: applications, customers, branches, collateral.

Used by: Unit tests, integration tests, functional tests, local development
"""

import random
import string
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import csv
import io


@dataclass
class TestDataConfig:
    """Configuration for test data generation"""
    num_records: int = 100
    valid_percentage: float = 0.9  # % of valid records
    error_percentage: float = 0.05  # % of error records
    duplicate_percentage: float = 0.05  # % of duplicates
    seed: int = 42  # For reproducibility


class TestDataFactory:
    """Factory for generating test data"""

    def __init__(self, config: TestDataConfig = None):
        self.config = config or TestDataConfig()
        if self.config.seed:
            random.seed(self.config.seed)

    # ==================== Application Records ====================

    @staticmethod
    def generate_application_id() -> str:
        """Generate valid application ID"""
        return f"APP{random.randint(100000, 999999)}"

    @staticmethod
    def generate_ssn() -> str:
        """Generate valid SSN (for testing only)"""
        return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"

    @staticmethod
    def generate_invalid_ssn() -> str:
        """Generate invalid SSN for testing"""
        return "000-00-0000"  # Invalid pattern

    @staticmethod
    def generate_name() -> str:
        """Generate random name"""
        first_names = ['John', 'Jane', 'Robert', 'Mary', 'James', 'Patricia']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia']
        return f"{random.choice(first_names)} {random.choice(last_names)}"

    @staticmethod
    def generate_email() -> str:
        """Generate valid email"""
        return f"{random.randint(1000, 9999)}@example.com"

    @staticmethod
    def generate_invalid_email() -> str:
        """Generate invalid email"""
        return "not_an_email"

    @staticmethod
    def generate_phone() -> str:
        """Generate valid phone number"""
        return f"+44{random.randint(2000000000, 7999999999)}"

    @staticmethod
    def generate_loan_amount() -> float:
        """Generate valid loan amount"""
        return round(random.uniform(5000, 500000), 2)

    @staticmethod
    def generate_invalid_loan_amount() -> str:
        """Generate invalid loan amount"""
        return "not_a_number"

    @staticmethod
    def generate_date_of_birth() -> str:
        """Generate valid date of birth"""
        age = random.randint(18, 70)
        dob = datetime.now() - timedelta(days=age*365 + random.randint(0, 365))
        return dob.strftime('%Y-%m-%d')

    @staticmethod
    def generate_application_date() -> str:
        """Generate application date"""
        days_back = random.randint(0, 90)
        date = datetime.now() - timedelta(days=days_back)
        return date.strftime('%Y-%m-%d')

    @staticmethod
    def generate_application_status() -> str:
        """Generate valid application status"""
        statuses = ['PENDING', 'APPROVED', 'REJECTED', 'WITHDRAWN']
        return random.choice(statuses)

    def generate_valid_application(self) -> Dict[str, Any]:
        """Generate a valid application record"""
        return {
            'application_id': self.generate_application_id(),
            'customer_id': f"CUST{random.randint(100000, 999999)}",
            'customer_name': self.generate_name(),
            'customer_ssn': self.generate_ssn(),
            'date_of_birth': self.generate_date_of_birth(),
            'email': self.generate_email(),
            'phone': self.generate_phone(),
            'loan_amount': self.generate_loan_amount(),
            'loan_term_months': random.randint(12, 360),
            'application_date': self.generate_application_date(),
            'application_status': self.generate_application_status(),
            'branch_code': f"BR{random.randint(100, 999)}",
            'employment_status': random.choice(['EMPLOYED', 'SELF_EMPLOYED', 'UNEMPLOYED']),
            'annual_income': round(random.uniform(20000, 200000), 2),
        }

    def generate_invalid_application(self) -> Dict[str, Any]:
        """Generate an invalid application record"""
        invalid_type = random.randint(1, 3)
        app = self.generate_valid_application()

        if invalid_type == 1:
            app['customer_ssn'] = self.generate_invalid_ssn()
        elif invalid_type == 2:
            app['email'] = self.generate_invalid_email()
        else:
            app['loan_amount'] = self.generate_invalid_loan_amount()

        return app

    def generate_applications(self, count: int = None) -> List[Dict[str, Any]]:
        """Generate application records"""
        count = count or self.config.num_records
        records = []

        num_valid = int(count * self.config.valid_percentage)
        num_invalid = int(count * self.config.error_percentage)
        num_duplicates = int(count * self.config.duplicate_percentage)
        num_normal = count - num_valid - num_invalid - num_duplicates

        # Valid records
        for _ in range(num_valid):
            records.append(self.generate_valid_application())

        # Invalid records
        for _ in range(num_invalid):
            records.append(self.generate_invalid_application())

        # Duplicate records (duplicate first valid record)
        if records:
            duplicate = records[0].copy()
            for _ in range(num_duplicates):
                records.append(duplicate)

        # Normal records
        for _ in range(num_normal):
            records.append(self.generate_valid_application())

        return records

    # ==================== Customer Records ====================

    def generate_valid_customer(self) -> Dict[str, Any]:
        """Generate a valid customer record"""
        return {
            'customer_id': f"CUST{random.randint(100000, 999999)}",
            'customer_name': self.generate_name(),
            'email': self.generate_email(),
            'phone': self.generate_phone(),
            'address': f"{random.randint(1, 100)} Main Street",
            'city': random.choice(['London', 'Manchester', 'Birmingham', 'Leeds']),
            'postal_code': f"{random.choice(['SW', 'E', 'N', 'W'])}1{random.randint(1, 9)} {random.randint(1, 9)}AA",
            'customer_type': random.choice(['INDIVIDUAL', 'BUSINESS']),
            'status': random.choice(['ACTIVE', 'INACTIVE', 'SUSPENDED']),
            'created_date': (datetime.now() - timedelta(days=random.randint(1, 1000))).strftime('%Y-%m-%d'),
        }

    def generate_customers(self, count: int = None) -> List[Dict[str, Any]]:
        """Generate customer records"""
        count = count or self.config.num_records
        return [self.generate_valid_customer() for _ in range(count)]

    # ==================== Branch Records ====================

    def generate_valid_branch(self) -> Dict[str, Any]:
        """Generate a valid branch record"""
        return {
            'branch_code': f"BR{random.randint(100, 999)}",
            'branch_name': f"{random.choice(['London', 'Manchester', 'Birmingham'])} Branch",
            'branch_address': f"{random.randint(1, 100)} High Street",
            'city': random.choice(['London', 'Manchester', 'Birmingham', 'Leeds']),
            'region': random.choice(['NORTH', 'SOUTH', 'EAST', 'WEST']),
            'manager_name': self.generate_name(),
            'phone': self.generate_phone(),
            'email': self.generate_email(),
            'open_date': (datetime.now() - timedelta(days=random.randint(1000, 10000))).strftime('%Y-%m-%d'),
            'status': random.choice(['OPEN', 'CLOSED', 'UNDER_RENOVATION']),
        }

    def generate_branches(self, count: int = None) -> List[Dict[str, Any]]:
        """Generate branch records"""
        count = count or self.config.num_records
        return [self.generate_valid_branch() for _ in range(count)]

    # ==================== Collateral Records ====================

    def generate_valid_collateral(self) -> Dict[str, Any]:
        """Generate a valid collateral record"""
        return {
            'collateral_id': f"COLL{random.randint(100000, 999999)}",
            'application_id': self.generate_application_id(),
            'collateral_type': random.choice(['PROPERTY', 'VEHICLE', 'OTHER']),
            'collateral_value': round(random.uniform(10000, 500000), 2),
            'currency': 'GBP',
            'valuation_date': (datetime.now() - timedelta(days=random.randint(1, 365))).strftime('%Y-%m-%d'),
            'lien_status': random.choice(['NO_LIEN', 'FIRST_LIEN', 'SECOND_LIEN']),
            'description': 'Property collateral for loan',
            'status': random.choice(['ACTIVE', 'RELEASED', 'PENDING_VALUATION']),
        }

    def generate_collaterals(self, count: int = None) -> List[Dict[str, Any]]:
        """Generate collateral records"""
        count = count or self.config.num_records
        return [self.generate_valid_collateral() for _ in range(count)]

    # ==================== Export Methods ====================

    def export_to_csv(self, records: List[Dict[str, Any]]) -> str:
        """Export records to CSV format"""
        if not records:
            return ""

        output = io.StringIO()
        fieldnames = records[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(records)

        return output.getvalue()

    def export_to_json_lines(self, records: List[Dict[str, Any]]) -> str:
        """Export records to JSON Lines format (one JSON object per line)"""
        import json
        lines = [json.dumps(record, default=str) for record in records]
        return '\n'.join(lines)

    # ==================== Error Scenario Generation ====================

    def generate_missing_field_error(self, record: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Create error by removing required field"""
        error_record = record.copy()
        if field_name in error_record:
            del error_record[field_name]
        return error_record

    def generate_invalid_type_error(self, record: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Create error by using wrong data type"""
        error_record = record.copy()
        if field_name in error_record:
            error_record[field_name] = "NOT_A_NUMBER"
        return error_record

    def generate_out_of_range_error(self, record: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Create error by using invalid value"""
        error_record = record.copy()
        if field_name in error_record:
            error_record[field_name] = -999999  # Invalid negative amount
        return error_record

    def generate_error_scenarios(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate records with various error scenarios"""
        record = self.generate_valid_application()

        return {
            'missing_ssn': [self.generate_missing_field_error(record, 'customer_ssn')],
            'invalid_email': [self.generate_invalid_application()],
            'invalid_loan_amount': [self.generate_invalid_application()],
            'invalid_date': [self.generate_invalid_application()],
        }


# ==================== Batch Generator ====================

class BatchDataGenerator:
    """Generates batches of test data for load testing"""

    def __init__(self, factory: TestDataFactory = None):
        self.factory = factory or TestDataFactory()

    def generate_large_batch(self, num_records: int = 10000) -> List[Dict[str, Any]]:
        """Generate large batch for load testing"""
        config = TestDataConfig(num_records=num_records)
        factory = TestDataFactory(config)
        return factory.generate_applications()

    def generate_batch_stream(self, batch_size: int = 100, num_batches: int = 10):
        """Generate batches as a stream"""
        for _ in range(num_batches):
            config = TestDataConfig(num_records=batch_size)
            factory = TestDataFactory(config)
            yield factory.generate_applications()


# ==================== Sample Data Sets ====================

class SampleDataSets:
    """Predefined sample data sets for testing"""

    @staticmethod
    def happy_path_applications() -> List[Dict[str, Any]]:
        """Sample data for happy path testing"""
        factory = TestDataFactory(TestDataConfig(
            num_records=10,
            valid_percentage=1.0,
            error_percentage=0.0,
            duplicate_percentage=0.0
        ))
        return factory.generate_applications()

    @staticmethod
    def validation_error_applications() -> List[Dict[str, Any]]:
        """Sample data with validation errors"""
        factory = TestDataFactory(TestDataConfig(
            num_records=10,
            valid_percentage=0.5,
            error_percentage=0.5,
            duplicate_percentage=0.0
        ))
        return factory.generate_applications()

    @staticmethod
    def duplicate_applications() -> List[Dict[str, Any]]:
        """Sample data with duplicates"""
        factory = TestDataFactory(TestDataConfig(
            num_records=10,
            valid_percentage=0.9,
            error_percentage=0.0,
            duplicate_percentage=0.1
        ))
        return factory.generate_applications()

    @staticmethod
    def edge_case_applications() -> List[Dict[str, Any]]:
        """Sample data with edge cases"""
        factory = TestDataFactory()

        return [
            {
                'application_id': 'APP000001',
                'customer_id': 'CUST000001',
                'customer_name': 'A',  # Minimal name
                'customer_ssn': '000-00-0001',
                'date_of_birth': '1900-01-01',  # Very old
                'email': 'a@b.co',
                'phone': '+441111111111',
                'loan_amount': 5000.01,  # Minimum
                'loan_term_months': 12,
                'application_date': (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
                'application_status': 'PENDING',
                'branch_code': 'BR001',
                'employment_status': 'EMPLOYED',
                'annual_income': 20000.00,
            },
            {
                'application_id': 'APP999999',
                'customer_id': 'CUST999999',
                'customer_name': 'Z' * 50,  # Very long name
                'customer_ssn': '999-99-9999',
                'date_of_birth': datetime.now().strftime('%Y-%m-%d'),  # Today (invalid)
                'email': 'a' * 100 + '@example.com',  # Very long email
                'phone': '+44' + '9' * 10,
                'loan_amount': 499999.99,  # Maximum
                'loan_term_months': 360,
                'application_date': datetime.now().strftime('%Y-%m-%d'),
                'application_status': 'APPROVED',
                'branch_code': 'BR999',
                'employment_status': 'SELF_EMPLOYED',
                'annual_income': 200000.00,
            }
        ]


# ==================== Convenience Functions ====================

def create_test_applications(count: int = 100) -> List[Dict[str, Any]]:
    """Quick helper to create test applications"""
    factory = TestDataFactory(TestDataConfig(num_records=count))
    return factory.generate_applications()


def create_test_csv(count: int = 100, entity_type: str = 'applications') -> str:
    """Quick helper to create test CSV data"""
    factory = TestDataFactory(TestDataConfig(num_records=count))

    if entity_type == 'applications':
        records = factory.generate_applications()
    elif entity_type == 'customers':
        records = factory.generate_customers()
    elif entity_type == 'branches':
        records = factory.generate_branches()
    elif entity_type == 'collateral':
        records = factory.generate_collaterals()
    else:
        raise ValueError(f"Unknown entity type: {entity_type}")

    return factory.export_to_csv(records)

