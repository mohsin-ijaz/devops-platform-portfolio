output "node_info" {
  value = [
    for vm in google_compute_instance.k8s_node : {
      name        = vm.name
      external_ip = vm.network_interface[0].access_config[0].nat_ip
      internal_ip = vm.network_interface[0].network_ip
    }
  ]
}
