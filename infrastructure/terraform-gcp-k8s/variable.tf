variable "project_id" {
  description = "Your GCP project ID"
  type        = string
  default     = "fast-art-462115-p8"
}

variable "region" {
  default = "<GCP_REGION>"
}

variable "zone" {
  default = "<GCP_REGION>-a"
}
