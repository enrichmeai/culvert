# 🏗️ MULTI-PLATFORM ARCHITECTURE - Blueprint Reuse Guide

**Document Version:** 1.0  
**Last Updated:** December 21, 2025  
**Audience:** Architects, Platform Engineers

---

## 📋 TABLE OF CONTENTS

1. [Shared Library Components](#shared-library-components)
2. [Multi-Platform Architecture](#multi-platform-architecture)
3. [Integration Patterns](#integration-patterns)
4. [the enterprise platform Setup](#enterprise-platform-setup)
5. [Risk Platform Setup](#risk-platform-setup)
6. [Commercial Platform Setup](#commercial-platform-setup)
7. [Cross-Platform Governance](#cross-platform-governance)
8. [Deployment Patterns](#deployment-patterns)

---

## 📦 SHARED LIBRARY COMPONENTS

### Overview

The LOA Blueprint provides **4 core reusable libraries** designed for multi-platform use:

```
loa_common/
├── error_handling.py       ← Error classification & retry logic
├── monitoring.py           ← Metrics & health monitoring
├── beam_helpers.py         ← Dataflow/Beam utilities
├── data_deletion.py        ← Safe deletion & retention
├── io_utils.py             ← I/O operations
├── schema.py               ← Schema management
├── validation.py           ← Data validation
├── audit.py                ← Audit logging
└── file_management.py      ← File lifecycle management
```

### Core Library Contracts

Each library follows a consistent contract:

```python
# Error handling pattern
from loa_common.error_handling import ErrorHandler

handler = ErrorHandler(
    pipeline_name='your_pipeline',
    run_id='run_identifier'
)

try:
    process_data()
except Exception as e:
    error = handler.handle_exception(e)
    # Automatic categorization, logging, retry logic

# Monitoring pattern
from loa_common.monitoring import ObservabilityManager

obs = ObservabilityManager(
    pipeline_name='your_pipeline',
    run_id='run_identifier'
)

obs.report_records_processed(count=100)
obs.report_records_error(count=5)
health = obs.check_health()
```

### Key Design Principles

1. **Platform Agnostic** - No business logic, pure infrastructure
2. **Configurable** - Environment variables control behavior
3. **Observable** - All operations logged and metered
4. **Resilient** - Built-in retry and error handling
5. **Testable** - Mocked dependencies for unit testing
6. **Reusable** - No cross-dependencies between platforms

---

## 🏗️ MULTI-PLATFORM ARCHITECTURE

### Reference Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  Shared Library Repository                   │
│                   (loa-blueprint.git)                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │             LOA Common Libraries (Phase 1-2)           │ │
│  │  • error_handling.py (550 lines)                       │ │
│  │  • monitoring.py (680 lines)                           │ │
│  │  • beam_helpers.py (650 lines)                         │ │
│  │  • data_deletion.py (520 lines)                        │ │
│  │  • + 5 more utility modules                            │ │
│  │                                                        │ │
│  │  Versioned: 1.0.0, 1.1.0, 2.0.0, ...                  │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ the enterprise platform  │ │ Risk Platform│ │Commercial Platform│
│  Repository      │ │  Repository  │ │   Repository     │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

### Repository Structure for Each Platform

```
enterprise-platform-repo/
├── .gitmodules
├── components/
│   ├── loa_common/                    ← Git submodule to shared
│   │   ├── error_handling.py
│   │   ├── monitoring.py
│   │   └── ...
│   └── domain_specific/
│       ├── domain_scorer.py           ← the enterprise platform code
│       ├── risk_calculator.py
│       ├── approval_engine.py
│       └── compliance_checker.py
├── orchestration/
│   └── airflow/dags/
│       ├── shared_patterns.py         ← Shared DAG utilities
│       ├── domain_scoring_dag.py      ← platform-specific DAGs
│       ├── risk_assessment_dag.py
│       └── compliance_dag.py
├── transformations/
│   └── dbt/
│       ├── models/shared/             ← Common dbt models
│       │   ├── fact_common.sql
│       │   └── dim_entities.sql
│       └── models/credit/             ← platform-specific models
│           ├── fact_applications.sql
│           ├── fact_approvals.sql
│           └── fact_rejections.sql
├── infrastructure/
│   └── terraform/
│       ├── shared/                    ← Shared infrastructure
│       │   ├── main.tf
│       │   └── outputs.tf
│       └── credit/                    ← platform-specific resources
│           ├── datasets.tf
│           ├── tables.tf
│           └── pipelines.tf
└── tests/
    ├── unit/
    ├── integration/
    └── functional/
```

---

## 🔗 INTEGRATION PATTERNS

### Pattern 1: Git Submodule (Recommended for Git-Native Teams)

**Setup:**
```bash
# In platform repository
git submodule add https://github.com/yourorg/loa-blueprint.git blueprint

# Initialize submodule
git submodule update --init --recursive

# Structure
platform-repo/
├── blueprint/
│   └── components/loa_common/    ← Submodule (read-only in platform repo)
└── components/
    └── platform_specific/        ← Your platform code
```

**Usage in Code:**
```python
from loa_common.error_handling import ErrorHandler
from loa_common.monitoring import ObservabilityManager

# Works seamlessly - submodule is on PYTHONPATH
```

**Update Shared Libraries:**
```bash
# Pull latest changes from shared repo
cd blueprint
git pull origin main

# Commit the update in platform repo
cd ..
git add blueprint
git commit -m "Update loa-blueprint to v1.2.0"
```

**Pros:**
- Single source of truth
- Version control integration
- Easy to update
- Atomic commits

**Cons:**
- Requires Git submodule knowledge
- Can be confusing for new developers
- Adds complexity to CI/CD

---

### Pattern 2: PyPI Package (Recommended for Package-Native Teams)

**Setup:**

Create package in shared repository:

```bash
loa-blueprint/
├── setup.py
├── loa_common/
│   ├── __init__.py
│   ├── error_handling.py
│   ├── monitoring.py
│   └── ...
└── requirements.txt

# In setup.py
setup(
    name='loa-common-libraries',
    version='1.2.0',
    packages=['loa_common'],
    install_requires=[
        'google-cloud-storage>=2.0.0',
        'google-cloud-bigquery>=3.0.0',
        # ...
    ]
)
```

**Publish to PyPI or Internal Registry:**
```bash
python -m build
twine upload dist/*
```

**In Platform Repositories:**

```bash
# requirements.txt or pyproject.toml
loa-common-libraries>=1.0.0

# Install
pip install loa-common-libraries

# Usage (same as submodule)
from loa_common.error_handling import ErrorHandler
```

**Pros:**
- Standard Python packaging
- Easy version management
- CI/CD friendly
- Works with any package manager

**Cons:**
- Decouples from Git
- Need package registry
- Version alignment responsibility

---

### Pattern 3: Docker Base Image (Recommended for Container-Native Teams)

**Create Shared Base Image:**

```dockerfile
# loa-blueprint/Dockerfile.base
FROM python:3.9-slim

WORKDIR /app

# Copy shared libraries
COPY loa_common/ /usr/local/lib/python3.9/site-packages/loa_common/

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Make libraries available
ENV PYTHONPATH="/usr/local/lib/python3.9/site-packages:${PYTHONPATH}"

# Tag: gcr.io/yourproject/loa-base:1.2.0
```

**Build and Push:**
```bash
docker build -t gcr.io/yourproject/loa-base:1.2.0 -f Dockerfile.base .
docker push gcr.io/yourproject/loa-base:1.2.0
```

**Use in Platform Repositories:**

```dockerfile
# enterprise-platform/Dockerfile
FROM gcr.io/yourproject/loa-base:1.2.0

# Your platform code
COPY components/domain_specific /app/components/domain_specific
COPY orchestration /app/orchestration
COPY transformations /app/transformations

CMD ["python", "-m", "enterprise_platform.main"]
```

**Pros:**
- Encapsulates all dependencies
- Consistent across environments
- Supports multiple container registries
- Easy to distribute

**Cons:**
- Docker requirement
- Image size management
- Registry infrastructure needed

---

## 💳 ENTERPRISE PLATFORM SETUP

### Platform-Specific Components

```
the enterprise platform has:
├── Domain Scoring Engine
│   ├── FICO score calculation
│   ├── DTI ratio calculation
│   ├── Payment history analysis
│   └── Credit limit assignment
├── Approval Workflow
│   ├── Automatic approval/decline
│   ├── Manual review queue
│   ├── Compliance checks (ECOA, FHA, etc.)
│   └── Documentation generation
├── Risk Assessment
│   ├── Portfolio risk calculation
│   ├── Loss forecasting
│   ├── Stress testing
│   └── Concentration risk analysis
└── Reporting
    ├── Consumer reports
    ├── Regulatory reports
    ├── Performance analytics
    └── Dashboard generation
```

### Using Shared Libraries in the enterprise platform

**Example: Domain Scoring Pipeline**

```python
# enterprise-platform/components/domain_specific/domain_scorer.py

from loa_common.error_handling import ErrorHandler, ErrorCategory
from loa_common.monitoring import ObservabilityManager
from loa_common.beam_helpers import ReadFromGCS, WriteToBQ, ValidateRecord
import apache_beam as beam

class CreditScoringTransform(beam.DoFn):
    def __init__(self, run_id):
        self.run_id = run_id
        self.error_handler = ErrorHandler(
            pipeline_name='domain_scoring',
            run_id=run_id
        )
        self.obs = ObservabilityManager(
            pipeline_name='domain_scoring',
            run_id=run_id
        )
    
    def process(self, application):
        try:
            # Validate using shared validator
            ValidateRecord(
                required_fields=['applicant_id', 'income', 'credit_history']
            ).process(application)
            
            # platform-specific scoring logic
            credit_score = self._calculate_fico_score(application)
            dti_ratio = self._calculate_dti(application)
            credit_limit = self._assign_credit_limit(credit_score, dti_ratio)
            
            result = {
                'applicant_id': application['applicant_id'],
                'credit_score': credit_score,
                'dti_ratio': dti_ratio,
                'credit_limit': credit_limit,
                'approval_status': self._determine_approval(credit_score, dti_ratio),
                'processed_at': datetime.utcnow().isoformat()
            }
            
            self.obs.report_records_processed(count=1)
            yield result
            
        except Exception as e:
            error = self.error_handler.handle_exception(
                e,
                source_file=application.get('source_file'),
                record_id=application.get('applicant_id'),
                category=ErrorCategory.VALIDATION
            )
            self.obs.report_records_error(count=1)
    
    def _calculate_fico_score(self, application):
        # platform-specific implementation
        return calculate_credit_score(application)
    
    def _calculate_dti(self, application):
        # platform-specific implementation
        return calculate_dti_ratio(application)
    
    def _assign_credit_limit(self, score, dti):
        # platform-specific implementation
        return determine_credit_limit(score, dti)
    
    def _determine_approval(self, score, dti):
        # platform-specific implementation
        if score >= 720 and dti < 0.43:
            return 'APPROVED'
        elif score >= 640 and dti < 0.50:
            return 'MANUAL_REVIEW'
        else:
            return 'DECLINED'

# Pipeline definition
def run_domain_scoring_pipeline(project_id, run_id):
    options = beam.options.pipeline_options.PipelineOptions(
        project=project_id,
        runner='DataflowRunner'
    )
    
    with beam.Pipeline(options=options) as p:
        (p
         | 'ReadApplications' >> ReadFromGCS(
             'gs://credit-bucket/applications/*.csv'
         )
         | 'ValidateApplications' >> beam.ParDo(ValidateRecord(
             required_fields=['applicant_id', 'income', 'credit_history']
         ))
         | 'ScoreApplications' >> beam.ParDo(CreditScoringTransform(run_id))
         | 'WriteResults' >> WriteToBQ(
             'credit-project.credit_dataset.applications_scored'
         ))
```

**Example: the enterprise platform DAG**

```python
# enterprise-platform/orchestration/airflow/dags/domain_scoring_dag.py

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from loa_common.monitoring import ObservabilityManager
from loa_common.error_handling import ErrorHandler

default_args = {
    'owner': 'credit_team',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': ['credit-alerts@company.com']
}

dag = DAG(
    'domain_scoring_pipeline',
    default_args=default_args,
    description='Daily credit application scoring',
    schedule_interval='0 2 * * *',  # 2 AM daily
    start_date=datetime(2025, 1, 1),
    catchup=False
)

def validate_input_files(**context):
    run_id = context['run_id']
    obs = ObservabilityManager(
        pipeline_name='domain_scoring',
        run_id=run_id
    )
    # Validation logic using shared library
    return True

def run_scoring_pipeline(**context):
    run_id = context['run_id']
    # Uses the CreditScoringTransform defined above
    pass

def generate_reports(**context):
    run_id = context['run_id']
    error_handler = ErrorHandler(
        pipeline_name='domain_scoring',
        run_id=run_id
    )
    # Report generation logic
    pass

validate_task = PythonOperator(
    task_id='validate_input_files',
    python_callable=validate_input_files,
    dag=dag
)

scoring_task = BashOperator(
    task_id='run_scoring_pipeline',
    bash_command='python -m enterprise_platform.pipelines.scoring {{ run_id }}',
    dag=dag
)

reports_task = PythonOperator(
    task_id='generate_reports',
    python_callable=generate_reports,
    dag=dag
)

validate_task >> scoring_task >> reports_task
```

---

## ⚠️ RISK PLATFORM SETUP

### Platform-Specific Components

```
Risk Platform has:
├── Risk Assessment Engine
│   ├── Market risk calculation (VaR, ES)
│   ├── Credit risk assessment
│   ├── Liquidity risk analysis
│   └── Operational risk evaluation
├── Portfolio Analytics
│   ├── Asset correlation analysis
│   ├── Concentration risk
│   ├── Exposure reporting
│   └── Stress testing
├── Compliance & Reporting
│   ├── Regulatory report generation
│   ├── Basel III compliance
│   ├── Risk limit monitoring
│   └── Alert generation
└── Data Integration
    ├── Market data feeds
    ├── Trade data integration
    ├── Reference data management
    └── Risk factor updates
```

### Using Shared Libraries in Risk Platform

**Example: Risk Assessment Pipeline**

```python
# risk-platform/components/risk_specific/risk_assessor.py

from loa_common.error_handling import ErrorHandler, ErrorSeverity
from loa_common.monitoring import ObservabilityManager
from loa_common.beam_helpers import ReadFromGCS, WriteToBQ
import apache_beam as beam
import numpy as np
from datetime import datetime

class RiskAssessmentTransform(beam.DoFn):
    def __init__(self, run_id):
        self.run_id = run_id
        self.error_handler = ErrorHandler(
            pipeline_name='risk_assessment',
            run_id=run_id
        )
        self.obs = ObservabilityManager(
            pipeline_name='risk_assessment',
            run_id=run_id
        )
    
    def process(self, portfolio_item):
        try:
            # Risk-specific calculations
            var_95 = self._calculate_var(portfolio_item, confidence=0.95)
            var_99 = self._calculate_var(portfolio_item, confidence=0.99)
            expected_shortfall = self._calculate_es(portfolio_item)
            
            # Check risk limits
            risk_alert = self._check_risk_limits(var_95, expected_shortfall)
            
            result = {
                'portfolio_id': portfolio_item['portfolio_id'],
                'asset_id': portfolio_item['asset_id'],
                'var_95': float(var_95),
                'var_99': float(var_99),
                'expected_shortfall': float(expected_shortfall),
                'risk_alert': risk_alert,
                'assessed_at': datetime.utcnow().isoformat()
            }
            
            self.obs.report_records_processed(count=1)
            
            if risk_alert:
                self.error_handler.handle_exception(
                    Exception(f"Risk limit exceeded: {risk_alert}"),
                    category=ErrorSeverity.HIGH
                )
            
            yield result
            
        except Exception as e:
            self.error_handler.handle_exception(
                e,
                source_file=portfolio_item.get('source_file'),
                record_id=portfolio_item.get('asset_id')
            )
            self.obs.report_records_error(count=1)
    
    def _calculate_var(self, portfolio_item, confidence=0.95):
        # Risk-specific VaR calculation
        returns = np.array(portfolio_item['historical_returns'])
        return np.percentile(returns, (1 - confidence) * 100)
    
    def _calculate_es(self, portfolio_item):
        # Risk-specific Expected Shortfall calculation
        var = self._calculate_var(portfolio_item, confidence=0.95)
        returns = np.array(portfolio_item['historical_returns'])
        return returns[returns <= var].mean()
    
    def _check_risk_limits(self, var, es):
        # Risk-specific limit checking
        alerts = []
        if var > 0.05:  # 5% daily loss limit
            alerts.append(f"VAR limit exceeded: {var}")
        if es > 0.08:   # 8% expected shortfall limit
            alerts.append(f"ES limit exceeded: {es}")
        return ' | '.join(alerts) if alerts else None
```

---

## 🛍️ COMMERCIAL PLATFORM SETUP

### Platform-Specific Components

```
Commercial Platform has:
├── Product Management
│   ├── Catalog management
│   ├── Pricing engine
│   ├── Promotion management
│   └── Inventory tracking
├── Revenue Optimization
│   ├── Dynamic pricing
│   ├── Promotion effectiveness
│   ├── Customer segmentation
│   └── Revenue forecasting
├── Customer Analytics
│   ├── Purchase behavior
│   ├── Churn prediction
│   ├── Customer lifetime value
│   └── Recommendation engine
└── Reporting
    ├── Sales reports
    ├── Revenue analytics
    ├── Product performance
    └── Marketing effectiveness
```

### Using Shared Libraries in Commercial Platform

```python
# commercial-platform/components/commercial_specific/pricing_engine.py

from loa_common.error_handling import ErrorHandler
from loa_common.monitoring import ObservabilityManager
from loa_common.beam_helpers import ReadFromGCS, WriteToBQ
import apache_beam as beam

class PricingTransform(beam.DoFn):
    def __init__(self, run_id):
        self.run_id = run_id
        self.error_handler = ErrorHandler(
            pipeline_name='dynamic_pricing',
            run_id=run_id
        )
        self.obs = ObservabilityManager(
            pipeline_name='dynamic_pricing',
            run_id=run_id
        )
    
    def process(self, product):
        try:
            # Commercial-specific pricing logic
            base_price = product['base_price']
            demand_factor = self._calculate_demand_factor(product)
            inventory_factor = self._calculate_inventory_factor(product)
            seasonal_factor = self._calculate_seasonal_factor(product)
            
            dynamic_price = base_price * demand_factor * inventory_factor * seasonal_factor
            recommended_price = self._round_price(dynamic_price)
            
            result = {
                'product_id': product['product_id'],
                'base_price': base_price,
                'dynamic_price': float(dynamic_price),
                'recommended_price': recommended_price,
                'margin': (recommended_price - product['cost']) / recommended_price,
                'calculated_at': datetime.utcnow().isoformat()
            }
            
            self.obs.report_records_processed(count=1)
            yield result
            
        except Exception as e:
            self.error_handler.handle_exception(
                e,
                source_file=product.get('source_file'),
                record_id=product.get('product_id')
            )
            self.obs.report_records_error(count=1)
    
    def _calculate_demand_factor(self, product):
        # Commercial-specific demand calculation
        pass
    
    def _calculate_inventory_factor(self, product):
        # Commercial-specific inventory calculation
        pass
    
    def _calculate_seasonal_factor(self, product):
        # Commercial-specific seasonal calculation
        pass
    
    def _round_price(self, price):
        # Price rounding to standard increments
        pass
```

---

## 🏛️ CROSS-PLATFORM GOVERNANCE

### Version Management

```
loa-blueprint/
├── VERSION: 1.2.0
├── CHANGELOG.md
│   v1.2.0 (Dec 21, 2025)
│   - Added file_management module
│   - Improved error categorization
│   - Enhanced monitoring metrics
│
│   v1.1.0 (Nov 15, 2025)
│   - Added data_deletion module
│   - Improved BigQuery integration
│
│   v1.0.0 (Oct 1, 2025)
│   - Initial release
└── compatibility.txt
    v1.2.0: Compatible with credit, risk, commercial platforms
    v1.1.0: Compatible with credit, risk platforms
    v1.0.0: Compatible with the enterprise platform only
```

### Update Strategy

```
Quarterly Update Cycle:
├── December: v1.0 → v1.1
├── March:    v1.1 → v1.2 (with file_management)
├── June:     v1.2 → v2.0 (major release with breaking changes)
└── September: v2.0 → v2.1 (patch release)

Platform Update Policy:
├── Major versions: 2-week evaluation period before upgrade
├── Minor versions: Automatic upgrade with CI/CD
└── Patch versions: Auto-upgrade immediately
```

### Compatibility Matrix

| Platform | v1.0.0 | v1.1.0 | v1.2.0 | v2.0.0 |
|----------|--------|--------|--------|--------|
| Credit   | ✅     | ✅     | ✅     | 📅     |
| Risk     | ✅     | ✅     | ✅     | 📅     |
| Commercial| ❌     | ✅     | ✅     | 📅     |

---

## 🚀 DEPLOYMENT PATTERNS

### Shared Library Deployment

**Via Git Submodule:**
```bash
# In each platform CI/CD
git submodule update --remote
git commit -m "Update loa-blueprint to latest"

# Version is implicit in commit SHA
```

**Via PyPI:**
```bash
# requirements.txt specifies version
loa-common-libraries>=1.2.0,<2.0.0

# During deployment
pip install -r requirements.txt
# Installs specific version based on constraints
```

**Via Docker:**
```bash
# docker-compose.yml
services:
  enterprise_platform:
    image: gcr.io/yourproject/enterprise-platform:1.0.0
    # This image already includes loa-base:1.2.0
```

---

## 📊 SUMMARY

### Reusable Components Across Platforms

| Component | Lines | Reuse | Credit | Risk | Commercial |
|-----------|-------|-------|--------|------|------------|
| error_handling.py | 550 | 100% | ✅ | ✅ | ✅ |
| monitoring.py | 680 | 100% | ✅ | ✅ | ✅ |
| beam_helpers.py | 650 | 100% | ✅ | ✅ | ✅ |
| data_deletion.py | 520 | 100% | ✅ | ✅ | ✅ |
| file_management.py | 748 | 100% | ✅ | ✅ | ✅ |

### Total Reusable Code

- **Core Libraries:** 3,748 lines
- **Reuse Factor:** 5-7 platforms can leverage
- **Time Saved Per Platform:** ~2-3 weeks
- **Quality Improvement:** Consistent patterns, reduced defects

---

**Document Version:** 1.0  
**Next Review:** March 2026  
**Maintained by:** Architecture Team

