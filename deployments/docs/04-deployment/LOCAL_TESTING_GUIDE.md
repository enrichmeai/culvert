# 🧪 LOCAL TESTING GUIDE - LOA Blueprint

**Version:** 1.0  
**Last Updated:** December 21, 2025  
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [System Requirements](#system-requirements)
3. [Setup & Installation](#setup--installation)
4. [Running Tests](#running-tests)
5. [Service Emulators](#service-emulators)
6. [Test Data Management](#test-data-management)
7. [Debugging & Troubleshooting](#debugging--troubleshooting)
8. [Best Practices](#best-practices)

---

## 🚀 Quick Start

### Get Up & Running in 5 Minutes

```bash
# 1. Start Docker services
cd blueprint/setup
docker-compose up -d

# 2. Wait for services to be ready (check health)
docker-compose ps

# 3. Run all tests
cd ..
./testing/run_tests.sh

# 4. View coverage report
pytest tests/local/test_local_pipeline.py --cov=loa_common --cov-report=html
open htmlcov/index.html
```

**That's it!** Your local pipeline is running. ✅

---

## 💻 System Requirements

### Minimum Requirements
- **Docker & Docker Compose:** Latest version (2.0+)
- **Python:** 3.8 or higher
- **Memory:** 4GB available RAM
- **Disk Space:** 2GB free (for containers and volumes)

### Recommended Setup
- **OS:** macOS, Linux, or Windows (WSL2)
- **Memory:** 8GB or more
- **CPU:** 4 cores or more
- **Python:** 3.9 or 3.10

### Installation Check

```bash
# Check Docker
docker --version
docker-compose --version

# Check Python
python --version
python -m pip --version

# Should output:
# Docker version 20.x or higher
# Docker Compose version 2.x or higher
# Python 3.8.x or higher
```

---

## 🔧 Setup & Installation

### Step 1: Install Docker

**macOS (using Homebrew):**
```bash
brew install docker docker-compose
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install docker.io docker-compose
sudo usermod -aG docker $USER
```

**Windows (WSL2):**
```bash
# Install Docker Desktop for Windows
# https://www.docker.com/products/docker-desktop
```

### Step 2: Clone Blueprint Repository

```bash
# Navigate to your projects folder
cd ~/projects/jsr/legacy-migration-reference/blueprint

# Verify structure
ls setup/
# Should show: docker-compose.yml, setup_airflow.sh
```

### Step 3: Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Should install:
# - pytest (testing)
# - pytest-cov (coverage)
# - pytest-mock (mocking)
# - google-cloud-bigquery-emulator
# - google-cloud-pubsub
# - google-cloud-storage
# - faker (test data)
```

### Step 4: Start Docker Services

```bash
# Navigate to test folder
cd blueprint/components/tests/local

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# Should show 5 services:
# - bigquery-emulator (healthy)
# - pubsub-emulator (healthy)
# - minio (healthy)
# - postgres (healthy)
# - redis (healthy)

# Watch startup logs
docker-compose logs -f

# Wait for "healthy" status on all services
```

### Step 5: Verify Setup

```bash
# Test BigQuery connection
python -c "
import os
os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'
from google.cloud import bigquery
client = bigquery.Client(project='test-project')
print('BigQuery: OK')
"

# Test Pub/Sub connection
python -c "
import os
os.environ['PUBSUB_EMULATOR_HOST'] = 'localhost:8085'
from google.cloud import pubsub_v1
client = pubsub_v1.PublisherClient()
print('Pub/Sub: OK')
"

# Test MinIO/GCS connection
python -c "
import boto3
s3 = boto3.client('s3', endpoint_url='http://localhost:9000', 
                   aws_access_key_id='minioadmin', 
                   aws_secret_access_key='minioadmin')
print('MinIO/GCS: OK')
"
```

---

## 🧪 Running Tests

### Run All Tests

```bash
# Navigate to blueprint root
cd blueprint

# Run all local tests with verbose output
pytest components/tests/local/test_local_pipeline.py -v

# Should show:
# test_local_pipeline.py::TestLocalPipelineSetup::test_mock_gcs_client_creation PASSED
# test_local_pipeline.py::TestLocalDataValidation::test_validate_csv_format_success PASSED
# ... [20+ more tests]
# ===================== 20 passed in 1.23s =====================
```

### Run Specific Test Class

```bash
# Run just pipeline setup tests
pytest components/tests/local/test_local_pipeline.py::TestLocalPipelineSetup -v

# Run just data transformation tests
pytest components/tests/local/test_local_pipeline.py::TestLocalDataTransformation -v

# Run just integration tests
pytest components/tests/local/test_local_pipeline.py::TestLocalPipelineIntegration -v
```

### Run Specific Test

```bash
# Run one specific test
pytest components/tests/local/test_local_pipeline.py::TestLocalPipelineIntegration::test_full_pipeline_flow -v

# Run with extra debugging
pytest components/tests/local/test_local_pipeline.py::TestLocalPipelineIntegration::test_full_pipeline_flow -vv -s
```

### Run with Coverage Report

```bash
# Generate coverage report
pytest components/tests/local/test_local_pipeline.py \
  --cov=loa_common \
  --cov=loa_pipelines \
  --cov-report=html \
  --cov-report=term-missing

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov\index.html  # Windows
```

### Run with Performance Metrics

```bash
# Show slowest tests
pytest components/tests/local/test_local_pipeline.py --durations=10

# Run tests in parallel (requires pytest-xdist)
pytest components/tests/local/test_local_pipeline.py -n auto
```

---

## 🖥️ Service Emulators

### BigQuery Emulator

**Port:** 9050  
**Project:** test-project  
**Dataset:** raw

**Connection Details:**

```python
import os
from google.cloud import bigquery

# Set emulator host
os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'

# Create client (uses emulator)
client = bigquery.Client(project='test-project')

# List datasets
for dataset in client.list_datasets():
    print(f"Dataset: {dataset.dataset_id}")

# Create table
table_id = 'test-project.raw.applications_raw'
schema = [
    bigquery.SchemaField("application_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("ssn", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("loan_amount", "INTEGER", mode="REQUIRED"),
]
table = bigquery.Table(table_id, schema=schema)
table = client.create_table(table)
print(f"Created table {table.project}.{table.dataset_id}.{table.table_id}")

# Insert data
rows_to_insert = [
    {"application_id": "APP001", "ssn": "123-45-6789", "loan_amount": 250000},
]
errors = client.insert_rows_json(table_id, rows_to_insert)
print(f"Inserted {len(rows_to_insert)} rows")
```

### Pub/Sub Emulator

**Port:** 8085  
**Project:** test-project

**Connection Details:**

```python
import os
from google.cloud import pubsub_v1

# Set emulator host
os.environ['PUBSUB_EMULATOR_HOST'] = 'localhost:8085'

# Create publisher
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path('test-project', 'test-topic')

# Create topic
topic = publisher.create_topic(request={"name": topic_path})
print(f"Created topic: {topic.name}")

# Publish message
message_data = b"Test message"
future = publisher.publish(topic_path, message_data)
print(f"Published message: {future.result()}")

# Create subscriber
subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path('test-project', 'test-sub')
subscription = subscriber.create_subscription(
    request={"name": subscription_path, "topic": topic_path}
)
print(f"Created subscription: {subscription.name}")
```

### MinIO (GCS Mock)

**Port:** 9000 (S3 API), 9001 (Console)  
**Access Key:** minioadmin  
**Secret Key:** minioadmin

**Web Console:**
- URL: http://localhost:9001
- Username: minioadmin
- Password: minioadmin

**Connection Details:**

```python
import boto3

# Create S3 client (using MinIO)
s3 = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin',
    region_name='us-east-1'
)

# Create bucket
s3.create_bucket(Bucket='loa-input')
print("Created bucket: loa-input")

# Upload file
with open('test.csv', 'rb') as f:
    s3.upload_fileobj(f, 'loa-input', 'test.csv')
print("Uploaded test.csv")

# List objects
response = s3.list_objects_v2(Bucket='loa-input')
for obj in response.get('Contents', []):
    print(f"Object: {obj['Key']}")

# Download file
s3.download_file('loa-input', 'test.csv', 'downloaded.csv')
print("Downloaded test.csv")
```

---

## 📊 Test Data Management

### Using Factory Pattern

```python
from tests.fixtures.test_data_factory import ApplicationFactory

# Create factory
factory = ApplicationFactory()

# Generate single record
app = factory.create_single()

# Generate batch of 100 records
apps = factory.create_batch(100)

# Generate with specific values
app = (factory
    .with_ssn("999-99-9999")
    .with_loan_amount(500000)
    .create_single())
```

### Load Test Data to BigQuery

```python
import csv
from google.cloud import bigquery
import os

os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'

# Create client
client = bigquery.Client(project='test-project')

# Load CSV to BigQuery
job_config = bigquery.LoadJobConfig(
    skip_leading_rows=1,
    autodetect=True,
)

with open('test_data.csv', 'rb') as f:
    load_job = client.load_table_from_file(
        f,
        'test-project.raw.test_table',
        job_config=job_config,
    )

load_job.result()
print(f"Loaded {load_job.output_rows} rows")
```

### Generate Sample CSV Files

```bash
# Create sample applications CSV
cat > blueprint/components/tests/local/sample_applications.csv << 'EOF'
application_id,ssn,loan_amount,application_date,branch_code
APP001,123-45-6789,250000,2025-01-15,BRANCH001
APP002,234-56-7890,500000,2025-01-16,BRANCH002
APP003,345-67-8901,750000,2025-01-17,BRANCH001
EOF

# Create sample customers CSV
cat > blueprint/components/tests/local/sample_customers.csv << 'EOF'
customer_id,ssn,email,phone,credit_score,branch_code
CUST001,123-45-6789,john@example.com,555-0001,750,BRANCH001
CUST002,234-56-7890,jane@example.com,555-0002,800,BRANCH002
CUST003,345-67-8901,bob@example.com,555-0003,650,BRANCH001
EOF
```

---

## 🐛 Debugging & Troubleshooting

### Common Issues

#### Issue: "Connection refused" on BigQuery

```
Error: Failed to establish a new connection
Reason: Emulator not running
Solution:
  docker-compose ps  # Check status
  docker-compose logs bigquery-emulator  # View logs
  docker-compose up -d bigquery-emulator  # Restart
```

#### Issue: "Cannot connect to Pub/Sub"

```
Error: PUBSUB_EMULATOR_HOST not set
Solution:
  export PUBSUB_EMULATOR_HOST=localhost:8085
  pytest tests/local/test_local_pipeline.py
```

#### Issue: "MinIO credentials invalid"

```
Error: Invalid access key id
Solution:
  Check credentials in docker-compose.yml
  Access key: minioadmin
  Secret key: minioadmin
  Update your code with correct credentials
```

#### Issue: "Port already in use"

```
Error: Port 9050 already in use
Solution:
  # Find process using port
  lsof -i :9050  # macOS/Linux
  netstat -ano | findstr :9050  # Windows
  
  # Kill process or stop other services
  docker-compose down
  # Or use different port in docker-compose.yml
```

### Debugging Tips

#### Enable Debug Logging

```python
import logging

# Set debug logging
logging.basicConfig(level=logging.DEBUG)

# Run with debug output
pytest tests/local/test_local_pipeline.py -vv -s
```

#### Check Service Logs

```bash
# View all logs
docker-compose logs

# View specific service
docker-compose logs bigquery-emulator

# Follow logs in real-time
docker-compose logs -f pubsub-emulator

# View last 100 lines
docker-compose logs --tail=100
```

#### Interactive Shell in Container

```bash
# Open shell in BigQuery container
docker-compose exec bigquery-emulator bash

# Open shell in MinIO container
docker-compose exec minio bash
```

#### Check Service Health

```bash
# Check health status
docker-compose ps

# Test BigQuery connectivity
docker-compose exec bigquery-emulator curl localhost:9050

# Test Pub/Sub connectivity
docker-compose exec pubsub-emulator curl localhost:8085
```

---

## 📚 Best Practices

### ✅ DO

1. **Isolate Tests**
   ```python
   # Use fixtures to isolate state
   @pytest.fixture
   def clean_database():
       # Setup
       yield
       # Teardown
   ```

2. **Use Mocks for External Services**
   ```python
   # Mock GCS calls in unit tests
   with patch('google.cloud.storage.Client'):
       # Test without real GCS
   ```

3. **Test Both Happy Path & Errors**
   ```python
   # Test success
   def test_valid_record():
       # Process valid data
   
   # Test errors
   def test_invalid_record():
       # Process invalid data
   ```

4. **Keep Tests Fast**
   ```bash
   # Tests should complete in < 1 second each
   pytest tests/local/ --durations=10
   ```

5. **Use Descriptive Names**
   ```python
   def test_pipeline_loads_application_records_to_bigquery():
       # Clear what is being tested
   ```

### ❌ DON'T

1. **Don't make real GCP calls** - Use emulators
2. **Don't create test files manually** - Use factories
3. **Don't skip error cases** - Test both paths
4. **Don't leave containers running** - `docker-compose down`
5. **Don't commit sensitive data** - Use environment variables

---

## ✅ Verification Checklist

Before considering local testing setup complete:

- [ ] Docker and Docker Compose installed
- [ ] Python 3.8+ with venv created
- [ ] All dependencies installed (`pip install -r requirements-dev.txt`)
- [ ] `docker-compose up -d` successful
- [ ] All 5 services showing as "healthy"
- [ ] `pytest tests/local/test_local_pipeline.py` passes
- [ ] Coverage report shows > 95%
- [ ] No external GCP calls made

---

## 📞 Support & Resources

### Useful Commands Reference

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View status
docker-compose ps

# View logs
docker-compose logs -f [service]

# Run tests
pytest tests/local/ -v

# Generate coverage
pytest tests/local/ --cov=loa_common --cov-report=html

# Clean up volumes
docker-compose down -v
```

### Documentation Links

- [Google Cloud BigQuery Emulator](https://github.com/goccy/bigquery-emulator)
- [Google Cloud Pub/Sub Emulator](https://cloud.google.com/pubsub/docs/emulator)
- [MinIO Documentation](https://docs.min.io/)
- [pytest Documentation](https://docs.pytest.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

## 🎯 Next Steps

After setting up local testing:

1. ✅ Run the test suite: `pytest tests/local/test_local_pipeline.py`
2. ✅ Review coverage: `open htmlcov/index.html`
3. ✅ Write your own tests using the patterns
4. ✅ Test your code locally before GCP deployment

---

**Status:** ✅ Local Testing Ready!

Your LOA Blueprint can now be tested entirely locally without any GCP dependencies. 🚀

