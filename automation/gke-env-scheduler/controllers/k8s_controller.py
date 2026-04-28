"""Kubernetes Controller for scaling workloads"""

import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class K8sController:
    """Controller for Kubernetes operations"""
    
    def __init__(self, namespace: str, context: str = None):
        """
        Initialize K8s controller
        
        Args:
            namespace: Kubernetes namespace to operate in
            context: Kubeconfig context (e.g., 'gke_<GCP_QA_PROJECT>_<GCP_REGION>-a_qa-cluster-1')
        """
        self.namespace = namespace
        self.context = context
        
        try:
            if context:
                config.load_kube_config(context=context)
            else:
                config.load_kube_config()
            
            self.apps_v1 = client.AppsV1Api()
            self.core_v1 = client.CoreV1Api()
            logger.info(f"K8s controller initialized for namespace: {namespace}")
        except Exception as e:
            logger.error(f"Failed to initialize K8s controller: {e}")
            raise
    
    def scale_all_deployments(self, replicas: int) -> dict:
        """
        Scale all deployments in namespace
        
        Args:
            replicas: Target replica count (0 to stop, >0 to start)
            
        Returns:
            dict with success status and details
        """
        try:
            deployments = self.apps_v1.list_namespaced_deployment(self.namespace)
            scaled_count = 0
            errors = []
            
            for deployment in deployments.items:
                try:
                    self.apps_v1.patch_namespaced_deployment_scale(
                        name=deployment.metadata.name,
                        namespace=self.namespace,
                        body={'spec': {'replicas': replicas}}
                    )
                    logger.info(f"Scaled deployment {deployment.metadata.name} to {replicas} replicas")
                    scaled_count += 1
                except ApiException as e:
                    error_msg = f"Failed to scale deployment {deployment.metadata.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            return {
                'success': len(errors) == 0,
                'scaled_count': scaled_count,
                'total': len(deployments.items),
                'errors': errors
            }
        except Exception as e:
            logger.error(f"Error listing deployments: {e}")
            return {'success': False, 'error': str(e)}
    
    def scale_all_statefulsets(self, replicas: int) -> dict:
        """
        Scale all statefulsets in namespace
        
        Args:
            replicas: Target replica count (0 to stop, >0 to start)
            
        Returns:
            dict with success status and details
        """
        try:
            statefulsets = self.apps_v1.list_namespaced_stateful_set(self.namespace)
            scaled_count = 0
            errors = []
            
            for sts in statefulsets.items:
                try:
                    self.apps_v1.patch_namespaced_stateful_set_scale(
                        name=sts.metadata.name,
                        namespace=self.namespace,
                        body={'spec': {'replicas': replicas}}
                    )
                    logger.info(f"Scaled statefulset {sts.metadata.name} to {replicas} replicas")
                    scaled_count += 1
                except ApiException as e:
                    error_msg = f"Failed to scale statefulset {sts.metadata.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            return {
                'success': len(errors) == 0,
                'scaled_count': scaled_count,
                'total': len(statefulsets.items),
                'errors': errors
            }
        except Exception as e:
            logger.error(f"Error listing statefulsets: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_pod_count(self) -> dict:
        """
        Get pod count by status
        
        Returns:
            dict with pod counts
        """
        try:
            pods = self.core_v1.list_namespaced_pod(self.namespace)
            
            running = sum(1 for pod in pods.items if pod.status.phase == 'Running')
            pending = sum(1 for pod in pods.items if pod.status.phase == 'Pending')
            failed = sum(1 for pod in pods.items if pod.status.phase == 'Failed')
            succeeded = sum(1 for pod in pods.items if pod.status.phase == 'Succeeded')
            
            return {
                'success': True,
                'total': len(pods.items),
                'running': running,
                'pending': pending,
                'failed': failed,
                'succeeded': succeeded
            }
        except Exception as e:
            logger.error(f"Error getting pod count: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_deployments(self) -> dict:
        """List all deployments with current replica counts"""
        try:
            deployments = self.apps_v1.list_namespaced_deployment(self.namespace)
            deployment_info = []
            
            for deployment in deployments.items:
                deployment_info.append({
                    'name': deployment.metadata.name,
                    'replicas': deployment.spec.replicas,
                    'ready_replicas': deployment.status.ready_replicas or 0,
                    'available_replicas': deployment.status.available_replicas or 0
                })
            
            return {
                'success': True,
                'deployments': deployment_info
            }
        except Exception as e:
            logger.error(f"Error listing deployments: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_statefulsets(self) -> dict:
        """List all statefulsets with current replica counts"""
        try:
            statefulsets = self.apps_v1.list_namespaced_stateful_set(self.namespace)
            sts_info = []
            
            for sts in statefulsets.items:
                sts_info.append({
                    'name': sts.metadata.name,
                    'replicas': sts.spec.replicas,
                    'ready_replicas': sts.status.ready_replicas or 0
                })
            
            return {
                'success': True,
                'statefulsets': sts_info
            }
        except Exception as e:
            logger.error(f"Error listing statefulsets: {e}")
            return {'success': False, 'error': str(e)}
    
    def suspend_all_cronjobs(self) -> dict:
        """Suspend all CronJobs in namespace"""
        try:
            batch_v1 = client.BatchV1Api()
            cronjobs = batch_v1.list_namespaced_cron_job(self.namespace)
            suspended_count = 0
            errors = []
            
            for cronjob in cronjobs.items:
                try:
                    # Patch to suspend
                    batch_v1.patch_namespaced_cron_job(
                        name=cronjob.metadata.name,
                        namespace=self.namespace,
                        body={'spec': {'suspend': True}}
                    )
                    logger.info(f"Suspended CronJob {cronjob.metadata.name}")
                    suspended_count += 1
                except ApiException as e:
                    error_msg = f"Failed to suspend CronJob {cronjob.metadata.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            return {
                'success': len(errors) == 0,
                'suspended_count': suspended_count,
                'total': len(cronjobs.items),
                'errors': errors
            }
        except Exception as e:
            logger.error(f"Error suspending CronJobs: {e}")
            return {'success': False, 'error': str(e)}
    
    def resume_all_cronjobs(self) -> dict:
        """Resume all CronJobs in namespace"""
        try:
            batch_v1 = client.BatchV1Api()
            cronjobs = batch_v1.list_namespaced_cron_job(self.namespace)
            resumed_count = 0
            errors = []
            
            for cronjob in cronjobs.items:
                try:
                    # Patch to resume
                    batch_v1.patch_namespaced_cron_job(
                        name=cronjob.metadata.name,
                        namespace=self.namespace,
                        body={'spec': {'suspend': False}}
                    )
                    logger.info(f"Resumed CronJob {cronjob.metadata.name}")
                    resumed_count += 1
                except ApiException as e:
                    error_msg = f"Failed to resume CronJob {cronjob.metadata.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            return {
                'success': len(errors) == 0,
                'resumed_count': resumed_count,
                'total': len(cronjobs.items),
                'errors': errors
            }
        except Exception as e:
            logger.error(f"Error resuming CronJobs: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_all_jobs(self) -> dict:
        """Delete all Jobs in namespace (optional for cleanup)"""
        try:
            batch_v1 = client.BatchV1Api()
            jobs = batch_v1.list_namespaced_job(self.namespace)
            deleted_count = 0
            errors = []
            
            for job in jobs.items:
                try:
                    batch_v1.delete_namespaced_job(
                        name=job.metadata.name,
                        namespace=self.namespace,
                        propagation_policy='Background'
                    )
                    logger.info(f"Deleted Job {job.metadata.name}")
                    deleted_count += 1
                except ApiException as e:
                    error_msg = f"Failed to delete Job {job.metadata.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            return {
                'success': len(errors) == 0,
                'deleted_count': deleted_count,
                'total': len(jobs.items),
                'errors': errors
            }
        except Exception as e:
            logger.error(f"Error deleting Jobs: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_all_pdbs(self) -> dict:
        """Delete all PodDisruptionBudgets to avoid blocking scale operations"""
        try:
            policy_v1 = client.PolicyV1Api()
            pdbs = policy_v1.list_namespaced_pod_disruption_budget(self.namespace)
            deleted_count = 0
            errors = []
            
            for pdb in pdbs.items:
                try:
                    policy_v1.delete_namespaced_pod_disruption_budget(
                        name=pdb.metadata.name,
                        namespace=self.namespace
                    )
                    logger.info(f"Deleted PDB {pdb.metadata.name}")
                    deleted_count += 1
                except ApiException as e:
                    error_msg = f"Failed to delete PDB {pdb.metadata.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            return {
                'success': len(errors) == 0,
                'deleted_count': deleted_count,
                'total': len(pdbs.items),
                'errors': errors
            }
        except Exception as e:
            logger.error(f"Error deleting PDBs: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_cronjob_count(self) -> dict:
        """Get count of CronJobs and their suspend status"""
        try:
            batch_v1 = client.BatchV1Api()
            cronjobs = batch_v1.list_namespaced_cron_job(self.namespace)
            
            total = len(cronjobs.items)
            suspended = sum(1 for cj in cronjobs.items if cj.spec.suspend)
            active = total - suspended
            
            return {
                'success': True,
                'total': total,
                'suspended': suspended,
                'active': active
            }
        except Exception as e:
            logger.error(f"Error getting CronJob count: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_pdb_count(self) -> dict:
        """Get count of PodDisruptionBudgets"""
        try:
            policy_v1 = client.PolicyV1Api()
            pdbs = policy_v1.list_namespaced_pod_disruption_budget(self.namespace)

            return {
                'success': True,
                'total': len(pdbs.items)
            }
        except Exception as e:
            logger.error(f"Error getting PDB count: {e}")
            return {'success': False, 'error': str(e)}

    def save_and_patch_pdbs_to_zero(self) -> dict:
        """
        Save current PDB configurations and patch them to allow all disruptions
        This enables node scale-down by setting minAvailable=0

        Returns:
            dict with success status and saved PDB configs
        """
        try:
            # Try PolicyV1Api first (kubernetes >= 21.x), fall back to PolicyV1beta1Api
            try:
                policy_api = client.PolicyV1Api()
            except AttributeError:
                policy_api = client.PolicyV1beta1Api()

            pdbs = policy_api.list_namespaced_pod_disruption_budget(self.namespace)

            saved_pdbs = []
            patched_count = 0
            errors = []

            for pdb in pdbs.items:
                try:
                    # Save original PDB spec
                    pdb_config = {
                        'name': pdb.metadata.name,
                        'namespace': pdb.metadata.namespace,
                        'min_available': pdb.spec.min_available,
                        'max_unavailable': pdb.spec.max_unavailable,
                        'selector': pdb.spec.selector
                    }
                    saved_pdbs.append(pdb_config)

                    # Patch PDB to allow all disruptions (minAvailable=0)
                    policy_api.patch_namespaced_pod_disruption_budget(
                        name=pdb.metadata.name,
                        namespace=self.namespace,
                        body={
                            'spec': {
                                'minAvailable': 0
                            }
                        }
                    )
                    logger.info(f"Patched PDB {pdb.metadata.name} to minAvailable=0 (original: {pdb_config})")
                    patched_count += 1

                except ApiException as e:
                    error_msg = f"Failed to patch PDB {pdb.metadata.name}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            return {
                'success': len(errors) == 0,
                'patched_count': patched_count,
                'total': len(pdbs.items),
                'saved_configs': saved_pdbs,
                'errors': errors
            }
        except Exception as e:
            logger.error(f"Error saving/patching PDBs: {e}")
            return {'success': False, 'error': str(e)}

    def restore_pdbs(self, saved_configs: list) -> dict:
        """
        Restore PDBs to their original configurations

        Args:
            saved_configs: List of PDB configs from save_and_patch_pdbs_to_zero()

        Returns:
            dict with success status
        """
        try:
            # Try PolicyV1Api first (kubernetes >= 21.x), fall back to PolicyV1beta1Api
            try:
                policy_api = client.PolicyV1Api()
            except AttributeError:
                policy_api = client.PolicyV1beta1Api()

            restored_count = 0
            errors = []

            for pdb_config in saved_configs:
                try:
                    # Restore original PDB spec
                    body = {
                        'spec': {
                            'minAvailable': pdb_config['min_available'],
                            'maxUnavailable': pdb_config['max_unavailable']
                        }
                    }

                    policy_api.patch_namespaced_pod_disruption_budget(
                        name=pdb_config['name'],
                        namespace=pdb_config['namespace'],
                        body=body
                    )
                    logger.info(f"Restored PDB {pdb_config['name']} to original values")
                    restored_count += 1

                except ApiException as e:
                    error_msg = f"Failed to restore PDB {pdb_config['name']}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            return {
                'success': len(errors) == 0,
                'restored_count': restored_count,
                'total': len(saved_configs),
                'errors': errors
            }
        except Exception as e:
            logger.error(f"Error restoring PDBs: {e}")
            return {'success': False, 'error': str(e)}
