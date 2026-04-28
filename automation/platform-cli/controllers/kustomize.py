import os
import shutil
import subprocess

import yaml
import json
from os import listdir
from os.path import isfile, join

from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from resources.messages import messages, flag_message

from lib.io import echo
from objects import registry


class KustomizeController(ICarBaseController):
    scope = 'cluster'
    skip_projects = [
        'ingress', 'shared', 'solr', 'imgserver', 'imageserver',
    ]
    skip_servers = [
        'kafka', 'kafka-timeline', 'keda', 'memcache', 'memcache-content', 'mongodb', 'mysql', 'nginx', 'nginx-content',
        'postgres', 'solr', 'solr-beta', 'temporal-elasticsearch', 'temporal-postgres', 'redis', 'mysql'
    ]
    environments = [
        "production", "preprod", "staging", "stag1", "stag2", "stag3", "stag4", "stag5"
    ]

    class Meta:
        label = 'kustomize'
        description = messages['cluster.info']
        arguments = [
            (['-p', '--project'], dict(help=flag_message['common.project']))
        ]
        usage = 'icarcli kustomize <command> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='Test configs to match kube and kustomization outputs')
    def test_configs(self):
        echo("Generate Test Config", 'green')

        env_projects = os.path.join(registry.kubectl_dir, 'production')
        projects = [f for f in listdir(env_projects) if isfile(join(env_projects, f)) is False]
        projects.sort()

        all_projects = {}
        for project in projects:

            # Skip projects already in work
            if project in self.skip_projects or project in self.skip_servers:
                continue

            all_projects[project] = project_generate_configs(env_projects, project)

        echo('\nKind:')
        for project, kinds in all_projects.items():
            echo("%s: %s" % (project, kinds), "blue")
            # for kind, count in kinds.items():
            #     echo("%s\t\t\t %s: %s" % (project, kind, count), "blue")

    @command
    @expose(help='WKustomized existing deployment')
    def wk(self):
        echo("Generate Test Config", 'green')
        env_projects = os.path.join(registry.kubectl_dir, 'production')
        if self.app.pargs.project:
            wk_copy_file_kustomize_dir(self.app.pargs.project)
        else:
            projects = [f for f in listdir(env_projects) if isfile(join(env_projects, f)) is False]
            echo(projects, "green")
            raise SystemExit("Unsupported action.")
        
