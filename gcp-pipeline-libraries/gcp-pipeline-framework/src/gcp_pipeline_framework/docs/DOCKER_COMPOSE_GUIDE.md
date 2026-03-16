# Docker Compose Local Testing Guide

Local testing environment with Airflow, PostgreSQL, Redis, pytest, and GCP emulators.

---

## Quick Start

```bash
cd blueprint

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# Run tests
docker-compose run test-runner

# Stop services
docker-compose down
```

---

## Services

| Service | Container | Port(s) | Notes |
|---------|-----------|---------|-------|
| PostgreSQL | generic-airflow-db | 5432 | Airflow metadata DB. User: `airflow` / `airflow` |
| Redis | generic-redis | 6379 | Celery broker, no auth |
| Airflow Webserver | generic-airflow-webserver | 8080 | UI login: `admin` / `admin` |
| Airflow Scheduler | generic-airflow-scheduler | -- | Background, no exposed port |
| Test Runner | generic-test-runner | -- | On-demand pytest container |
| BigQuery Emulator | generic-bigquery-emulator | 9050 (gRPC), 9060 (REST) | Local BQ testing |
| Pub/Sub Emulator | generic-pubsub-emulator | 8085 | Local Pub/Sub testing |
| JupyterLab | generic-jupyter | 8888 | No password |

---

## Commands Reference

### Lifecycle

```bash
docker-compose up -d                        # Start all services
docker-compose up -d airflow-webserver redis # Start specific services
docker-compose down                         # Stop and remove containers
docker-compose down -v                      # Stop, remove containers and volumes
docker-compose restart airflow-webserver    # Restart a service
```

### Logs and Status

```bash
docker-compose ps                                # Service status
docker-compose logs -f                           # Tail all logs
docker-compose logs -f --tail=100 airflow-webserver  # Tail specific service
```

### Testing

```bash
docker-compose run test-runner                                          # All tests
docker-compose run test-runner pytest src/tests/unit/ -v                # Unit tests
docker-compose run test-runner pytest src/tests/integration/ -v         # Integration tests
docker-compose run test-runner pytest --cov=components.generic_common --cov-report=html  # Coverage
```

### Airflow

```bash
docker exec generic-airflow-webserver airflow dags list
docker exec generic-airflow-webserver airflow dags trigger generic_test_applications_migration
docker exec generic-airflow-webserver airflow dags test generic_test_applications_migration 2025-01-01
```

### Database

```bash
docker-compose exec airflow-db psql -U airflow -d airflow
docker-compose exec airflow-db psql -U airflow -d airflow -c "SELECT COUNT(*) FROM dag;"
```

---

## Configuration

Create a `.env` file (git-ignored) to override defaults:

```bash
AIRFLOW_DB_USER=airflow
AIRFLOW_DB_PASSWORD=airflow
AIRFLOW_DB_PORT=5432
AIRFLOW_WEBSERVER_PORT=8080
GCP_PROJECT_ID=generic-test-project
LOG_LEVEL=INFO
PYTEST_ARGS=-v --cov=components.generic_common --cov-report=html
```

For persistent overrides, use `docker-compose.override.yml` (auto-loaded by Compose alongside the main file).

---

## Troubleshooting

### Port already in use

```bash
lsof -i :8080              # Find the conflicting process
# Either kill it, or change the port in .env:
AIRFLOW_WEBSERVER_PORT=8081
```

### PostgreSQL connection failed

```bash
docker-compose logs airflow-db                  # Check DB logs
docker-compose down -v && docker-compose up -d  # Reset from scratch
```

### Module not found in tests

```bash
docker-compose build test-runner                # Rebuild the test image
docker-compose run test-runner pytest -v -s     # Re-run with verbose output
```

---

## CI/CD Integration

```bash
#!/bin/bash
docker-compose build
docker-compose up -d
docker-compose run test-runner pytest --cov --cov-report=xml
docker-compose down -v
```
