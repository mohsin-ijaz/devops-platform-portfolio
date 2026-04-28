import subprocess

from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from objects import registry
from resources.messages import messages


class NodepoolController(ICarBaseController):
    required = {'default': [], 'create': ['name'], 'cordon': ['name']}
    actions = {'start': {'status': 'Terminated', 'run': 'start'},
               'stop': {'status': 'Running', 'run': 'stop'}}
    scope = "cluster"
    create_command = 'gcloud container node-pools create %s ' \
                     '--cluster %s --zone <GCP_REGION>-a ' \
                     '--enable-autoscaling --min-nodes %s --max-nodes %s ' \
                     '--num-nodes %s ' \
                     '--scopes %s ' \
                     '--disk-size %s ' \
                     '--disk-type %s ' \
                     '--node-labels=%s ' \
                     '--machine-type %s ' \
                     '%s'

    config = {
        'ubp-pool': {
            'min_node': '3',
            'max_node': '16',
            'num_node': '3',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '50',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=apps,category=ubp',
            'machine_type': 'n1-standard-8'
        },
        'ubp-pool-prem': {
            'min_node': '3',
            'max_node': '20',
            'num_node': '3',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '20',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=apps,category=ubp',
            'machine_type': 'n1-standard-8',
            'preemptible': True
        },
        'api-pool': {
            'min_node': '2',
            'max_node': '10',
            'num_node': '2',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '50',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=apps,category=api,node=nonpreemptible',
            'machine_type': 'n1-standard-8'
        },
        'api-pool-prem': {
            'min_node': '1',
            'max_node': '10',
            'num_node': '1',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '50',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=apps,category=api',
            'machine_type': 'n1-standard-8',
            'preemptible': True
        },
        'capi-pool': {
            'min_node': '2',
            'max_node': '10',
            'num_node': '2',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '50',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=apps,category=capi,node=nonpreemptible',
            'machine_type': 'n1-standard-8'
        },
        'image-server-pool': {
            'min_node': '2',
            'max_node': '10',
            'num_node': '2',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '30',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=apps,category=image',
            'machine_type': 'n1-standard-8'
        },
        'image-server-pool-prem': {
            'min_node': '1',
            'max_node': '10',
            'num_node': '1',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '30',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=apps,category=image',
            'machine_type': 'n1-standard-8',
            'preemptible': True
        },
        'memory-pool': {
            'min_node': '3',
            'max_node': '5',
            'num_node': '3',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '20',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=memory',
            'machine_type': 'n1-standard-2'
        },
        'misc-pool': {
            'min_node': '2',
            'max_node': '8',
            'num_node': '2',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '20',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=others',
            'machine_type': 'n1-standard-8'
        },
        'data-pool': {
            'min_node': '1',
            'max_node': '8',
            'num_node': '3',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '50',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=data',
            'machine_type': 'n1-standard-8'
        },
        'job-pool-small': {
            'min_node': '1',
            'max_node': '10',
            'num_node': '1',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '20',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=jobs',
            'machine_type': 'n1-standard-4'
        },
        'timeline-pool': {
            'min_node': '3',
            'max_node': '16',
            'num_node': '3',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '20',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=apps,category=timeline',
            'machine_type': 'n1-standard-8'
        },
        'timeline-pool-cassandra': {
            'min_node': '3',
            'max_node': '16',
            'num_node': '3',
            'scopes': 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,'
                      'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring',
            'disk_size': '20',
            'disk_type': 'pd-ssd',
            'node_labels': 'environment=%s,type=apps,category=timeline',
            'machine_type': 'n1-standard-8'
        }
    }

    class Meta:
        label = 'nodepool'
        description = "Manage nodepools such as create, cordon, drian and delete"
        arguments = [
            (['-n', '--name'], dict(help="Pool name")),
            (['-pn', '--pool_name'], dict(help="Pool name to overwrite the default one")),
            (['-mt', '--machine_type'], dict(help="Machine type (default: n1-standard-8)")),
            (['-lt', '--label_type'], dict(help="Label type (default: apps)")),
            (['-ls', '--label_scale'], dict(help="Label scale (default: auto)")),
            (['-ds', '--disk_size'], dict(help="Disk size (default: 150)")),
            (['-dt', '--disk_type'], dict(help="Disk type (default: pd-ssd)")),
            (['-num', '--num_node'], dict(help="Number of nodes (default: 1)")),
            (['-min', '--min_node'], dict(help="Min nodes (default: 1)")),
            (['-max', '--max_node'], dict(help="Maximum nodes (default: 1)")),
            (['-prem', '--preemptible'], dict(help="Preemptible (default: false)"))
        ]
        usage = 'icarcli nodepool --environment <environment> --name <nodepool_name> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        echo("Will return nodepool summary", 'green', 'on_white')

    @command
    @expose(help="Create new node pool \n    Usage: icarcli nodepool create --name <pool name> "
                 "[--label_type <type>] [--label_scale <scale>] [--machine_type <machine_type>]")
    def create(self):
        name = self.app.pargs.name
        pool_name = name if self.app.pargs.pool_name is None else self.app.pargs.pool_name

        cluster = registry.cloud_auth.config.get('cluster')
        num_node = '1' if self.app.pargs.num_node is None else self.app.pargs.num_node
        min_node = '1' if self.app.pargs.min_node is None else self.app.pargs.min_node
        max_node = '10' if self.app.pargs.max_node is None else self.app.pargs.max_node
        scopes = 'https://www.googleapis.com/auth/projecthosting,storage-rw,cloud-platform,' \
                 'https://www.googleapis.com/auth/trace.append,https://www.googleapis.com/auth/monitoring'
        disk_size = '150' if self.app.pargs.disk_size is None else self.app.pargs.disk_size
        disk_type = 'pd-ssd' if self.app.pargs.disk_type is None else self.app.pargs.disk_type
        label_scale = 'auto' if self.app.pargs.label_scale is None else self.app.pargs.label_scale
        label_type = 'data' if self.app.pargs.label_type is None else self.app.pargs.label_type
        node_labels = 'environment=%s,scale=%s,type=%s' % (self.app.pargs.environment, label_scale, label_type)
        machine_type = 'n1-standard-8' if self.app.pargs.machine_type is None else self.app.pargs.machine_type
        preemptible = '--preemptible' \
            if self.app.pargs.preemptible is not None and self.app.pargs.preemptible == 'true' else ''

        create_command = self.create_command % (pool_name, cluster, min_node, max_node, num_node, scopes,
                                                disk_size, disk_type, node_labels, machine_type, preemptible)

        echo(create_command, 'yellow')
        proc = subprocess.run(create_command, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        echo(proc.stdout, 'blue')
        echo(proc.stderr, 'red')

    @command
    @expose(help="Create new node pool using config (main-pool, scale-pool, data-pool, job-pool)"
                 " \n    Usage: icarcli nodepool init --name <pool name>"
                 " [--pool_name <pool_name>]")
    def init(self):
        name = self.app.pargs.name
        cluster = registry.cloud_auth.config.get('cluster')

        config = self.config.get(name)
        if config is None:
            raise ValueError('Missing nodepool % config' % name)

        pool_name = name if self.app.pargs.pool_name is None else self.app.pargs.pool_name
        preemptible = '--preemptible' if config.get('preemptible', False) else ''

        create_command = self.create_command % (pool_name, cluster, config['min_node'],
                                                config['max_node'], config['num_node'], config['scopes'],
                                                config['disk_size'], config['disk_type'],
                                                config['node_labels'] % self.app.pargs.environment,
                                                config['machine_type'], preemptible)

        echo(create_command, 'yellow')
        proc = subprocess.run(create_command, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        echo(proc.stdout, 'blue')
        echo(proc.stderr, 'red')

    @command
    @expose(help="Cordon nodepool \n    Usage: icarcli nodepool cordon --name <pool name>")
    def cordon(self):
        proc = subprocess.run('for node in $(kubectl get nodes -l cloud.google.com/gke-nodepool=%s -o=name); '
                              'do kubectl cordon "$node"; done' % self.app.pargs.name, shell=True,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

        echo(proc.stdout, 'green')
        echo(proc.stderr, 'red')

    @command
    @expose(help="Drain nodepool \n    Usage: icarcli nodepool drain --name <pool name>")
    def drain(self):
        proc = subprocess.run('for node in $(kubectl get nodes -l cloud.google.com/gke-nodepool=%s -o=name); '
                              'do kubectl drain --force --ignore-daemonsets "$node"; done' % self.app.pargs.name,
                              shell=True,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

        echo(proc.stdout, 'green')
        echo(proc.stderr, 'red')

    @command
    @expose(help="Delete nodepool \n    Usage: icarcli nodepool delete --name <pool name>")
    def delete(self):
        proc = subprocess.run('gcloud container node-pools delete %s --cluster %s'
                              % (self.app.pargs.name, registry.cloud_auth.config['cluster']),
                              shell=True,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

        echo(proc.stdout, 'green')
        echo(proc.stderr, 'red')