def wk_copy_file_kustomize_dir(project: str):
    env_projects = os.path.join(registry.kubectl_dir, 'production')
    env_projects = os.path.join(env_projects, project)
    project_k_path = os.path.join(registry.kustomize_dir, project)
    # list all file in dir
    files = [f for f in listdir(env_projects) if isfile(join(env_projects, f)) is True and 'kustomization' not in f]
    from deepdiff import DeepDiff
    
    prod_file = '/Users/weng.kham/code/icarcli/objects/../../kube/production/circuits/<GCP_PROJECT>-remove-listing-cache-crm-deployment.yaml'
    preprod_file = '/Users/weng.kham/code/icarcli/objects/../../kube/preprod/circuits/<GCP_PROJECT>-remove-listing-cache-crm-deployment.yaml'
    
    with open(prod_file) as file:
        prod_file_data = yaml.safe_load(file)
    with open(preprod_file) as file:
        preprod_file_data = yaml.safe_load(file)
    
    ddiff = DeepDiff(prod_file_data, preprod_file_data, ignore_order=True)
    print(ddiff)
    
    raise SystemError

    # create base
    k_base_dir = project_k_path + '/base'
    for file in files:
        yaml_src_file_path = os.path.join(env_projects, file)
        if os.path.isdir(k_base_dir) is False:
            echo("Creating base dir", "green")
            os.mkdir(k_base_dir)
        echo(f"Copying file {file}...", "green")
        shutil.copy(yaml_src_file_path, k_base_dir)

    # kustomize create base
    echo("Creating kustomize base", "green")
    k_create_command = f"cd {k_base_dir}; rm kustomization.yaml; kustomize create --autodetect --recursive"
    subprocess.run(k_create_command, capture_output=True, shell=True)

    # create overlays
    k_overlays_dir = project_k_path + '/overlays'
    if os.path.isdir(k_overlays_dir) is False:
        echo("Creating overlays dir " + k_overlays_dir, "green")
        os.mkdir(k_overlays_dir)

    # create envs
    for env in KustomizeController.environments:
        k_env_dir = k_overlays_dir + '/' + env
        if os.path.isdir(k_env_dir) is False:
            echo("Creating env dir for " + env, "green")
            os.mkdir(k_env_dir)

        # kustomize create overlay envs
        echo(f"Creating kustomize {env} from base in {k_env_dir}", "green")
        k_env_create_command = f"cd {k_env_dir}; rm kustomization.yaml; kustomize create --resources ../../base"
        subprocess.run(k_env_create_command, capture_output=True, shell=True)
        # echo(f"Running {k_env_create_command}")
        if env != "production":
            # set name prefix
            k_env_edit_set_nameprefix_command = f"cd {k_env_dir}; kustomize edit set nameprefix {env}-"
            subprocess.run(k_env_edit_set_nameprefix_command, capture_output=True, shell=True)
            #  set image
            k_env_edit_set_image_command = f"cd {k_env_dir}; kustomize edit set image \
            asia.gcr.io/<GCP_PROJECT_PROD>/<GCP_PROJECT>/{project}=asia.gcr.io/<GCP_PROJECT_PREPROD>/<GCP_PROJECT>/{project}-{env}:master"
            subprocess.run(k_env_edit_set_image_command, capture_output=True, shell=True)
            # add transformer
            k_env_add_transformer = f"cd {k_env_dir}; kustomize edit add transformer transformer.yaml"
            subprocess.run(k_env_add_transformer, capture_output=True, shell=True)
            

