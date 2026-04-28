# UAT Account Bootstrap

project_name = "otis"
company      = "acme"
aws_region   = "<AWS_REGION>"
environment  = "uat"

additional_principals = [
  "<AWS_NETWORK_ACCOUNT_ID>"  # Network account for cross-state access
]

tags = {}
