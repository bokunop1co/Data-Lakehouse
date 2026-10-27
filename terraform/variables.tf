variable "project_id" {
  description = "GCP project ID that hosts the lakehouse."
  type        = string
}

variable "region" {
  description = <<-EOT
    Location for the bucket and BigQuery datasets. southamerica-east1 (Sao Paulo)
    is the closest region to Argentina and keeps data in the same geography as the
    source. Bucket and datasets MUST share a location for external tables to work.
  EOT
  type        = string
  default     = "southamerica-east1"
}

variable "billing_account_id" {
  description = "Billing account ID (format XXXXXX-XXXXXX-XXXXXX) used for the budget alert."
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget in budget_currency. Alerts fire at 50%, 90% and 100%."
  type        = number
  default     = 10
}

variable "budget_currency" {
  description = "Currency of the billing account (the budget must match it)."
  type        = string
  default     = "USD"
}

variable "force_destroy" {
  description = "Allow terraform destroy to delete a non-empty bucket/datasets. Keep true only for this sandbox."
  type        = bool
  default     = true
}
