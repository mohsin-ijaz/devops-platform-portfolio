#!/usr/bin/env python3

"""
Script to patch Kubernetes ConfigMaps and Secrets with new MySQL endpoint values
Reads from CSV file and replaces Full_Value with Replace_Value
"""

import csv
import json
import base64
import subprocess
import argparse
import sys
from urllib.parse import urlparse, urlunparse
import re

# Color codes for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_colored(text, color=Colors.NC):
    """Print colored text to terminal"""
    print(f"{color}{text}{Colors.NC}")

def run_kubectl_command(command, dry_run=True):
    """Execute kubectl command and return output"""
    if dry_run:
        print_colored(f"[DRY-RUN] Would execute: {command}", Colors.BLUE)
        return True, ""
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
        return False, str(e)

def get_current_value(resource_type, namespace, resource, key):
    """Get current value from ConfigMap or Secret"""
    if resource_type.lower() == "configmap":
        cmd = f"kubectl get configmap {resource} -n {namespace} -o jsonpath='{{.data.{key}}}'"
    else:  # Secret
        cmd = f"kubectl get secret {resource} -n {namespace} -o jsonpath='{{.data.{key}}}'"
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            value = result.stdout.strip()
            if resource_type.lower() == "secret" and value:
                # Decode base64 for secrets
                decoded = base64.b64decode(value).decode('utf-8')
                return decoded
            return value
        return None
    except Exception as e:
        print_colored(f"Error getting current value: {e}", Colors.RED)
        return None

def replace_host_in_url(url, old_host, new_host):
    """Replace host in a MySQL URL"""
    # Pattern to match MySQL URLs with optional query parameters
    mysql_pattern = r'(mysql://[^:]+:[^@]+@)([^:/]+)(:[0-9]+/.*)'
    
    # Use re.sub to replace the host part
    def replacer(match):
        prefix = match.group(1)  # mysql://user:pass@
        host = match.group(2)     # the host
        suffix = match.group(3)   # :port/database?params
        
        if host == old_host:
            return prefix + new_host + suffix
        return match.group(0)
    
    new_url = re.sub(mysql_pattern, replacer, url)
    return new_url

def patch_configmap(namespace, resource, key, old_value, new_value, dry_run=True):
    """Patch a ConfigMap with new value"""
    print_colored("="*50, Colors.BLUE)
    print_colored(f"Patching ConfigMap: {resource}", Colors.GREEN)
    print_colored(f"Namespace: {namespace}", Colors.GREEN)
    print_colored(f"Key: {key}", Colors.GREEN)
    print_colored(f"Old Value: {old_value}", Colors.YELLOW)
    print_colored(f"New Value: {new_value}", Colors.YELLOW)
    
    # Get current value for verification
    current = get_current_value("configmap", namespace, resource, key)
    if current:
        print_colored(f"Current Value: {current}", Colors.BLUE)
    
    # Create patch JSON
    patch_data = {
        "data": {
            key: new_value
        }
    }
    patch_json = json.dumps(patch_data)
    
    # Execute patch
    cmd = f"kubectl patch configmap {resource} -n {namespace} --type merge -p '{patch_json}'"
    success, output = run_kubectl_command(cmd, dry_run)
    
    if not dry_run and success:
        print_colored("Patch applied successfully!", Colors.GREEN)
    elif not dry_run:
        print_colored(f"Patch failed: {output}", Colors.RED)
    
    print()
    return success

def patch_secret(namespace, resource, key, old_value, new_value, url_type, dry_run=True):
    """Patch a Secret with new value"""
    print_colored("="*50, Colors.BLUE)
    print_colored(f"Patching Secret: {resource}", Colors.GREEN)
    print_colored(f"Namespace: {namespace}", Colors.GREEN)
    print_colored(f"Key: {key}", Colors.GREEN)
    print_colored(f"URL Type: {url_type}", Colors.GREEN)
    
    # Get current value
    current = get_current_value("secret", namespace, resource, key)
    if current:
        print_colored(f"Current Value (decoded): {current}", Colors.BLUE)
        
        if url_type == "MySQL_URL":
            # Extract hostname from the old_value URL if it's a complete URL
            if old_value.startswith('mysql://'):
                # Extract hostname from the URL
                import re
                host_match = re.search(r'@([^:/]+):', old_value)
                if host_match:
                    old_host = host_match.group(1)
                else:
                    old_host = old_value
            else:
                old_host = old_value
            
            # Replace host in URL
            new_decoded = replace_host_in_url(current, old_host, new_value)
            print_colored(f"Replacing host: {old_host} -> {new_value}", Colors.YELLOW)
            print_colored(f"New Value (decoded): {new_decoded}", Colors.BLUE)
        else:
            new_decoded = new_value
    else:
        print_colored("Warning: Could not retrieve current value", Colors.YELLOW)
        if url_type == "MySQL_URL":
            # If we can't get current value, we can't properly replace the URL
            print_colored("Cannot patch MySQL URL without current value", Colors.RED)
            return False
        new_decoded = new_value
    
    # Encode the new value for secret
    new_encoded = base64.b64encode(new_decoded.encode()).decode()
    
    # Create patch JSON
    patch_data = {
        "data": {
            key: new_encoded
        }
    }
    patch_json = json.dumps(patch_data)
    
    # Execute patch
    cmd = f"kubectl patch secret {resource} -n {namespace} --type merge -p '{patch_json}'"
    success, output = run_kubectl_command(cmd, dry_run)
    
    if not dry_run and success:
        print_colored("Patch applied successfully!", Colors.GREEN)
    elif not dry_run:
        print_colored(f"Patch failed: {output}", Colors.RED)
    
    print()
    return success

