#!/bin/bash
set -euo pipefail

# Load configuration
CONFIG_FILE="${CONFIG_FILE:-/config/config.yaml}"

# Parse YAML config (simple key-value extraction)
parse_config() {
  grep "^[[:space:]]*$1:" "$CONFIG_FILE" | sed 's/.*:[[:space:]]*//' | tr -d '"'
}

ARGOCD_NAMESPACE=$(parse_config "argocdNamespace")
GIT_SECRET=$(parse_config "gitCredentialsSecret")
GIT_SECRET_NAMESPACE=$(parse_config "gitCredentialsNamespace")
GIT_AUTHOR=$(parse_config "gitCommitAuthor")
GIT_EMAIL=$(parse_config "gitCommitEmail")
POLL_INTERVAL=$(parse_config "pollIntervalSeconds")
LOG_LEVEL=$(parse_config "logLevel")

# Logging functions - ALL go to stderr to avoid corrupting function return values
log_debug() { [[ "$LOG_LEVEL" == "debug" ]] && echo "[DEBUG] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >&2 || true; }
log_info() { echo "[INFO] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >&2; }
log_warn() { echo "[WARN] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >&2; }
log_error() { echo "[ERROR] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >&2; }

# Discover Application resource for a given Rollout
discover_application() {
  local rollout_name=$1
  local rollout_namespace=$2

  log_debug "Discovering Application for Rollout: $rollout_name in namespace: $rollout_namespace"

  # Try 1: Find using app.kubernetes.io/instance label
  local app_label=$(kubectl get rollout "$rollout_name" -n "$rollout_namespace" \
    -o jsonpath='{.metadata.labels.app\.kubernetes\.io/instance}' 2>/dev/null || echo "")

  if [[ -n "$app_label" ]]; then
    log_debug "Found app.kubernetes.io/instance label: $app_label"

    # Check if Application exists with this name
    if kubectl get application "$app_label" -n "$ARGOCD_NAMESPACE" &>/dev/null; then
      echo "$app_label"
      return 0
    fi
  fi

  # Try 2: Fallback - search for Application with matching namespace
  log_debug "Fallback: Searching Applications with destination namespace: $rollout_namespace"

  local app_name=$(kubectl get applications -n "$ARGOCD_NAMESPACE" \
    -o json | jq -r --arg ns "$rollout_namespace" \
    '.items[] | select(.spec.destination.namespace == $ns) | .metadata.name' \
    | head -n1)

  if [[ -n "$app_name" ]]; then
    log_debug "Found Application by namespace match: $app_name"
    echo "$app_name"
    return 0
  fi

  log_error "Could not discover Application for Rollout: $rollout_name"
  return 1
}

# Extract repository information from Application
extract_repo_info() {
  local app_name=$1

  log_debug "Extracting repo info from Application: $app_name"

  local app_json=$(kubectl get application "$app_name" -n "$ARGOCD_NAMESPACE" -o json)

  # Check if multi-source application
  local sources_count=$(echo "$app_json" | jq -r '.spec.sources | length // 0')

  local repo_url=""
  local target_revision=""
  local path=""

  if [[ "$sources_count" -gt 0 ]]; then
    log_debug "Multi-source Application detected (sources: $sources_count)"

    repo_url=$(echo "$app_json" | jq -r '
      .spec.sources[] |
      select(.path != null and .path != "") |
      .repoURL' | head -n1)

    target_revision=$(echo "$app_json" | jq -r '
      .spec.sources[] |
      select(.path != null and .path != "") |
      .targetRevision' | head -n1)

    path=$(echo "$app_json" | jq -r '
      .spec.sources[] |
      select(.path != null and .path != "") |
      .path' | head -n1)
  else
    log_debug "Single-source Application detected"

    repo_url=$(echo "$app_json" | jq -r '.spec.source.repoURL')
    target_revision=$(echo "$app_json" | jq -r '.spec.source.targetRevision')
    path=$(echo "$app_json" | jq -r '.spec.source.path // ""')
  fi

  if [[ -z "$repo_url" || "$repo_url" == "null" ]]; then
    log_error "Failed to extract repoURL from Application: $app_name"
    return 1
  fi

  if [[ -z "$target_revision" || "$target_revision" == "null" ]]; then
    log_error "Failed to extract targetRevision from Application: $app_name"
    return 1
  fi

  log_info "Discovered repo info - URL: $repo_url, Branch: $target_revision, Path: $path"

  jq -n \
    --arg url "$repo_url" \
    --arg branch "$target_revision" \
    --arg path "$path" \
    '{repoUrl: $url, branch: $branch, path: $path}'
}

# Extract Image Updater alias from Application annotations
get_image_alias() {
  local app_name=$1

  log_debug "Extracting Image Updater alias from Application: $app_name"

  local image_list=$(kubectl get application "$app_name" -n "$ARGOCD_NAMESPACE" \
    -o jsonpath='{.metadata.annotations.argocd-image-updater\.argoproj\.io/image-list}' 2>/dev/null || echo "")

  if [[ -z "$image_list" ]]; then
    log_error "No image-list annotation found on Application: $app_name"
    return 1
  fi

  # Extract alias from "alias=registry/image" format
  local alias=$(echo "$image_list" | cut -d'=' -f1)

  if [[ -z "$alias" ]]; then
    log_error "Could not parse alias from image-list: $image_list"
    return 1
  fi

  log_debug "Found Image Updater alias: $alias"
  echo "$alias"
}

# Freeze Image Updater for a specific Application using ignore-tags
freeze_app_updates() {
  local app_name=$1
  local alias=$2

  log_info "Freezing Image Updater for app: $app_name (alias: $alias)"

  kubectl annotate application "$app_name" -n "$ARGOCD_NAMESPACE" \
    "argocd-image-updater.argoproj.io/${alias}.ignore-tags=*" \
    "rollback.acme.com/frozen=true" \
    "rollback.acme.com/frozen-at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --overwrite 2>&1 || log_warn "Failed to freeze app updates"
}

# Store the revert commit hash on the Application so we can detect new developer commits
store_frozen_commit() {
  local app_name=$1
  local commit_hash=$2

  kubectl annotate application "$app_name" -n "$ARGOCD_NAMESPACE" \
    "rollback.acme.com/frozen-commit=${commit_hash}" \
    --overwrite &>/dev/null || log_warn "Failed to store frozen commit hash"
}

# Unfreeze a specific Application (remove ignore-tags and frozen markers)
unfreeze_app() {
  local app_name=$1

  local alias
  if ! alias=$(get_image_alias "$app_name"); then
    log_warn "Cannot unfreeze $app_name - failed to get image alias"
    return 1
  fi

  log_info "Unfreezing Image Updater for app: $app_name (auto-resume: new developer commit detected)"

  kubectl annotate application "$app_name" -n "$ARGOCD_NAMESPACE" \
    "argocd-image-updater.argoproj.io/${alias}.ignore-tags-" \
    "rollback.acme.com/frozen-" \
    "rollback.acme.com/frozen-at-" \
    "rollback.acme.com/frozen-commit-" \
    &>/dev/null || log_warn "Failed to remove freeze annotations from $app_name"

  log_info "App $app_name unfrozen - Image Updater will resume on next cycle"
}

# Check frozen apps for new developer commits and auto-resume
check_frozen_apps() {
  log_debug "Checking frozen apps for new developer commits..."

  # Find all Applications with rollback.acme.com/frozen=true
  local frozen_apps=$(kubectl get applications -n "$ARGOCD_NAMESPACE" \
    -o json 2>/dev/null | jq -r '
      .items[] |
      select(.metadata.annotations["rollback.acme.com/frozen"] == "true") |
      .metadata.name
    ' 2>/dev/null)

  if [[ -z "$frozen_apps" ]]; then
    log_debug "No frozen apps found"
    return 0
  fi

  local git_token
  if ! git_token=$(get_git_credentials); then
    log_warn "Cannot check frozen apps - failed to get git credentials"
    return 1
  fi

  echo "$frozen_apps" | while read -r app_name; do
    [[ -z "$app_name" ]] && continue

    log_debug "Checking frozen app: $app_name"

    # Get the commit hash stored at freeze time
    local frozen_commit=$(kubectl get application "$app_name" -n "$ARGOCD_NAMESPACE" \
      -o jsonpath='{.metadata.annotations.rollback\.acme\.com/frozen-commit}' 2>/dev/null || echo "")

    if [[ -z "$frozen_commit" ]]; then
      log_debug "No frozen-commit annotation on $app_name, skipping auto-resume check"
      continue
    fi

    # Get repo info
    local repo_info
    if ! repo_info=$(extract_repo_info "$app_name"); then
      log_warn "Failed to extract repo info for frozen app: $app_name"
      continue
    fi

    local repo_url=$(echo "$repo_info" | jq -r '.repoUrl')
    local branch=$(echo "$repo_info" | jq -r '.branch')
    local auth_repo_url="${repo_url/https:\/\//https://oauth2:${git_token}@}"

    # Use git ls-remote to check HEAD without cloning (fast)
    local remote_head=$(git ls-remote "$auth_repo_url" "refs/heads/$branch" 2>/dev/null | awk '{print $1}')

    if [[ -z "$remote_head" ]]; then
      log_warn "Failed to get remote HEAD for $app_name ($branch)"
      continue
    fi

    # If HEAD is same as frozen commit, nothing new
    if [[ "$remote_head" == "$frozen_commit" ]]; then
      log_debug "No new commits on $app_name since freeze"
      continue
    fi

    # HEAD has moved - check if the new commit is a developer commit (not Image Updater)
    # Clone shallow to inspect the new commits
    local work_dir="/tmp/freeze-check-${app_name}-$$"
    if ! git clone --depth 10 -b "$branch" "$auth_repo_url" "$work_dir" &>/dev/null; then
      log_warn "Failed to clone repo for freeze check: $app_name"
      rm -rf "$work_dir"
      continue
    fi

    cd "$work_dir"

    # Get commits since the frozen commit, excluding Image Updater and Revert commits
    local developer_commits=$(git log "${frozen_commit}..HEAD" \
      --format="%H %an: %s" 2>/dev/null | \
      grep -v "argocd-image-updater" | \
      grep -iv "ArgoCD Rollback Controller" || echo "")

    rm -rf "$work_dir"

    if [[ -n "$developer_commits" ]]; then
      log_info "New developer commits detected on frozen app $app_name:"
      echo "$developer_commits" | while read -r line; do
        log_info "  $line"
      done >&2
      unfreeze_app "$app_name"
    else
      log_debug "Only Image Updater/rollback commits since freeze on $app_name, staying frozen"
    fi
  done
}

# Get git credentials from secret
get_git_credentials() {
  log_debug "Fetching git credentials from secret: $GIT_SECRET"

  local token=$(kubectl get secret "$GIT_SECRET" -n "$GIT_SECRET_NAMESPACE" \
    -o jsonpath='{.data.token}' 2>/dev/null | base64 -d)

  if [[ -z "$token" ]]; then
    log_error "Failed to get git token from secret: $GIT_SECRET"
    return 1
  fi

  echo "$token"
}

# Find latest Image Updater commit by author
find_image_updater_commit() {
  local repo_dir=$1
  local branch=$2

  log_debug "Searching for latest Image Updater commit on branch: $branch"

  cd "$repo_dir"

  # Find commit by author (only matches actual Image Updater commits, not reverts)
  local commit=$(git log "$branch" --author="argocd-image-updater" \
    --grep="automatic update" --format="%H" -n 1 2>/dev/null || echo "")

  if [[ -z "$commit" ]]; then
    # Fallback: search by commit message pattern, exclude reverts
    commit=$(git log "$branch" --format="%H %s" -n 20 | \
      grep -i "build: automatic update\|chore: automatic update" | \
      grep -iv "^[a-f0-9]* Revert" | \
      head -n1 | awk '{print $1}')
  fi

  if [[ -z "$commit" ]]; then
    log_error "Could not find Image Updater commit on branch: $branch"
    return 1
  fi

  log_info "Found Image Updater commit: $commit"
  echo "$commit"
}

# Perform rollback
perform_rollback() {
  local rollout_name=$1
  local rollout_namespace=$2

  log_info "Starting rollback for Rollout: $rollout_name in namespace: $rollout_namespace"

  # Step 1: Discover Application
  local app_name
  if ! app_name=$(discover_application "$rollout_name" "$rollout_namespace"); then
    log_error "Cannot proceed with rollback - Application discovery failed"
    return 1
  fi

  log_info "Discovered Application: $app_name"

  # Step 2: Get Image Updater alias for per-app freeze
  local image_alias
  if ! image_alias=$(get_image_alias "$app_name"); then
    log_error "Cannot proceed with rollback - Failed to get Image Updater alias"
    return 1
  fi

  # Step 3: Extract repo info
  local repo_info
  if ! repo_info=$(extract_repo_info "$app_name"); then
    log_error "Cannot proceed with rollback - Failed to extract repo info"
    return 1
  fi

  local repo_url=$(echo "$repo_info" | jq -r '.repoUrl')
  local branch=$(echo "$repo_info" | jq -r '.branch')

  # Step 4: Get git credentials
  local git_token
  if ! git_token=$(get_git_credentials); then
    log_error "Cannot proceed with rollback - Failed to get git credentials"
    return 1
  fi

  # Step 5: Prepare authenticated repo URL
  local auth_repo_url="${repo_url/https:\/\//https://oauth2:${git_token}@}"

  # Step 6: Clone repository
  local work_dir="/tmp/rollback-${rollout_name}-$$"
  mkdir -p "$work_dir"

  log_info "Cloning repository: $repo_url (branch: $branch)"

  if ! git clone --depth 50 -b "$branch" "$auth_repo_url" "$work_dir" &>/dev/null; then
    log_error "Failed to clone repository: $repo_url"
    rm -rf "$work_dir"
    return 1
  fi

  # Step 7: Find Image Updater commit
  local commit_to_revert
  if ! commit_to_revert=$(find_image_updater_commit "$work_dir" "$branch"); then
    log_error "Failed to find Image Updater commit"
    rm -rf "$work_dir"
    return 1
  fi

  # Step 8: Freeze Image Updater for this specific app (per-app, not global)
  freeze_app_updates "$app_name" "$image_alias"

  # Step 9: Perform git revert
  cd "$work_dir"

  git config user.name "$GIT_AUTHOR"
  git config user.email "$GIT_EMAIL"

  log_info "Reverting commit: $commit_to_revert"

  if ! git revert --no-edit "$commit_to_revert" &>/dev/null; then
    log_error "Git revert failed - may have conflicts"
    rm -rf "$work_dir"
    return 1
  fi

  # Amend the revert commit to add [skip ci] so it doesn't trigger a new pipeline
  git commit --amend -m "$(git log -1 --format=%s) [skip ci]" &>/dev/null

  # Step 10: Push revert commit
  log_info "Pushing revert commit to $branch"

  if ! git push "$auth_repo_url" "$branch" &>/dev/null; then
    log_error "Failed to push revert commit"
    rm -rf "$work_dir"
    return 1
  fi

  log_info "Rollback successful - revert commit pushed"

  # Step 11: Store the revert commit hash for auto-resume detection
  local revert_commit=$(cd "$work_dir" && git rev-parse HEAD 2>/dev/null || echo "")
  if [[ -n "$revert_commit" ]]; then
    store_frozen_commit "$app_name" "$revert_commit"
    log_info "Stored frozen commit: $revert_commit"
  fi

  log_info "Image Updater frozen for app $app_name (ignore-tags=*). Will auto-resume on new developer commit, or use 'Resume Updates' in ArgoCD UI."

  # Step 12: Clean up
  rm -rf "$work_dir"

  # Step 13: Remove rollback annotations from Rollout
  remove_rollback_annotations "$rollout_name" "$rollout_namespace"

  log_info "Rollback process completed successfully"
  return 0
}

# Scan for Rollouts with rollback annotation on a specific cluster
scan_cluster_for_rollbacks() {
  local cluster_name=$1
  local server=$2
  local token=$3

  log_debug "Scanning cluster: $cluster_name"

  local kubectl_cmd="kubectl"
  local kubectl_args=""

  if [[ "$server" != "local" ]]; then
    kubectl_args="--server=$server --token=$token --insecure-skip-tls-verify"
  fi

  rollouts_json=$($kubectl_cmd get rollouts --all-namespaces $kubectl_args -o json 2>/dev/null || echo '{"items":[]}')

  echo "$rollouts_json" | jq -r '
    .items[] |
    select(.metadata.annotations["rollback.acme.com/requested"] != null) |
    "\(.metadata.namespace) \(.metadata.name)"
  ' 2>/dev/null | while read -r namespace name; do
    if [[ -n "$namespace" && -n "$name" ]]; then
      log_info "Found rollback request on $cluster_name: $name in namespace: $namespace"

      export CLUSTER_NAME="$cluster_name"
      export CLUSTER_SERVER="$server"
      export CLUSTER_TOKEN="$token"
      perform_rollback "$name" "$namespace" || true
      unset CLUSTER_NAME CLUSTER_SERVER CLUSTER_TOKEN
    fi
  done

  return 0
}

# Remove rollback annotations from Rollout (supports both local and remote clusters)
remove_rollback_annotations() {
  local rollout_name=$1
  local rollout_namespace=$2

  log_info "Removing rollback request annotations from Rollout"

  local kubectl_cmd="kubectl patch rollout $rollout_name -n $rollout_namespace"
  local kubectl_args=""

  if [[ -n "${CLUSTER_SERVER:-}" && "$CLUSTER_SERVER" != "local" ]]; then
    kubectl_args="--server=$CLUSTER_SERVER --token=$CLUSTER_TOKEN --insecure-skip-tls-verify"
  fi

  $kubectl_cmd $kubectl_args \
    --type=json -p='[
      {"op": "remove", "path": "/metadata/annotations/rollback.acme.com~1requested"},
      {"op": "remove", "path": "/metadata/annotations/rollback.acme.com~1requested-by"}
    ]' &>/dev/null || log_warn "Failed to remove rollback annotations"
}

# Main controller loop
main() {
  log_info "Rollback Controller started (Multi-Cluster Mode, Per-App Freeze)"
  log_info "Configuration: ArgoCD NS=$ARGOCD_NAMESPACE"
  log_info "Polling interval: ${POLL_INTERVAL}s"

  while true; do
    log_debug "Checking for rollback requests across all clusters..."

    # Check frozen apps for new developer commits (auto-resume)
    check_frozen_apps || log_warn "Failed to check frozen apps"

    # Scan local cluster
    scan_cluster_for_rollbacks "local-cluster" "local" "" || log_warn "Failed to scan local cluster"

    # Discover and scan remote clusters (secrets with label component=cluster-credentials)
    cluster_secrets=$(kubectl get secrets -n "$ARGOCD_NAMESPACE" \
      -l app=rollback-controller,component=automation \
      -o json 2>/dev/null || echo '{"items":[]}')

    # Filter to only secrets that have a 'server' key (cluster credentials, not git creds)
    echo "$cluster_secrets" | jq -r '.items[] | select(.data.server != null) | @json' | while read -r secret_json; do
      cluster_name=$(echo "$secret_json" | jq -r '.data.name // .metadata.name' 2>/dev/null)
      cluster_name=$(echo "$cluster_name" | base64 -d 2>/dev/null || echo "$cluster_name")
      server=$(echo "$secret_json" | jq -r '.data.server' 2>/dev/null | base64 -d 2>/dev/null || echo "")
      token=$(echo "$secret_json" | jq -r '.data.token' 2>/dev/null | base64 -d 2>/dev/null || echo "")

      if [[ -n "$server" && -n "$token" ]]; then
        log_debug "Scanning remote cluster: $cluster_name (${server:0:50}...)"
        scan_cluster_for_rollbacks "$cluster_name" "$server" "$token" || log_warn "Failed to scan cluster $cluster_name"
      else
        log_warn "Skipping cluster $cluster_name - missing server or token"
      fi
    done

    sleep "$POLL_INTERVAL"
  done
}

# Run main loop
main
