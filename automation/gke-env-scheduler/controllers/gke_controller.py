"""GKE Controller for node pool operations"""

import logging
import time
import re
from google.cloud import container_v1
from google.cloud import compute_v1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GKEController:
    """Controller for GKE node pool operations"""
    
    def __init__(self, project_id: str, location: str, cluster_name: str):
        """
        Initialize GKE controller
        
        Args:
            project_id: GCP project ID
            location: GCP location (zone like '<GCP_REGION>-a' or region like '<GCP_REGION>')
            cluster_name: GKE cluster name
        """
        self.project_id = project_id
        self.location = location
        self.cluster_name = cluster_name
        self.client = container_v1.ClusterManagerClient()
        self.compute_client = compute_v1.InstanceGroupManagersClient()
        
        # Detect if zonal or regional
        self.is_regional = location.count('-') == 1  # Regional: <GCP_REGION>, Zonal: <GCP_REGION>-a
        logger.info(f"GKE controller initialized for {'regional' if self.is_regional else 'zonal'} cluster: {cluster_name} in {location}")
    
    def scale_node_pool(self, node_pool_name: str, node_count: int, wait: bool = True) -> dict:
        """
        Scale node pool to specified size
        
        Args:
            node_pool_name: Name of the node pool
            node_count: Target node count (0 to stop, >0 to start)
            wait: Wait for operation to complete
            
        Returns:
            dict with success status and details
        """
        # Construct full node pool path
        node_pool_path = (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"clusters/{self.cluster_name}/nodePools/{node_pool_name}"
        )

        logger.info(f"Scaling node pool {node_pool_name} to {node_count} nodes (wait={wait})...")

        # Create scale request
        request = container_v1.SetNodePoolSizeRequest(
            name=node_pool_path,
            node_count=node_count
        )

        max_retries = 3
        backoff_seconds = 30

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Scaling {node_pool_name} to {node_count} nodes "
                    f"(attempt {attempt}/{max_retries})"
                )
                operation = self.client.set_node_pool_size(request=request)
                logger.info(f"Scale operation initiated: {operation.name}")

                if wait:
                    # Wait for operation to complete
                    result = self._wait_for_operation(operation.name, timeout_minutes=10)
                    if result.get('success'):
                        logger.info(
                            f"Node pool {node_pool_name} scaled to {node_count} nodes successfully"
                        )
                    else:
                        logger.error(
                            f"Scale operation for {node_pool_name} did not complete successfully: "
                            f"{result.get('error')}"
                        )
                    return result
                else:
                    # Fire-and-forget mode: we don't wait for completion, only for the API call
                    return {
                        'success': True,
                        'operation': operation.name,
                        'message': f'Scale operation started for {node_pool_name}'
                    }

            except Exception as e:
                msg = str(e)
                if "CLUSTER_ALREADY_HAS_OPERATION" in msg and attempt < max_retries:
                    logger.warning(
                        f"Cluster already has an operation in progress when scaling {node_pool_name}: "
                        f"{msg}. Backing off for {backoff_seconds} seconds before retry..."
                    )
                    time.sleep(backoff_seconds)
                    continue

                logger.error(f"Error scaling node pool {node_pool_name}: {e}")
                return {'success': False, 'error': msg}

        # If we exhausted all retries due to CLUSTER_ALREADY_HAS_OPERATION
        # check if the node pool is already at the desired size
        logger.warning(
            f"Failed to scale {node_pool_name} after {max_retries} attempts due to ongoing operations. "
            f"Checking current size..."
        )
        current_status = self.get_node_pool_status(node_pool_name, skip_compute_api=True)
        if current_status.get('success'):
            current_count = current_status.get('node_count', -1)
            if current_count == node_count:
                logger.info(
                    f"Node pool {node_pool_name} is already at target size {node_count}, "
                    f"treating as success despite operation conflicts"
                )
                return {
                    'success': True,
                    'message': f'Node pool {node_pool_name} already at target size {node_count}',
                    'already_scaled': True
                }

        error_msg = (
            f"Failed to scale node pool {node_pool_name} to {node_count} after "
            f"{max_retries} attempts due to ongoing cluster operations"
        )
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}
    
    def get_node_pool_status(self, node_pool_name: str, skip_compute_api: bool = False) -> dict:
        """
        Get current status of node pool
        
        Args:
            node_pool_name: Name of the node pool
            skip_compute_api: Skip Compute Engine API call for faster response (use initial_node_count)
            
        Returns:
            dict with node pool status
        """
        try:
            # Construct full node pool path
            node_pool_path = (
                f"projects/{self.project_id}/locations/{self.location}/"
                f"clusters/{self.cluster_name}/nodePools/{node_pool_name}"
            )
            
            request = container_v1.GetNodePoolRequest(name=node_pool_path)
            node_pool = self.client.get_node_pool(request=request)
            
            # Get autoscaling settings if enabled
            autoscaling_info = {}
            if node_pool.autoscaling and node_pool.autoscaling.enabled:
                autoscaling_info = {
                    'enabled': True,
                    'min_node_count': node_pool.autoscaling.min_node_count,
                    'max_node_count': node_pool.autoscaling.max_node_count
                }
            else:
                autoscaling_info = {'enabled': False}
            
            # Use initial_node_count as default (faster)
            node_count = node_pool.initial_node_count
            
            # Only fetch from Compute API if explicitly requested (slower but more accurate)
            if not skip_compute_api and node_pool.instance_group_urls:
                try:
                    # For regional clusters, there may be multiple instance groups (one per zone)
                    # We need to sum the target_size across ALL instance groups
                    total_nodes = 0
                    
                    for ig_url in node_pool.instance_group_urls:
                        # Parse instance group URL to get zone and name
                        # Format: https://www.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instanceGroupManagers/{name}
                        match = re.search(r'/zones/([^/]+)/instanceGroupManagers/([^/]+)', ig_url)
                        if match:
                            zone = match.group(1)
                            ig_name = match.group(2)
                            
                            try:
                                # Get instance group manager
                                ig_manager = self.compute_client.get(
                                    project=self.project_id,
                                    zone=zone,
                                    instance_group_manager=ig_name
                                )
                                
                                # Add target_size from this zone
                                total_nodes += ig_manager.target_size
                                logger.debug(f"  Zone {zone}: {ig_manager.target_size} nodes")
                            except Exception as zone_error:
                                logger.warning(f"Could not fetch instance group size for {node_pool_name} in zone {zone}: {zone_error}")
                    
                    # Use the sum of all instance groups
                    node_count = total_nodes
                    logger.debug(f"Total nodes across all zones for {node_pool_name}: {total_nodes}")
                    
                except Exception as e:
                    logger.warning(f"Could not fetch instance group sizes for {node_pool_name}: {e}")
                    # Fall back to initial_node_count
            
            return {
                'success': True,
                'name': node_pool.name,
                'node_count': node_count,  # Current actual node count
                'initial_node_count': node_pool.initial_node_count,  # Configured size
                'status': node_pool.status.name if node_pool.status else 'UNKNOWN',
                'version': node_pool.version,
                'autoscaling': autoscaling_info
            }
        except Exception as e:
            logger.error(f"Error getting node pool status: {e}")
            return {'success': False, 'error': str(e)}
    
    def set_autoscaling(self, node_pool_name: str, min_nodes: int, max_nodes: int, enabled: bool = True, force: bool = False) -> dict:
        """
        Configure autoscaling for a node pool.
        
        Args:
            node_pool_name: Name of the node pool
            min_nodes: Minimum number of nodes (used when enabled=True)
            max_nodes: Maximum number of nodes (used when enabled=True)
            enabled: Whether autoscaling should be enabled or disabled
            force: If False, check current state and skip if already in desired state
            
        Returns:
            dict with success status
        """
        # Check current autoscaling state first (unless force=True)
        if not force:
            current_status = self.get_node_pool_status(node_pool_name)
            if current_status.get('success'):
                current_autoscaling = current_status.get('autoscaling', {})
                current_enabled = current_autoscaling.get('enabled', False)
                
                # If we want to disable and it's already disabled, skip
                if not enabled and not current_enabled:
                    logger.info(f"Autoscaling already disabled for {node_pool_name}, skipping")
                    return {'success': True, 'message': f'Autoscaling already disabled for {node_pool_name}'}
                
                # If we want to enable and it's already enabled with same min/max, skip
                if enabled and current_enabled:
                    current_min = current_autoscaling.get('min_node_count', 0)
                    current_max = current_autoscaling.get('max_node_count', 0)
                    if current_min == min_nodes and current_max == max_nodes:
                        logger.info(f"Autoscaling already configured for {node_pool_name} with min={min_nodes}, max={max_nodes}, skipping")
                        return {'success': True, 'message': f'Autoscaling already configured for {node_pool_name}'}
        
        # GKE only allows one cluster-level operation at a time. If we hit
        # CLUSTER_ALREADY_HAS_OPERATION we should back off and retry.
        node_pool_path = (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"clusters/{self.cluster_name}/nodePools/{node_pool_name}"
        )

        autoscaling = container_v1.NodePoolAutoscaling(
            enabled=enabled,
            min_node_count=min_nodes,
            max_node_count=max_nodes
        )

        request = container_v1.SetNodePoolAutoscalingRequest(
            name=node_pool_path,
            autoscaling=autoscaling
        )

        max_retries = 3
        backoff_seconds = 30

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Setting autoscaling for {node_pool_name}: "
                    f"enabled={enabled}, min={min_nodes}, max={max_nodes} "
                    f"(attempt {attempt}/{max_retries})"
                )

                operation = self.client.set_node_pool_autoscaling(request=request)
                logger.info(f"Autoscaling update initiated: {operation.name}")

                # Wait for the operation to actually complete instead of a fixed sleep
                result = self._wait_for_operation(operation.name, timeout_minutes=10)
                if result.get("success"):
                    logger.info(
                        f"Autoscaling set for {node_pool_name}: "
                        f"enabled={enabled}, min={min_nodes}, max={max_nodes}"
                    )
                    return {
                        'success': True,
                        'message': (
                            f'Autoscaling updated for {node_pool_name} '
                            f'(enabled={enabled}, min={min_nodes}, max={max_nodes})'
                        )
                    }
                else:
                    logger.error(
                        f"Autoscaling operation for {node_pool_name} did not complete successfully: "
                        f"{result.get('error')}"
                    )
                    return result

            except Exception as e:
                msg = str(e)
                if "CLUSTER_ALREADY_HAS_OPERATION" in msg and attempt < max_retries:
                    logger.error(
                        f"Cluster already has an operation in progress when updating {node_pool_name}: "
                        f"{msg}. Backing off for {backoff_seconds} seconds before retry..."
                    )
                    time.sleep(backoff_seconds)
                    continue

                logger.error(f"Error setting autoscaling for {node_pool_name}: {e}")
                return {'success': False, 'error': msg}

        # If we exit the loop without returning, all retries hit CLUSTER_ALREADY_HAS_OPERATION
        error_msg = (
            f"Failed to set autoscaling for {node_pool_name} after {max_retries} attempts "
            f"due to ongoing cluster operations"
        )
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}
    
    def _wait_for_operation(self, operation_name: str, timeout_minutes: int = 10) -> dict:
        """
        Wait for GKE operation to complete
        
        Args:
            operation_name: Full operation name/path
            timeout_minutes: Maximum time to wait
            
        Returns:
            dict with operation result
        """
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        
        while True:
            try:
                request = container_v1.GetOperationRequest(name=operation_name)
                operation = self.client.get_operation(request=request)
                
                if operation.status == container_v1.Operation.Status.DONE:
                    logger.info(f"Operation {operation_name} completed successfully")
                    return {'success': True, 'message': 'Operation completed'}
                
                if operation.status == container_v1.Operation.Status.ABORTING:
                    logger.error(f"Operation {operation_name} is aborting")
                    return {'success': False, 'error': 'Operation aborted'}
                
                # Check timeout
                if time.time() - start_time > timeout_seconds:
                    logger.error(f"Operation {operation_name} timed out after {timeout_minutes} minutes")
                    return {'success': False, 'error': 'Operation timed out'}
                
                # Wait before next check
                time.sleep(10)
                logger.debug(f"Waiting for operation {operation_name}... Status: {operation.status.name}")
                
            except Exception as e:
                error_msg = str(e)
                # If operation not found, it likely completed very quickly
                if "Requested entity was not found" in error_msg or "NOT_FOUND" in error_msg:
                    logger.info(f"Operation {operation_name} not found - likely completed already")
                    return {'success': True, 'message': 'Operation completed (not found in API, assumed successful)'}
                
                logger.error(f"Error checking operation status: {e}")
                return {'success': False, 'error': error_msg}
