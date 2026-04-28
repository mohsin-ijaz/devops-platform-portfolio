variable "org" {
  type        = string
  description = "Organization short code like lk"
  default     = "lk"
}
variable "env" {
  type        = string
  description = "Environment code like mgmt/dev/qa/prod"
}

variable "security_mode" {
  type    = string
  default = "BASIC"
}

variable "vulnerability_mode" {
  type    = string
  default = "VULNERABILITY_BASIC"
}

variable "description" {
  type        = string
  description = "The description of the cluster"
  default     = ""
}

variable "gateway_api_channel" {
  type        = string
  description = "The gateway api channel of this cluster. Accepted values are CHANNEL_STANDARD and CHANNEL_DISABLED."
  default     = null
}

variable "deletion_protection" {
  type = bool
}

variable "enable_gcfs" {
  type = bool
}

variable "import_custom_routes" {
  type = bool
}

variable "export_custom_routes" {
  type = bool
}

variable "project_id" {
  type        = string
  description = "The project ID to host the cluster in (required)"
}

variable "labels" {
  type        = map(string)
  description = "The GCE resource labels (a map of key/value pairs) to be applied to the cluster"
  default     = {}

  validation {
    condition     = can(var.labels["account"])
    error_message = "A account labels is required."
  }
  validation {
    condition     = can(var.labels["env"])
    error_message = "A env labels is required."
  }
}

variable "region" {
  type        = string
  description = "The region to host the cluster in (required)"
}

variable "cluster" {
  type        = string
  description = "Name of the cluster to be given"
}

variable "network" {
  type        = string
  description = "Name of the vpc network"
}

variable "subnetwork" {
  type        = string
  description = "Name of the vpc subnet"
}

variable "initial_node_count" {
  default = "1"
}

variable "logging_service" {
  description = "The logging service that the cluster should write logs to. Available options include logging.googleapis.com/kubernetes, logging.googleapis.com (legacy), and none"
  type        = string
  default     = "logging.googleapis.com/kubernetes"
}

variable "monitoring_service" {
  description = "The monitoring service that the cluster should write metrics to. Automatically send metrics from pods in the cluster to the Stackdriver Monitoring API. VM metrics will be collected by Google Compute Engine regardless of this setting. Available options include monitoring.googleapis.com/kubernetes, monitoring.googleapis.com (legacy), and none"
  type        = string
  default     = "monitoring.googleapis.com/kubernetes"
}

variable "master_authorized_networks_config" {
  type        = list(object({ cidr_blocks = list(object({ cidr_block = string, display_name = string })) }))
  description = "The desired configuration options for master authorized networks. The object format is {cidr_blocks = list(object({cidr_block = string, display_name = string}))}. Omit the nested cidr_blocks attribute to disallow external access (except the cluster node IPs, which GKE automatically whitelists)."
  default     = []
}

variable "issue_client_certificate" {
  type        = bool
  description = "Issues a client certificate to authenticate to the cluster endpoint. To maximize the security of your cluster, leave this option disabled. Client certificates don't automatically rotate and aren't easily revocable. WARNING: changing this after cluster creation is destructive!"
  default     = false
}

variable "ip_range_pods" {
  type        = string
  description = "The _name_ of the secondary subnet ip range to use for pods"
}

variable "ip_range_services" {
  type        = string
  description = "The _name_ of the secondary subnet range to use for services"
}

variable "enable_shielded_nodes" {
  type        = bool
  description = "Enable Shielded Nodes features on all nodes in this cluster"
  default     = true
}

variable "master_version" {
  type        = string
  description = "The Kubernetes version of the masters. If set to 'latest' it will pull latest available version in the selected region."
  default     = "latest"
}

variable "remove_default_node_pool" {
  type        = bool
  description = "Remove default node pool while setting up the cluster"
  default     = true
}

variable "release_channel" {
  type        = string
  description = "The release channel of this cluster. Accepted values are `UNSPECIFIED`, `RAPID`, `REGULAR` and `STABLE`. Defaults to `REGULAR`."
  default     = "UNSPECIFIED"
}

variable "enable_private_endpoint" {
  type        = bool
  description = "(Beta) Whether the master's internal IP address is used as the cluster endpoint"
  default     = true
}

variable "enable_private_nodes" {
  type        = bool
  description = "(Beta) Whether nodes have internal IP addresses only"
  default     = true
}

variable "master_ipv4_cidr_block" {
  type        = string
  description = "(Beta) The IP range in CIDR notation to use for the hosted master network"
}

variable "master_global_access" {
  default = "true"
}

variable "workload_pool" {
  description = "connect to Google API's"
  type        = string
}

variable "logging_enabled_components" {
  type        = list(string)
  description = "List of services to monitor: SYSTEM_COMPONENTS, WORKLOADS. Empty list is default GKE configuration."
  default     = ["SYSTEM_COMPONENTS", "WORKLOADS"]
}

variable "monitoring_enabled_components" {
  type        = list(string)
  description = "List of services to monitor: SYSTEM_COMPONENTS, WORKLOADS (provider version >= 3.89.0). Empty list is default GKE configuration."
  default     = ["SYSTEM_COMPONENTS"]
}

variable "monitoring_enable_managed_prometheus" {
  type        = bool
  description = "Configuration for Managed Service for Prometheus. Whether or not the managed collection is enabled."
  default     = false
}

variable "enable_cost_allocation" {
  type        = bool
  description = "Enables Cost Allocation Feature and the cluster name and namespace of your GKE workloads appear in the labels field of the billing export to BigQuery"
  default     = true
}

variable "http_load_balancing" {
  type        = bool
  description = "Enable httpload balancer addon"
  default     = true
}

variable "horizontal_pod_autoscaling" {
  type        = bool
  description = "Enable horizontal pod autoscaling addon"
  default     = true
}

variable "network_policy" {
  type        = bool
  description = "Enable network policy addon"
  default     = false
}

variable "dns_cache" {
  type        = bool
  description = "The status of the NodeLocal DNSCache addon."
  default     = false
}

variable "filestore_csi_driver" {
  type        = bool
  description = "The status of the Filestore CSI driver addon, which allows the usage of filestore instance as volumes"
  default     = true
}

variable "gce_pd_csi_driver" {
  type        = bool
  description = "Whether this cluster should enable the Google Compute Engine Persistent Disk Container Storage Interface (CSI) Driver."
  default     = true
}

variable "gke_backup_agent_config" {
  type        = bool
  description = "Whether Backup for GKE agent is enabled for this cluster."
  default     = true
}