import json
import os
import subprocess
from os import walk

import yaml
from boltons.iterutils import remap
from cement.core.controller import expose
from jinja2 import Template
from slugify import slugify
from tabulate import tabulate

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from core.icarerrors import CommandError
from lib.io import echo
from objects import registry
from resources.messages import messages, flag_message


class JobController(ICarBaseController):
    required = {'run': ['project', 'command', 'label', 'ref'], 'generate': ['project']}
    messages = {'run': 'Job {label} on {environment}'}
    scope = "cluster"
    projects = ['lapi', 'ubp']
    kinds = {}

    class Meta:
        label = 'job'
        description = messages['cluster.info']
        arguments = [
            (['-b', '--branch'], dict(help=flag_message['common.branch'])),
            (['-p', '--project'], dict(help=flag_message['common.project'])),
            (['-tp', '--template_project'], dict(help="Template to take for job generation")),
            (['-t', '--target'], dict(help='Target Environment')),
            (['-sid', '--source_image_deployment'], dict(help=flag_message['common.command'])),
            (['-c', '--command'], dict(help=flag_message['common.command'])),
            (['-l', '--label'], dict(help=flag_message['common.command'])),
            (['-ol', '--only'], dict(help='Target job name')),
            (['name'], dict(
                help=flag_message['compute.state'], nargs='?', default=[])),
        ]
        usage = 'icarcli pods <service_name> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(help="Run job")
    def run(self):

        if self.app.pargs.project not in self.projects:
            raise ValueError("Missing %s" % self.app.pargs.project)

        name_postfix = self.app.pargs.environment
        name_separator = '-'

        if self.app.pargs.environment == 'production' or self.app.pargs.environment == 'new-car':
            name_postfix = ""
            name_separator = ""

        deployment_name = "%s%s%s" % (name_postfix, name_separator, self.app.pargs.project)
        image_name = "%s%s%s" % (self.app.pargs.project, name_separator, name_postfix)

        branch = self.app.pargs.branch

        if branch is None:
            registry_target = subprocess.run("kubectl get deployments %s "
                                             "-o=jsonpath='{$.spec.template.spec.containers[:1].image}'"
                                             % deployment_name, shell=True, stdout=subprocess.PIPE) \
                .stdout.decode('utf-8')

            branch_slug = registry_target.replace("asia.gcr.io/%s/<GCP_PROJECT>/%s:"
                                                  % (registry.cloud_auth.config.get('project'), image_name), "")
        else:
            branch_slug = slugify(branch).replace("-", "_")
            registry_target = "<GCP_PROJECT>/%s:%s" % (image_name, branch_slug)
            registry_target = "asia.gcr.io/%s/%s" % (registry.cloud_auth.config.get('project'), registry_target)

        registry.notify.send('log', 'Job %s for %s %s' % (
            self.app.pargs.label, self.app.pargs.project, branch_slug)
                             )

        instance_name = "%s--%s--%s" % (self.app.pargs.project, branch_slug, self.app.pargs.ref)

        echo(registry_target, 'yellow')

        # Get Deployment Specs
        deployment_spec = subprocess.run("kubectl get deployment %s -o json" % deployment_name, shell=True,
                                         stdout=subprocess.PIPE).stdout.decode('utf-8')

        deployment = json.loads(deployment_spec)
        specs = deployment['spec']['template']['spec']

        # Get host aliases and if they exist, inject them into the /etc/hosts file
        host_aliases = specs.get('hostAliases')
        command = "sh -c \""
        if host_aliases is not None:
            command = command + "echo '"
            for host_alias in host_aliases:
                hostnames = ','.join(host_alias.get('hostnames'))
                ip = host_alias.get('ip')
                command = command + "\n%s\t%s" % (ip, hostnames)
            command = command + "\n' >> /etc/hosts;"

        # The actual command that was passed as arguement
        command = command + self.app.pargs.command + ";\""

        # Get environment variables
        envs = []
        for types in specs['containers']:
            for entityname, entity in types.items():
                if entityname == 'env':
                    for env in entity:
                        envs.append("%s=%s" % (env.get('name'), env.get('value')))
                    break

        run_args = " "
        if len(envs) > 0:
            run_args = " --env "
            run_args = run_args + ' --env '.join(envs)

        echo(registry.term + "docker run %s --name %s --rm %s %s" % (run_args, instance_name, registry_target,
                                                                     command), 'white', 'on_yellow')

        echo(subprocess.run('gcloud docker -- pull %s' % registry_target, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE).stdout.decode('utf-8'), 'white', 'on_green')
        proc = subprocess.run(registry.term + "docker run %s --name %s --rm %s %s" % (run_args, instance_name,
                                                                                      registry_target, command),
                              shell=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        error = proc.stderr.decode('utf-8')
        if error != '':
            raise CommandError('Command exited with the following error %s' % error)

    @command
    @expose(help="Generate job configs")
    def generate(self):

        target_environment = self.app.pargs.environment if self.app.pargs.target is None else self.app.pargs.target

        # load configs for app
        template = self.app.pargs.template_project if self.app.pargs.template_project is not None else self.app.pargs.project
        config_path = "%s/template/%s" % (registry.kubectl_dir, template)
        job_config_path = "%s/config" % config_path
        template_path = "%s/jobs" % config_path
        out_path = "%s/%s/%s/jobs" % (registry.kubectl_dir, target_environment, self.app.pargs.project)

        subprocess.run('mkdir -p %s' % out_path, shell=True)

        # config files
        main_config = None
        with open("%s/main.yaml" % job_config_path) as f:
            main_config = yaml.safe_load(f)

            sub_deployment = ''
            sub_deployments = None
            if not main_config.get('legacy', False):
                # Load configuration file
                project_config_file = os.path.join(registry.dockers_dir, 'project', self.app.pargs.project, 'config',
                                                   'config.json')
                project_config = self._load_config(project_config_file)

                sub_deployments = project_config.get('sub_deployments')
                if sub_deployments is not None and len(
                        sub_deployments) > 0 and self.app.pargs.environment == 'production':
                    sub_deployment = '-%s' % sub_deployments[0]

            # data
            args = {
                'environment': target_environment,
                'environment_prefix': '' if target_environment == 'production' or
                                            self.app.pargs.environment == 'new-car' else target_environment + '-',
                'environment_postfix': '' if target_environment == 'production' or
                                             self.app.pargs.environment == 'new-car' else '-' + target_environment,
                'gcp_project': registry.cloud_auth.config.get('project')
            }

            # Get the default variables to be set for all environments
            env_variables_defaults = main_config.get('schema', {}).get('env', {}).get('default')
            # Get environment specific variables
            env_variables = main_config.get('schema', {}).get('env', {}).get(target_environment)

            # Use the defaults if they are set
            if env_variables_defaults is not None:

                for env_variable, env_variable_value in env_variables_defaults.items():
                    args[env_variable] = env_variable_value

            # Overwrite the defaults with environment specific ones, currently there is no merge
            # @todo: Introduce Merge if requested by users
            if env_variables is not None:

                merge = env_variables.get('merge', {})

                for env_variable, env_variable_value in env_variables.items():
                    if merge.get(env_variable, None) is None:
                        args[env_variable] = env_variable_value
                    elif merge.get(env_variable, None) == "default":
                        args[env_variable] = args[env_variable] + env_variable_value

            configs = []
            for (dirpath, dirnames, filenames) in walk(template_path):
                configs.extend(filenames)
                break

            source_image_deployment = None
            if not self.app.pargs.source_image_deployment:
                source_image_deployment = "%s%s" % (self.app.pargs.project, sub_deployment)
            else:
                source_image_deployment = self.app.pargs.source_image_deployment

            # to append environment prefix if its not production
            if self.app.pargs.environment != 'production':
                source_image_deployment = "%s%s" % (args.get('environment_prefix'), source_image_deployment)

            deployment_name = "%s%s" % (args.get('environment_prefix'), source_image_deployment)

            get_image_command = "kubectl get deployments %s " \
                                "-o=jsonpath='{$.spec.template.spec.containers[:1].image}'" % \
                                source_image_deployment
            echo(get_image_command, "green")

            registry_target = subprocess.run(get_image_command, shell=True, stdout=subprocess.PIPE).stdout.decode(
                'utf-8')

            args['image_name'] = registry_target

            is_project_specific = main_config.get('settings', {}).get('project_specific', False)
            projects = main_config.get('settings', {}).get('projects', [''])

            # Get template files
            for project in projects:
                for config in configs:
                    try:
                        file_name = config.replace(".yaml", "")
                        if self.app.pargs.only is not None and self.app.pargs.only != file_name:
                            continue

                        for kind_type, kind in main_config['kinds'].items():

                            # Set Data
                            args['kind_type'] = kind_type
                            args['kind'] = kind['kind']
                            args['api_version'] = kind['api_version']
                            args['restart_policy'] = kind['restart_policy']
                            if is_project_specific:
                                args['project_postfix'] = '-%s' % project
                                args['project_prefix'] = '%s-' % project
                                args['project'] = project
                            # Create config text
                            config_text_all = self._create_config(template_path, file_name, args)
                            config_files = config_text_all.split('---')

                            config_index = 0
                            for config_text in config_files:

                                # Do some advanced stuff that requires yaml load
                                config = yaml.load(config_text, Loader=yaml.SafeLoader)

                                if kind_type == "job":

                                    # active deadline seconds for jobs that don't expire
                                    if config['spec']['jobTemplate']['spec'].get('activeDeadlineSeconds',
                                                                                 None) is not None:
                                        del config['spec']['jobTemplate']['spec']['activeDeadlineSeconds']

                                    template = config['spec']['jobTemplate']['spec']
                                    del config['spec']['jobTemplate']
                                    del config['spec']['schedule']

                                    if config['spec'].get('successfulJobsHistoryLimit', None) is not None:
                                        del config['spec']['successfulJobsHistoryLimit']

                                    if config['spec'].get('failedJobsHistoryLimit', None) is not None:
                                        del config['spec']['failedJobsHistoryLimit']

                                    if config['spec'].get('concurrencyPolicy', None) is not None:
                                        del config['spec']['concurrencyPolicy']

                                    config['spec'].update(template)

                                drop_none = lambda path, key, value: value != 'null' and value != 'None' and value is not None

                                config = remap(config, visit=drop_none)

                                # Stop sorting keys till things are stable
                                # default_flow_style=False,
                                config_text = yaml.dump(config, sort_keys=True)
                                config_files[config_index] = config_text
                                config_index = config_index + 1

                            # Write config file
                            self._write_config(out_path, file_name, kind_type, "\n---\n".join(config_files))

                    except Exception as ex:
                        echo("Something went wrong")
                        echo(ex)

    @command
    @expose(help="List job data")
    def list(self):

        command_list_jobs = "kubectl get cronjobs -o json"
        jobs_data = subprocess.run(command_list_jobs, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        jobs_list = json.loads(jobs_data.stdout.decode('utf-8'))
        jobs = []

        for job_data in jobs_list.get('items'):

            if 'ubp' in job_data.get('metadata').get('name'):
                job = {
                    'name': job_data.get('metadata').get('name'),
                    'kind': job_data.get('kind'),
                    'activeDeadlineSeconds': job_data.get('spec').get('jobTemplate').get('spec').get(
                        'activeDeadlineSeconds'),
                }
                jobs.append(job)

        echo(tabulate(jobs, headers="keys"))

    def _create_config(self, template_path, file_name, args):

        echo(args, "yellow")
        template_file = open('%s/%s.yaml' % (template_path, file_name))
        src = Template(template_file.read())
        return src.render(args)

    def _write_config(self, out_path, file_name, kind_type, config_text):

        config_file_name = '%s/%s-%s.yaml' % (out_path, file_name, kind_type)
        echo(config_file_name)
        config_file = open(config_file_name, 'w+')
        config_file.write(config_text)
        config_file.close()

    def _load_config(self, file_path):

        if not os.path.isfile(file_path):
            self._on_process_end("Failed to find configuration file %s" % file_path)

        config = {}
        with open(file_path) as f:
            config = json.load(f)

        print("Loaded configuration file: %s" % file_path)
        print(config)
        return config
