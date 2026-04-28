variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "location" {
  description = "The GCP region or zone"
  type        = string
}

variable "cluster_name" {
  description = "The GKE cluster name"
  type        = string
}

variable "namespace" {
  description = "The namespace to deploy ArgoCD into"
  type        = string
  default     = "argocd"
}

variable "release_name" {
  description = "The name of the Helm release"
  type        = string
  default     = "argocd"
}

variable "chart_version" {
  description = "The version of the ArgoCD Helm chart to use"
  type        = string
  default     = "5.46.8" # Specify a version to avoid breaking changes
}

variable "extra_values" {
  description = "Key-value pairs to override chart values"
  type        = map(string)
  default     = {}
}

variable "sensitive_values" {
  description = "Sensitive key-value pairs to override chart values"
  type        = map(string)
  default     = {}
}

variable "values_file_path" {
  description = "Path to values.yaml file for Helm chart"
  type        = string
  default     = "" # Empty means no values file will be used
}
