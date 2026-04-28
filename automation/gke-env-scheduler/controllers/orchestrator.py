"""Orchestrator for coordinating environment operations"""

import logging
import os
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from .k8s_controller import K8sController
from .gke_controller import GKEController
from .cloudsql_controller import CloudSQLController
from .argocd_controller import ArgoCDController
from .gke_utils import list_node_pools_status

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# State directory for saving PDB configs
STATE_DIR = Path.home() / '.dev-env-manager'
STATE_DIR.mkdir(exist_ok=True)


# Import kubectl-based PDB functions from mgmt_manual_stop_start
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from mgmt_manual_stop_start import backup_pdbs, patch_pdbs_to_zero, restore_pdbs
    KUBECTL_PDB_AVAILABLE = True
except ImportError:
    KUBECTL_PDB_AVAILABLE = False
    logger.warning("kubectl-based PDB functions not available")


class Orchestrator:
    """Coordinates all environment operations"""
    
    def __init__(self):
        """Initialize orchestrator with environment configurations"""
        self.environments = self._load_environment_configs()
        self.env_groups = self._load_environment_groups()
        self.cloudsql_dependencies = self._build_cloudsql_dependencies()
        logger.info(f"Orchestrator initialized with {len(self.environments)} environments")
        if self.env_groups:
            logger.info(f"Environment groups: {self.env_groups}")
        if self.cloudsql_dependencies:
            logger.info(f"CloudSQL shared instances: {self.cloudsql_dependencies}")
    
    def _build_cloudsql_dependencies(self) -> dict:
        """
        Build a map of CloudSQL instances to environments that depend on them.
        Returns: {instance_name: [env1, env2, ...]}
        """
        dependencies = {}
        for env_name, config in self.environments.items():
            cloudsql_instances = [i.strip() for i in config.get('cloudsql_instances', []) if i.strip()]
            for instance in cloudsql_instances:
                if instance not in dependencies:
                    dependencies[instance] = []
                dependencies[instance].append(env_name)
        
        # Filter to only show shared instances (used by multiple envs)
        shared = {k: v for k, v in dependencies.items() if len(v) > 1}
        return shared
    
    def _can_stop_cloudsql(self, instance_name: str, current_env: str) -> dict:
        """
        Check if a CloudSQL instance can be stopped.
        If it's shared with other environments, check if all are stopped.
        
        Returns:
            dict with 'can_stop' (bool), 'reason' (str), 'dependent_envs' (list)
        """
        # If not a shared instance, can always stop
        if instance_name not in self.cloudsql_dependencies:
            return {
                'can_stop': True,
                'reason': 'Not shared with other environments',
                'dependent_envs': []
            }
        
        # Get all environments that share this instance
        dependent_envs = self.cloudsql_dependencies[instance_name]
        other_envs = [e for e in dependent_envs if e != current_env]
        
        if not other_envs:
            return {
                'can_stop': True,
                'reason': 'No other dependent environments',
                'dependent_envs': []
            }
        
        # Check if all other dependent environments are stopped (all nodes at 0)
        running_envs = []
        for env in other_envs:
            config = self.environments.get(env)
            if not config:
                continue
            
            try:
                gke = GKEController(config['project_id'], config['cluster_location'], config['cluster_name'])
                total_nodes = 0
                
                for node_pool in config['node_pools']:
                    node_pool = node_pool.strip()
                    if node_pool:
                        status = gke.get_node_pool_status(node_pool)
                        if status.get('success'):
                            total_nodes += status.get('node_count', 0)
                
                if total_nodes > 0:
                    running_envs.append(env)
            except Exception as e:
                logger.warning(f"Could not check status of {env}: {e}")
                # Assume it's running to be safe
                running_envs.append(env)
        
        if running_envs:
            return {
                'can_stop': False,
                'reason': f'Still in use by running environments: {", ".join(running_envs)}',
                'dependent_envs': running_envs
            }
        
        return {
            'can_stop': True,
            'reason': 'All dependent environments are stopped',
            'dependent_envs': other_envs
        }
    
    def _load_environment_configs(self) -> dict:
        """Load all environment configurations from environment variables"""
        envs = {}
        
        # Get list of active environments
        active_envs = os.getenv('ENVIRONMENTS', '').split(',')
        
        for env_name in active_envs:
            env_name = env_name.strip().upper().replace('-', '_')
            if not env_name:
                continue
            
            # Load configuration for this environment
            config = {
                'project_id': os.getenv(f'{env_name}_PROJECT_ID'),
                'cluster_name': os.getenv(f'{env_name}_CLUSTER_NAME'),
                'cluster_location': os.getenv(f'{env_name}_CLUSTER_LOCATION'),  # Changed from CLUSTER_ZONE to support both zonal and regional
                'namespace': os.getenv(f'{env_name}_NAMESPACE'),
                'argocd_projects': os.getenv(f'{env_name}_ARGOCD_PROJECTS', '').split(','),  # ArgoCD Projects (not Apps)
                'cloudsql_instances': os.getenv(f'{env_name}_CLOUDSQL_INSTANCES', '').split(','),  # Support multiple instances
                'node_pools': os.getenv(f'{env_name}_NODE_POOLS', '').split(','),
                'min_nodes': [int(n) for n in os.getenv(f'{env_name}_MIN_NODES', '1').split(',')],  # Minimum nodes for autoscaling during normal operation
                'max_nodes': [int(n) for n in os.getenv(f'{env_name}_MAX_NODES', '10').split(',')]  # Maximum nodes for autoscaling
            }
            
            # Validate configuration
            if config['project_id'] and config['namespace']:
                envs[env_name.lower()] = config
                logger.info(f"Loaded config for {env_name.lower()}: {config['namespace']} in {config['project_id']}")
        
        return envs

    def _load_environment_groups(self) -> dict:
        """
        Load environment group definitions.
        Groups allow multiple clusters to be managed as a single logical environment.

        Format in .env: ENV_GROUPS=qa:qa-consumer+qa-enterprise,uat:uat-consumer+uat-enterprise,mgmt:mgmt-dev

        Returns:
            dict: {group_name: [cluster1, cluster2, ...]}
        """
        groups = {}
        env_groups_str = os.getenv('ENV_GROUPS', '')

        if not env_groups_str:
            return groups

        for group_def in env_groups_str.split(','):
            group_def = group_def.strip()
            if ':' not in group_def:
                continue

            group_name, clusters_str = group_def.split(':', 1)
            group_name = group_name.strip().lower()

            # Parse clusters (separated by +)
            clusters = [c.strip().lower().replace('-', '_') for c in clusters_str.split('+') if c.strip()]

            if clusters:
                groups[group_name] = clusters
                logger.info(f"Loaded environment group '{group_name}': {clusters}")

        return groups

    def list_environments(self):
        """
        List all environments (groups if defined, otherwise individual clusters)

        Returns:
            list: Environment names to display in UI
        """
        if self.env_groups:
            # Return group names if groups are defined
            return sorted(self.env_groups.keys())
        else:
            # Return individual environment names
            return sorted(self.environments.keys())

    def _resolve_environment(self, env_name: str) -> list:
        """
        Resolve an environment name to a list of actual cluster environments.

        If env_name is a group, returns all clusters in the group.
        Otherwise, returns the single environment.

        Args:
            env_name: Environment or group name

        Returns:
            list: List of actual environment names to operate on
        """
        env_name_normalized = env_name.lower().replace('-', '_')

        # Check if it's a group
        if env_name_normalized in self.env_groups:
            return self.env_groups[env_name_normalized]

        # Check if it's a direct environment
        if env_name_normalized in self.environments:
            return [env_name_normalized]

        # Not found
        return []

    def stop_environment(self, env_name: str) -> dict:
        """
        Stop all resources for an environment or group.

        If env_name is a group (e.g., 'uat'), stops all clusters in the group.
        If env_name is a single environment, stops that environment.

        Sequence (per cluster):
        1. Disable ArgoCD auto-sync
        2. Suspend CronJobs
        3. Delete PodDisruptionBudgets
        4. Scale deployments to 0
        5. Scale statefulsets to 0
        6. Stop CloudSQL instance
        7. Scale node pools to 0

        Args:
            env_name: Environment or group name (e.g., 'uat', 'qa', 'mgmt-dev')

        Returns:
            dict with operation results
        """
        # Resolve to actual environments
        env_list = self._resolve_environment(env_name)

        if not env_list:
            return {'success': False, 'error': f'Environment or group {env_name} not found'}

        # If it's a group with multiple environments, stop each one
        if len(env_list) > 1:
            logger.info(f"========== STOPPING GROUP: {env_name} ({len(env_list)} clusters) ==========")
            group_results = {'environment': env_name, 'is_group': True, 'clusters': []}

            all_success = True
            for cluster_env in env_list:
                logger.info(f"\n--- Stopping cluster: {cluster_env} ---")
                result = self._stop_single_environment(cluster_env)
                group_results['clusters'].append(result)
                if not result.get('success'):
                    all_success = False

            group_results['success'] = all_success
            if all_success:
                group_results['message'] = f'Successfully stopped all {len(env_list)} clusters in {env_name}'
            else:
                group_results['message'] = f'Stopped {env_name} with some errors - check individual cluster results'

            logger.info(f"========== GROUP STOP COMPLETED: {env_name} ==========\n")
            return group_results
        else:
            # Single environment
            return self._stop_single_environment(env_list[0])

    def _stop_single_environment(self, env_name: str) -> dict:
        """
        Stop a single environment with proper sequence and validation.
        
        STOP SEQUENCE:
        1. Disable autoscaling on ALL node pools → validate
        2. Apply ArgoCD DENY sync windows → validate
        3. Suspend CronJobs → validate
        4. Scale Elastic operator STS to 0 (consumer-uat, qa-consumer only) → validate
        5. Patch ALL PDBs to 0 → validate
        6. Scale ALL nodes to 0 → validate
        7. Stop CloudSQL instances (with dependency check) → validate
        
        Each step is idempotent - skips if already done.
        Each step validates completion before proceeding.

        Args:
            env_name: Normalized environment name

        Returns:
            dict with operation results
        """
        if env_name not in self.environments:
            return {'success': False, 'error': f'Environment {env_name} not found'}

        config = self.environments[env_name]
        results = {'environment': env_name, 'steps': [], 'logs': []}
        
        def add_log(level, message):
            """Add log entry to results"""
            logger.log(getattr(logging, level.upper()), message)
            results['logs'].append({'level': level, 'message': message})
        
        try:
            add_log('INFO', f"========== STOPPING ENVIRONMENT: {env_name} ==========")
            
            # Construct cluster context
            cluster_context = f"gke_{config['project_id']}_{config['cluster_location']}_{config['cluster_name']}"
            
            # Determine if ArgoCD-managed
            argocd_projects = [p.strip() for p in config.get('argocd_projects', []) if p.strip()]
            has_argocd = len(argocd_projects) > 0
            
            # Initialize GKE controller
            gke = GKEController(config['project_id'], config['cluster_location'], config['cluster_name'])
            
            # ============================================================
            # STEP 1: DISABLE AUTOSCALING (FIRST - CRITICAL)
            # ============================================================
            add_log('INFO', "STEP 1: Disabling autoscaling on all node pools")
            
            autoscaling_disabled = {}
            for node_pool in config['node_pools']:
                node_pool = node_pool.strip()
                if not node_pool:
                    continue
                
                # Check current status
                status = gke.get_node_pool_status(node_pool)
                if not status.get('success'):
                    add_log('ERROR', f"  ✗ Failed to get status for {node_pool}: {status.get('error')}")
                    autoscaling_disabled[node_pool] = False
                    continue
                
                autoscaling_enabled = status.get('autoscaling', {}).get('enabled', False)
                
                if autoscaling_enabled:
                    add_log('INFO', f"  → Disabling autoscaling for {node_pool}")
                    result = gke.set_autoscaling(node_pool, min_nodes=0, max_nodes=0, enabled=False)
                    results['steps'].append({'step': f'autoscaling_disable_{node_pool}', 'result': result})
                    
                    if result.get('success'):
                        add_log('INFO', f"  ✓ Autoscaling disabled for {node_pool}")
                        autoscaling_disabled[node_pool] = True
                    else:
                        add_log('ERROR', f"  ✗ Failed to disable autoscaling for {node_pool}: {result.get('error')}")
                        autoscaling_disabled[node_pool] = False
                else:
                    add_log('INFO', f"  ✓ Autoscaling already disabled for {node_pool}")
                    autoscaling_disabled[node_pool] = True
            
            # VALIDATION: All autoscaling must be disabled before proceeding
            if not all(autoscaling_disabled.values()):
                failed_pools = [p for p, disabled in autoscaling_disabled.items() if not disabled]
                error_msg = f"STOP ABORTED: Autoscaling disable failed for: {failed_pools}. Fix this before proceeding."
                add_log('ERROR', error_msg)
                return {
                    'success': False,
                    'environment': env_name,
                    'error': error_msg,
                    'steps': results['steps'],
                    'logs': results['logs']
                }
            
            add_log('INFO', "✓ STEP 1 COMPLETE: All autoscaling disabled")
            
            # ============================================================
            # STEP 2: ARGOCD SYNC WINDOWS (QA/UAT only)
            # ============================================================
            if has_argocd:
                add_log('INFO', f"STEP 2: Adding DENY sync windows to ArgoCD projects: {argocd_projects}")
                
                # Get ArgoCD cluster context
                argocd_project_id = os.getenv('ARGOCD_PROJECT_ID', config['project_id'])
                argocd_cluster_name = os.getenv('ARGOCD_CLUSTER_NAME', config['cluster_name'])
                argocd_cluster_location = os.getenv('ARGOCD_CLUSTER_LOCATION', config['cluster_location'])
                argocd_context = f"gke_{argocd_project_id}_{argocd_cluster_location}_{argocd_cluster_name}"
                
                add_log('INFO', f"  Using ArgoCD server context: {argocd_context}")
                
                argocd = ArgoCDController(context=argocd_context)
                sync_window_success = True
                
                for project in argocd_projects:
                    result = argocd.add_sync_window(project, duration_hours=12, window_kind='deny')
                    results['steps'].append({'step': f'argocd_sync_window_{project}', 'result': result})
                    
                    if result.get('success'):
                        add_log('INFO', f"  ✓ DENY sync window added for {project}")
                    else:
                        add_log('ERROR', f"  ✗ Failed to add sync window for {project}: {result.get('error')}")
                        sync_window_success = False
                
                # VALIDATION: Sync windows should be added (but not critical - can continue)
                if not sync_window_success:
                    add_log('WARNING', "  ⚠ Some sync windows failed, but continuing...")
                else:
                    add_log('INFO', "✓ STEP 2 COMPLETE: ArgoCD sync windows applied")
            
            # ============================================================
            # STEP 3: SUSPEND CRONJOBS (QA/UAT only)
            # ============================================================
            if has_argocd:
                add_log('INFO', f"STEP 3: Suspending CronJobs in namespace {config.get('namespace', 'default')}")
                
                k8s = K8sController(config.get('namespace', 'default'), context=cluster_context)
                result = k8s.suspend_all_cronjobs()
                results['steps'].append({'step': 'cronjobs_suspend', 'result': result})
                
                if result.get('success'):
                    suspended_count = result.get('suspended_count', 0)
                    add_log('INFO', f"  ✓ Suspended {suspended_count} CronJob(s)")
                    add_log('INFO', "✓ STEP 3 COMPLETE: CronJobs suspended")
                else:
                    add_log('WARNING', f"  ⚠ CronJob suspension had issues: {result.get('error')}, but continuing...")
            
            # ============================================================
            # STEP 4: SCALE ELASTIC OPERATOR (consumer-uat, qa-consumer ONLY)
            # ============================================================
            if has_argocd and 'consumer' in env_name:
                add_log('INFO', "STEP 4: Scaling down Elastic operator StatefulSet")
                
                try:
                    from kubernetes import client as k8s_client, config as k8s_config
                    k8s_config.load_kube_config(context=cluster_context)
                    apps_api = k8s_client.AppsV1Api()
                    
                    operator_namespaces = ['elastic-system', 'elastic-operator', 'default']
                    operator_names = ['elastic-operator', 'eck-operator']
                    scaled_count = 0
                    
                    # Scale StatefulSets
                    for ns in operator_namespaces:
                        for op_name in operator_names:
                            try:
                                sts = apps_api.read_namespaced_stateful_set(name=op_name, namespace=ns)
                                if sts and sts.spec.replicas > 0:
                                    add_log('INFO', f"  → Scaling {op_name} STS in {ns} to 0 replicas")
                                    sts.spec.replicas = 0
                                    apps_api.patch_namespaced_stateful_set(name=op_name, namespace=ns, body=sts)
                                    add_log('INFO', f"  ✓ Scaled {op_name} STS to 0")
                                    scaled_count += 1
                            except Exception:
                                pass  # Operator doesn't exist
                    
                    if scaled_count > 0:
                        add_log('INFO', f"  Waiting 10 seconds for operator pods to terminate...")
                        import time
                        time.sleep(10)
                        add_log('INFO', "✓ STEP 4 COMPLETE: Elastic operator scaled down")
                    else:
                        add_log('INFO', "  ✓ No Elastic operators found or already scaled")
                        
                except Exception as e:
                    add_log('WARNING', f"  ⚠ Could not scale Elastic operator: {e}, but continuing...")
            
            # ============================================================
            # STEP 5 (UAT/QA) or STEP 2 (MGMT): PATCH ALL PDBS TO 0
            # ============================================================
            step_label = "STEP 5" if has_argocd else "STEP 2"
            add_log('INFO', f"{step_label}: Auto-discovering and patching PDBs across all namespaces")
            add_log('INFO', f"  Timeout: 120 seconds for entire operation")
            
            all_pdbs_saved = []
            total_patched = 0
            
            import threading
            import time
            
            timeout_occurred = threading.Event()
            start_time = time.time()
            
            def check_timeout():
                elapsed = time.time() - start_time
                if elapsed > 120:
                    timeout_occurred.set()
                    return True
                return False
            
            try:
                from kubernetes import client as k8s_client, config as k8s_config
                
                add_log('INFO', f"  Loading kubeconfig with context: {cluster_context}")
                k8s_config.load_kube_config(context=cluster_context)
                
                add_log('INFO', f"  Initializing Kubernetes API clients...")
                # Set a timeout for API calls to prevent hanging
                configuration = k8s_client.Configuration()
                configuration.connection_pool_maxsize = 10
                
                core_api = k8s_client.CoreV1Api(k8s_client.ApiClient(configuration))
                policy_api = k8s_client.PolicyV1Api(k8s_client.ApiClient(configuration))
                
                add_log('INFO', f"  Fetching namespace list (with timeout)...")
                all_namespaces = core_api.list_namespace(_request_timeout=30)
                add_log('INFO', f"  Found {len(all_namespaces.items)} namespaces to scan")
                
                namespaces_scanned = 0
                namespaces_with_pdbs = 0
                
                for ns_obj in all_namespaces.items:
                    # Check for timeout before processing each namespace
                    if check_timeout():
                        raise TimeoutError("PDB patching exceeded 120 second timeout")
                    
                    ns = ns_obj.metadata.name
                    
                    # Don't skip any namespaces - check all of them
                    # (Previously skipped kube-system, kube-public, kube-node-lease)
                    
                    try:
                        pdbs = policy_api.list_namespaced_pod_disruption_budget(namespace=ns)
                        namespaces_scanned += 1
                        
                        if pdbs.items:
                            namespaces_with_pdbs += 1
                            pdb_names = [pdb.metadata.name for pdb in pdbs.items]
                            add_log('INFO', f"  → Found {len(pdbs.items)} PDB(s) in namespace '{ns}': {', '.join(pdb_names)}")
                            
                            k8s = K8sController(ns, context=cluster_context)
                            pdb_result = k8s.save_and_patch_pdbs_to_zero()
                            
                            if pdb_result.get('success'):
                                saved_configs = pdb_result.get('saved_configs', [])
                                patched_count = pdb_result.get('patched_count', 0)
                                all_pdbs_saved.extend(saved_configs)
                                total_patched += patched_count
                                add_log('INFO', f"  ✓ Successfully patched {patched_count}/{len(pdbs.items)} PDB(s) in '{ns}'")
                            else:
                                add_log('ERROR', f"  ✗ Failed to patch PDBs in '{ns}': {pdb_result.get('error')}")
                                
                    except Exception as e:
                        error_msg = str(e)
                        if "Forbidden" in error_msg or "forbidden" in error_msg:
                            add_log('DEBUG', f"  ⊘ Skipping namespace '{ns}' (permission denied)")
                        else:
                            add_log('WARNING', f"  ⚠ Error accessing namespace '{ns}': {error_msg}")
                            namespaces_scanned += 1
                
                add_log('INFO', f"  Scanned {namespaces_scanned} namespaces, found PDBs in {namespaces_with_pdbs} namespaces")
                
                # Save PDB state
                state_file = STATE_DIR / f'{env_name}-pdb-state.json'
                with open(state_file, 'w') as f:
                    json.dump({'pdbs': all_pdbs_saved}, f, indent=2, default=str)
                
                add_log('INFO', f"✓ {step_label} COMPLETE: Patched {total_patched} PDB(s), state saved")
                results['steps'].append({
                    'step': 'pdb_patch',
                    'result': {'success': True, 'message': f'Patched {total_patched} PDBs'}
                })
                
            except Exception as e:
                error_msg = str(e)
                add_log('ERROR', f"  ✗ PDB patching failed: {error_msg}")
                
                # Add helpful context for common errors
                if "127.0.0.1" in error_msg or "localhost" in error_msg:
                    add_log('ERROR', f"  ⚠ Kubeconfig is pointing to localhost! Run: ./fix_all_kubeconfig.sh")
                elif "Connection refused" in error_msg:
                    add_log('ERROR', f"  ⚠ Cannot connect to cluster. Check SOCKS proxy and kubeconfig.")
                elif "Timeout" in error_msg or "timeout" in error_msg or "120 second" in error_msg:
                    add_log('ERROR', f"  ⚠ PDB patching timed out after 120 seconds. Moving to next step.")
                
                results['steps'].append({
                    'step': 'pdb_patch',
                    'result': {'success': False, 'error': error_msg}
                })
                
                add_log('WARNING', f"  ⚠ Continuing to next step despite PDB patching failure...")
            
            # ============================================================
            # STEP 6 (UAT/QA) or STEP 3 (MGMT): SCALE ALL NODES TO 0
            # ============================================================
            step_label = "STEP 6" if has_argocd else "STEP 3"
            add_log('INFO', f"{step_label}: Scaling all node pools to 0")
            
            nodes_scaled = {}
            for node_pool in config['node_pools']:
                node_pool = node_pool.strip()
                if not node_pool:
                    continue
                
                # Check current node count (will check ALL instance groups for regional clusters)
                add_log('DEBUG', f"  → Checking actual node count for {node_pool}...")
                status = gke.get_node_pool_status(node_pool, skip_compute_api=False)  # Force real count
                
                if not status.get('success'):
                    add_log('ERROR', f"  ✗ Failed to get status for {node_pool}: {status.get('error')}")
                    nodes_scaled[node_pool] = False
                    continue
                
                current_count = status.get('node_count', -1)
                initial_count = status.get('initial_node_count', 'unknown')
                
                add_log('DEBUG', f"  → {node_pool}: actual_running={current_count}, config_size={initial_count}")
                
                if current_count == 0:
                    add_log('INFO', f"  ✓ {node_pool} already at 0 nodes (verified across all zones)")
                    nodes_scaled[node_pool] = True
                elif current_count > 0:
                    add_log('INFO', f"  → Scaling {node_pool} from {current_count} nodes to 0")
                    result = gke.scale_node_pool(node_pool, 0, wait=True)
                    results['steps'].append({'step': f'nodepool_scale_{node_pool}', 'result': result})
                    
                    if result.get('success'):
                        add_log('INFO', f"  ✓ {node_pool} scaled to 0 successfully")
                        nodes_scaled[node_pool] = True
                    else:
                        add_log('ERROR', f"  ✗ Failed to scale {node_pool}: {result.get('error')}")
                        nodes_scaled[node_pool] = False
                else:
                    add_log('WARNING', f"  ⚠ Could not determine node count for {node_pool} (returned {current_count})")
                    nodes_scaled[node_pool] = False
            
            # VALIDATION: All nodes should be at 0
            if not all(nodes_scaled.values()):
                failed_pools = [p for p, scaled in nodes_scaled.items() if not scaled]
                add_log('ERROR', f"  ✗ Some node pools failed to scale: {failed_pools}")
            else:
                add_log('INFO', f"✓ {step_label} COMPLETE: All nodes scaled to 0")
            
            # ============================================================
            # STEP 7: STOP CLOUDSQL (LAST - with dependency check)
            # ============================================================
            cloudsql_instances = [i.strip() for i in config.get('cloudsql_instances', []) if i.strip()]
            if cloudsql_instances:
                add_log('INFO', f"STEP 7: Checking CloudSQL instances: {cloudsql_instances}")
                
                sql = CloudSQLController(config['project_id'])
                for instance in cloudsql_instances:
                    can_stop_check = self._can_stop_cloudsql(instance, env_name)
                    
                    if can_stop_check['can_stop']:
                        add_log('INFO', f"  → Stopping CloudSQL '{instance}': {can_stop_check['reason']}")
                        result = sql.stop_instance(instance, wait=False)
                        results['steps'].append({'step': f'cloudsql_stop_{instance}', 'result': result})
                        
                        if result.get('success'):
                            add_log('INFO', f"  ✓ CloudSQL '{instance}' stop initiated")
                        else:
                            add_log('WARNING', f"  ⚠ CloudSQL '{instance}' stop failed: {result.get('error')}")
                    else:
                        add_log('WARNING', f"  ⊘ Skipping CloudSQL '{instance}': {can_stop_check['reason']}")
                        results['steps'].append({
                            'step': f'cloudsql_stop_{instance}',
                            'result': {
                                'success': True,
                                'skipped': True,
                                'message': can_stop_check['reason']
                            }
                        })
                
                add_log('INFO', "✓ STEP 7 COMPLETE: CloudSQL operations completed")
            
            # ============================================================
            # FINAL VALIDATION
            # ============================================================
            add_log('INFO', f"========== STOP COMPLETED: {env_name} ==========")
            
            critical_failures = [s for s in results['steps'] if not s['result'].get('success') and not s['result'].get('skipped')]
            results['success'] = len(critical_failures) == 0
            results['message'] = f"Environment {env_name} stopped successfully" if results['success'] else f"Some steps failed for {env_name}"
            
            return results
            
        except Exception as e:
            add_log('ERROR', f"FATAL ERROR stopping {env_name}: {e}")
            return {
                'success': False,
                'environment': env_name,
                'error': str(e),
                'steps': results['steps'],
                'logs': results['logs']
            }
    
    def start_environment(self, env_name: str) -> dict:
        """
        Start all resources for an environment or group.

        If env_name is a group (e.g., 'uat'), starts all clusters in the group.
        If env_name is a single environment, starts that environment.

        Sequence (per cluster):
        1. Start CloudSQL instance (parallel, takes longest)
        2. Scale node pools to desired size
        3. Enable ArgoCD auto-sync
        4. Trigger ArgoCD sync (workloads will come back via ArgoCD)
        5. Resume CronJobs

        Args:
            env_name: Environment or group name (e.g., 'uat', 'qa', 'mgmt-dev')

        Returns:
            dict with operation results
        """
        # Resolve to actual environments
        env_list = self._resolve_environment(env_name)

        if not env_list:
            return {'success': False, 'error': f'Environment or group {env_name} not found'}

        # If it's a group with multiple environments, start each one
        if len(env_list) > 1:
            logger.info(f"========== STARTING GROUP: {env_name} ({len(env_list)} clusters) ==========")
            group_results = {'environment': env_name, 'is_group': True, 'clusters': []}

            all_success = True
            for cluster_env in env_list:
                logger.info(f"\n--- Starting cluster: {cluster_env} ---")
                result = self._start_single_environment(cluster_env)
                group_results['clusters'].append(result)
                if not result.get('success'):
                    all_success = False

            group_results['success'] = all_success
            if all_success:
                group_results['message'] = f'Successfully started all {len(env_list)} clusters in {env_name}'
            else:
                group_results['message'] = f'Started {env_name} with some errors - check individual cluster results'

            logger.info(f"========== GROUP START COMPLETED: {env_name} ==========\n")
            return group_results
        else:
            # Single environment
            return self._start_single_environment(env_list[0])

    def _start_single_environment(self, env_name: str) -> dict:
        """
        Start a single environment (internal method).

        Args:
            env_name: Normalized environment name

        Returns:
            dict with operation results
        """
        if env_name not in self.environments:
            return {'success': False, 'error': f'Environment {env_name} not found'}

        config = self.environments[env_name]
        results = {'environment': env_name, 'steps': []}
        
        try:
            logger.info(f"========== STARTING ENVIRONMENT: {env_name} ==========")
            
            # Check if environment is already running
            logger.info(f"Checking current state of {env_name}...")
            gke = GKEController(config['project_id'], config['cluster_location'], config['cluster_name'])
            
            all_running = True
            total_nodes = 0
            autoscaling_enabled_count = 0
            
            for idx, node_pool in enumerate(config['node_pools']):
                node_pool = node_pool.strip()
                if node_pool:
                    status = gke.get_node_pool_status(node_pool)
                    if status.get('success'):
                        node_count = status.get('node_count', 0)
                        total_nodes += node_count
                        
                        autoscaling = status.get('autoscaling', {})
                        is_enabled = autoscaling.get('enabled', False)
                        
                        if is_enabled:
                            autoscaling_enabled_count += 1
                            
                        # Check if this pool has desired min nodes
                        expected_min = config['min_nodes'][idx] if idx < len(config['min_nodes']) else 1
                        if not is_enabled or node_count < expected_min:
                            all_running = False
            
            # If all pools have autoscaling enabled and at least some nodes are running, consider it running
            if all_running and autoscaling_enabled_count == len([p for p in config['node_pools'] if p.strip()]) and total_nodes > 0:
                logger.info(f"Environment {env_name} is already running ({total_nodes} nodes, autoscaling enabled)")
                return {
                    'success': True,
                    'environment': env_name,
                    'message': f'Environment {env_name} is already running with {total_nodes} nodes',
                    'steps': []
                }
            
            logger.info(f"Environment {env_name} needs to be started (current: {total_nodes} nodes, {autoscaling_enabled_count} pools with autoscaling), proceeding...")
            
            # Step 1: Start CloudSQL instances (don't wait, they're slow)
            # For shared instances, this is safe - starting an already-running instance is a no-op
            cloudsql_instances = [i.strip() for i in config.get('cloudsql_instances', []) if i.strip()]
            if cloudsql_instances:
                logger.info(f"Step 1: Starting CloudSQL instances: {cloudsql_instances}")
                sql = CloudSQLController(config['project_id'])
                for instance in cloudsql_instances:
                    # Check if shared
                    if instance in self.cloudsql_dependencies:
                        logger.info(f"  ℹ CloudSQL instance '{instance}' is shared with: {self.cloudsql_dependencies[instance]}")
                    
                    result = sql.start_instance(instance, wait=False)
                    results['steps'].append({'step': f'cloudsql_start_{instance}', 'result': result})
            
            # Step 2: Restore autoscaling settings (let autoscaler bring nodes back)
            logger.info("Step 2: Restoring autoscaling settings for node pools")

            argocd_projects = [p.strip() for p in config.get('argocd_projects', []) if p.strip()]
            has_argocd = len(argocd_projects) > 0

            gke = GKEController(config['project_id'], config['cluster_location'], config['cluster_name'])
            for idx, node_pool in enumerate(config['node_pools']):
                node_pool = node_pool.strip()
                if not node_pool:
                    continue

                # Restore autoscaling with configured min/max from .env
                min_nodes = config['min_nodes'][idx] if idx < len(config['min_nodes']) else 1
                max_nodes = config['max_nodes'][idx] if idx < len(config['max_nodes']) else 10

                # For both MGMT and QA/UAT, we want autoscaling ENABLED during normal operation
                logger.info(
                    f"Environment {env_name}: enabling autoscaling for {node_pool} "
                    f"with min={min_nodes}, max={max_nodes}"
                )
                result = gke.set_autoscaling(
                    node_pool,
                    min_nodes=min_nodes,
                    max_nodes=max_nodes,
                    enabled=True,
                )
                results['steps'].append({'step': f'nodepool_autoscaling_restore_{node_pool}', 'result': result})
            
            # Determine if this environment uses ArgoCD
            argocd_projects = [p.strip() for p in config.get('argocd_projects', []) if p.strip()]
            has_argocd = len(argocd_projects) > 0

            # Step 3: Restore PDBs using Python Kubernetes client (for ALL environments)
            logger.info(f"Step 3: Restoring PDBs")

            # Construct cluster context
            cluster_context = f"gke_{config['project_id']}_{config['cluster_location']}_{config['cluster_name']}"
            logger.info(f"  Using context: {cluster_context}")

            state_file = STATE_DIR / f'{env_name}-pdb-state.json'

            if state_file.exists():
                with open(state_file, 'r') as f:
                    pdb_state = json.load(f)
                    saved_pdbs = pdb_state.get('pdbs', [])

                if saved_pdbs:
                    # Group PDBs by namespace
                    pdbs_by_namespace = {}
                    for pdb in saved_pdbs:
                        ns = pdb.get('namespace', 'default')
                        if ns not in pdbs_by_namespace:
                            pdbs_by_namespace[ns] = []
                        pdbs_by_namespace[ns].append(pdb)

                    total_restored = 0
                    for ns, pdb_configs in pdbs_by_namespace.items():
                        logger.info(f"  Restoring {len(pdb_configs)} PDBs in namespace: {ns}")
                        k8s = K8sController(ns, context=cluster_context)
                        restore_result = k8s.restore_pdbs(pdb_configs)

                        if restore_result.get('success'):
                            restored_count = restore_result.get('restored_count', 0)
                            total_restored += restored_count
                            logger.info(f"  Restored {restored_count} PDBs in namespace {ns}")
                        else:
                            logger.warning(f"  Failed to restore PDBs in namespace {ns}: {restore_result.get('error')}")

                    results['steps'].append({
                        'step': 'pdb_restore',
                        'result': {'success': True, 'message': f'Restored {total_restored} PDBs'}
                    })
                else:
                    results['steps'].append({
                        'step': 'pdb_restore',
                        'result': {'success': True, 'message': 'No PDBs to restore'}
                    })
            else:
                logger.warning(f"No PDB state file found for {env_name}")
                results['steps'].append({
                    'step': 'pdb_restore',
                    'result': {'success': True, 'message': 'No PDB state file found (ArgoCD will recreate them)'}
                })

            # Step 3b: Scale up operators that were scaled down (e.g., Elastic operator)
            logger.info(f"Step 3b: Restoring operators that manage PDBs")
            logger.info(f"  Using context: {cluster_context}")

            try:
                from kubernetes import client as k8s_client, config as k8s_config
                k8s_config.load_kube_config(context=cluster_context)
                apps_api = k8s_client.AppsV1Api()

                # Same namespaces and names as in stop sequence
                operator_namespaces = ['elastic-system', 'elastic-operator', 'default']
                operator_names = ['elastic-operator', 'eck-operator']

                for ns in operator_namespaces:
                    for op_name in operator_names:
                        try:
                            deployment = apps_api.read_namespaced_deployment(name=op_name, namespace=ns)
                            if deployment and deployment.spec.replicas == 0:
                                logger.info(f"  Found scaled-down operator: {op_name} in namespace: {ns}")
                                # Scale back to 1
                                deployment.spec.replicas = 1
                                apps_api.patch_namespaced_deployment(name=op_name, namespace=ns, body=deployment)
                                logger.info(f"    ✓ Scaled {op_name} back to 1 replica")
                        except Exception:
                            # Operator doesn't exist in this namespace, continue
                            pass

                # Also check for StatefulSets
                for ns in operator_namespaces:
                    for op_name in operator_names:
                        try:
                            sts = apps_api.read_namespaced_stateful_set(name=op_name, namespace=ns)
                            if sts and sts.spec.replicas == 0:
                                logger.info(f"  Found scaled-down operator StatefulSet: {op_name} in namespace: {ns}")
                                sts.spec.replicas = 1
                                apps_api.patch_namespaced_stateful_set(name=op_name, namespace=ns, body=sts)
                                logger.info(f"    ✓ Scaled {op_name} back to 1 replica")
                        except Exception:
                            pass

            except Exception as e:
                logger.warning(f"  Could not restore operators: {e}")

            # Step 4: Remove ArgoCD sync windows to allow auto-sync (QA/UAT only)
            if has_argocd:
                logger.info(f"Step 3: Removing sync windows from ArgoCD projects: {argocd_projects}")
                
                # ArgoCD runs in a specific cluster (usually UAT-CONSUMER), not necessarily the target cluster
                argocd_project_id = os.getenv('ARGOCD_PROJECT_ID', config['project_id'])
                argocd_cluster_name = os.getenv('ARGOCD_CLUSTER_NAME', config['cluster_name'])
                argocd_cluster_location = os.getenv('ARGOCD_CLUSTER_LOCATION', config['cluster_location'])
                
                argocd_context = f"gke_{argocd_project_id}_{argocd_cluster_location}_{argocd_cluster_name}"
                logger.info(f"  Using ArgoCD cluster context: {argocd_context}")
                
                argocd = ArgoCDController(context=argocd_context)
                for project in argocd_projects:
                    result = argocd.remove_sync_window(project)
                    results['steps'].append({'step': f'argocd_sync_window_remove_{project}', 'result': result})

            # Step 5: Resume CronJobs (only if ArgoCD is configured)
            if has_argocd:
                context = f"gke_{config['project_id']}_{config['cluster_location']}_{config['cluster_name']}"
                logger.info(f"Step 5: Resuming CronJobs in namespace {config['namespace']}")
                k8s = K8sController(config['namespace'], context=context)
                result = k8s.resume_all_cronjobs()
                results['steps'].append({'step': 'cronjobs_resume', 'result': result})
            
            logger.info(f"========== START COMPLETED: {env_name} ==========")
            
            # Check if all critical steps succeeded
            critical_failures = [s for s in results['steps'] if not s['result'].get('success')]
            results['success'] = len(critical_failures) == 0
            results['message'] = f"Environment {env_name} started successfully" if results['success'] else f"Some steps failed for {env_name}"
            
            return results
            
        except Exception as e:
            logger.error(f"Error starting environment {env_name}: {e}")
            return {
                'success': False,
                'environment': env_name,
                'error': str(e),
                'steps': results['steps']
            }
    
    def get_status(self, env_name: str) -> dict:
        """
        Get current status of an environment
        
        Args:
            env_name: Environment name
            
        Returns:
            dict with status information
        """
        env_name = env_name.lower().replace('-', '_')
        
        if env_name not in self.environments:
            return {'success': False, 'error': f'Environment {env_name} not found'}
        
        config = self.environments[env_name]
        status = {'environment': env_name}
        
        try:
            context = f"gke_{config['project_id']}_{config['cluster_location']}_{config['cluster_name']}"
            
            # Get K8s status
            k8s = K8sController(config['namespace'], context=context)
            pod_count = k8s.get_pod_count()
            status['pods'] = pod_count
            
            # Get node pool status
            gke = GKEController(config['project_id'], config['cluster_location'], config['cluster_name'])
            node_pools_status = []
            for node_pool in config['node_pools']:
                node_pool = node_pool.strip()
                if node_pool:
                    np_status = gke.get_node_pool_status(node_pool)
                    node_pools_status.append(np_status)
            status['node_pools'] = node_pools_status
            
            # Get CloudSQL status
            if config.get('cloudsql_instance'):
                sql = CloudSQLController(config['project_id'])
                sql_status = sql.get_instance_status(config['cloudsql_instance'])
                status['cloudsql'] = sql_status
            
            # Get ArgoCD status
            if config.get('argocd_app'):
                argocd = ArgoCDController()
                argocd_status = argocd.get_app_status(config['argocd_app'])
                status['argocd'] = argocd_status
            
            status['success'] = True
            return status
            
        except Exception as e:
            logger.error(f"Error getting status for {env_name}: {e}")
            return {
                'success': False,
                'environment': env_name,
                'error': str(e)
            }
    
    # REMOVED: Duplicate list_environments() method - using the one with group support at line 198
    
    def get_simple_status(self, env_name: str, include_cloudsql: bool = False) -> dict:
        """
        Get simplified cluster status.

        This is intentionally kept SIMPLE and ROBUST:
        - Uses per-node-pool `get_node_pool_status` with `skip_compute_api=True`
          so it works reliably over the SOCKS proxy.
        - Optionally fetches CloudSQL status (disabled by default for speed).
        """
        env_name = env_name.lower().replace('-', '_')

        if env_name not in self.environments:
            return {'success': False, 'error': f'Environment {env_name} not found'}

        config = self.environments[env_name]
        status = {
            'environment': env_name,
            'project': config['project_id'],
            'cluster': config['cluster_name'],
            'node_pools': [],
            'cloudsql': []
        }

        try:
            gke = GKEController(config['project_id'], config['cluster_location'], config['cluster_name'])
            total_nodes = 0

            for node_pool in config['node_pools']:
                node_pool = node_pool.strip()
                if not node_pool:
                    continue

                np_status = gke.get_node_pool_status(node_pool, skip_compute_api=True)
                if np_status.get('success'):
                    node_count = np_status.get('node_count', 0)
                    status['node_pools'].append({
                        'name': node_pool,
                        'node_count': node_count,
                        'status': np_status.get('status', 'UNKNOWN')
                    })
                    total_nodes += node_count
                else:
                    # Surface the error in the UI instead of crashing
                    err = np_status.get('error', 'unknown error')
                    logger.warning(f"Failed to get status for node pool {node_pool}: {err}")
                    status['node_pools'].append({
                        'name': node_pool,
                        'node_count': '?',
                        'status': f"ERROR: {err}"
                    })

            status['total_nodes'] = total_nodes
            status['cluster_state'] = 'RUNNING' if total_nodes > 0 else 'STOPPED'

            if include_cloudsql:
                cloudsql_instances = [i.strip() for i in config.get('cloudsql_instances', []) if i.strip()]
                if cloudsql_instances:
                    sql = CloudSQLController(config['project_id'])
                    for instance_name in cloudsql_instances:
                        try:
                            sql_status = sql.get_instance_status(instance_name)
                            if sql_status.get('success'):
                                status['cloudsql'].append({
                                    'name': instance_name,
                                    'state': sql_status.get('state', 'UNKNOWN'),
                                    'activation_policy': sql_status.get('activation_policy', 'UNKNOWN')
                                })
                        except Exception as e:
                            logger.warning(f"Failed to get CloudSQL status for {instance_name}: {e}")
                            status['cloudsql'].append({
                                'name': instance_name,
                                'state': f'ERROR: {str(e)[:60]}',
                                'activation_policy': 'UNKNOWN'
                            })

            status['success'] = True
            return status

        except Exception as e:
            logger.error(f"Error getting simple status for {env_name}: {e}")
            return {
                'success': False,
                'environment': env_name,
                'error': str(e)
            }
