# Outputs

output "s3_bucket_name" {
  description = "Name of the S3 bucket for Terraform state"
  value       = aws_s3_bucket.terraform_state.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for Terraform state"
  value       = aws_s3_bucket.terraform_state.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for state locking"
  value       = aws_dynamodb_table.terraform_locks.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table for state locking"
  value       = aws_dynamodb_table.terraform_locks.arn
}

output "kms_key_arn" {
  description = "ARN of the KMS key for state encryption"
  value       = aws_kms_key.terraform_state.arn
}

output "kms_key_alias" {
  description = "Alias of the KMS key for state encryption"
  value       = aws_kms_alias.terraform_state.name
}

output "terraform_execution_role_arn" {
  description = "ARN of the IAM role for Terraform execution"
  value       = aws_iam_role.terraform_execution.arn
}

output "terraform_state_reader_role_arn" {
  description = "ARN of the IAM role for cross-account state reading"
  value       = aws_iam_role.terraform_state_reader.arn
}

output "backend_config" {
  description = "Backend configuration snippet for other Terraform configurations"
  value = <<-EOT
    terraform {
      backend "s3" {
        bucket         = "${aws_s3_bucket.terraform_state.id}"
        key            = "<environment>/terraform.tfstate"
        region         = "${data.aws_region.current.name}"
        encrypt        = true
        kms_key_id     = "${aws_kms_key.terraform_state.arn}"
        dynamodb_table = "${aws_dynamodb_table.terraform_locks.name}"
      }
    }
  EOT
}
