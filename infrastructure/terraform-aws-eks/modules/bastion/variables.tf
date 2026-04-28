# Bastion Module - Variables

variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for the bastion host"
  type        = string
}

variable "security_group_ids" {
  description = "Security group IDs to attach"
  type        = list(string)
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
}

variable "associate_public_ip" {
  description = "Associate public IP (should be false for SSM-only access)"
  type        = bool
}

variable "enable_monitoring" {
  description = "Enable detailed monitoring"
  type        = bool
}

variable "root_volume_size" {
  description = "Root volume size in GB"
  type        = number
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
}

variable "eks_cluster_name" {
  description = "EKS cluster name for kubectl configuration"
  type        = string
}

variable "aws_region" {
  description = "AWS region for kubectl configuration"
  type        = string
}

# GitLab Runner
variable "gitlab_runner_token" {
  description = "GitLab Runner registration token"
  type        = string
  sensitive   = true
}

variable "gitlab_runner_url" {
  description = "GitLab instance URL"
  type        = string
}

variable "gitlab_runner_tag" {
  description = "GitLab Runner tag for job matching"
  type        = string
  default     = ""
}
