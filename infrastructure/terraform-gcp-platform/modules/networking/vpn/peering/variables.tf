variable "region" {
  description = "Region name for GCP"
  type        = string
}

variable "project_id" {
  description = "name of GCP Project"
  type        = string
}

variable "gateway_name" {
  description = "name of Gateway Name"
  type        = string
}

variable "external_gateway_name" {
  description = "name of External Gateway Name"
  type        = string
}

variable "router_name" {
  description = "name of router Name"
  type        = string
}

variable "network" {
  description = "name of network Name"
  type        = string
}

variable "asn" {
  description = "Google Cloud side ASN"
  type        = number
}

# variable "cus_rt_psc_range" {
#   description = "CIDR group for private Service Connection"
#   type        = list(string)
# }

variable "redundancy_type" {
  type        = string
  description = "the redundancy type of the peer VPN gateway Possible values are FOUR_IPS_REDUNDANCY, SINGLE_IP_INTERNALLY_REDUNDANT, and TWO_IPS_REDUNDANCY"
  default     = "FOUR_IPS_REDUNDANCY"
}
variable "ike_version" {
  type        = number
  description = "IKE protocol version to use when establishing the VPN tunnel with peer VPN gateway"
}

variable "external_vpn_gateway_interfaces" {
  type = map(object({
    name_tunnel           = string
    tunnel_address        = string
    router_int_name       = string
    router_peer_name      = string
    vgw_inside_address    = string
    asn                   = number
    cgw_inside_address    = string
    secret_name           = string
    vpn_gateway_interface = number
  }))

}


variable "router_advertise_config" {
  description = <<EOT
Optional BGP advertisement configuration for the router.
- mode: (string) Advertisement mode ("DEFAULT" or "CUSTOM").
- groups: (list(string)) List of advertised groups if mode is CUSTOM.
- ip_ranges: (map(string)) Map of advertised IP ranges (CIDR => description).
EOT
  type = object({
    mode      = string
    groups    = optional(list(string), [])
    ip_ranges = optional(map(string), {})
  })
  default = null
}

variable "org" {}

variable "env" {}

variable "region_code" {}

variable "destination" {}

variable "src" {}