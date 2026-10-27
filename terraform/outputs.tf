output "bronze_bucket" {
  value = google_storage_bucket.bronze.name
}

output "ingestion_service_account" {
  value = google_service_account.ingestion.email
}

output "datasets" {
  value = [for d in google_bigquery_dataset.layers : d.dataset_id]
}
