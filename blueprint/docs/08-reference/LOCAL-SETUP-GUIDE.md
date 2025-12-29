# 🚀 LOCAL SETUP & MIGRATION GUIDE

A complete guide to run the legacy migration locally for learning and development.

---

## 📋 Prerequisites

### macOS Setup
```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install python@3.11 git docker postgresql
brew install --cask docker  # Docker Desktop

# Verify installations
python3 --version           # Should be 3.9+
pip3 --version
git --version
docker --version
```

### GCP Setup (Optional - for cloud components)
```bash
# Install Google Cloud SDK
brew install google-cloud-sdk

# Authenticate
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

---

## 🎯 Quick Start (5 minutes)

### 1. Clone & Setup Environment
```bash
# Navigate to project
cd /path/to/project

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "fastapi|apache-beam|dbt|airflow|google-cloud"
```

### 2. Run Your First Migration Example (COBOL → Python)
```bash
# Study the original COBOL program
cat src/migrations/cobol-to-python/CUSTPROC.cbl

# Study the Python equivalent
cat src/migrations/cobol-to-python/custproc.py

# Run the Python version (local simulation)
python3 src/migrations/cobol-to-python/custproc.py
```

### 3. Start the FastAPI Microservice
```bash
# Install FastAPI dependencies (already in requirements.txt)
cd src/microservices/customer-service

# Run the service locally
python3 -m uvicorn main:app --reload --port 8000

# In another terminal, test it
curl http://localhost:8000/docs  # Interactive API docs
curl -X GET http://localhost:8000/health
```

---

## 📦 Step-by-Step Setup

### Step 1: Python Environment
```bash
cd /path/to/project

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Check it's working
which python3
# Should output: /path/to/project/venv/bin/python3

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### Step 2: Install All Dependencies
```bash
# Install from requirements.txt
pip install -r requirements.txt

# This installs:
# - FastAPI, Flask, Uvicorn (Web frameworks)
# - Apache Beam, Pandas, NumPy (Data processing)
# - dbt-core, dbt-bigquery (Data transformations)
# - Apache Airflow (Orchestration)
# - Google Cloud libraries (GCP integration)

# Verify critical packages
python3 -c "import fastapi; import apache_beam; import dbt; import airflow; print('✅ All packages installed!')"
```

### Step 3: Create Local Data Files
```bash
# Create a local data directory
mkdir -p data/input data/output

# Create sample customer file (fixed-width format, like mainframe)
cat > data/input/customers.txt << 'EOF'
CUST00001John Doe             123 Main Street           San Francisco   CA 94102    415-555-0123john@example.com  PREMIUM   ACTIVE  0000050000
CUST00002Jane Smith           456 Oak Avenue            New York        NY 10001    212-555-0456jane@example.com   STANDARD  ACTIVE  0000075000
CUST00003Bob Johnson          789 Pine Road             Chicago         IL 60601    312-555-0789bob@example.com    PREMIUM   INACTIVE 0000030000
CUST00004Alice Brown          321 Elm Street            Boston          MA 02101    617-555-0321alice@example.com  STANDARD  ACTIVE  0000100000
EOF

echo "✅ Sample data created in data/input/customers.txt"
```

