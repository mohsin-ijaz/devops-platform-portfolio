# Mohsin Ijaz

## Senior DevOps / SRE / Platform Engineer

I build infrastructure that helps teams ship faster, recover cleanly, and operate with discipline.

This repository is a production-oriented portfolio for Kubernetes platform engineering, cloud infrastructure, GitOps delivery, observability, and automation. It is not a tutorial repo. The strongest work here reflects reusable platform patterns across AWS EKS, GCP/GKE, Terraform, Helm, Kustomize, Argo CD, CI/CD, SRE telemetry, and operational tooling.

- **Location:** Malaysia
- **Citizenship:** Pakistan
- **Core focus:** Kubernetes + AWS/GCP + Terraform + SRE + GitOps + Production Reliability

[Open the portfolio site](https://mohsin-ijaz.github.io/devops-platform-portfolio/)
[Explore the repository](https://github.com/mohsin-ijaz/devops-platform-portfolio)

---

## Selected Professional Outcomes

The following are anonymized, verified professional outcomes from production experience. They are intentionally separated from repository-code claims.

| Outcome area | Verified impact |
| --- | --- |
| Production scale | 150+ services/applications, 20+ Kubernetes clusters, 200+ production nodes |
| Cloud migration | Major AWS to GCP migration with under 10 minutes production downtime |
| Cost and capacity | More than US$60K annual cloud savings |
| Delivery speed | Release cycle improved from approximately 45 minutes to under 5 minutes |
| Observability performance | High-cardinality observability queries improved from 6+ seconds to under 100ms |
| Resilience | DR exercise with RTO under 25 minutes |
| Data and automation | 50+ databases involved in migration work and 40+ automation/remediation workflows |

---

## Featured Engineering

### 1. Kubernetes Platform Engineering

[AWS EKS Terraform platform](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/infrastructure/terraform-aws-eks)
Reusable EKS infrastructure with VPC/network modules, managed node groups, access entries, IRSA/OIDC patterns, ECR, bastion access, transit networking, VPN, and GitLab CI roles for workload delivery.

[GCP platform Terraform modules](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/infrastructure/terraform-gcp-platform)
GCP infrastructure modules for GKE, shared VPC, IAM, service accounts, Artifact Registry, Cloud SQL, Redis, Secret Manager, storage, VPN, NAT, and private connectivity.

[GCP Kubernetes bootstrap](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/infrastructure/terraform-gcp-k8s)
Terraform and Ansible flow for custom Kubernetes infrastructure, inventory generation, node provisioning, firewall rules, and bootstrap automation.

### 2. GitOps and CI/CD

[GitLab pipeline collection](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/cicd/pipelines)
Pipelines cover Terraform validation/plan/apply, AWS OIDC role assumption, GCP provisioning, Helm/ECR deployments, Semgrep SAST, triggered downstream environments, and manual production gates.

[Argo CD and Kustomize platform resources](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/kubernetes/argocd)
GitOps manifests and ApplicationSet-style patterns for reusable cluster deployments.

[Kustomize overlays](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/infrastructure/kustomize)
Environment overlays for Kafka, Kafka Connect, Debezium, KSQL, Temporal, Argo CD, cluster secret stores, and related Kubernetes workloads.

### 3. SRE and Observability

[LGTM observability stack](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/observability/lgtm-stack)
Prometheus/Grafana/Loki/Tempo/Mimir-oriented stack with Terraform, Helm wrappers, dashboards, alert rules, internal load balancers, tracing, Mimir rules, FinOps recording rules, and production-style workload placement.

[Anomaly detection pipeline](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/observability/anomaly-detection)
Python training and serving pipeline for telemetry extraction, feature engineering, ensemble-based anomaly scoring, and Kubernetes deployment.

[Kubernetes audit and runtime security](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/security)
Kubernetes audit policy, Loki alert rules, Elasticsearch ingest/index assets, forensic query tooling, CrowdSec scenarios, and production-oriented security values.

### 4. Automation and Platform Operations

[GKE environment scheduler](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/automation/gke-env-scheduler)
Python orchestration for GKE node pools, Cloud SQL dependencies, Argo CD state, Kubernetes resources, PDB handling, and scheduled environment operations.

[Cloud SQL backup validation](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/automation/cloudrun-backup)
Cloud Run oriented backup, restore, validation, report generation, GCS upload, and cleanup workflow for Cloud SQL.

[Platform CLI](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/automation/platform-cli)
Operational CLI controllers for builds, CI/CD workflows, Kubernetes resources, databases, Kafka, Redis, Solr, storage, images, jobs, and Kustomize generation.

---

## Platform Approach

The repository is strongest where it shows platform behavior rather than isolated scripts:

- **Reusable infrastructure:** Terraform modules for clusters, networking, IAM, artifact registries, state backends, service accounts, storage, and managed data services.
- **Controlled delivery:** OIDC-based CI/CD, manual production approvals, Helm deployments, Kustomize overlays, Argo CD patterns, and rollback-aware rollout settings.
- **Reliability by design:** health probes, disruption budgets, topology spread, node pool separation, audit policy, alert rules, workload identity, and explicit production safety checks.
- **Observability as an operating system:** logs, metrics, traces, dashboards, SLO-style alerting, FinOps rules, query performance tuning, and anomaly detection.
- **Automation with guardrails:** dry-run defaults, explicit restore-test suffix checks, dependency-aware environment stop/start, and endpoint scanning/patching workflows.

---

## Core Stack

| Domain | Technologies represented in this repository |
| --- | --- |
| Kubernetes | EKS, GKE, Helm, Kustomize, Argo CD, Argo Rollouts, HPA, node pools, service accounts |
| Cloud | AWS, GCP, ECR, Artifact Registry, Cloud SQL, Redis, GCS, IAM, OIDC, Workload Identity |
| Infrastructure as Code | Terraform modules, environment tfvars, backend bootstrap, reusable networking modules |
| CI/CD and GitOps | GitLab CI/CD, Terraform plan/apply, OIDC role assumption, Helm deploys, Kustomize image promotion, Semgrep SAST |
| Observability | Prometheus, Grafana, Loki, Tempo, Mimir, Alloy, OpenTelemetry/OTLP, dashboards, alerting, FinOps rules |
| Automation | Python, Bash, Cloud Run jobs, Kubernetes automation, database scanning, backup validation, platform CLI |
| Security | Kubernetes audit policy, CrowdSec scenarios, secret access alerts, RBAC alerts, forensic queries |

---

## Repository Navigation

| Area | What to inspect first |
| --- | --- |
| [`infrastructure/terraform-aws-eks`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/infrastructure/terraform-aws-eks) | AWS EKS platform, VPC, OIDC/IRSA, GitLab CI role, ECR, transit/VPN |
| [`infrastructure/terraform-gcp-platform`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/infrastructure/terraform-gcp-platform) | GCP platform modules, GKE, shared VPC, IAM, Cloud SQL, Redis, Secret Manager |
| [`infrastructure/kustomize`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/infrastructure/kustomize) | Kustomize bases and overlays for Kafka, Debezium, Temporal, Argo CD, secret stores |
| [`kubernetes/argocd`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/kubernetes/argocd) | Argo CD GitOps entry points |
| [`helm/microservice-chart`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/helm/microservice-chart) | Reusable microservice deployment chart with probes, HPA, security contexts, topology rules |
| [`cicd/pipelines`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/cicd/pipelines) | Terraform, Helm, GitOps, SAST, and orchestrator pipeline examples |
| [`observability/lgtm-stack`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/observability/lgtm-stack) | LGTM stack, dashboards, alerts, tracing, FinOps and query-performance tuning |
| [`observability/anomaly-detection`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/observability/anomaly-detection) | Telemetry feature engineering, training, scoring API, Kubernetes deployment |
| [`automation`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/automation) | Cloud SQL backup validation, GKE scheduler, platform CLI, DB endpoint migration tools |
| [`security`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/security) | Kubernetes audit policy, CrowdSec scenarios, alert rules, forensics |
| [`dockerfiles`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/dockerfiles) | Runtime images for exporters, Cloud Run, Debezium, Secor, and Go/Alpine workloads |

---

## Engineering Principles

- Build platforms that reduce repeated operational work.
- Prefer explicit, reviewable infrastructure over click-path changes.
- Design deployment paths with rollback, observability, and blast-radius awareness.
- Treat cost, capacity, and reliability as engineering constraints, not afterthoughts.
- Use automation for repeatability, but keep dangerous actions guarded and auditable.
- Keep public portfolio claims grounded in repository evidence and verified professional outcomes.

---

## Portfolio Site

The GitHub Pages site lives in [`docs/`](https://github.com/mohsin-ijaz/devops-platform-portfolio/tree/main/docs) and is intentionally lightweight:

- static `index.html`, `styles.css`, and `app.js`
- no build system
- no external JavaScript dependencies
- responsive layout
- semantic HTML
- OpenGraph and SEO metadata
- reduced-motion support
- keyboard-accessible navigation and controls

Open it here: [https://mohsin-ijaz.github.io/devops-platform-portfolio/](https://mohsin-ijaz.github.io/devops-platform-portfolio/)
