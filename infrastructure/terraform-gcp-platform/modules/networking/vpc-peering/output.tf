output "peering_names" {
  description = "List of created VPC peering connections"
  value       = [for k, v in google_compute_network_peering.forward : v.name]
}
