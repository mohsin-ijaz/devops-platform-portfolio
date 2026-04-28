terraform {
  required_providers {
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2"
    }
  }
  required_version = ">= 1.11.0"
}
