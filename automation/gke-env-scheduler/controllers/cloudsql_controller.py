"""CloudSQL Controller for database operations"""

import logging
import time
from googleapiclient import discovery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CloudSQLController:
    """Controller for CloudSQL operations"""
    
    def __init__(self, project_id: str):
        """
        Initialize CloudSQL controller
        
        Args:
            project_id: GCP project ID
        """
        self.project_id = project_id
        self.client = discovery.build('sqladmin', 'v1')
        
        logger.info(f"CloudSQL controller initialized for project: {project_id}")
    
    def stop_instance(self, instance_name: str, wait: bool = True) -> dict:
        """
        Stop CloudSQL instance by setting activationPolicy=NEVER

        Args:
            instance_name: CloudSQL instance name
            wait: Wait for operation to complete

        Returns:
            dict with success status and details
        """
        try:
            # Check current state first
            status = self.get_instance_status(instance_name)
            if not status.get('success'):
                return status

            current_policy = status.get('activation_policy', 'UNKNOWN')
            current_state = status.get('state', 'UNKNOWN')

            # If already stopped or stopping, return success
            if current_policy == 'NEVER':
                logger.info(f"CloudSQL instance {instance_name} already has activationPolicy=NEVER (state: {current_state}), skipping stop")
                return {
                    'success': True,
                    'message': f'Instance {instance_name} already stopped (activationPolicy=NEVER, state={current_state})',
                    'already_stopped': True
                }

            logger.info(f"Stopping CloudSQL instance: {instance_name} (current policy: {current_policy}, state: {current_state})")

            request = self.client.instances().patch(
                project=self.project_id,
                instance=instance_name,
                body={'settings': {'activationPolicy': 'NEVER'}}
            )
            operation = request.execute()

            logger.info(f"Stop operation initiated: {operation['name']}")

            if wait:
                result = self._wait_for_operation(operation['name'], timeout_minutes=15)
                if result['success']:
                    logger.info(f"CloudSQL instance {instance_name} stopped successfully")
                return result
            else:
                return {
                    'success': True,
                    'operation': operation['name'],
                    'message': f'Stop operation started for {instance_name}'
                }

        except Exception as e:
            error_msg = str(e)
            # Handle case where instance is already stopped
            if "is stopped and not started in the same operation" in error_msg:
                logger.info(f"CloudSQL instance {instance_name} is already stopped")
                return {
                    'success': True,
                    'message': f'Instance {instance_name} already stopped',
                    'already_stopped': True
                }
            logger.error(f"Error stopping CloudSQL instance {instance_name}: {e}")
            return {'success': False, 'error': error_msg}
    
    def start_instance(self, instance_name: str, wait: bool = True) -> dict:
        """
        Start CloudSQL instance by setting activationPolicy=ALWAYS

        Args:
            instance_name: CloudSQL instance name
            wait: Wait for operation to complete

        Returns:
            dict with success status and details
        """
        try:
            # Check current state first
            status = self.get_instance_status(instance_name)
            if not status.get('success'):
                return status

            current_policy = status.get('activation_policy', 'UNKNOWN')
            current_state = status.get('state', 'UNKNOWN')

            # If already running with ALWAYS policy, return success
            if current_policy == 'ALWAYS' and current_state == 'RUNNABLE':
                logger.info(f"CloudSQL instance {instance_name} already running (activationPolicy=ALWAYS), skipping start")
                return {
                    'success': True,
                    'message': f'Instance {instance_name} already running',
                    'already_running': True
                }

            logger.info(f"Starting CloudSQL instance: {instance_name} (current policy: {current_policy}, state: {current_state})")

            request = self.client.instances().patch(
                project=self.project_id,
                instance=instance_name,
                body={'settings': {'activationPolicy': 'ALWAYS'}}
            )
            operation = request.execute()

            logger.info(f"Start operation initiated: {operation['name']}")

            if wait:
                result = self._wait_for_operation(operation['name'], timeout_minutes=15)
                if result['success']:
                    logger.info(f"CloudSQL instance {instance_name} started successfully")
                return result
            else:
                return {
                    'success': True,
                    'operation': operation['name'],
                    'message': f'Start operation started for {instance_name}'
                }

        except Exception as e:
            logger.error(f"Error starting CloudSQL instance {instance_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_instance_status(self, instance_name: str) -> dict:
        """
        Get current status of CloudSQL instance
        
        Args:
            instance_name: CloudSQL instance name
            
        Returns:
            dict with instance status
        """
        try:
            request = self.client.instances().get(
                project=self.project_id,
                instance=instance_name
            )
            instance = request.execute()
            
            return {
                'success': True,
                'name': instance.get('name'),
                'state': instance.get('state'),
                'activation_policy': instance.get('settings', {}).get('activationPolicy', 'UNKNOWN'),
                'database_version': instance.get('databaseVersion')
            }
        except Exception as e:
            logger.error(f"Error getting CloudSQL instance status: {e}")
            return {'success': False, 'error': str(e)}
    
    def _wait_for_operation(self, operation_name: str, timeout_minutes: int = 15) -> dict:
        """
        Wait for CloudSQL operation to complete
        
        Args:
            operation_name: Operation name
            timeout_minutes: Maximum time to wait
            
        Returns:
            dict with operation result
        """
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        
        while True:
            try:
                request = self.client.operations().get(
                    project=self.project_id,
                    operation=operation_name
                )
                operation = request.execute()
                
                if operation['status'] == 'DONE':
                    if 'error' in operation:
                        logger.error(f"Operation failed: {operation['error']}")
                        return {'success': False, 'error': operation['error']}
                    logger.info(f"Operation {operation_name} completed successfully")
                    return {'success': True, 'message': 'Operation completed'}
                
                if time.time() - start_time > timeout_seconds:
                    logger.error(f"Operation {operation_name} timed out")
                    return {'success': False, 'error': 'Operation timed out'}
                
                time.sleep(10)
                logger.debug(f"Waiting for operation {operation_name}... Status: {operation['status']}")
                
            except Exception as e:
                logger.error(f"Error checking operation status: {e}")
                return {'success': False, 'error': str(e)}
