variable "project_id" {
  type        = string
  description = "The project ID to deploy to"
}


variable "region" {
  type        = string
  description = "The region to deploy to"
}

variable "icmp_idle_timeout_sec" {
  type        = string
  description = "Timeout (in seconds) for ICMP connections. Defaults to 30s if not set. Changing this forces a new NAT to be created."
  default     = "30"
}

variable "min_ports_per_vm" {
  type        = string
  description = "Minimum number of ports allocated to a VM from this NAT config. Defaults to 64 if not set. Changing this forces a new NAT to be created."
  default     = "64"
}

variable "max_ports_per_vm" {
  type        = string
  description = "Maximum number of ports allocated to a VM from this NAT. This field can only be set when enableDynamicPortAllocation is enabled.This will be ignored if enable_dynamic_port_allocation is set to false."
  default     = null
}

variable "natgw_name" {
  type = string
}

variable "router_name" {
  type = string
}

variable "nat_ips" {
  type        = list(string)
  description = "List of self_links of external IPs. Changing this forces a new NAT to be created. Value of `nat_ip_allocate_option` is inferred based on nat_ips. If present set to MANUAL_ONLY, otherwise AUTO_ONLY."
  default     = []
}

variable "source_subnetwork_ip_ranges_to_nat" {
  type        = string
  description = "Defaults to ALL_SUBNETWORKS_ALL_IP_RANGES. How NAT should be configured per Subnetwork. Valid values include: ALL_SUBNETWORKS_ALL_IP_RANGES, ALL_SUBNETWORKS_ALL_PRIMARY_IP_RANGES, LIST_OF_SUBNETWORKS. Changing this forces a new NAT to be created."
  default     = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

variable "tcp_established_idle_timeout_sec" {
  type        = string
  description = "Timeout (in seconds) for TCP established connections. Defaults to 1200s if not set. Changing this forces a new NAT to be created."
  default     = "1200"
}

variable "tcp_transitory_idle_timeout_sec" {
  type        = string
  description = "Timeout (in seconds) for TCP transitory connections. Defaults to 30s if not set. Changing this forces a new NAT to be created."
  default     = "30"
}

variable "tcp_time_wait_timeout_sec" {
  type        = string
  description = "Timeout (in seconds) for TCP connections that are in TIME_WAIT state. Defaults to 120s if not set."
  default     = "120"
}

variable "udp_idle_timeout_sec" {
  type        = string
  description = "Timeout (in seconds) for UDP connections. Defaults to 30s if not set. Changing this forces a new NAT to be created."
  default     = "30"
}

variable "subnetworks" {
  description = "Specifies one or more subnetwork NAT configurations"
  type = list(object({
    name                     = string,
    source_ip_ranges_to_nat  = list(string)
    secondary_ip_range_names = list(string)
  }))
  default = []
}

variable "log_config_enable" {
  type        = bool
  description = "Indicates whether or not to export logs"
  default     = false
}
variable "log_config_filter" {
  type        = string
  description = "Specifies the desired filtering of logs on this NAT. Valid values are: \"ERRORS_ONLY\", \"TRANSLATIONS_ONLY\", \"ALL\""
  default     = "ALL"
}

variable "enable_dynamic_port_allocation" {
  type        = bool
  description = "Enable Dynamic Port Allocation. If minPorts is set, minPortsPerVm must be set to a power of two greater than or equal to 32."
  default     = false

}
variable "enable_endpoint_independent_mapping" {
  type        = bool
  description = "Specifies if endpoint independent mapping is enabled."
  default     = null
}