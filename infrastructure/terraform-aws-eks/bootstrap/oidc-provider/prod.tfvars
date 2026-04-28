aws_region          = "<AWS_REGION>"
gitlab_url          = "https://gitlab.com"
gitlab_project_path = "acme/infrastructure/acme-platform-terraform-infra"
allowed_branches    = ["main", "master"]
role_name           = "GitLabCIRole"
role_max_session_duration = 3600
attach_admin_policy = true
environment         = "prod"

tags = {
  Project     = "OTIS"
  Company     = "Acme"
  Environment = "prod"
  ManagedBy   = "Terraform"
}
