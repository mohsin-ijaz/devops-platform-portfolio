import json
import os
import subprocess
import requests
import typer
import re

from cement.core.controller import expose
from tabulate import tabulate

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from core.icarerrors import CommandError
from lib.io import echo
from resources.messages import messages


class DebeziumController(ICarBaseController):
    # this is a read-only password
    BITBUCKET = {'username': 'wengkhamkan', 'password': '<REDIS_PASSWORD>'}
    BITBUCKET_PLUGS_URL = 'https://api.bitbucket.org/2.0/repositories/<GCP_PROJECT>/plugs/src/master'
    BITBUCKET_KAFKA_DIR = 'kafka'
    PERMITTED_PROJECTS = ['crm', 'listing', 'accounts']

    required = {'delete': ['name'], 'create': ['file'], 'describe': ['name'], 'edit': ['name', 'file'],
                'pause': ['name'], 'resume': ['name'], 'validatePlugin': ['name'], 
                'delete_all': ['env'], 'create_all': ['env'], 'pause_all': ['env'], 'resume_all': ['env']}
    messages = {'default': 'Manage Debezium Kafka Connectors {environment}'}
    scope = 'cluster'

    class Meta:
        def str2bool(v):
            if isinstance(v, bool):
                return v
            if v.lower() in ('yes', 'true', 't', 'y', '1'):
                return True
            elif v.lower() in ('no', 'false', 'f', 'n', '0'):
                return False
            else:
                raise SystemError('Boolean value expected.')

        label = 'debezium'
        description = messages['cluster.info']
        usage = 'icarcli debezium <action> -e <environment> [options ...]'
        epilog = messages['init.epilog']
        arguments = [
            (['-name', '--name'], dict(help="Connector's name", nargs='?', default=[])),
            (['-exp', '--expand'], dict(help="Expand info", nargs='?', default=[])),
            (['-file', '--file'], dict(help="JSON file to create connector", nargs='?', default=[])),
            (['-lb', '--label'], dict(help="Debezium label", nargs='?', default='debezium-connect-kafka')),
            (['-env', '--env'], dict(help="Test environment name", nargs='?', default='preprod')),
            (['-dryrun', '--dryrun'], dict(help="Perform dry run ", nargs='?', default=True, type=str2bool)),
            (['-no-interaction', '--no-interaction'], dict(help="No interaction mode", nargs='?', default=False, type=str2bool),),
            (['-projects', '--projects'], dict(help="Project names in list", nargs='?', default=None)),
            (['-dn', '--dynamic-name'], dict(help="Dynamic connector name", nargs='?', default=False, type=str2bool)),
        ]

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()
        
    @command
    @expose(help='Recreate failed connectors')
    def recreate_failed(self):
        self.__prohibit_production()
        self.__show_status()
        is_env_up = False
        
        get_dbz_status_commmand = "kubectl get pods --selector=app=debezium-connect-kafka -o jsonpath=\"{.items[*].status.phase}\""
        get_dbz_status_commmand = subprocess.run(get_dbz_status_commmand, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        command_result = get_dbz_status_commmand.stdout.decode('utf-8')
        if "Running" in command_result:
            echo("Debezium is running", "green")
        else:
            echo("Debezium is not running", "yellow")
            raise typer.Exit()
        
        # check if the env is up
        if self.app.pargs.env != "preprod":
            env_mysql = f"{self.app.pargs.env}-mysql"
            get_status_commmand = "kubectl get pods --selector=app=%s -o jsonpath=\"{.items[*].status.phase}\"" % env_mysql
            get_status_commmand_call = subprocess.run(get_status_commmand, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
            command_result = get_status_commmand_call.stdout.decode('utf-8')
            if "Running" in command_result:
                is_env_up = True
        else:
            get_status_commmand = "gcloud compute instances list --filter='(labels.shutdown:auto AND labels.environment:preprod AND name:<GCP_PROJECT_PREPROD>mysql-master)'"
            instances = subprocess.run(get_status_commmand, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
            if len(instances) > 0:
                is_env_up = True
        # should re-create connectors?
        if is_env_up:
            echo(f"ENV {self.app.pargs.env} is running", "green")
            # get failed connectors
            failed_connectors = self.get_connectors(get_failed=True)
            if failed_connectors:
                for path in self.__get_config_files(env=self.app.pargs.env):
                    r = requests.get(f"{self.BITBUCKET_PLUGS_URL}/{path}", auth=(self.BITBUCKET['username'], self.BITBUCKET['password']))
                    if r.status_code == 200:
                        file_connector = r.json()
                        for fc in failed_connectors:
                            # echo(fc)
                            pattern = r"-\d{4}-\d{2}-\d{2}"
                            failed_conn_name = re.sub(pattern, "", fc)
                            file_conn_name = re.sub(pattern, "", file_connector['name'])
                            echo(failed_conn_name + " <-> " + file_conn_name)
                            if failed_conn_name == file_conn_name:
                                # create the connector first
                                typer.secho(f"Creating connector {file_connector['name']}", **self.__typer_bright_green())
                                self.app.pargs.file = json.dumps(file_connector)
                                self.app.pargs.dynamic_name = True
                                if (self.create()):
                                    # delete the connector
                                    database_server_names = {file_connector['config']['database.server.name']}
                                    typer.secho(f"Deleting connector {fc}", **self.__typer_bright_yellow())
                                    self.app.pargs.name = fc
                                    self.delete()
                                    self._delete_dsn(database_server_names)
                    else:
                        typer.secho(f"Reqest failed with status code = {r.status_code}, reposnse = {r.text}")
                        raise SystemExit
            else:
                echo(f"No failed connectors in env {self.app.pargs.env}", "green")
        else:
            echo(f"ENV {self.app.pargs.env} is not up.", "yellow")
        

    # curl -u "wengkham:hSAZZCvKW6GaY6BEdF4M" "https://api.bitbucket.org/2.0/repositories/<GCP_PROJECT>/plugs/src/master/kafka/staging" | jq
    @command
    @expose(help='Delete all Kafka connectors in specific test env, --env')
    def delete_all(self):
        self.__prohibit_production()
        self.__show_status()
        database_server_names = set()
        if self.app.pargs.no_interaction or typer.confirm(f"Are you sure you want to delete them in env {self.app.pargs.env} for projects {self.app.pargs.projects}?"):
            # for path in self.__get_config_files(env=self.app.pargs.env):
            #     r = requests.get(f"{self.BITBUCKET_PLUGS_URL}/{path}", auth=(self.BITBUCKET['username'], self.BITBUCKET['password']))
            #     if r.status_code == 200:
            #         connector = r.json()
            #         typer.secho(f"Deleting connector {connector['name']}", **self.__typer_bright_yellow())
            #         self.app.pargs.name = connector['name']
            #         database_server_names.add(connector['config']['database.server.name'])
            #         if self.app.pargs.dryrun == False:
            #             self.delete()
            #     else:
            #         typer.secho(f"Reqest failed with status code = {r.status_code}, reposnse = {r.text}")
            #         raise SystemExit

            # Get database server name
            for path in self.__get_config_files(env=self.app.pargs.env):
                r = requests.get(f"{self.BITBUCKET_PLUGS_URL}/{path}", auth=(self.BITBUCKET['username'], self.BITBUCKET['password']))
                if r.status_code == 200:
                    connector = r.json()
                    database_server_names.add(connector['config']['database.server.name'])
                else:
                    typer.secho(f"Reqest failed with status code = {r.status_code}, reposnse = {r.text}")
                    raise SystemExit

            running_connectors = self.get_connectors()
            for running_connector in running_connectors:
                typer.secho(f"Deleting connector {running_connector}", **self.__typer_bright_yellow())
                self.app.pargs.name = running_connector
                if self.app.pargs.dryrun == False:
                    self.delete()

            if self.app.pargs.no_interaction or typer.confirm(f"Are you sure you want to delete {database_server_names} schemas from schema-registry in env {self.app.pargs.env}"):
                if self.app.pargs.dryrun == False:
                    self._delete_dsn(database_server_names)
        else:
            raise SystemExit

    def _delete_dsn(self, database_server_names):
        for dsn in database_server_names:
            container_name = self.get_container_name()
            run_command = "kubectl exec %s -- curl -X DELETE \"http://kafka-schema-registry:8082/subjects/%s-value\"" % (container_name, dsn)
            echo(run_command)
            run_command_call = subprocess.run(
                run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if run_command_call.returncode == 0:
                echo(run_command_call.stdout.decode('utf-8'))
            else:
                raise CommandError('Command exited with the following error %s' %
                                run_command_call.stderr.decode('utf-8'))
            run_command = "kubectl exec %s -- curl -X DELETE \"http://kafka-schema-registry:8082/subjects/%s-value?permanent=true\"" % (container_name, dsn)
            echo(run_command)
            run_command_call = subprocess.run(
                run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if run_command_call.returncode == 0:
                echo(run_command_call.stdout.decode('utf-8'))
            else:
                raise CommandError('Command exited with the following error %s' %
                                run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='Create all Kafka connectors in specific test env, --env')
    def create_all(self):
        self.__prohibit_production()
        self.__show_status()
        if self.app.pargs.no_interaction or typer.confirm(f"Are you sure you want to create them in env {self.app.pargs.env} for projects {self.app.pargs.projects}?"):
            import json
            for path in self.__get_config_files(env=self.app.pargs.env):
                r = requests.get(f"{self.BITBUCKET_PLUGS_URL}/{path}", auth=(self.BITBUCKET['username'], self.BITBUCKET['password']))
                if r.status_code == 200:
                    connector = r.json()
                    typer.secho(f"Creating connector {connector['name']}", **self.__typer_bright_green())
                    self.app.pargs.file = json.dumps(connector)
                    if self.app.pargs.dryrun == False:
                        self.create()
                else:
                    typer.secho(f"Reqest failed with status code = {r.status_code}, reposnse = {r.text}")
                    raise SystemExit

    @command
    @expose(help='Pause all Kafka connectors in specific text env, --env')
    def pause_all(self):
        self.__prohibit_production()
        self.__show_status()
        if self.app.pargs.no_interaction or typer.confirm(f"Are you sure you want to pause all of them in env {self.app.pargs.env} for projects {self.app.pargs.projects}?"):
            for path in self.__get_config_files(env=self.app.pargs.env):
                r = requests.get(f"{self.BITBUCKET_PLUGS_URL}/{path}", auth=(self.BITBUCKET['username'], self.BITBUCKET['password']))
                if r.status_code == 200:
                    connector = r.json()
                    typer.secho(f"Pausing connector {connector['name']}", **self.__typer_bright_yellow())
                    self.app.pargs.name = connector['name']
                    if self.app.pargs.dryrun == False:
                        self.pause()
                else:
                    typer.secho(f"Reqest failed with status code = {r.status_code}, reposnse = {r.text}")
                    raise SystemExit
        else:
            raise SystemExit
                
    @command
    @expose(help='Resume all Kafka connectors in specific text env, --env')
    def resume_all(self):
        self.__prohibit_production()
        self.__show_status()
        if self.app.pargs.no_interaction or typer.confirm(f"Are you sure you want to resume all of them in env {self.app.pargs.env} for projects {self.app.pargs.projects}?"):
            for path in self.__get_config_files(env=self.app.pargs.env):
                r = requests.get(f"{self.BITBUCKET_PLUGS_URL}/{path}", auth=(self.BITBUCKET['username'], self.BITBUCKET['password']))
                if r.status_code == 200:
                    connector = r.json()
                    typer.secho(f"Resuming connector {connector['name']}", **self.__typer_bright_yellow())
                    self.app.pargs.name = connector['name']
                    if self.app.pargs.dryrun == False:
                        self.resume()
                else:
                    typer.secho(f"Reqest failed with status code = {r.status_code}, reposnse = {r.text}")
                    raise SystemExit
        else:
            raise SystemExit

    @command
    @expose(help='List Kafka connectors and its status, --exp')
    def list(self):
        container_name = self.get_container_name()
        if self.app.pargs.expand:
            expand_query = "?expand=info&expand=status"
        else:
            expand_query = ""
        run_command = "kubectl exec %s -- curl -s \"%s:8083/connectors%s\"" % (
            container_name, self.app.pargs.label, expand_query)
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            command_output = run_command_call.stdout.decode('utf-8')
            connectors = json.loads(command_output)
            if self.app.pargs.expand:
                connectors_statuses = []
                for name in connectors:
                    value = connectors[name]
                    for task in value.get('status').get('tasks'):
                        connector = {
                            'type': value.get('status').get('type'),
                            'name': name,
                            'connector class': value.get('info').get('config').get('connector.class'),
                            'connector status': value.get('status').get('connector').get('state'),
                            'task id': task.get('id'),
                            'task status': task.get('state')
                        }
                        connectors_statuses.append(connector)
                echo(tabulate(connectors_statuses, headers="keys"))
            else:
                connectors_names = []
                for key in connectors:
                    name = {'name': key}
                    connectors_names.append(name)
                echo(tabulate(connectors_names, headers="keys"))
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='Monitor and restart failed Kafka connectors')
    def monitor(self):
        container_name = self.get_container_name()
        run_command = "kubectl exec %s -- curl -s \"%s:8083/connectors?expand=status\"" % (
            container_name, self.app.pargs.label)
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            command_output = run_command_call.stdout.decode('utf-8')
            connectors = json.loads(command_output)
            has_failed_connector = False
            for name in connectors:
                value = connectors[name]
                if value.get('status').get('connector').get('state') == 'UNASSIGNED':
                    has_failed_connector = True
                    restart_command = "kubectl exec %s -- curl -X POST \"%s:8083/connectors/%s/restart\"" % (
                        container_name, self.app.pargs.label, name)
                    echo(restart_command)
                    restart_command_call = subprocess.run(
                        restart_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if restart_command_call.returncode == 0:
                        echo("Successfully restarted UNASSIGNED connector '%s'" % (
                            name))
                    else:
                        echo("Fail to restart UNASSIGNED connector '%s'" %
                             name, "red")
                for task in value.get('status').get('tasks'):
                    if task.get('state') == 'FAILED' or task.get('state') == 'UNASSIGNED':
                        has_failed_connector = True
                        restart_command = "kubectl exec %s -- curl -X POST \"%s:8083/connectors/%s/tasks/%s/restart\"" % (
                            container_name, self.app.pargs.label, name, task.get('id'))
                        echo(restart_command)
                        restart_command_call = subprocess.run(
                            restart_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if restart_command_call.returncode == 0:
                            echo("Successfully restarted FAILED connector '%s'" % (
                                name))
                        else:
                            echo("Fail to restart failed connector '%s'" %
                                 name, "red")
            if not has_failed_connector:
                echo("No failing connector")
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='Delete kafka connector, --name')
    def delete(self):
        container_name = self.get_container_name()
        run_command = "kubectl exec %s -- curl -s -X DELETE \"%s:8083/connectors/%s\"" % (
            container_name, self.app.pargs.label, self.app.pargs.name)
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            echo(run_command_call.stdout.decode('utf-8'))
            return True
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='Create kafka connector, --file')
    def create(self):
        import re
        container_name = self.get_container_name()
        config = self.app.pargs.file
        if os.path.isfile(self.app.pargs.file):
            with open(self.app.pargs.file) as f:
                config = f.read()
        config_json = json.loads(config)
        if (self.app.pargs.dynamic_name):
            from datetime import date
            today = date.today()
            current_date = today.strftime("%Y-%m-%d")
            
            config_json['name'] = re.sub(r'(\d+-\d+-\d+)', current_date, config_json['name'])
            config = json.dumps(config_json)
        run_command = "kubectl exec %s -- curl -i -X POST -H \"Accept:application/json\" -H \"Content-Type:application/json\" %s:8083/connectors/ -d '%s'" % (
            container_name, self.app.pargs.label, config)
        typer.secho(f"Creating connector {config_json['name']}", **self.__typer_bright_green())
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            echo(run_command_call.stdout.decode('utf-8'))
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))
        if "error_code" in run_command_call.stdout.decode('utf-8'):
            typer.secho(f"Fail to create connector {config_json['name']}", **self.__typer_bright_red())
            return False
        else:
            return True

    @command
    @expose(help='Get kafka connector config, --name')
    def describe(self):
        container_name = self.get_container_name()
        run_command = "kubectl exec %s -- curl -s \"%s:8083/connectors/%s\"" % (
            container_name, self.app.pargs.label, self.app.pargs.name)
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            echo(run_command_call.stdout.decode('utf-8'))
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='Recofigure existing kafka connector, --name, --file')
    def edit(self):
        container_name = self.get_container_name()
        if os.path.isfile(self.app.pargs.file):
            with open(self.app.pargs.file) as f:
                config = json.loads(f.read())
        run_command = "kubectl exec %s -- curl -i -X PUT -H \"Accept:application/json\" -H \"Content-Type:application/json\" %s:8083/connectors/%s/config -d '%s'" % (
            container_name, self.app.pargs.label, self.app.pargs.name, json.dumps(config.get('config')))
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            echo(run_command_call.stdout.decode('utf-8'))
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='Pause kafka connector, --name')
    def pause(self):
        container_name = self.get_container_name()
        run_command = "kubectl exec %s -- curl -s -X PUT \"%s:8083/connectors/%s/pause\"" % (
            container_name, self.app.pargs.label, self.app.pargs.name)
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            echo(run_command_call.stdout.decode('utf-8'))
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='Resume kafka connector, --name')
    def resume(self):
        container_name = self.get_container_name()
        run_command = "kubectl exec %s -- curl -s -X PUT \"%s:8083/connectors/%s/resume\"" % (
            container_name, self.app.pargs.label, self.app.pargs.name)
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            echo(run_command_call.stdout.decode('utf-8'))
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='List plugins')
    def plugins(self):
        container_name = self.get_container_name()
        run_command = "kubectl exec %s -- curl -s \"%s:8083/connector-plugins\"" % (
            container_name, self.app.pargs.label)
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            command_output = run_command_call.stdout.decode('utf-8')
            plugins = json.loads(command_output)
            plugin_list = []

            for plugin in plugins:
                plug = {'type': plugin.get('type'), 'version': plugin.get('version'), 'class': plugin.get('class')}
                plugin_list.append(plug)
            echo(tabulate(plugin_list, headers="keys"))
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='Validate plugins')
    def validatePlugin(self):
        container_name = self.get_container_name()
        run_command = "kubectl exec %s -- curl -s -X PUT \"%s:8083/connector-plugins/%s/config/validate\"" % (
            container_name, self.app.pargs.label, self.app.pargs.name)
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            echo(run_command_call.stdout.decode('utf-8'))
        else:
            raise CommandError('Command exited with the following error %s' %
                               run_command_call.stderr.decode('utf-8'))

    @command
    @expose(help='Get running connectors')
    def get_connectors(self, get_failed=False):
        container_name = self.get_container_name()
        run_command = "kubectl exec %s -- curl -s \"%s:8083/connectors?expand=status\"" % (
                container_name, self.app.pargs.label)
        echo(run_command)
        run_command_call = subprocess.run(
            run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            command_output = run_command_call.stdout.decode('utf-8')
            connectors = json.loads(command_output)
        import re
        connector_names = []
        failed_connector_names = set()
        connectors_statuses = []
        for name in connectors:
            value =  connectors[name]
            # info = f"{name} | {value.get('status').get('connector').get('state')}"
            is_matching = False
            if self.app.pargs.env == 'preprod' or self.app.pargs.env is None:
                if re.match(r"^stag", name, re.IGNORECASE) is None:
                    is_matching = True
            else:
                if re.match(rf"^{self.app.pargs.env}", name, re.IGNORECASE):
                    is_matching = True
            if is_matching:
                connector_names.append(name)
                for task in value.get('status').get('tasks'):
                    if task.get('state') != "RUNNING":
                        failed_connector_names.add(name)
                    connector = {
                        'type': value.get('status').get('type'),
                        'name': name,
                        'connector status': value.get('status').get('connector').get('state'),
                        'tasks': task.get('state')
                    }
                    connectors_statuses.append(connector)
        echo(tabulate(connectors_statuses, headers="keys"))
        if get_failed:
            return failed_connector_names
        else:
            return connector_names
                

    def get_container_name(self):
        label = self.app.pargs.label
        container_name = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=' + label,
             '--field-selector=status.phase=Running' ,'-o', "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "").split()
        return container_name[0]

    def __typer_bright_white(self, **kwargs):
        style = {"fg": typer.colors.BRIGHT_WHITE}
        style.update(kwargs)
        return style

    def __typer_bright_yellow(self, **kwargs):
        style = {"fg": typer.colors.BRIGHT_YELLOW}
        style.update(kwargs)
        return style

    def __typer_bright_green(self, **kwargs):
        style = {"fg": typer.colors.BRIGHT_GREEN}
        style.update(kwargs)
        return style

    def __typer_bright_red(self, **kwargs):
        style = {"fg": typer.colors.BRIGHT_WHITE, "bg": typer.colors.RED}
        style.update(kwargs)
        return style

    def __prohibit_production(self):
        if self.app.pargs.env == 'production':
            typer.secho("Action is not allowed on production!", **self.__typer_bright_red())
            raise SystemExit

    def __show_status(self):
        if self.app.pargs.dryrun:
            typer.secho(f"dryrun is ON", **self.__typer_bright_green(underline=True))
        else:
            typer.secho(f"dryrun is OFF", **self.__typer_bright_red(underline=True))
        if self.app.pargs.no_interaction:
            typer.secho(f"no-interaction is ON", **self.__typer_bright_red(underline=True))
        else:
            typer.secho(f"no-interaction is OFF", **self.__typer_bright_green(underline=True))

    def __get_config_files(self, env) -> list:
        # relative paths
        file_paths = []

        if self.app.pargs.projects is not None:
            projects = self.app.pargs.projects.split(",")
            if set(projects).issubset(set(self.PERMITTED_PROJECTS)) is False:
                typer.secho(f"Atleast one of the project in {projects} is not permitted, allowed projects are {self.PERMITTED_PROJECTS}", **self.__typer_bright_red())
                raise SystemExit
        else:
            projects = self.PERMITTED_PROJECTS

        for project in projects:
            url = f"{self.BITBUCKET_PLUGS_URL}/{self.BITBUCKET_KAFKA_DIR}/{env}/{project}/connect/source"
            while True:
                r = requests.get(url, auth=(self.BITBUCKET['username'], self.BITBUCKET['password']))
                if r.status_code == 200:
                    results = r.json()
                    for file in results['values']:
                        file_paths.append(file['escaped_path'])
                    if 'next' in results:
                        url = results['next']
                    else:
                        break
                else:
                    typer.secho(f"Failed to get result form {url}, status code={r.status_code}, response={r.text}", **self.__typer_bright_red())
                    break
                    # raise SystemExit
        return file_paths