def process_csv(csv_file, dry_run=True, verbose=False, revert=False):
    """Process CSV file and apply patches"""
    print_colored("===== Kubernetes MySQL Endpoint Patcher =====", Colors.GREEN)
    mode_text = 'DRY-RUN' if dry_run else 'EXECUTE'
    if revert:
        mode_text += ' (REVERT MODE)'
    print_colored(f"Mode: {mode_text}", Colors.YELLOW)
    print_colored(f"CSV File: {csv_file}", Colors.YELLOW)
    if revert:
        print_colored("REVERT MODE: Will restore original RDS endpoints", Colors.RED)
    print()
    
    total_patches = 0
    successful_patches = 0
    failed_patches = 0
    
    try:
        with open(csv_file, 'r') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                # Skip empty rows
                if not row.get('Type'):
                    continue
                
                total_patches += 1
                
                # Extract values from CSV
                resource_type = row['Type'].strip()
                namespace = row['Namespace'].strip()
                resource = row['Resource'].strip()
                key = row['Key'].strip()
                full_value = row['Full_Value'].strip()
                replace_value = row['Replace_Value'].strip()
                url_type = row.get('URL_Type', '').strip()
                
                # If revert mode, swap the values
                if revert:
                    old_value = replace_value  # Current state should be the replaced value
                    new_value = full_value      # We want to restore the original value
                else:
                    old_value = full_value      # Current state should be the full value
                    new_value = replace_value   # We want to apply the replacement
                
                # Process based on type
                if resource_type == 'ConfigMap':
                    success = patch_configmap(
                        namespace, resource, key, 
                        old_value, new_value, dry_run
                    )
                elif resource_type == 'Secret':
                    success = patch_secret(
                        namespace, resource, key,
                        old_value, new_value, url_type, dry_run
                    )
                else:
                    print_colored(f"Unknown resource type: {resource_type}", Colors.RED)
                    success = False
                
                if success:
                    successful_patches += 1
                else:
                    failed_patches += 1
    
    except FileNotFoundError:
        print_colored(f"Error: CSV file '{csv_file}' not found!", Colors.RED)
        return 1
    except Exception as e:
        print_colored(f"Error processing CSV: {e}", Colors.RED)
        return 1
    
    # Print summary
    print_colored("="*50, Colors.BLUE)
    print_colored("===== Summary =====", Colors.GREEN)
    print(f"Total patches to apply: {total_patches}")
    
    if dry_run:
        print_colored("This was a DRY-RUN. No changes were made.", Colors.YELLOW)
        print_colored("To execute the patches, run with -e flag", Colors.YELLOW)
    else:
        print_colored(f"Successful patches: {successful_patches}", Colors.GREEN)
        if failed_patches > 0:
            print_colored(f"Failed patches: {failed_patches}", Colors.RED)
    
    print_colored("="*50, Colors.BLUE)
    
    return 0 if failed_patches == 0 else 1

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Patch Kubernetes ConfigMaps and Secrets with new MySQL endpoint values'
    )
    parser.add_argument(
        '-f', '--file',
        default='list-test.csv',
        help='CSV file containing patch information (default: list-test.csv)'
    )
    parser.add_argument(
        '-e', '--execute',
        action='store_true',
        help='Execute patches (default: dry-run only)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '-r', '--revert',
        action='store_true',
        help='Revert mode: restore original RDS endpoints (rollback changes)'
    )
    
    args = parser.parse_args()
    
    # Process CSV file
    return process_csv(
        csv_file=args.file,
        dry_run=not args.execute,
        verbose=args.verbose,
        revert=args.revert
    )

if __name__ == "__main__":
    sys.exit(main())
