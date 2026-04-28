"""ArgoCD Controller for managing sync windows via kubectl"""

import logging
import os
import json
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArgoCDController:
    """Controller for ArgoCD operations using kubectl"""
    
    def __init__(self, kubeconfig: str = None, context: str = None):
        """
        Initialize ArgoCD controller
        
        Args:
            kubeconfig: Path to kubeconfig file
            context: Kubernetes context to use
        """
        self.kubeconfig = kubeconfig or os.getenv('KUBECONFIG', os.path.expanduser('~/.kube/config'))
        self.context = context
        self.argocd_namespace = 'argocd'
        
        logger.info(f"ArgoCD controller initialized (kubectl mode)")
        if self.context:
            logger.info(f"Using context: {self.context}")
    
    def _run_kubectl(self, args: List[str]) -> subprocess.CompletedProcess:
        """
        Run kubectl command
        
        Args:
            args: kubectl arguments
            
        Returns:
            CompletedProcess result
        """
        cmd = ['kubectl']
        if self.context:
            cmd.extend(['--context', self.context])
        cmd.extend(args)
        
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def add_sync_window(self, project_name: str, duration_hours: int = 12, 
                       window_kind: str = 'deny') -> dict:
        """
        Add sync window to ArgoCD project
        
        Args:
            project_name: ArgoCD project name
            duration_hours: Duration of sync window in hours
            window_kind: 'deny' or 'allow'
            
        Returns:
            dict with success status
        """
        try:
            logger.info(f"Adding {window_kind} sync window to project: {project_name}")
            
            # Get current AppProject
            result = self._run_kubectl([
                'get', 'appproject', project_name,
                '-n', self.argocd_namespace,
                '-o', 'json'
            ])
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f'Failed to get project: {result.stderr}'
                }
            
            project = json.loads(result.stdout)
            
            # Calculate time window
            now = datetime.now()
            end_time = now + timedelta(hours=duration_hours)
            
            # Create sync window
            # Use wildcard schedule to match any time during the window
            sync_window = {
                'kind': window_kind,
                'schedule': '* * * * *',  # Every minute (active immediately)
                'duration': f'{duration_hours}h',
                'applications': ['*'],  # Apply to all apps in project
                'manualSync': True  # Allow manual sync even during deny window
            }
            
            # Add to syncWindows array
            if 'spec' not in project:
                project['spec'] = {}
            if 'syncWindows' not in project['spec']:
                project['spec']['syncWindows'] = []
            
            # Remove any existing sync windows first
            project['spec']['syncWindows'] = [sync_window]
            
            # Apply updated project
            result = self._run_kubectl([
                'apply', '-f', '-',
                '-n', self.argocd_namespace
            ])
            
            # Send JSON via stdin
            apply_result = subprocess.run(
                ['kubectl'] + (['--context', self.context] if self.context else []) +
                ['apply', '-f', '-', '-n', self.argocd_namespace],
                input=json.dumps(project),
                capture_output=True,
                text=True
            )
            
            if apply_result.returncode == 0:
                logger.info(f"Sync window added to {project_name} (duration: {duration_hours}h)")
                return {
                    'success': True,
                    'message': f'Sync window added to {project_name}',
                    'duration': f'{duration_hours}h'
                }
            else:
                return {
                    'success': False,
                    'error': f'Failed to apply project: {apply_result.stderr}'
                }
                
        except Exception as e:
            logger.error(f"Error adding sync window to {project_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def remove_sync_window(self, project_name: str) -> dict:
        """
        Remove all sync windows from ArgoCD project
        
        Args:
            project_name: ArgoCD project name
            
        Returns:
            dict with success status
        """
        try:
            logger.info(f"Removing sync windows from project: {project_name}")
            
            # Get current AppProject
            result = self._run_kubectl([
                'get', 'appproject', project_name,
                '-n', self.argocd_namespace,
                '-o', 'json'
            ])
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f'Failed to get project: {result.stderr}'
                }
            
            project = json.loads(result.stdout)
            
            # Remove syncWindows
            if 'spec' in project and 'syncWindows' in project['spec']:
                project['spec']['syncWindows'] = []
            
            # Apply updated project
            apply_result = subprocess.run(
                ['kubectl'] + (['--context', self.context] if self.context else []) +
                ['apply', '-f', '-', '-n', self.argocd_namespace],
                input=json.dumps(project),
                capture_output=True,
                text=True
            )
            
            if apply_result.returncode == 0:
                logger.info(f"Sync windows removed from {project_name}")
                return {
                    'success': True,
                    'message': f'Sync windows removed from {project_name}'
                }
            else:
                return {
                    'success': False,
                    'error': f'Failed to apply project: {apply_result.stderr}'
                }
                
        except Exception as e:
            logger.error(f"Error removing sync windows from {project_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_project_sync_windows(self, project_name: str) -> dict:
        """
        Get sync windows for ArgoCD project
        
        Args:
            project_name: ArgoCD project name
            
        Returns:
            dict with sync windows
        """
        try:
            result = self._run_kubectl([
                'get', 'appproject', project_name,
                '-n', self.argocd_namespace,
                '-o', 'json'
            ])
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f'Failed to get project: {result.stderr}'
                }
            
            project = json.loads(result.stdout)
            sync_windows = project.get('spec', {}).get('syncWindows', [])
            
            return {
                'success': True,
                'project': project_name,
                'sync_windows': sync_windows,
                'has_deny_window': any(w.get('kind') == 'deny' for w in sync_windows)
            }
            
        except Exception as e:
            logger.error(f"Error getting sync windows for {project_name}: {e}")
            return {'success': False, 'error': str(e)}
    
