provider "google" {
  project     = var.project_id
  region      = var.region
  zone        = var.zone
}

# ---------- Network ----------
resource "google_compute_network" "k8s_network" {
  name                    = "k8s-custom-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "k8s_subnet" {
  name          = "k8s-subnet"
  ip_cidr_range = "10.10.0.0/16"
  region        = var.region
  network       = google_compute_network.k8s_network.id
}

# ---------- Firewall Rules ----------

resource "google_compute_firewall" "allow-k8s-api" {
  name    = "allow-k8s-api"
  network = google_compute_network.k8s_network.name

  allow {
    protocol = "tcp"
    ports    = ["6443"]
  }

  source_ranges = ["<TRUSTED_IP>/32"]
  target_tags   = ["k8s"]
}


resource "google_compute_firewall" "allow-nodeport" {
  name    = "allow-nodeport"
  network = google_compute_network.k8s_network.name

  allow {
    protocol = "tcp"
    ports    = ["30000-32767"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["k8s"]
}

resource "google_compute_firewall" "allow-ssh" {
  name    = "allow-ssh"
  network = google_compute_network.k8s_network.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["k8s"]
}

resource "google_compute_firewall" "allow-internal" {
  name    = "allow-internal"
  network = google_compute_network.k8s_network.name

  allow {
    protocol = "icmp"
  }

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  source_ranges = ["10.10.0.0/16"]
  target_tags   = ["k8s"]
}

resource "google_compute_firewall" "allow-k3s-internal" {
  name    = "allow-k3s-internal"
  network = google_compute_network.k8s_network.name

  allow {
    protocol = "tcp"
    ports = [
      "6443",   # K3s API
      "8472",   # Flannel VXLAN
      "10250"   # Kubelet API
    ]
  }

  source_ranges = ["10.10.0.0/16"]
  target_tags   = ["k8s"]
}

# ---------- Compute Instances ----------
resource "google_compute_instance" "k8s_node" {
  count        = 3
  name         = "k8s-node-${count.index}"
  machine_type = "e2-medium"
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    subnetwork    = google_compute_subnetwork.k8s_subnet.name
    access_config {}
  }

  metadata = {
    ssh-keys = "ubuntu:${file("${path.module}/ci-ssh-key.pub")}"
  }


  tags = ["k8s"]
}

# ---------- Local Inventory Output ----------
locals {
  node_info = [
    for idx, vm in google_compute_instance.k8s_node : {
      name        = vm.name
      external_ip = vm.network_interface[0].access_config[0].nat_ip
      internal_ip = vm.network_interface[0].network_ip
    }
  ]
}

resource "local_file" "inventory" {
  filename = "${path.module}/../ansible/inventory.ini"

  content = templatefile("${path.module}/inventory.tpl", {
    node_info = local.node_info
  })
}

