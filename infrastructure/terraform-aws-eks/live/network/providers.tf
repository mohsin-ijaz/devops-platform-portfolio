# Network Account - Provider Configuration

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = upper(var.project_name)
      Company     = var.company
      Environment = "network"
      ManagedBy   = "Terraform"
      Owner       = "DevOps"
    }
  }
}
