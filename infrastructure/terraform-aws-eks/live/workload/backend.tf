# Workload Account - Backend Configuration
# Note: Backend config is set dynamically via -backend-config or init script

terraform {
  backend "s3" {
    # These values are set via:
    # terraform init -backend-config=backend-<env>.hcl
    # or via environment-specific backend files

    # bucket         = "acme-otis-terraform-state-<ACCOUNT_ID>"
    # key            = "<env>/terraform.tfstate"
    # region         = "<AWS_REGION>"
    # encrypt        = true
    # dynamodb_table = "acme-otis-terraform-locks"
  }
}
