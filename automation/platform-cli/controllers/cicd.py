import json
import os
import subprocess
import time
import sys
from subprocess import PIPE

import gspread
from cement.core.controller import expose
from gspread.models import Cell
from oauth2client.service_account import ServiceAccountCredentials

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from core.icarerrors import CommandError
from lib.io import echo
from objects import registry
from resources.messages import messages


class CicdController(ICarBaseController):
    required = {'reapply_job': ['name']}
    scope = 'cluster'
    env_prefix = {
        'preprod': ['memcache', 'redis', 'mysql-timeline', 'icardata-postgresql', 'debezium', 'kafka', 'ksql', 'temporal-elasticsearch', 'temporal-postgres', 'redis-cluster-classifieds']
    }
    no_scale = {
        'preprod': [
            '<GCP_PROJECT_PREPROD>imageserver-nfs',
            '<GCP_PROJECT_PREPROD>adhoc-scripts'
        ],
        'staging': [],
        'stag0': [],
        'stag1': [],
        'stag2': [],
        'stag3': [],
        'stag4': [],
        'stag5': [],
        'qa': [],
    }
    fixed_deployments = {
        'preprod': {
            '-es': 1,
            '-docs': 1,
            '-cron': 1,
            'openproject': 1,
            '-postgresql': 1,
            '-solr': 1,
            '-websocket': 1,
            '-websocket-nginx': 1,
            '-zeppelin': 1,
            '-secor': 1,
            '-events': 1,
            '-events-nginx': 1,
            '-icarsuite': 1,
            '-api-leadmarket': 1,
            '-api-leadmarket-nginx': 1,
            '-api-leadmarket-queues': 1,
            # '-cms-varnish': 1,
            '-varnish-newcar': 1,
            '-varnish-ubp': 1,
            '-design': 1,
            '-design-nginx': 1,
            '-front-leadmarket': 1,
            '-<GCP_PROJECT>': 1,
            '-<GCP_PROJECT>-nginx': 1,
            '-icardata': 1,
            '-icon': 1,
            '-nfs-server': 1,
            '-imageserver': 3,
            '-imageserver-thumb': 3,
            '-eapi-platform-a': 2,
            '-eapi-platform-b': 2,
            '-eapi-platform-d': 2,
            '-eapi-platform-c': 2,
            '-eapi-nginx': 2,
            '-timeline': 3,
            'undertaker*': 1,
            'vortex*': 1,       # * means all matching the word regardless where its in the string it will apply rule
            'notifyr*': 1,
            'gearbox*': 1,
            # '-timeline-vortex': 3,
            '-icardata-nginx': 1,
            '-icardata-queues': 1,
            '-pyspark': 1,
            '-comms': 3,
            # '-comms-notifyr': 1,
            # '-comms-notifyr-device': 3,
            # '-comms-notifyr-push-notification': 3,
            '-icardata-postgres': 1,
            '-postgres': 1,
            '-proxysql': 1,
            '-proxysql-influxdb': 1,
            '-redis': 1,
            'kafka': 3,
            '-connect-kafka': 20,
            '-server-kafka': 0,
            'ksql-timeline-server-kafka': 1,
            'mysql-timeline': 1,
            '-data-refresh': 0,
            'redis-combine': 0,
            'redis-sentinel-listing': 3,
            'temporal-elasticsearch': 1,
            'temporal-postgres': 1,
            'redis-cluster-classifieds': 6,
            'email-consumer': 1,
            'sms-consumer': 1
        }
    }

    class Meta:
        label = 'cicd'
        description = 'Manage CICD related apps'
        arguments = [
            (['-n', '--name'], dict(help="job name")),
        ]
        usage = 'icarcli cicd <command> [options]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        echo("Will return cicd environment summary")

    @command
    @expose(help="Maintain the jenkins implementation - "
                 "need  add manually new version in docker image if also want to upgrade")
    def auto_maintain(self):
        """"Maintain the Jenkins app by auto build and restart, can schedule this command"""
        # @todo INCOMPLETE - Will complete after coming back
        # Shutdown the jenkins
        os.system("kubectl scale --replicas=0 deployment/jenkins")

    @command
    @expose(help="Restart")
    def restart_jenkins(self):
        os.system("kubectl scale --replicas=0 deployment/jenkins")
        os.system("kubectl scale --replicas=1 deployment/jenkins")

    @command
    @expose(help="Cleanup JNLP")
    def delete_jenkin_slaves(self):

        po = subprocess.run('kubectl get po --selector="jenkins=slave" -o json', shell=True, stdout=PIPE,
                            stderr=PIPE)

        echo(po.stdout.decode('utf-8'), 'green')
        echo(po.stderr.decode('utf-8'), 'red')

        # Pods
        pods = {}
        out = po.stdout.decode('utf-8')
        if out is not None:
            pods = json.loads(out)

        for pod in pods.get('items'):
            containers = pod.get('status').get('containerStatuses')

            label = pod.get('metadata').get('labels').get('app')
            name = pod.get('metadata').get('name')

            echo("Name: %s" % name)

            # po = subprocess.run('kubectl delete po %s' % name, shell=True, stdout=PIPE, stderr=PIPE)

            # echo(po.stdout.decode('utf-8'), 'green')
            # echo(po.stderr.decode('utf-8'), 'red')

    @command
    @expose(help="Stop ENV")
    def stop_env(self):

        if self.app.pargs.environment == 'production' or self.app.pargs.environment == 'new-car':
            echo("Cannot do production", "red")
            exit(1)

        self.scale_kind('deploy', self.app.pargs.environment, 0)
        self.scale_kind('cronjob', self.app.pargs.environment, 0)
        self.scale_kind('statefulset', self.app.pargs.environment, 0)

        # This will be used by variable env_prefix. If got what we specify in the environment,
        # this below code will be executed.
        if self.env_prefix.get(self.app.pargs.environment, None) is not None:
            for prefix in self.env_prefix.get(self.app.pargs.environment):
                self.scale_kind('deploy', prefix, 0)
                self.scale_kind('statefulset', prefix, 0)
        
        if self.app.pargs.environment == 'stag1' or self.app.pargs.environment == 'stag2' or self.app.pargs.environment == 'stag3' or self.app.pargs.environment == 'stag4' or self.app.pargs.environment == 'stag5' or self.app.pargs.environment == 'staging':
            self.resize_cluster_to_zero(self.app.pargs.environment)

    @command
    @expose(help="Start ENV")
    def start_env(self):

        if self.app.pargs.environment == 'production' or self.app.pargs.environment == 'new-car':
            echo("Cannot do production", "red")
            exit(1)

        scale_to = 1 if self.app.pargs.environment != 'preprod' else 2
        self.scale_kind('deploy', self.app.pargs.environment, scale_to)
        self.scale_kind('cronjob', self.app.pargs.environment, scale_to)
        self.scale_kind('statefulset', self.app.pargs.environment, scale_to)

        if self.env_prefix.get(self.app.pargs.environment, None) is not None:
            for prefix in self.env_prefix.get(self.app.pargs.environment):
                self.scale_kind('deploy', prefix, 1)
                self.scale_kind('statefulset', prefix, 1)

    def scale_kind(self, kind, prefix, replicas):
        get_kind_command = 'kubectl get %s -o json' % kind
        po = subprocess.run(get_kind_command, shell=True, stdout=PIPE,
                            stderr=PIPE)

        # Pods
        deploys = {}
        out = po.stdout.decode('utf-8')
        if out is not None:
            deploys = json.loads(out)

        for deploy in deploys.get('items'):
            name = deploy.get('metadata').get('name')
            no_scale = self.no_scale.get(self.app.pargs.environment, None)

            if name in no_scale:
                pass
            else:
                if name.startswith(prefix):
                    echo("Name: %s" % name)

                    # @todo: move into an array in class so that it becomes configurable instead of hardcoded
                    scale_to = replicas
                    fixed_deployments = self.fixed_deployments.get(self.app.pargs.environment, None)
                    if fixed_deployments is not None:
                        for fixed_postfix in fixed_deployments:

                            # no matter where the wildcard * is it will search the string inside deployments and set
                            # the fixed number to scale
                            wildcard_postfix = fixed_postfix.find("*")
                            if wildcard_postfix != -1:
                                if name.find(fixed_postfix.replace("*", "")) != -1:
                                    scale_to = fixed_deployments[fixed_postfix]

                            # scale to the defined number based on fixed number in config
                            elif name.endswith(fixed_postfix) and replicas > 0:
                                scale_to = fixed_deployments[fixed_postfix]

                    scale_cmd = ""
                    if kind == "deploy":
                        scale_cmd = 'kubectl scale --replicas=%s deploy %s' % (scale_to, name)
                    elif kind == "statefulset":
                        scale_cmd = 'kubectl scale --replicas=%s statefulset %s' % (scale_to, name)
                    elif kind == "cronjob":
                        state = "false" if scale_to > 0 else "true"
                        scale_cmd = "kubectl patch cronjobs %s -p '{\"spec\" : {\"suspend\" : %s }}'" % (name, state)
                        if state == "false":
                            self._job_reset(deploy)
                    else:
                        echo("Unsuppoted Kind")
                        exit(1)

                    echo(scale_cmd, 'green')
                    po = subprocess.run(scale_cmd, shell=True, stdout=PIPE, stderr=PIPE)
                    echo(po.stdout.decode('utf-8'), 'green')
                    echo(po.stderr.decode('utf-8'), 'red')
    
    def resize_cluster_to_zero(self, pool_env):

        list_env_nodepool_cmd = "gcloud container node-pools list --cluster <GCP_PROJECT_PREPROD>environment --filter %s | grep -v DISK_SIZE_GB | awk '{print $1}'" % (pool_env)
        output_of_nodepool=subprocess.run(list_env_nodepool_cmd, shell=True, stdout=PIPE, stderr=PIPE)
        string_of_nodepool = output_of_nodepool.stdout.decode('utf-8')
        list_of_nodepool = list(string_of_nodepool.split("\n"))
        list_of_nodepool.pop()
        print(list_of_nodepool)

        for nodepool in list_of_nodepool:
            resize_cluster_command = "gcloud container clusters resize <GCP_PROJECT_PREPROD>environment --node-pool %s --num-nodes 0" % (nodepool)
            print(resize_cluster_command)
            output_of_resize_cluster_command=subprocess.run(resize_cluster_command, shell=True, stdout=PIPE, stderr=PIPE)
            if output_of_resize_cluster_command.returncode != 0:
                echo(output_of_resize_cluster_command.stderr.decode('utf-8'), 'red')
                sys.exit()
            echo("Successfully scalling %s to 0" % (nodepool), 'green')


    def _job_reset(self, job):
        jobName = job.get('metadata').get('name')
        echo("Starting Job Reset %s" % jobName, 'green')

        failed_jobs_command = 'kubectl describe cronjob %s | grep Warning' % jobName
        failed_jobs_command_call = subprocess.run(failed_jobs_command, shell=True, stdout=PIPE, stderr=PIPE)

        echo(failed_jobs_command_call.stdout.decode('utf-8'), 'green')
        echo(failed_jobs_command_call.stderr.decode('utf-8'), 'green')
        echo(failed_jobs_command_call.returncode, 'green')

        # If the job has errors, will consider as failed job, delete it and create it again
        if failed_jobs_command_call.returncode == 0:
            echo(failed_jobs_command_call.stdout.decode('utf-8'), 'red')
            # Force suspend to false
            if job.get('spec', {}).get('suspend', None) is not None:
                job['spec']['suspend'] = False

            delete_job_command = 'kubectl delete cronjob %s' % jobName
            delete_job_command_call = subprocess.run(delete_job_command, shell=True, stdout=PIPE, stderr=PIPE)
            if delete_job_command_call.returncode != 0:
                echo(delete_job_command)
                raise CommandError("Unable to delete cronjob %s" % jobName)
            echo(delete_job_command_call.stdout.decode('utf-8'), 'green')

            while subprocess.run(failed_jobs_command, shell=True, stdout=PIPE, stderr=PIPE).returncode == 0:
                echo("Waiting for job to delete", 'red')
                time.sleep(10)

            temp_config_file = '%s.yaml' % jobName
            with open(temp_config_file, "w") as outfile:
                json.dump(job, outfile)

            create_job_command = "kubectl create -f %s" % temp_config_file
            create_job_command_call = subprocess.run(create_job_command, shell=True, stdout=PIPE, stderr=PIPE)
            echo(create_job_command_call.stdout.decode('utf-8'), 'green')
            echo(create_job_command_call.stderr.decode('utf-8'), 'yellow')
            if create_job_command_call.returncode != 0:
                echo(create_job_command)
                raise CommandError("Unable to create cronjob %s" % jobName)
            echo(create_job_command_call.stdout.decode('utf-8'), 'green')

        echo("End Job Reset", 'green')

    @command
    @expose(help="Update CICD firewall rules in production & preprod")
    def firewall(self):

        # Get ip addresses of cicd nodes in preprod
        echo("Getting external ip addresses of CICD nodes...", "green")
        get_ips_cmd = "kubectl get nodes -l category=cicd -o jsonpath='{$.items[*].status.addresses[?(@.type==\"ExternalIP\")].address}'"
        echo(get_ips_cmd, "yellow")
        get_ips_cmd_call = subprocess.run(get_ips_cmd, shell=True, stdout=PIPE, stderr=PIPE)
        get_ips_nodes = get_ips_cmd_call.stdout.decode("utf-8")
        node_ips = get_ips_nodes.split()

        # Add /32 cidr to each ip in list
        node_ips_cidr = list(map(lambda x: x + '/32', node_ips))
        ip_set = ','.join(node_ips_cidr)
        echo("CICD nodes external ip addresses: " + ip_set, "green")

        # If not EXTERNAL IP in list, exit 1.
        if not ip_set:
            echo("NO EXTERNAL IP DETECTED: " + ip_set, "green")
            exit(1)

        print("GOT IP list, UPDATING JENKINS FIREWALL RULES IN PRODUCTION NOW.")

        echo("Updating firewall rule...", "green")
        update_rule = 'gcloud compute firewall-rules update jenkins --source-ranges=%s' % (ip_set)
        echo(update_rule, "yellow")
        os.system(update_rule)

        # Authenticate to production
        echo("Switching to production environment...", "green")
        auth_production_cmd = 'icarcli auth cluster --environment production'
        echo(auth_production_cmd, "yellow")
        os.system(auth_production_cmd)

        # Add cicd nodes ip addresses to firewall rule in production
        echo("Updating firewall rule...", "green")
        update_rule = 'gcloud compute firewall-rules update jenkins --source-ranges=%s' % (ip_set)
        echo(update_rule, "yellow")
        os.system(update_rule)

    @command
    @expose(help="Update preprod firewall for FTP access from Production cluster")
    def firewall_ftp(self):

        # Get ip addresses of cicd nodes in preprod
        echo("Getting external ip addresses of node --type=jobs", "green")
        get_ips_cmd = "kubectl get nodes -l type=jobs -o jsonpath='{$.items[*].status.addresses[?(@.type==\"ExternalIP\")].address}'"
        echo(get_ips_cmd, "yellow")
        get_ips_cmd_call = subprocess.run(get_ips_cmd, shell=True, stdout=PIPE, stderr=PIPE)
        get_ips_nodes = get_ips_cmd_call.stdout.decode("utf-8")
        node_ips = get_ips_nodes.split()

        # Add /32 cidr to each ip in list
        node_ips_cidr = list(map(lambda x: x + '/32', node_ips))
        ip_set = ','.join(node_ips_cidr)
        echo("CICD nodes external ip addresses: " + ip_set, "green")

        # If not EXTERNAL IP in list, exit 1.
        if not ip_set:
            echo("NO EXTERNAL IP DETECTED: " + ip_set, "green")
            exit(1)

        print("GOT IP list, UPDATING JENKINS FIREWALL RULES IN PREPROD NOW.")

        # Authenticate to production
        echo("Switching to production environment...", "green")
        auth_production_cmd = 'icarcli auth cluster --environment preprod'
        echo(auth_production_cmd, "yellow")
        os.system(auth_production_cmd)

        echo("Updating firewall rule...", "green")
        update_rule = 'gcloud compute firewall-rules update allow-production-node-job-to-vsftp --source-ranges=%s' % (
            ip_set)
        echo(update_rule, "yellow")
        os.system(update_rule)

    @command
    @expose(help="Retrieve current image on k8s deployments")
    def current_image(self):

        # @todo: Change to use project list and environment list QA_MISSING
        deployments = [
            "accounts",
            "applicator",
            "capi",
            "dealerships",
            "lapi-platform-a", "lapi",
            "eapi-platform-a", "eapi",
            "<GCP_PROJECT>-cms",
            "minisite",
            "ubp",
            "newcar",
            "timeline",
            "comms",
            "classifieds-vehicles",
            "classifieds-listings"
        ]

        envs = [
            "preprod",
            "staging",
            "stag1",
            "stag2",
            "stag3",
            "stag4",
            "stag5",
            ""
        ]

        cells = []

        # Using enumerate()
        row_index = 0
        for i, deploy in enumerate(deployments):
            for j, env in enumerate(envs):
                env_deploy = deploy
                # For deployments with prefixes
                if env != "":
                    env_deploy = "%s-%s" % (env, deploy)
                kubectl_cmd = "kubectl get deploy %s -o jsonpath=\"{..image}\"" % env_deploy
                kubectl_cmd_call = subprocess.run(kubectl_cmd, shell=True, stdout=PIPE, stderr=PIPE)
                kubectl_images = kubectl_cmd_call.stdout.decode("utf-8")
                if kubectl_images != "":
                    echo("Current image for " + env_deploy + ": " + kubectl_images, "green")
                    cells.append(Cell(row=row_index + 2, col=1, value=env_deploy))
                    cells.append(Cell(row=row_index + 2, col=2, value=kubectl_images))
                    row_index = row_index + 1

        # define the scope
        # scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        # relative path to google service account key
        build_directory = os.path.join(registry.dockers_dir, 'project')
        docker_directory = os.path.join(build_directory, 'dockers-beta')
        sa_key = os.path.join(docker_directory, 'config', 'keys', '<GCP_PROJECT_PREPROD>service-account.json')

        # add credentials to the account
        creds = ServiceAccountCredentials.from_json_keyfile_name(sa_key, scope)

        # authorize the clientsheet 
        client = gspread.authorize(creds)

        # get the instance of the Spreadsheet
        sheet = client.open('Deployed Images')

        # get the first sheet of the Spreadsheet
        sheet_instance = sheet.get_worksheet(0)

        # update sheet
        sheet_instance.update_cells(cells)

    @command
    @expose(help="Reapply job")
    def reapply_job(self):
        job_name = self.app.pargs.name
        get_kind_command = 'kubectl get cronjobs %s -o json' % job_name
        po = subprocess.run(get_kind_command, shell=True, stdout=PIPE,
                            stderr=PIPE)
        job = {}
        out = po.stdout.decode('utf-8')

        if out is not None:
            job = json.loads(out)

        if job.get("metadata", None) is not None:
            echo('Force reset job %s' % job.get('metadata').get('name'))
            self._job_reset(job)

