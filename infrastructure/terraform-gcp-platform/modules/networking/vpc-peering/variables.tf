variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "vpc_peering_pairs" {
  description = <<EOT
List of VPC peering configurations. Each object supports:

- vpc1 / vpc2: Name of the VPC networks.
- project1 / project2 (optional): Project IDs where vpc1 and vpc2 exist. Defaults to var.project_id.
- create_forward: (optional, default true) Whether to create the forward peering (vpc1 → vpc2).
- create_reverse: (optional, default false) Whether to create the reverse peering (vpc2 → vpc1).

- forward_export_custom_routes / forward_import_custom_routes
- forward_export_subnet_routes_with_public_ip / forward_import_subnet_routes_with_public_ip
- reverse_export_custom_routes / reverse_import_custom_routes
- reverse_export_subnet_routes_with_public_ip / reverse_import_subnet_routes_with_public_ip
EOT

  type = list(object({
    vpc1  = string
    vpc2  = string

    name = optional(string) 

    project1 = optional(string)
    project2 = optional(string)

    create_forward = optional(bool, true)
    create_reverse = optional(bool, false)

    forward_export_custom_routes                = bool
    forward_import_custom_routes                = bool
    forward_export_subnet_routes_with_public_ip = bool
    forward_import_subnet_routes_with_public_ip = bool

    reverse_export_custom_routes                = optional(bool, false)
    reverse_import_custom_routes                = optional(bool, false)
    reverse_export_subnet_routes_with_public_ip = optional(bool, false)
    reverse_import_subnet_routes_with_public_ip = optional(bool, false)
  }))
}


