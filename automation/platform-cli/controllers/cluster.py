import os
import subprocess
import time
from os import walk

from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from objects import registry
from resources.messages import messages, flag_message


class ClusterController(ICarBaseController):
    required = {'pods': []}
    config = {'start': {'status': 'Terminated', 'run': 'start'},
              'stop': {'status': 'Running', 'run': 'stop'}}
    scope = "cluster"

    class Meta:
        label = 'cluster'
        description = messages['cluster.info']
        arguments = [
            (['-r', '--resource'], dict(help="Resource to work with (memcache, etc)")),
            (['-t', '--type'], dict(help="Type of file to deploy")),
            (['-j', '--job'], dict(help="To apply jobs instead of normal configs")),
            (['-na', '--not_apply'], dict(help="Not apply configs")),
            (['-d', '--delete'], dict(help=flag_message['common.command'])),
            (['-sj', '--specific_job'], dict(help="To run a specific job one time, like Yii Migrate etc.")),
        ]
        usage = 'icarcli cluster <service_name> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        echo("Will return cluster summary", 'green', 'on_white')

    @command
    @expose(help="Apply DB migration jobs)")
    def db_migrate(self, *args):

        path = os.path.join(registry.kubectl_dir, self.app.pargs.environment, self.app.pargs.resource + '/jobs')
        # job_name = self.app.pargs.specific_job
        job_file = self.app.pargs.specific_job + '.yaml'
        # prefix_env = self.app.pargs.environment + '-' if self.app.pargs.environment != 'production' else ''

        echo("Delete existing DB migration job")
        # os.system('kubectl delete job %s%s' % (prefix_env, job_name))
        os.system('kubectl delete -f %s' % os.path.join(path, job_file))
        time.sleep(2)
        echo("Re-Creating DB migration job")
        os.system('kubectl apply -f %s' % os.path.join(path, job_file))

    @command
    @expose(help="Apply job files")
    def config(self, *args):

        sub_folder = ''
        if self.app.pargs.job == 'true':
            sub_folder = os.path.sep + 'jobs'

        path = os.path.join(registry.kubectl_dir, self.app.pargs.environment, self.app.pargs.resource + sub_folder)
        configs = []
        echo(path, 'white', 'on_blue')
        for (dirpath, dirnames, filenames) in walk(path):
            configs.extend(filenames)
            break
        echo(configs, 'white', 'on_yellow')
        for config in configs:

            if '-job.' in config and 'db-migrate' not in config:
                # job_name = config.replace('.yaml', '')
                # prefix_env = self.app.pargs.environment + '-' if self.app.pargs.environment != 'production' else ''
                # echo("Delete job %s%s-%s" % (prefix_env, self.app.pargs.resource, job_name), "green")
                # os.system('kubectl delete jobs %s%s-%s' % (prefix_env, self.app.pargs.resource, job_name))
                # time.sleep(2)
                continue
            if '-cronjob.' in config and 'db-migrate' not in config:
                if self.app.pargs.delete is not None:
                    job_name = self.app.pargs.resource + "-" + config.replace('.yaml', '')
                    prefix_env = self.app.pargs.environment + '-' if self.app.pargs.environment != 'production' else ''
                    echo("Deleting cronjob %s%s" % (prefix_env, job_name))
                    os.system('kubectl delete cronjobs %s%s' % (prefix_env, job_name))

            if self.app.pargs.not_apply != 'true' and 'db-migrate' not in config:
                echo("Apply file %s" % os.path.join(path, config), "green")
                os.system('kubectl apply -f %s' % os.path.join(path, config))

    @command
    @expose(help="Get cluster pods based on arguments in current environment")
    def pods(self, *args):

        filters = ' '
        # if self.app.pargs.environment != 'production':
        #    filters = "--filter='(labels.environment:%s)'" % self.app.pargs.environment

        cmd_get = ["kubectl get pods"]
        instances = subprocess.run(cmd_get, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')

        echo(instances, 'yellow')

    @command
    @expose(help="Go to nodes and clean up the dockers that are left hanging")
    def cleanup(self, *args):

        subprocess.run("docker rm $(docker ps -f status=exited -q)", shell=True)
