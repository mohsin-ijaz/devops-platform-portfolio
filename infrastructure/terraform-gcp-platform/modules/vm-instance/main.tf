/******************************************
	Reserving Static Private IP
*****************************************/
resource "google_compute_address" "static_private_ip" {
  count        = var.create_static_private_ip ? 1 : 0
  name         = var.private_ip_name
  address_type = var.address_type
  purpose      = var.purpose
  address      = var.private_address
  subnetwork   = var.subnetwork
  region       = var.region
}

resource "google_compute_address" "static_public_ip" {
  count        = var.create_static_public_ip ? 1 : 0
  name         = var.public_ip_name
  description  = var.public_ip_address_description
  address_type = var.address_type_public
  region       = var.region
}

/******************************************
	Virtual Machine Instance
*****************************************/
resource "google_compute_instance" "vm-instance" {
  boot_disk {
    auto_delete = var.auto_delete_disk
    initialize_params {
      image = var.image
      size  = var.size
    }
  }

  key_revocation_action_type = var.key_revocation_action_type
  can_ip_forward             = var.can_ip_forward
  deletion_protection        = var.deletion_protection
  labels                     = merge(var.labels)
  zone                       = var.zone
  machine_type               = var.machine_type
  name                       = var.name

  network_interface {
    network            = var.network
    stack_type         = var.stack_type
    subnetwork         = var.subnetwork
    subnetwork_project = var.subnetwork_project
    network_ip         = var.create_static_private_ip ? google_compute_address.static_private_ip[0].address : ""

    dynamic "access_config" {
      for_each = var.create_static_public_ip || var.create_ephemeral_public_ip ? [1] : []
      content {
        nat_ip       = var.create_static_public_ip ? google_compute_address.static_public_ip[0].address : null
        network_tier = var.network_tier
      }
    }
  }

  project = var.project_id

  reservation_affinity {
    type = "ANY_RESERVATION"
  }

  scheduling {
    on_host_maintenance = var.on_host_maintenance
    automatic_restart   = var.preemptible ? "false" : "true"
    preemptible         = var.preemptible
  }

  service_account {
    email  = var.email
    scopes = var.scopes
  }

  metadata = {}

  tags = var.tags

  lifecycle {
    ignore_changes = [
      boot_disk[0].initialize_params,
      metadata
    ]
  }
}
