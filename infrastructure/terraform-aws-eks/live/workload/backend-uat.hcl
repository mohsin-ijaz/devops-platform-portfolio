################################################################################
# UAT Backend Configuration
# Usage: terraform init -backend-config=backend-uat.hcl
################################################################################

bucket         = "acme-otis-terraform-state-<AWS_ACCOUNT_ID>"
key            = "uat/terraform.tfstate"
region         = "<AWS_REGION>"
encrypt        = true
dynamodb_table = "acme-otis-terraform-locks"
