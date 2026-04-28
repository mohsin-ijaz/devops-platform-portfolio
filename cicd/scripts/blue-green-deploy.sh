#!/bin/bash

# $1 = environment name to verify
function verify_k8s_environment {
    # make sure environment name is provided
    result=0
    env_suffix=$1
    
    if [[ "$1" ]]; then
        # special handling to strip off prod from environment name
        env_suffix=${env_suffix//prod/}

        # retreive list of resources
        echo -e "\nVerifying k8s environment with $1..." >&2
        readarray -t tmp < <(kubectl get namespace -o custom-columns=:metadata.name)
        if [[ $? == 0 ]]; then
            for t in "${tmp[@]}"; do
                if [[ "$t" == *$env_suffix ]] ; then
                    result=1
                fi
            done
        fi
        
        if [[ $result == 0 ]]; then
            echo -e "[ERROR] Mismatch of environments provided!\n" >&2
            exit 1
        fi
    else
        echo -e "[ERROR] No environment provided!\n" >&2
        exit 1
    fi
}

# $1 = type of resource for kubectl
# $2 = additional full param for kubectl (example, --namespace=enterprise-cms-id)
# return: string text of selection
function prompt_k8s_resource_choices {
    # make sure variables on 
    if [[ -z "$1" ]]; then
        echo -e "[ERROR] No resource type provided!\n" >&2
        exit 1
    fi

    # retreive list of resources
    echo -e "\nRetrieving $1..." >&2
    resources=()
    idx=0
    readarray -t tmp < <(kubectl get $1 $2 -o custom-columns=:metadata.name)
    if [[ $? == 0 ]]; then
        namespace_keywords=("namespaces" "namespace" "ns")
        exclude_namespace_names=("kube-node-lease" "kube-public" "kube-system" "kubernetes-dashboard")
        for t in "${tmp[@]}"; do
            if ! [ -z $t ] ; then
                if [[ " ${namespace_keywords[@]} " =~ " $1 " ]]; then
                    if [[ ! " ${exclude_namespace_names[@]} " =~ " $t " ]]; then
                        (( idx++ ))
                        resources+=($t)
                    fi
                else
                    (( idx++ ))
                    resources+=($t)
                fi
            fi
        done
    else
        echo -e "[ERROR] Unable to retrieve resource `$1`!\n" >&2
        exit 1
    fi

    # prompt choices to allow selection
    if [[ $idx > 0 ]]; then
        choice=$(prompt_choices ${resources[@]})
        echo "$choice"
    else
        echo -e "[ERROR] No available choice for resource `$1`!" >&2
        exit 1
    fi
}

# $1 = array of choice
# return: string text of selected choice
function prompt_choices {
    choices=("$@")
    while : ; do
        idx=0
        for item in "${choices[@]}"; do
            (( idx++ ))
            echo -e " ${idx}. ${item}" >&2
        done
        
        len=${#choices[@]}
        read -p " === Choose (1-$len): " choice >&2
        if [[ $choice == ?(-)+([0-9]) ]] && (( choice >= 1 && choice <= len )); then
            (( choice-- ))
            echo "${choices[$choice]}"
            break
        fi
    done
}

# ask user for desired environment, namespace and then target deployment information
echo -e "\nChoose your desired environment..."
choices=('prod-my' 'uat-my')
environment=$(prompt_choices ${choices[@]})

# double check if selected environment matches the current bastion's environment
verify_k8s_environment $environment
namespace=$(prompt_k8s_resource_choices namespace)
current_deployment=$(prompt_k8s_resource_choices deployment --namespace=$namespace)
deployment=""
bg_deployment=""

# determine to proceed with blue or green deployment
if [[ "$current_deployment" == *-deployment-blue ]] ; then
    deployment=${current_deployment//-deployment-blue/}
    bg_deployment="$deployment-deployment-green"
else
    deployment=${current_deployment//-deployment-green/}
    bg_deployment="$deployment-deployment-blue"
fi

# make sure selected deployment exists
if ! [ -f "$environment/$deployment/$deployment.yaml" ]; then
    echo -e "[ERROR] Invalid selections to start deployment!\n"
    exit 1
fi

# update deployment file according
echo -e "Retrieving existing deployment information..."
target_version=$(date +"%Y%m%d%H%M%S")
yq ".metadata.name=\"$bg_deployment\"" $environment/$deployment/$deployment.yaml > $environment/$deployment/$deployment.tmp1
yq ".metadata.labels.version=\"$target_version\"" $environment/$deployment/$deployment.tmp1 > $environment/$deployment/$deployment.tmp2
yq ".spec.template.metadata.labels.version=\"$target_version\"" $environment/$deployment/$deployment.tmp2 > $environment/$deployment/$deployment.json

# creating new deployment
echo -e "Creating deployment [$environment] $namespace/$bg_deployment:$target_version..."
kubectl apply -f $environment/$deployment/$deployment.json -n $namespace
sudo rm -rf $environment/$deployment/$deployment.json $environment/$deployment/$deployment.tmp*

# wait until the deployment is ready by checking the MinimumReplicasAvailable condition
duration=10
ready="processing"
while [[ ! -z "$ready" ]]; do
    echo -e " === Checking deployment [$environment] $namespace/$bg_deployment:$target_version..."
    ready=$(kubectl get pod -n $namespace -o json -l=app=$deployment -l=version=$target_version | jq '.items[].status.conditions[] | select(.type == "Ready") | select(.status == "False")')
    sleep $duration

    if [[ $duration -gt 3 ]]; then
        (( duration-- ))
    fi
done

# update the service selector with the new version
echo -e " === Switching new deployment [$environment] $namespace/$bg_deployment:$target_version to service..."
kubectl patch svc $deployment-service -n $namespace -p "{\"spec\":{\"selector\": {\"app\": \"${deployment}\", \"version\": \"${target_version}\"}}}"
if [[ $bg_deployment =~ "cms-gateway" ]]; then
    kubectl patch svc $deployment-service-http -n $namespace -p "{\"spec\":{\"selector\": {\"app\": \"${deployment}\", \"version\": \"${target_version}\"}}}"
fi
if [[ $? == 0 ]]; then
    echo -e "[SUCCESS] New deployment [$environment] $namespace/$bg_deployment:$target_version has been attached to service successful!\n"

    # delay 30 seconds before terminating old deployment (KIV - to implement graceful termination)
    readarray -t old_deployments < <(kubectl get deployment -n $namespace -o json -l=app=$deployment,version!=$target_version | jq ".items[].metadata.name")
    sleep 180
    for old_deployment in "${old_deployments[@]}"; do
        old_deployment="${old_deployment//\"}"
        echo -e "old_deployment: $old_deployment..."
        if ! [ -z $old_deployment ] ; then
            sleep 5
            echo -e " === Removing old deployment [$environment] $namespace/$old_deployment..."
            kubectl delete -n $namespace deployment $old_deployment
        fi
    done

    echo -e "[COMPLETED] Cleanup of old deployment(s) done successfully!\n"
else
    echo -e "[ERROR] Failed to switch new deployment to service!"
fi