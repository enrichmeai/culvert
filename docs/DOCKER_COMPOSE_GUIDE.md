# 🐳 Docker Compose Complete Local Testing Guide

**Version:** 1.0  
**Date:** December 21, 2025  
**Purpose:** Complete local testing environment with Airflow, PostgreSQL, and pytest  
**Status:** ✅ PRODUCTION-READY  

---

## 📋 TABLE OF CONTENTS

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Services](#services)
4. [Usage Commands](#usage-commands)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Usage](#advanced-usage)

---

## 📖 OVERVIEW

### What This Provides

**Complete Local Testing Environment:**
- ✅ Airflow webserver with scheduler
- ✅ PostgreSQL database (Airflow metadata)
- ✅ Redis cache
- ✅ Pytest test runner
- ✅ GCP Emulators (BigQuery, Pub/Sub)
- ✅ JupyterLab (optional)

### Key Features

- **No Airflow Services Needed:** Everything runs in Docker
- **PostgreSQL Metadata:** Professional setup (not SQLite)
- **Integrated Testing:** Run pytest in same environment
- **GCP Emulation:** Test BigQuery and Pub/Sub locally
- **Volume Mounts:** Live code editing
- **Health Checks:** Automatic service monitoring
- **Environment Variables:** Full configuration flexibility

### System Requirements

```bash
# Check requirements
docker --version              # Docker 20.10+
docker-compose --version      # 2.0+
docker ps                      # Can run containers
```

---

## 🚀 QUICK START

### 1. Start All Services

```bash
cd blueprint
docker-compose up -d
```

**Expected Output:**
```
Creating generic-airflow-db        ... done
Creating generic-redis             ... done
Creating generic-airflow-webserver ... done
Creating generic-airflow-scheduler ... done
Creating generic-test-runner       ... done
Creating generic-bigquery-emulator ... done
Creating generic-pubsub-emulator   ... done
```

### 2. Verify Services

```bash
docker-compose ps
```

**Expected Output:**
```
NAME                         STATUS              PORTS
generic-airflow-db              Up (healthy)        0.0.0.0:5432->5432/tcp
generic-airflow-webserver       Up (healthy)        0.0.0.0:8080->8080/tcp
generic-airflow-scheduler       Up (healthy)        (no ports)
generic-redis                   Up (healthy)        0.0.0.0:6379->6379/tcp
generic-test-runner             Up (healthy)        (no ports)
generic-bigquery-emulator       Up (healthy)        0.0.0.0:9050->9050/tcp
                                                0.0.0.0:9060->9060/tcp
generic-pubsub-emulator         Up (healthy)        0.0.0.0:8085->8085/tcp
generic-jupyter                 Up (healthy)        0.0.0.0:8888->8888/tcp
```

### 3. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | http://localhost:8080 | admin / admin |
| JupyterLab | http://localhost:8888 | No password |
| PostgreSQL | localhost:5432 | airflow / airflow |
| Redis | localhost:6379 | No auth |

### 4. Run Tests

```bash
# Run all tests
docker-compose run test-runner

# Run specific test
docker-compose run test-runner pytest src/tests/unit/test_validation.py -v

# Run with coverage
docker-compose run test-runner pytest src/tests/ --cov=components.generic_common --cov-report=html
```

### 5. Stop Services

```bash
docker-compose down
```

---

## 🔧 SERVICES

### Database Layer

#### airflow-db (PostgreSQL)
```yaml
Container: generic-airflow-db
Image: postgres:15-alpine
Port: 5432:5432
Database: airflow
User: airflow / Password: airflow
```

**Usage:**
```bash
# Connect with psql
docker exec -it generic-airflow-db psql -U airflow -d airflow

# View logs
docker-compose logs airflow-db
```

#### redis
```yaml
Container: generic-redis
Image: redis:7-alpine
Port: 6379:6379
```

**Usage:**
```bash
# Connect with redis-cli
docker exec -it generic-redis redis-cli

# Check info
docker exec -it generic-redis redis-cli INFO
```

### Airflow Services

#### airflow-webserver
```yaml
Container: generic-airflow-webserver
Port: 8080:8080
UI: http://localhost:8080
Depends on: airflow-db, redis
```

**Features:**
- Web UI for DAG management
- Manual DAG triggering
- Task monitoring
- Logs viewer

**Usage:**
```bash
# View logs
docker-compose logs airflow-webserver

# Restart
docker-compose restart airflow-webserver

# Execute command in container
docker exec generic-airflow-webserver airflow dags list
```

#### airflow-scheduler
```yaml
Container: generic-airflow-scheduler
Background: No exposed port
Depends on: airflow-db, airflow-webserver, redis
```

**Features:**
- Automated DAG scheduling
- Task triggering
- Dependency management

**Usage:**
```bash
# View logs
docker-compose logs -f airflow-scheduler

# Check status
docker exec generic-airflow-scheduler ps aux | grep scheduler
```

### Testing Service

#### test-runner
```yaml
Container: generic-test-runner
Type: On-demand
Runs: pytest
```

**Usage:**
```bash
# Run all tests
docker-compose run test-runner

# Run specific tests
docker-compose run test-runner pytest src/tests/unit/ -v

# Run with coverage report
docker-compose run test-runner pytest --cov=components.generic_common --cov-report=html

# Run specific test file
docker-compose run test-runner pytest src/tests/unit/test_validation.py -v

# Run with verbose output
docker-compose run test-runner pytest src/tests/ -vv -s
```

### GCP Emulators

#### bigquery-emulator
```yaml
Container: generic-bigquery-emulator
GRPC: 9050:9050
REST: 9060:9060
```

#### pubsub-emulator
```yaml
Container: generic-pubsub-emulator
Port: 8085:8085
```

### Development Services

#### jupyter
```yaml
Container: generic-jupyter
Port: 8888:8888
URL: http://localhost:8888
No authentication required
```

---

## 📝 USAGE COMMANDS

### Common Operations

**Start everything:**
```bash
docker-compose up -d
```

**Start specific services:**
```bash
docker-compose up -d airflow-webserver airflow-scheduler airflow-db redis
```

**View logs:**
```bash
docker-compose logs -f                    # All services
docker-compose logs -f airflow-webserver  # Specific service
```

**Stop services:**
```bash
docker-compose stop                       # Graceful stop
docker-compose kill                       # Force stop
```

**Remove containers and volumes:**
```bash
docker-compose down                       # Remove containers
docker-compose down -v                    # Remove containers and volumes
```

### Database Operations

**Connect to PostgreSQL:**
```bash
docker-compose exec airflow-db psql -U airflow -d airflow
```

**Run SQL query:**
```bash
docker-compose exec airflow-db psql -U airflow -d airflow -c "SELECT COUNT(*) FROM dag;"
```

**Backup database:**
```bash
docker-compose exec airflow-db pg_dump -U airflow airflow > airflow_backup.sql
```

**Restore database:**
```bash
docker-compose exec -T airflow-db psql -U airflow airflow < airflow_backup.sql
```

### Testing Operations

**Run all tests:**
```bash
docker-compose run test-runner
```

**Run unit tests only:**
```bash
docker-compose run test-runner pytest src/tests/unit/ -v
```

**Run integration tests:**
```bash
docker-compose run test-runner pytest src/tests/integration/ -v
```

**Run with coverage:**
```bash
docker-compose run test-runner pytest --cov=components.generic_common --cov-report=html
```

**View coverage report:**
```bash
open deployments/htmlcov/index.html  # macOS
```

### Airflow Operations

**List DAGs:**
```bash
docker exec generic-airflow-webserver airflow dags list
```

**Test DAG parsing:**
```bash
docker exec generic-airflow-webserver airflow dags test generic_test_applications_migration 2025-01-01
```

**Trigger DAG:**
```bash
docker exec generic-airflow-webserver airflow dags trigger generic_test_applications_migration
```

**View task logs:**
```bash
docker exec generic-airflow-webserver ls /home/appuser/airflow/logs/
```

---

## ⚙️ CONFIGURATION

### Environment Variables

**Create `.env` file for custom settings:**

```bash
# .env file (git ignored)

# Airflow Configuration
AIRFLOW_DB_USER=airflow
AIRFLOW_DB_PASSWORD=airflow
AIRFLOW_DB_NAME=airflow
AIRFLOW_DB_PORT=5432
AIRFLOW_WEBSERVER_PORT=8080
AIRFLOW_SECRET_KEY=your-secret-key-here
AIRFLOW_FERNET_KEY=your-fernet-key-here

# GCP Configuration
GCP_PROJECT_ID=generic-test-project

# Logging
LOG_LEVEL=INFO

# Redis
REDIS_PORT=6379

# BigQuery Emulator
BIGQUERY_EMULATOR_GRPC_PORT=9050
BIGQUERY_EMULATOR_REST_PORT=9060

# Pub/Sub Emulator
PUBSUB_EMULATOR_PORT=8085

# Testing
PYTEST_ARGS=-v --cov=components.generic_common --cov-report=html

# JupyterLab
JUPYTER_PORT=8888

# Generic App
Generic_APP_PORT=8000
```

**Load environment file:**
```bash
export $(cat .env | xargs)
docker-compose up -d
```

### Override Configuration

**Development setup with custom settings:**

```bash
# Copy example
cp docker-compose.override.yml.example docker-compose.override.yml

# Edit as needed
vim docker-compose.override.yml

# Compose automatically loads both files
docker-compose up -d
```

---

## 🐛 TROUBLESHOOTING

### Issue 1: Port Already in Use

**Error:** `Address already in use`

**Solution:**
```bash
# Find process using port
lsof -i :8080

# Change port in .env or override file
AIRFLOW_WEBSERVER_PORT=8081

# Or stop conflicting container
docker kill <container_id>
```

### Issue 2: PostgreSQL Connection Failed

**Error:** `connection refused` or `database "airflow" does not exist`

**Solution:**
```bash
# Check database status
docker-compose logs airflow-db

# Wait for database initialization
docker-compose down -v && docker-compose up -d airflow-db

# Check database exists
docker exec generic-airflow-db psql -U airflow -l
```

### Issue 3: Airflow Can't Connect to Database

**Error:** `OperationalError: could not connect to server`

**Solution:**
```bash
# Verify database is running
docker-compose ps airflow-db

# Check connection string in logs
docker-compose logs airflow-webserver | grep alchemy

# Restart services in order
docker-compose down
docker-compose up -d airflow-db
sleep 10
docker-compose up -d airflow-webserver
```

### Issue 4: Tests Not Running

**Error:** `No module named 'generic_common'`

**Solution:**
```bash
# Rebuild test image
docker-compose build test-runner

# Run tests with verbose output
docker-compose run test-runner pytest src/tests/ -v -s

# Check volumes are mounted
docker exec generic-test-runner ls /app/deployments/
```

### Issue 5: Out of Disk Space

**Solution:**
```bash
# Clean up unused images and volumes
docker system prune -a

# Remove specific volumes
docker volume rm generic-airflow-db_data

# Clean old containers
docker container prune
```

### Issue 6: Services Not Healthy

**Check health status:**
```bash
docker-compose ps

# View detailed health logs
docker inspect --format='{{.State.Health}}' generic-airflow-db

# Restart unhealthy service
docker-compose restart airflow-db
```

### Getting Help

**View detailed logs:**
```bash
# All logs
docker-compose logs

# Specific service with tail
docker-compose logs -f --tail=100 airflow-webserver

# Service startup issues
docker-compose logs -f airflow-db | head -50
```

---

## 🎯 ADVANCED USAGE

### Custom DAG Development

**Mount DAG directory:**
```bash
# Edit docker-compose.override.yml
volumes:
  - ./src/orchestration/airflow/dags:/home/appuser/airflow/dags
```

**Reload DAGs:**
```bash
# Just wait 30 seconds (auto-refresh) or restart
docker-compose restart airflow-scheduler
```

### Performance Testing

**Scale test runner:**
```bash
# Run multiple test instances
docker-compose run -d --name test-runner-1 test-runner
docker-compose run -d --name test-runner-2 test-runner
```

### Database Snapshots

**Create snapshot:**
```bash
docker-compose exec airflow-db pg_dump -U airflow airflow > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Restore from snapshot:**
```bash
docker-compose exec -T airflow-db psql -U airflow airflow < backup_20250121_100000.sql
```

### Custom Build

**Build images with custom settings:**
```bash
docker-compose build --no-cache airflow-webserver
```

### CI/CD Integration

**Run in CI pipeline:**
```bash
#!/bin/bash
docker-compose build
docker-compose up -d
docker-compose run test-runner pytest --cov --cov-report=xml
docker-compose down -v
```

---

## 📊 DISK USAGE

**Check volume sizes:**
```bash
docker volume ls
docker system df
```

**Clean up:**
```bash
# Remove unused volumes
docker volume prune

# Remove unused images
docker image prune -a

# Complete cleanup
docker system prune -a --volumes
```

---

## 🔐 SECURITY NOTES

### For Production

⚠️ **NEVER use default credentials in production!**

```bash
# Generate secure keys
openssl rand -hex 32                    # Secret key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"  # Fernet key

# Use environment variables
export AIRFLOW_SECRET_KEY=$(openssl rand -hex 32)
export AIRFLOW_FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())")
```

### For Local Development

✅ **Current setup is fine for local use only**

- Default credentials are acceptable
- PostgreSQL is local-only
- No external network exposure

---

## 📞 QUICK REFERENCE

```bash
# Start/Stop
docker-compose up -d              # Start all
docker-compose down               # Stop all
docker-compose down -v            # Stop and remove volumes

# Monitor
docker-compose ps                 # Status
docker-compose logs -f            # Live logs
docker-compose logs SERVICE       # Specific service

# Access
docker-compose exec SERVICE bash  # Shell
docker exec CONTAINER COMMAND     # Run command

# Testing
docker-compose run test-runner    # Run tests
docker-compose run test-runner pytest -k FILTER  # Run specific tests

# Database
docker-compose exec airflow-db psql -U airflow  # Connect
```

---

**Status:** ✅ Ready for Production  
**Last Updated:** December 21, 2025  
**Audience:** All developers, DevOps, QA engineers

For issues or questions, see Troubleshooting section or check service logs.