### Step 4: Run COBOL Migration Example (Locally)
```bash
# Create a working directory for the migration
mkdir -p local_migration
cd local_migration

# Copy the migration files
cp ../src/migrations/cobol-to-python/custproc.py .

# Create a local processor that doesn't require GCP
cat > run_migration.py << 'EOF'
"""
Local COBOL to Python Migration Example
Demonstrates the conversion without requiring GCP credentials
"""
from dataclasses import dataclass
from typing import Tuple
from decimal import Decimal
from datetime import datetime
import csv

@dataclass
class CustomerRecord:
    """Customer record structure (replaces COBOL 01 level)"""
    cust_id: str
    cust_name: str
    cust_address: str
    cust_phone: str
    cust_email: str
    cust_type: str
    cust_status: str
    cust_balance: Decimal
    
    @classmethod
    def from_fixed_width(cls, line: str):
        """Parse fixed-width format (like COBOL file)"""
        return cls(
            cust_id=line[0:10].strip(),
            cust_name=line[10:50].strip(),
            cust_address=line[50:100].strip(),
            cust_phone=line[100:120].strip(),
            cust_email=line[120:150].strip(),
            cust_type=line[150:160].strip(),
            cust_status=line[160:170].strip(),
            cust_balance=Decimal(line[170:180].strip() or '0') / 100
        )
    
    def to_dict(self):
        """Convert to dictionary for output"""
        return {
            'customer_id': self.cust_id,
            'customer_name': self.cust_name,
            'address': self.cust_address,
            'phone': self.cust_phone,
            'email': self.cust_email,
            'customer_type': self.cust_type,
            'status': self.cust_status,
            'balance': float(self.cust_balance),
            'processed_at': datetime.utcnow().isoformat()
        }

def validate_record(customer: CustomerRecord) -> Tuple[bool, str]:
    """Validate customer record"""
    if not customer.cust_id:
        return False, "Missing customer ID"
    if not customer.cust_name:
        return False, "Missing customer name"
    if "@" not in customer.cust_email:
        return False, "Invalid email format"
    return True, ""

def process_customers_local(input_file: str, output_file: str):
    """Process customers locally (simulates COBOL program)"""
    records_read = 0
    records_processed = 0
    records_error = 0
    
    print("🚀 Starting Customer Processing (COBOL to Python Migration)")
    print(f"📖 Input file: {input_file}")
    print(f"📝 Output file: {output_file}")
    print("-" * 80)
    
    try:
        with open(input_file, 'r') as infile, \
             open(output_file, 'w', newline='') as outfile:
            
            writer = csv.DictWriter(outfile, fieldnames=[
                'customer_id', 'customer_name', 'address', 'phone',
                'email', 'customer_type', 'status', 'balance', 'processed_at'
            ])
            writer.writeheader()
            
            for line in infile:
                if not line.strip():
                    continue
                    
                records_read += 1
                
                try:
                    # Parse the record (like COBOL READ statement)
                    customer = CustomerRecord.from_fixed_width(line)
                    
                    # Validate (like 2200-VALIDATE-RECORD)
                    is_valid, error_msg = validate_record(customer)
                    
                    if is_valid:
                        # Process customer (like 2300-PROCESS-CUSTOMER)
                        writer.writerow(customer.to_dict())
                        records_processed += 1
                        print(f"✅ Processed: {customer.cust_id} - {customer.cust_name}")
                    else:
                        records_error += 1
                        print(f"❌ Invalid: {customer.cust_id} - {error_msg}")
                
                except Exception as e:
                    records_error += 1
                    print(f"❌ Error processing line {records_read}: {str(e)}")
        
        # Print summary (like 3000-FINALIZE)
        print("-" * 80)
        print(f"📊 PROCESSING COMPLETE")
        print(f"   Records Read:      {records_read}")
        print(f"   Records Processed: {records_processed}")
        print(f"   Records Error:     {records_error}")
        print(f"   Success Rate:      {records_processed/max(records_read, 1)*100:.1f}%")
        
    except FileNotFoundError:
        print(f"❌ Error: Input file not found: {input_file}")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")

if __name__ == "__main__":
    # Process customers
    process_customers_local(
        input_file="../data/input/customers.txt",
        output_file="../data/output/customers_processed.csv"
    )
    
    print("\n✅ Migration complete!")
    print("📁 Output saved to: ../data/output/customers_processed.csv")
EOF

# Run the migration
python3 run_migration.py
cd ..
```

### Step 5: Run FastAPI Microservice
```bash
# Terminal 1: Start the service
cd src/microservices/customer-service
python3 -m uvicorn main:app --reload --port 8000

# Terminal 2: Test the service
curl http://localhost:8000/health

# Open in browser: http://localhost:8000/docs
# You'll see the interactive Swagger API documentation
```

### Step 6: Run Apache Airflow Locally
```bash
# Set Airflow home
export AIRFLOW_HOME=$(pwd)/airflow_local

# Initialize Airflow database
python3 -m airflow db init

# Create an admin user
python3 -m airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin

# Start the webserver (Terminal 1)
python3 -m airflow webserver --port 8080

# Start the scheduler (Terminal 2)
python3 -m airflow scheduler

# Access Airflow UI: http://localhost:8080
# Username: admin
# Password: admin
```

### Step 7: Run dbt Models Locally
```bash
# Install dbt for local development
pip install dbt-core dbt-sqlite  # Use SQLite for local testing

# Navigate to dbt project
cd dbt

# Initialize dbt
dbt debug

# Create a profiles.yml for local SQLite testing
cat > ~/.dbt/profiles.yml << 'EOF'
legacy_migration_reference:
  target: dev
  outputs:
    dev:
      type: sqlite
      path: '/tmp/dbt_local.db'
      schema: analytics
      threads: 4
EOF

# Run dbt models
dbt run

# Test models
dbt test

# Generate documentation
dbt docs generate

# Serve documentation locally
dbt docs serve
# Access at http://localhost:8001
```

---

## 🔄 Complete Local Migration Flow

### Scenario: Migrate a Customer Processing Batch Job

