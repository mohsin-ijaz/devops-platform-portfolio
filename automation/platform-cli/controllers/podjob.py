import subprocess
import sys

from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from resources.messages import messages


class PodJobController(ICarBaseController):
    required = {'runcommand': ['name', 'command']}
    # messages = {'default': 'THIS IS MESSAGE DEFAULT'} # This message will appear at starting this file is running and after finish running.
    scope = 'cluster'

    class Meta:
        label = 'podjob'
        description = messages['podjob.desc']  # description for `icarcli --help`
        arguments = [
            (['-n', '--name'], dict(help="Specify the site you want to change the ads.txt")),
            (['-c', '--command'],
             dict(help="Enter the content you want to paste inside file ads.txt"))
        ]
        usage = 'icarcli podjob'
        epilog = 'Please report to DevOps team if you face an errors.'

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='To run command in the pod')
    def runcommand(self):
        ## VARIABLES
        env = self.app.pargs.environment
        pod_prefix_name = self.app.pargs.name
        command_to_run = self.app.pargs.command
        env_podname = "%s-%s" % (env, pod_prefix_name)
        env_podname_running = env_podname + ".*Running"

        ## Running kubectl get pod | grep env-pod_prefix_name | head -n1 | awk '{print $1}'
        command_get_pod_list_kubectl = subprocess.run(['kubectl', 'get', 'pods'], stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE)
        if command_get_pod_list_kubectl.returncode != 0:
            echo(command_get_pod_list_kubectl.stderr.decode('utf-8'), 'red')
            sys.exit(1)
        command_get_pod_list_grep = subprocess.run(['grep', env_podname_running],
                                                   input=command_get_pod_list_kubectl.stdout, stdout=subprocess.PIPE,
                                                   stderr=subprocess.PIPE)
        if command_get_pod_list_grep.returncode != 0:
            echo('STDERR: ' + command_get_pod_list_grep.stderr.decode('utf-8'), 'red')
            echo('Check if ' + env_podname + 'is running', 'red')
            sys.exit(1)
        command_get_pod_list_head = subprocess.run(['head', '-n1'], input=command_get_pod_list_grep.stdout,
                                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(command_get_pod_list_head.stdout.decode('utf-8'))
        if (command_get_pod_list_head.returncode != 0) or (command_get_pod_list_head.stdout.decode('utf-8') == ''):
            echo('STDERR: ' + command_get_pod_list_head.stderr.decode('utf-8'), 'red')
            echo('Check if ' + env_podname + 'is running, HEAD return no output or error.', 'red')
            sys.exit(1)
        command_get_pod_list_awk = subprocess.run(['awk', '{print $1}'], input=command_get_pod_list_head.stdout,
                                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Selected Pod: " + command_get_pod_list_awk.stdout.decode('utf-8'))
        podname = command_get_pod_list_awk.stdout.decode('utf-8')
        if (command_get_pod_list_awk.returncode != 0) or (command_get_pod_list_awk.stdout.decode('utf-8') == ''):
            echo('STDERR: ' + command_get_pod_list_awk.stderr.decode('utf-8'), 'red')
            echo('Check if ' + env_podname + 'is running, AWK return no output or error.', 'red')
            sys.exit(1)

        ## RUNNING COMMAND IN CONTAINER USING `kubectl exec -it`
        # print(type(podname))
        podname = podname.rstrip("\n")
        # print(podname + command_to_run)
        run_command = "kubectl exec " + podname + " -- /bin/sh -c '" + command_to_run + "' > output_command.log 2>&1 "  # Redirect stderr to stdout
        print("Command that be run: \n" + run_command)
        command_run_in_pod = subprocess.run(run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with open('output_command.log',encoding='cp1252') as reader:
            print(reader.read())
        if (command_run_in_pod.returncode != 0):
            echo('STDERR', 'red')
            sys.exit(1)

