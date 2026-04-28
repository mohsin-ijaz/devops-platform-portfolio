# VPN Module - Outputs

output "customer_gateway_id" {
  description = "Customer Gateway ID"
  value       = aws_customer_gateway.this.id
}

output "vpn_connection_id" {
  description = "VPN Connection ID"
  value       = aws_vpn_connection.this.id
}

output "vpn_connection_transit_gateway_attachment_id" {
  description = "VPN Connection Transit Gateway Attachment ID"
  value       = aws_vpn_connection.this.transit_gateway_attachment_id
}

output "tunnel1_address" {
  description = "Tunnel 1 public IP address"
  value       = aws_vpn_connection.this.tunnel1_address
}

output "tunnel1_preshared_key" {
  description = "Tunnel 1 preshared key"
  value       = aws_vpn_connection.this.tunnel1_preshared_key
  sensitive   = true
}

output "tunnel2_address" {
  description = "Tunnel 2 public IP address"
  value       = aws_vpn_connection.this.tunnel2_address
}

output "tunnel2_preshared_key" {
  description = "Tunnel 2 preshared key"
  value       = aws_vpn_connection.this.tunnel2_preshared_key
  sensitive   = true
}