def project_generate_configs(env_projects: str, project: str):

    kind_aliases = {
        'HorizontalPodAutoscaler': 'hpa',
        'PodDisruptionBudget': 'pdb'
    }
    all_kinds = {}

    # project path
    project_path = os.path.join(env_projects, project)
    project_k_path = os.path.join(registry.kustomize_dir, project)

    yaml_configs = [f for f in listdir(project_path)
                    if (isfile(join(project_path, f)) is True and (('.yaml' in f or '.yml' in f)
                                                                   and 'kustomization' not in f))]
    yaml_configs.sort()

    # Create Test Config
    create_kustomize_config(project_path, yaml_configs)

    # Create Final Configs
    create_kustomize_config_skeleton(project_path, project_k_path, yaml_configs)

    project_kinds_org = {}
    project_kinds = {}
    project_patches = {}

    # get yaml config files for the project to create `kustomize.yaml`
    # this will do the most work to create base files
    for yaml_config in yaml_configs:

        # yaml config path
        yaml_config_path = os.path.join(project_path, yaml_config)
        echo("Open file [%s]" % os.path.join(project, yaml_config), "green")

        # open config file for further processing
        with open(yaml_config_path) as yaml_file:
            config_all = yaml_file.read()
        # echo(config_all, 'green')

        if 'configmap' in yaml_config_path:
            config_files = [config_all]
        else:
            config_files = config_all.split('---\n')
            config_files_sub = {}  # have to create a separate set of configs for sub deployments
            config_index = 0

        for config_text in config_files:
            config = yaml.load(config_text, Loader=yaml.SafeLoader)
            kind_type = type(config)

            if kind_type is not dict:
                echo("Invalid type %s \n %s" % (kind_type, config), "red")
                continue
            kind = config.get('kind', '')
            if kind == '':
                echo("Kind is empty %s" % config, "red")
                continue
            if kind not in all_kinds:
                all_kinds[kind] = 1
            else:
                all_kinds[kind] = all_kinds[kind] + 1

            kind_name = config.get('metadata').get('name')

            # ensure all kinds have unique names
            if kind in project_kinds_org and kind_name in project_kinds_org.get(kind):
                echo(project_kinds_org[kind][kind_name])
                exit(1)

            if kind not in project_kinds_org:
                project_kinds_org[kind] = {}
                project_kinds[kind] = {}
                project_patches[kind] = {}

            project_kinds_org[kind][kind_name] = config
            if kind_name not in project_patches[kind]:
                project_patches[kind][kind_name] = {}

            if kind not in ["ConfigMap", "PodDisruptionBudget", "HorizontalPodAutoscaler"]:
                # ### Create base template for Deployments ###
                containers = config.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])

                config_template = {
                    'apiVersion': config.get('apiVersion'),
                    'kind': config.get('kind'),
                    'metadata': config.get('metadata'),
                }
                # Remove the following:
                if len(containers) > 0:

                    # liveness_probe = []
                    # readiness_probe = []
                    # volume_mounts = []
                    env = []
                    resources = []
                    image = []
                    for container_index, container in enumerate(containers):

                        # 1. liveness probes (container 0) /spec/template/spec/containers/0/livenessProbe
                        # liveness_probe = containers[container_index].get('livenessProbe', None)
                        # if liveness_probe is not None:
                        #     config['spec']['template']['spec']['containers'][container_index].pop('livenessProbe')
                        #
                        # # 3. readiness probe (container 0) /spec/template/spec/containers/0/readinessProbe
                        # readiness_probe = containers[container_index].get('readinessProbe', None)
                        # if readiness_probe is not None:
                        #     config['spec']['template']['spec']['containers'][container_index].pop('readinessProbe')

                        # 6. volume mounts (container 0) /spec/template/spec/containers/0/volumeMounts
                        # volume_mounts = containers[container_index].get('volumeMounts', None)
                        # if volume_mounts is not None:
                        #     config['spec']['template']['spec']['containers'][container_index].pop('volumeMounts')

                        # 9. env (container 0) /spec/template/spec/containers/0/env
                        env.append(container.get('env', None))
                        if env[container_index] is not None:
                            config['spec']['template']['spec']['containers'][container_index].pop('env')

                        # 11. resources (container 0) /spec/template/spec/containers/0/resources
                        resources.append(container.get('resources', None))
                        if resources[container_index] is not None:
                            config['spec']['template']['spec']['containers'][container_index].pop('resources')

                        # Clean up image /spec/template/spec/containers[0]/image
                        image.append(container.get('image').replace("<GCP_PROJECT_PROD>", "from-base"))
                        image_tag_start_index = image[container_index].find(":")
                        if image_tag_start_index != -1:
                            image[container_index] = image[container_index][:image_tag_start_index]
                        config['spec']['template']['spec']['containers'][container_index]['image'] = \
                            image[container_index]

                # 2. node selector spec.template.spec.nodeSelector
                node_selector = config.get('spec', {}).get('template', {}).get('spec', {}).get('nodeSelector', None)
                if node_selector is not None:
                    config['spec']['template']['spec'].pop('nodeSelector')
                    project_patches[kind][kind_name]['node_selector'] = {
                        'config': node_selector,
                        'project_path': project_k_path,
                        'patch_name': 'node_selector',
                        'patch_key': 'nodeSelector',
                        'config_template': config_template,
                        'project': project,
                        'env': 'base'}

                # 4. strategy spec.strategy
                # strategy = config.get('spec', {}).get('strategy', None)
                # if strategy is not None:
                #     config['spec'].pop('strategy')
                #     project_patches[kind][kind_name]['strategy'] = {
                #         'config': node_selector,
                #         'project_path': project_k_path,
                #         'patch_name': 'strategy',
                #         'patch_key': 'strategy',
                #         'config_template': config_template,
                #         'project': project,
                #         'env': 'base'}

                # 5. tolerations spec.template.spec.tolerations
                tolerations = config.get('spec', {}).get('template', {}).get('spec', {}).get('tolerations', None)
                if tolerations is not None:
                    config['spec']['template']['spec'].pop('tolerations')
                    project_patches[kind][kind_name]['tolerations'] = {
                        'config': tolerations,
                        'project_path': project_k_path,
                        'patch_name': 'tolerations',
                        'patch_key': 'tolerations',
                        'config_template': config_template,
                        'project': project,
                        'env': 'base'}

                # 7. volumes spec.template.spec.volumes
                # volumes = config.get('spec', {}).get('template', {}).get('spec', {}).get('volumes', None)
                # if volumes is not None:
                #     config['spec']['template']['spec'].pop('volumes')
                #     project_patches[kind][kind_name]['volumes'] = {
                #         'config': node_selector,
                #         'project_path': project_k_path,
                #         'patch_name': 'volumes',
                #         'patch_key': 'volumes',
                #         'config_template': config_template,
                #         'project': project,
                #         'env': 'base'}

                # 8. affinity spec.template.spec.affinity
                affinity = config.get('spec', {}).get('template', {}).get('spec', {}).get('affinity', None)
                if affinity is not None:
                    config['spec']['template']['spec'].pop('affinity')
                    project_patches[kind][kind_name]['affinity'] = {
                        'config': affinity,
                        'project_path': project_k_path,
                        'patch_name': 'affinity',
                        'patch_key': 'affinity',
                        'config_template': config_template,
                        'project': project,
                        'env': 'base'}

                # 10. hostAliases spec.template.spec.hostAliases
                host_aliases = config.get('spec', {}).get('template', {}).get('spec', {}).get('hostAliases', None)
                if host_aliases is not None:
                    config['spec']['template']['spec'].pop('hostAliases')
                    project_patches[kind][kind_name]['host_aliases'] = {
                        'config': host_aliases,
                        'project_path': project_k_path,
                        'patch_name': 'host_aliases',
                        'patch_key': 'hostAliases',
                        'config_template': config_template,
                        'project': project,
                        'env': 'base'}

                # echo(yaml.dump(config, sort_keys=True, indent=4), 'red')

                # Write config to base
                kind_name_file = kind_name.replace(project, '')
                config_file_name = '%s.yaml' % kind_aliases.get(kind, kind).lower()

                section_dir = ""
                if kind_name_file == "":
                    section_dir = project
                else:
                    kind_name_file = kind_name_file.replace("--", "-")
                    if kind_name_file[0] != "-":
                        kind_name_file = "-%s" % kind_name_file

                    section_dir = kind_name_file.removeprefix("-").removesuffix("-")
                    kind_name_file = kind_name_file.replace("-%s" % section_dir, "")

                    config_file_name = '%s%s.yaml' % (kind_aliases.get(kind, kind).lower(), kind_name_file)
                    config_file_name = config_file_name.replace("-.", ".")

                # All should go to base, unless it has www1, www0 or project code, then it should go to different place
                dir_target = 'base'
                is_project_deployment = False
                is_canary_deployment = False

                for project_substr in ['platform-a', 'platform-c', 'platform-d', 'platform-b']:
                    if project_substr in kind_name and 'platform-b-' not in project and 'cron' not in project_substr \
                            and 'cms' not in project_substr:

                        project_dir_path = os.path.join(project_k_path, 'overlays', 'production', 'projects')
                        if os.path.isdir(project_dir_path) is False:
                            os.mkdir(project_dir_path)

                        dir_target = os.path.join('overlays', 'production', 'projects')
                        is_project_deployment = True
                        break

                canary_substr = ''
                for canary_substr in ['www1', 'www0']:
                    if canary_substr in kind_name:

                        canary_dir_path = os.path.join(project_k_path, 'overlays', canary_substr)
                        if os.path.isdir(canary_dir_path) is False:
                            os.mkdir(canary_dir_path)
                        canary_dir_project_path = os.path.join(project_k_path, 'overlays', canary_substr, project)
                        if os.path.isdir(canary_dir_project_path) is False:
                            os.mkdir(canary_dir_project_path)

                        dir_target = os.path.join('overlays', canary_substr)

                        section_dir = section_dir.replace(canary_substr, '').removeprefix('-').removesuffix('-')
                        if section_dir == '':
                            section_dir = project

                        is_canary_deployment = True
                        break

                kind_path_dir = os.path.join(project_k_path, dir_target, section_dir)
                if os.path.isdir(kind_path_dir) is False:
                    os.mkdir(kind_path_dir)
                kind_path = os.path.join(kind_path_dir, config_file_name)
                if kind in ["PodDisruptionBudget", "HorizontalPodAutoscaler"]:
                    if is_canary_deployment is False and is_project_deployment is False:
                        dir_target = os.path.join('overlays', 'production')
                    if is_canary_deployment is True:
                        dir_target = os.path.join('overlays', canary_substr)

                    kind_path = os.path.join(project_k_path, dir_target, section_dir,
                                             config_file_name)
                if os.path.isfile(kind_path):
                    echo("File already exists %s" % kind_path, 'red')
                    exit(1)

                # echo(deployment_path, 'blue')
                kind_config_text = yaml.safe_dump(config)
                kind_config_file = open(kind_path, 'w+')
                kind_config_file.write(kind_config_text)
                kind_config_file.close()

                if kind == 'Deployment':
                    config_template = {
                        'apiVersion': 'apps/v1',
                        'kind': 'Deployment',
                        'metadata': {
                            'name': kind_name
                        },
                        'spec': {}
                    }
                    create_patch_file(node_selector, project_k_path, 'node_selector', 'nodeSelector',
                                      project, 'production', config_template)
                    create_patch_file(host_aliases, project_k_path, 'host_aliases', 'hostAliases',
                                      project, 'production', config_template)
                    create_patch_file(affinity, project_k_path, 'affinity', 'affinity',
                                      project, 'production', config_template)
                    create_patch_file(tolerations, project_k_path, 'tolerations', 'tolerations',
                                      project, 'production', config_template)

            project_kinds[kind][kind_name] = config

    return all_kinds


