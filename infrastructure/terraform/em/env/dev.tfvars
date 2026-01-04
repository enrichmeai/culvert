# EM Development Environment Configuration
# NOTE: gcp_project_id is passed via -var flag from GitHub secret

gcp_project_id    = "set-via-github-secret"
gcp_region        = "europe-west2"
bq_location       = "EU"
environment       = "dev"
force_destroy     = true   # Allow bucket deletion in dev
enable_versioning = true

