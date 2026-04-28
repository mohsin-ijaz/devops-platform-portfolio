# Terraform State Backend Bootstrap

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = upper(var.project_name)
      Company     = var.company
      Environment = var.environment
      ManagedBy   = "Terraform"
      Component   = "state-backend"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  name_prefix = "${var.company}-${var.project_name}"
  account_id  = data.aws_caller_identity.current.account_id
  tags        = var.tags
}

# KMS Key for State Encryption

resource "aws_kms_key" "terraform_state" {
  description             = "KMS key for Terraform state encryption - ${var.environment}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccountFullAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCrossAccountStateAccess"
        Effect = "Allow"
        Principal = {
          AWS = concat(
            ["arn:aws:iam::${local.account_id}:root"],
            [for id in var.additional_principals : "arn:aws:iam::${id}:root"]
          )
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.tags
}

resource "aws_kms_alias" "terraform_state" {
  name          = "alias/${local.name_prefix}-terraform-state-${var.environment}"
  target_key_id = aws_kms_key.terraform_state.key_id
}

# S3 Bucket for State Storage

resource "aws_s3_bucket" "terraform_state" {
  bucket = "${local.name_prefix}-terraform-state-${local.account_id}"

  lifecycle {
    prevent_destroy = true
  }

  tags = local.tags
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.terraform_state.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    id     = "cleanup-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }
  }
}

resource "aws_s3_bucket_policy" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid       = "EnforceTLS"
          Effect    = "Deny"
          Principal = "*"
          Action    = "s3:*"
          Resource = [
            aws_s3_bucket.terraform_state.arn,
            "${aws_s3_bucket.terraform_state.arn}/*"
          ]
          Condition = {
            Bool = {
              "aws:SecureTransport" = "false"
            }
          }
        }
      ],
      length(var.additional_principals) > 0 ? [
        {
          Sid    = "AllowCrossAccountAccess"
          Effect = "Allow"
          Principal = {
            AWS = [for id in var.additional_principals : "arn:aws:iam::${id}:root"]
          }
          Action = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:DeleteObject",
            "s3:ListBucket"
          ]
          Resource = [
            aws_s3_bucket.terraform_state.arn,
            "${aws_s3_bucket.terraform_state.arn}/*"
          ]
        }
      ] : []
    )
  })
}

# DynamoDB Table for State Locking

resource "aws_dynamodb_table" "terraform_locks" {
  name         = "${local.name_prefix}-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.terraform_state.arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = local.tags
}

# IAM Role for Terraform Execution

resource "aws_iam_role" "terraform_execution" {
  name = "${local.name_prefix}-terraform-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = concat(
            ["arn:aws:iam::${local.account_id}:root"],
            [for id in var.additional_principals : "arn:aws:iam::${id}:root"]
          )
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "${var.project_name}-terraform"
          }
        }
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "terraform_execution_admin" {
  role       = aws_iam_role.terraform_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# IAM Role for Cross-Account State Reading

resource "aws_iam_role" "terraform_state_reader" {
  name = "${local.name_prefix}-terraform-state-reader"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = concat(
            ["arn:aws:iam::${local.account_id}:root"],
            [for id in var.additional_principals : "arn:aws:iam::${id}:root"]
          )
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "${var.project_name}-terraform"
          }
        }
      }
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "terraform_state_reader" {
  name = "state-read-access"
  role = aws_iam_role.terraform_state_reader.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.terraform_state.arn,
          "${aws_s3_bucket.terraform_state.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.terraform_state.arn
      }
    ]
  })
}