def create_kustomize_config(project_path,
                            resources: list = None, common_labels: list = None, patches: list = None,
                            config_map_generator: list = None, patches_strategic_merge: list = None,
                            replacements: list = None, name_prefix: str = None, build_metadata: list = None,
                            common_annotations: dict = None, components: list = None, configurations: list = None,
                            crds: list = None, generator_options: dict = None, generators: list = None,
                            images: list = None, labels: list = None, inventory: dict = None, namespace: str = None,
                            name_suffix: str = None, patches_json6902: list = None, replicas: list = None,
                            secret_generator: list = None, transformers: list = None, validators: list = None,
                            vars: list = None):
    config = {
        'kind': 'Kustomization',
        'apiVersion': 'kustomize.config.k8s.io/v1beta1',
    }

    if resources:
        config['resources'] = resources
    if common_labels:
        config['commonLabels'] = common_labels
    if patches:
        config['patches'] = patches
    if config_map_generator:
        config['configMapGenerator'] = config_map_generator
    if patches_strategic_merge:
        config['patchesStrategicMerge'] = patches_strategic_merge
    if replacements:
        config['replacements'] = replacements
    if name_prefix:
        config['namePrefix'] = name_prefix
    if build_metadata:
        config['buildMetadata'] = build_metadata
    if common_annotations:
        config['commonAnnotations'] = common_annotations
    if components:
        config['components'] = components
    if configurations:
        config['configurations'] = configurations
    if crds:
        config['crds'] = crds
    if generator_options:
        config['generatorOptions'] = generator_options
    if generators:
        config['generators'] = generators
    if images:
        config['images'] = images
    if labels:
        config['labels'] = labels
    if inventory:
        config['inventory'] = inventory
    if namespace:
        config['namespace'] = namespace
    if name_suffix:
        config['nameSuffix'] = name_suffix
    if patches_json6902:
        config['patchesJson6902'] = patches_json6902
    if replicas:
        config['replicas'] = replicas
    if secret_generator:
        config['secretGenerator'] = secret_generator
    if transformers:
        config['transformers'] = transformers
    if validators:
        config['validators'] = validators
    if vars:
        config['vars'] = vars

    kustomize_config = os.path.join(project_path, 'kustomization.yaml')

    if os.path.isfile(kustomize_config):
        os.remove(kustomize_config)

    config_text = yaml.safe_dump(config)
    config_file = open(kustomize_config, 'w+')
    config_file.write(config_text)
    config_file.close()


