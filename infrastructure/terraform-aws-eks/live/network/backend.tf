# Network Account - Backend Configuration

terraform {
  backend "s3" {
    bucket         = "acme-otis-terraform-state-<AWS_NETWORK_ACCOUNT_ID>"
    key            = "network/terraform.tfstate"
    region         = "<AWS_REGION>"
    encrypt        = true
    dynamodb_table = "acme-otis-terraform-locks"
  }
}
