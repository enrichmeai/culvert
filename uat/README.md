# Culvert UAT harness — internal-demo only

Sprint-6 deliverable. Provides a WireMock-based mock-service harness for running end-to-end demos of the framework without live cloud accounts or credentials.

**Internal-demo only.** Not a customer-facing UAT environment.

## What this provides

- A single `docker-compose.uat.yml` standing up [WireMock 3.5.4](https://wiremock.org/) on `localhost:8080`.
- Three pre-built mock endpoints (`uat/wiremock/mappings/`):

| Endpoint | Method | Purpose |
|---|---|---|
| `POST /oauth2/token` | mock OAuth2 token endpoint | Demo of authenticated downstream calls |
| `POST /webhooks/pipeline-event` | mock webhook receiver | Demo of audit / lineage emission via HTTP |
| `GET /api/v1/health` | mock health check | Demo of orchestration polling |

## What this does NOT provide

- **Mocks for GCP Pub/Sub, BigQuery, Cloud Storage.** Those clients use gRPC; Mockito at the SDK level is the right tool, and unit tests in each `data-pipeline-gcp-*-java` module already do that.
- A wired sample pipeline that demonstrates a full flow against these mocks (deferred to sprint-7+).

## Running

```bash
cd uat
docker-compose -f docker-compose.uat.yml up -d

# Sanity check
curl -s http://localhost:8080/api/v1/health | jq

# Mock an OAuth2 token
curl -s -X POST http://localhost:8080/oauth2/token | jq

# Mock a webhook submission
curl -s -X POST http://localhost:8080/webhooks/pipeline-event \
  -H "Authorization: Bearer uat-mock-access-token-1234" \
  -d '{"event": "stage.completed", "run_id": "demo-1"}' | jq

# WireMock admin
curl -s http://localhost:8080/__admin/mappings | jq

# Tear down
docker-compose -f docker-compose.uat.yml down
```

## Adding more mocks

Drop a JSON file into `uat/wiremock/mappings/`. WireMock auto-loads on container start. See the [WireMock JSON spec](https://wiremock.org/docs/stubbing/) for the shape.

For dynamic templated responses, mappings can reference `{{request.body}}`, `{{randomValue}}`, and other helpers — see `webhook-event.json` for an example using a templated UUID.

## CI considerations

This harness is local-developer-only at sprint-6 close. CI integration (a make target that spins WireMock up, runs the framework's integration tests against it, tears down) is sprint-7+ scope. CI workflows themselves are currently disabled (#14) to save Actions minutes during the sprint phase.