def create_kustomize_config_skeleton(project_src_path: str, project_dest_path: str, config_files: list):

    k_project_dir = project_dest_path
    echo(k_project_dir, "red")

    if os.path.isdir(k_project_dir) is True:
        shutil.rmtree(k_project_dir)

    os.mkdir(k_project_dir)

    # Base Directory
    base_k_project_dir = os.path.join(k_project_dir, "base")
    os.mkdir(base_k_project_dir)
    os.mkdir(os.path.join(base_k_project_dir, 'patch'))

    # Don't need kustomize in base anymore
    # create_kustomize_config(base_k_project_dir)

    env_o_project_dir = os.path.join(k_project_dir, 'overlays')
    os.mkdir(env_o_project_dir)
    for env in KustomizeController.environments:
        env_k_project_dir = os.path.join(env_o_project_dir, env)
        os.mkdir(env_k_project_dir)
        os.mkdir(os.path.join(env_k_project_dir, 'patch'))
        create_kustomize_config(env_k_project_dir)


def parse_deployment(deployment_config):
    echo("Parse deployment")


def create_patch_file(config: dict, project_path: str, patch_name: str, patch_key: str,
                      project: str, env_name: str, config_template: dict = None, patch_type: str = "simple"):
    echo("Create patch")

    if config is None:
        echo("Skip config")
        return

    if config_template is None:
        config_template = {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {
                'name': '<required-field>'
            },
            'spec': {}
        }
    config_formatted = config_template
    if patch_type == "simple":
        config_formatted['spec'] = {
            'template': {
                'spec': {
                    patch_key: config
                }
            }
        }

    kind_name = config_formatted.get('metadata', {}).get('name', None)
    env_dir = os.path.join(project_path, env_name)
    if os.path.isdir(env_dir) is False:
        os.mkdir(env_dir)

    patch_dir = os.path.join(project_path, env_name, 'patches')
    if os.path.isdir(patch_dir) is False:
        os.mkdir(patch_dir)

    config_file_name = '%s.yaml' % patch_name
    config_path = os.path.join(patch_dir, config_file_name)
    # these should go it production for base
    # if env_name == "base" and patch_name in ["affinity", "env", "node_selector", "tolerations"]:
    #     config_path = os.path.join(project_path, 'production', 'patch', config_file_name)

    if os.path.isfile(config_path):
        echo("Patch already exists %s" % config_path, "white", "on_red")

        with open(config_path) as existing_config_file:
            existing_config_data = yaml.safe_load(existing_config_file)
            if config_formatted.get('spec') == existing_config_data.get('spec'):
                echo("Spec matches with %s" % config_path, "white", "on_yellow")
                return
                # exit(1)

        if kind_name is not None:
            config_file_name = '%s-%s.yaml' % (patch_name, kind_name)
            config_path = os.path.join(patch_dir, config_file_name)
            if os.path.isfile(config_path):
                echo("Patch already exists %s" % config_path, "white", "on_red")
                exit(1)

    config_file = open(config_path, 'w+')

    config_formatted['metadata']['name'] = '<required-field>'
    config_text = yaml.safe_dump(config_formatted)
    config_formatted['metadata']['name'] = kind_name
    config_file.write(config_text)
    config_file.close()


# def configure_base_configs(project: str):
#     k_project_dir = os.path.join(registry.kustomize_dir, project)
#     # Base Directory
#     base_k_project_dir = os.path.join(k_project_dir, "base")
#     os.mkdir(base_k_project_dir)