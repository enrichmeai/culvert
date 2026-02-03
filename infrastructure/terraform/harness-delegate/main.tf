# Terraform for Harness Delegate on GCE
# This provisions a VM on GCP that runs the Harness Delegate as a Docker container.

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west2"
}

variable "zone" {
  description = "GCP Zone"
  type        = string
  default     = "europe-west2-a"
}

variable "delegate_name" {
  description = "Name of the Harness Delegate"
  type        = string
  default     = "gcp-delegate"
}

variable "harness_account_id" {
  description = "Your Harness Account ID"
  type        = string
}

variable "harness_delegate_token" {
  description = "Your Harness Delegate Token"
  type        = string
  sensitive   = true
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Network for the Delegate
resource "google_compute_network" "harness_vpc" {
  name                    = "harness-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "harness_subnet" {
  name          = "harness-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.harness_vpc.id
}

# Service Account for the Delegate VM
resource "google_service_account" "delegate_sa" {
  account_id   = "harness-delegate-sa"
  display_name = "Harness Delegate Service Account"
}

# Grant the Service Account permissions to manage GCP resources
resource "google_project_iam_member" "delegate_admin" {
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.delegate_sa.email}"
}

# Firewall rule to allow SSH (for debugging)
resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh"
  network = google_compute_network.harness_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
}

# Harness Delegate VM
resource "google_compute_instance" "delegate_vm" {
  name         = var.delegate_name
  machine_type = "e2-medium" # Minimum recommended for Delegate
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 50
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.harness_subnet.id
    access_config {
      # Ephemeral IP for outbound internet access
    }
  }

  service_account {
    email  = google_service_account.delegate_sa.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    apt-get update
    apt-get install -y docker.io
    systemctl start docker
    systemctl enable docker

    docker run -d --cpus=2 --memory=2g \
      -e ACCOUNT_ID=${var.harness_account_id} \
      -e DELEGATE_TOKEN=${var.harness_delegate_token} \
      -e DELEGATE_NAME=${var.delegate_name} \
      -e DELEGATE_TYPE=DOCKER \
      -e DELEGATE_NAMESPACE=harness-delegate \
      -e DEPLOY_MODE=KUBERNETES \
      -e MANAGER_HOST_AND_PORT=https://app.harness.io \
      -e WATCHER_STORAGE_URL=https://app.harness.io/public/shared/watchers \
      -e WATCHER_CHECK_LOCATION=https://app.harness.io/check \
      -e REMOTE_WATCHER_URL_V2=https://app.harness.io/public/shared/watchers/watcher.txt \
      harness/delegate:latest
  EOT

  labels = {
    managed_by = "terraform"
    service    = "harness-delegate"
  }
}

output "delegate_vm_external_ip" {
  value = google_compute_instance.delegate_vm.network_interface[0].access_config[0].nat_ip
}
