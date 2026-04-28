import json
import subprocess
from subprocess import PIPE

from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from objects import registry
from resources.messages import messages


class PodController(ICarBaseController):
    scope = "cluster"

    class Meta:
        label = 'pod'
        description = 'Manage and Read pods'
        arguments = []
        usage = 'icarcli pod [options]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        echo('Get pods')

    @command
    @expose(help="icarcli pod monitor")
    def monitor(self):

        summary = {
            'stats': {'ready': 0, 'not_ready': 0},
            'states': {},
            'pods': {},
            'waiting': {}
        }

        po = subprocess.run('kubectl get po -o json', shell=True, stdout=PIPE, stderr=PIPE)

        # Pods
        pods = {}
        out = po.stdout.decode('utf-8')
        if out is not None:
            pods = json.loads(out)

        for pod in pods.get('items'):
            containers = pod.get('status').get('containerStatuses')

            label = pod.get('metadata').get('labels').get('app')
            name = pod.get('metadata').get('name')

            summary['pods'][name] = {'name': name, 'label': label, 'containers': {}}

            # As a pod can have multiple containers
            for container in containers:

                # Get the state
                container_state = None

                for state, state_data in container['state'].items():
                    container_state = state
                    if summary['states'].get(state) is None:
                        summary['states'][state] = {'state': state, 'count': 1}
                    else:
                        summary['states'][state]['count'] = summary['states'].get(state, {'count': 0}).get('count') + 1

                # Get the containers in waiting state
                if container_state == 'waiting':

                    if container.get('containerID') is not None:
                        summary['waiting'][container.get('containerID')] = container
                        echo("\n\n")

                summary['pods'][name]['containers'][container.get('name')] = {'name': container.get('name'),
                                                                              'ready': container.get('ready')}
                ready_key = 'ready' if container.get('ready') is True else 'not_ready'

                summary['stats'][ready_key] = int(summary['stats'].get(ready_key)) + 1

        report = '``` %s \n %s ```' % \
                 (json.dumps(summary['stats'], sort_keys=True, indent=4, separators=(',', ': ')),
                  json.dumps(summary['states'], sort_keys=True, indent=4, separators=(',', ': ')))

        waiting_containers = summary.get('waiting', [])

        if len(waiting_containers) > 0:

            registry.notify.send('log', report, notify=True)

            for container in waiting_containers.items():
                registry.notify.send('log', '``` %s ```' % json.dumps(container), notify=True)
