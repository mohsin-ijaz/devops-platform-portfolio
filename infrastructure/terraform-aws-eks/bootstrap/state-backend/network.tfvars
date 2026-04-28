# Network Account Bootstrap

project_name = "otis"
company      = "acme"
aws_region   = "<AWS_REGION>"
environment  = "network"

additional_principals = [
  "<AWS_ACCOUNT_ID>",  # UAT
  "<AWS_ACCOUNT_ID>"   # Prod
]

tags = {}