```bash
#!/bin/bash
# run_complete_migration.sh

set -e  # Exit on error

echo "🚀 Starting Complete Local Migration"
echo "=================================="

# Step 1: Prepare environment
echo "1️⃣  Setting up environment..."
source venv/bin/activate

# Step 2: Run COBOL migration
echo "2️⃣  Running COBOL to Python migration..."
cd local_migration
python3 run_migration.py
cd ..

# Step 3: Transform data with dbt
echo "3️⃣  Running dbt transformations..."
cd dbt
dbt run --profiles-dir ~/.dbt
cd ..

# Step 4: Load to local database
echo "4️⃣  Loading processed data..."
python3 << 'PYEOF'
import sqlite3
import csv
from pathlib import Path

conn = sqlite3.connect('/tmp/dbt_local.db')
cursor = conn.cursor()

# Create table if not exists
cursor.execute('''
    CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        customer_name TEXT,
        address TEXT,
        phone TEXT,
        email TEXT,
        customer_type TEXT,
        status TEXT,
        balance REAL,
        processed_at TEXT
    )
''')

# Load data
with open('data/output/customers_processed.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cursor.execute('''
            INSERT OR REPLACE INTO customers
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            row['customer_id'], row['customer_name'], row['address'],
            row['phone'], row['email'], row['customer_type'],
            row['status'], row['balance'], row['processed_at']
        ))

conn.commit()
conn.close()
print("✅ Data loaded to SQLite")
PYEOF

# Step 5: Query results
echo "5️⃣  Querying results..."
python3 << 'PYEOF'
import sqlite3

conn = sqlite3.connect('/tmp/dbt_local.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM customers')
count = cursor.fetchone()[0]
print(f"✅ Total customers in database: {count}")

cursor.execute('SELECT customer_id, customer_name, balance FROM customers LIMIT 5')
print("\n📊 Sample data:")
for row in cursor.fetchall():
    print(f"   {row[0]} | {row[1]:20} | ${row[2]:,.2f}")

conn.close()
PYEOF

echo ""
echo "=================================="
echo "✅ MIGRATION COMPLETE!"
echo "=================================="
```

### Run it:
```bash
chmod +x run_complete_migration.sh
./run_complete_migration.sh
```

---

## 🛠️ Local Development Tools

### FastAPI Service Development
```bash
# Terminal 1: Start service with hot-reload
cd src/microservices/customer-service
python3 -m uvicorn main:app --reload --port 8000

# Terminal 2: Run tests
python3 -m pytest tests/ -v

# Terminal 3: Check code quality
python3 -m pylint main.py
python3 -m black main.py  # Format code
```

### Apache Beam (Dataflow) Locally
```bash
# Run Dataflow pipeline with DirectRunner (local)
python3 src/dataflow/pipelines/customer_etl_pipeline.py \
    --runner DirectRunner \
    --input data/input/customers.txt \
    --output data/output/beam_output
```

### Docker Local Development
```bash
# Build Docker image
docker build -t customer-service:local src/microservices/customer-service/

# Run in container
docker run -p 8000:8000 \
    -e GCP_PROJECT_ID=local \
    -e PORT=8000 \
    customer-service:local

# Access at http://localhost:8000
```

---

## 📊 Local Architecture

```
┌─────────────────────────────────────────────────┐
│         LOCAL DEVELOPMENT ENVIRONMENT           │
├─────────────────────────────────────────────────┤
│                                                 │
│  📁 data/input/                                 │
│  ├── customers.txt (COBOL-like fixed-width)    │
│  └── other_sources/                            │
│                                                 │
│  🔄 Migration Pipeline                         │
│  ├── COBOL→Python (custproc.py)                │
│  ├── Process & Validate                        │
│  └── Output to CSV                             │
│                                                 │
│  📊 Transform with dbt                         │
│  ├── Staging models                            │
│  ├── Mart models                               │
│  └── Analytics models                          │
│                                                 │
│  💾 Local SQLite Database                      │
│  └── /tmp/dbt_local.db                         │
│                                                 │
│  🌐 FastAPI Microservice (Port 8000)          │
│  ├── REST API                                  │
│  ├── Swagger UI (/docs)                        │
│  └── API Schema (/openapi.json)                │
│                                                 │
│  🔄 Apache Airflow (Port 8080)                 │
│  ├── DAG Scheduler                             │
│  ├── Web UI                                    │
│  └── Local Task Execution                      │
│                                                 │
│  📁 data/output/                               │
│  ├── customers_processed.csv                   │
│  └── transformation_results/                   │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 🧪 Testing Locally

### Unit Tests
```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_customer_processor.py -v

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=html
```

### Integration Tests
```bash
# Test full migration flow
python3 -m pytest tests/integration/test_migration_flow.py -v

# Test API endpoints
python3 -m pytest tests/integration/test_api.py -v
```

---

## 🐛 Troubleshooting

### Python Virtual Environment Issues
```bash
# If venv doesn't work, recreate it
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Try different port
python3 -m uvicorn main:app --port 8001
```

### GCP Credentials Issues (when testing cloud features)
```bash
# Set up authentication
gcloud auth application-default login

# Or use service account key
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### Airflow Database Issues
```bash
# Reset Airflow database
rm -rf airflow_local
export AIRFLOW_HOME=$(pwd)/airflow_local
python3 -m airflow db init
```

---

## 📝 Next Steps

1. ✅ **Complete local setup** (you are here)
2. 📖 **Study the migration patterns** in `src/migrations/`
3. 🔄 **Run the complete flow** with the script above
4. 💻 **Modify examples** for your use case
5. 🧪 **Write tests** for your migrations
6. 🚀 **Deploy to GCP** using Terraform (see INFRASTRUCTURE.md)

---

## 🆘 Getting Help

- **Questions about setup?** Check TROUBLESHOOTING.md
- **Migration patterns?** See docs/MIGRATION_GUIDE.md
- **Architecture decisions?** Read docs/ARCHITECTURE.md
- **GCP specifics?** Check docs/GCP-CRASH-COURSE.md

---

**Last Updated**: December 2024
**Status**: ✅ Ready for local development

