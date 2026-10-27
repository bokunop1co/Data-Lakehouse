provider "google" {
  project = var.project_id
  region  = var.region

  # Billing budgets are billed/quota'd against a project, not the caller's
  # default one. Without this, google_billing_budget fails with a quota error.
  user_project_override = true
  billing_project       = var.project_id
}

locals {
  apis = [
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "billingbudgets.googleapis.com",
    "dataform.googleapis.com",
    "iam.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------- Bronze: raw Parquet files in GCS ----------
resource "google_storage_bucket" "bronze" {
  name                        = "${var.project_id}-lakehouse-bronze"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = var.force_destroy

  # Raw files are re-creatable from the BCRA API; expire old ones to cap cost.
  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

# ---------- BigQuery datasets (same location as the bucket, required for external tables) ----------
resource "google_bigquery_dataset" "layers" {
  for_each = toset(["bronze", "silver", "gold"])

  dataset_id                 = each.value
  location                   = var.region
  delete_contents_on_destroy = var.force_destroy
  description                = "Lakehouse ${each.value} layer"

  depends_on = [google_project_service.apis]
}

# ---------- Ingestion service account (least privilege) ----------
resource "google_service_account" "ingestion" {
  account_id   = "lakehouse-ingestion"
  display_name = "Lakehouse ingestion (BCRA to GCS bronze)"

  depends_on = [google_project_service.apis]
}

# Write objects to the bronze bucket only, not project-wide.
resource "google_storage_bucket_iam_member" "ingestion_writer" {
  bucket = google_storage_bucket.bronze.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

# ---------- Budget alert ----------
resource "google_billing_budget" "project" {
  billing_account = var.billing_account_id
  display_name    = "${var.project_id}-budget"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(var.budget_amount)
    }
  }

  dynamic "threshold_rules" {
    for_each = [0.5, 0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
    }
  }

  depends_on = [google_project_service.apis]
}

data "google_project" "this" {
  project_id = var.project_id
}
