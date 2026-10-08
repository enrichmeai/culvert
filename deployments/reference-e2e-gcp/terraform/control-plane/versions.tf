terraform {
  # Write-only arguments (password_wo, secret_data_wo) need Terraform 1.11; the ephemeral
  # random_password needs 1.10. Together they keep the database password out of state.
  required_version = ">= 1.11"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.50, < 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.7"
    }
  }
}
