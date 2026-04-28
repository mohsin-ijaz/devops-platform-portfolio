import subprocess

import mysql.connector
import requests
from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from objects import registry
from objects.profiler import profile
from resources.messages import messages, flag_message


class FlushController(ICarBaseController):
    required = {'default': ['service', 'project'], 'cdn': ['project', 'asset_path'], 'rbac': ['rbac_key']}
    services = {'memcache': {'command': "echo 'flush_all' | nc localhost 11211"},
                'redis': {'command': "redis-cli flushall"}}
    projects = ['api', 'crm', 'cms', 'ubp', 'accounts', 'icarsuite', 'minisite', '<GCP_PROJECT>-cms']
    config = {'memcache': {'command': "sh /flush.sh"}, 'redis': {'command': 'redis-cli flushall'}}
    messages = {'default': 'Flush {service} for {environment}'}
    scope = "cluster"
    credentials = {
        'preprod': {
            'user': '<DB_USER>',
            'password': '<DB_PASSWORD>',
            'database': '<DB_NAME>',
            'host': '<PREPROD_DB_HOST>'
        },
        'production': {
            'user': '<DB_USER>',
            'password': '<DB_PASSWORD>',
            'database': '<DB_NAME>',
            'host': '<PROD_DB_HOST>'
        },
        'staging': {
            'user': '<DB_USER>',
            'password': '<DB_PASSWORD>',
            'database': '<DB_NAME>',
            'host': 'staging-mysql'
        },
        'stag1': {
            'user': '<DB_USER>',
            'password': '<DB_PASSWORD>',
            'database': '<DB_NAME>',
            'host': 'stag1-mysql'
        },
        'stag2': {
            'user': '<DB_USER>',
            'password': '<DB_PASSWORD>',
            'database': '<DB_NAME>',
            'host': 'stag2-mysql'
        },
        'stag3': {
            'user': '<DB_USER>',
            'password': '<DB_PASSWORD>',
            'database': '<DB_NAME>',
            'host': 'stag3-mysql'
        },
        'stag4': {
            'user': '<DB_USER>',
            'password': '<DB_PASSWORD>',
            'database': '<DB_NAME>',
            'host': 'stag4-mysql'
        },
        'qa': {
            'user': '<DB_USER>',
            'password': '<DB_PASSWORD>',
            'database': '<DB_NAME>',
            'host': 'qa-mysql'
        },

    }

    ## WHERE YOU SPECIFY THE CDN.
    cdns = {
        'service-a': {
            'cdn_ids': ['<CDN77_RESOURCE_ID>'],
            'assets': [],
        },
        'service-b': {
            'cdn_ids': ['<CDN77_RESOURCE_ID>', '<CDN77_RESOURCE_ID>'],
            # TODO: add per-site CDN resource IDs
            'assets': [
                '/images/*',
                '/common/images/*',
                '/js/*',
                '/css/*',
            ]
        },
        'service-c': {
            'cdn_ids': ['<CDN77_RESOURCE_ID>'],
            'assets': [
                '/drive/common/js/all.js',
            ]
        },
    }

    class Meta:
        label = 'flush'
        description = messages['flush.info']
        arguments = [
            (['service'], dict(
                help=flag_message['common.service'], nargs='?', default=[])),
            (['-p', '--project'], dict(help=flag_message['common.project'])),
            (['-rk', '--rbac-key'], dict(help="RBAC Key")),
            (['-ap', '--asset-path'], dict(help="Asset path for the project, 'all' is keyword meaning run all"))
        ]
        usage = ICarBaseController.Meta.usage.replace('{cmd}', label)
        epilog = messages['flush.epilog']

    @command
    @expose(hide=True)
    def default(self):

        if self.app.pargs.project not in self.projects:
            raise ValueError('Wrong project %s' % str(self.app.pargs.project))

        env_prefix = self.app.pargs.environment + '-' if self.app.pargs.environment != 'preprod' else ''
        label = env_prefix + self.app.pargs.service + "-" + self.app.pargs.project

        config = self.config.get(self.app.pargs.service)
        credentials = self.credentials.get(self.app.pargs.environment)

        if config is None:
            raise NameError('No matching service %s command found' % self.app.pargs.service)

        registry.notify.send('log', 'Flushing data for %s' % label)

        # checks if redis crm is being flushed on any environment, then also flush redis icarsuite using `redis-cli -n 7 FLUSHDB` command on the same environment, and truncate <GCP_PROJECT>_CRMPortal.ContactToken table in MySQL on the same environment
        if self.app.pargs.project == 'crm' and self.app.pargs.service == 'redis':

            icarsuite_label = env_prefix + self.app.pargs.service + '-icarsuite'

            containers = subprocess.run(
                ['kubectl', 'get', 'pod', '--selector=app=' + label, '-o', "jsonpath='{.items..metadata.name}'"],
                stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "").split()

            icarsuite_containers = subprocess.run(
                ['kubectl', 'get', 'pod', '--selector=app=' + icarsuite_label, '-o',
                 "jsonpath='{.items..metadata.name}'"],
                stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "").split()

            echo("Total Number of Containers Running: %s" % len(containers), 'white', 'on_blue')
            echo("Total Number of icarsuite Containers Running: %s" % len(icarsuite_containers), 'white', 'on_blue')

            for container in containers:
                echo("Containers been flushed %s using %s" % (container, config.get('command')), 'blue')
                echo(
                    subprocess.run(registry.term + "kubectl exec %s -- %s" % (container, config.get('command')),
                                   shell=True,
                                   stdout=subprocess.PIPE).stdout.decode('utf-8'), 'yellow')

            # flush redis icarsuite using `redis-cli -n 7 FLUSHDB` command
            for icarsuite_container in icarsuite_containers:
                icarsuite_redis_flush_command = 'redis-cli -n 7 FLUSHDB'

                echo("icarsuite Containers been flushed %s using %s" % (
                    icarsuite_container, icarsuite_redis_flush_command), 'blue')
                echo(
                    subprocess.run(registry.term + "kubectl exec %s -- %s" % (container, icarsuite_redis_flush_command),
                                   shell=True,
                                   stdout=subprocess.PIPE).stdout.decode('utf-8'), 'yellow')

            # truncate <GCP_PROJECT>_CRMPortal.ContactToken in MySQL
            connection = mysql.connector.connect(
                host=credentials.get('host'),
                user=credentials.get('user'),
                password=credentials.get('password'),
                database=credentials.get('database')
            )

            echo("Truncated <GCP_PROJECT>_CRMPortal.ContactToken table in MySQL", 'blue')
            cursor = connection.cursor()
            cursor.execute("TRUNCATE TABLE ContactToken")
            connection.close()

        else:
            containers = subprocess.run(
                ['kubectl', 'get', 'pod', '--selector=app=' + label, '-o', "jsonpath='{.items..metadata.name}'"],
                stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "").split()

            echo("Total Number of Containers Running: %s" % len(containers), 'white', 'on_blue')

            for container in containers:
                echo("Containers been flushed %s using %s" % (container, config.get('command')), 'blue')
                echo(
                    subprocess.run(registry.term + "kubectl exec %s -- %s" % (container, config.get('command')),
                                   shell=True,
                                   stdout=subprocess.PIPE).stdout.decode('utf-8'), 'yellow')

        return True

    @command
    @expose(help="Clears CDN for projects")
    def cdn(self):

        # Can add it for new-car, if they need it.
        config = self.cdns.get(self.app.pargs.project)
        if self.app.pargs.environment != "production" or config is None:
            echo("No CDN to clear. Only needed in production OR for certain projects.", "red")
            return False

        cdn_ids = config.get('cdn_ids', '')
        assets = config.get('assets', {})

        asset_path = self.app.pargs.asset_path
        echo(cdn_ids)
        if cdn_ids != '' and len(asset_path) != 0:  # --asset-path ${ASSET_PATH}
            if asset_path == 'all':
                self._flush_all_cdn(cdn_ids)
            elif asset_path == 'standard':
                self._flush_cdn_standard(cdn_ids, assets)
            else:
                self._flush_cdn(cdn_ids, asset_path)

    @command
    @expose(
        help="Clears tokens from redis, memcached and truncates <GCP_PROJECT>_CRMPortal.ContactToken table in MySQL in "
             "production environment")
    def tokens(self):

        if self.app.pargs.environment != "production":
            echo("Error: This command can only be run on production environment", "red")
            return False

        memcache_flush_command = 'sh /flush.sh'
        redis_crm_flush_command = 'redis-cli flushall'
        redis_icarsuite_flush_command = 'redis-cli -n 7 FLUSHDB'
        redis_icarsuite_refresh_token_flush_command = 'redis-cli -n 9 FLUSHDB'
        credentials = self.credentials.get(self.app.pargs.environment)

        # get pod names
        redis_crm_container = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=redis-crm', '-o', "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")

        redis_icarsuite_container = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=redis-icarsuite', '-o', "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")

        memcache_crm = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=memcache-crm', '-o', "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")

        memcache_lapi_mobil123 = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=memcache-lapi-platform-c', '-o',
             "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")

        memcache_lapi_carlist = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=memcache-lapi-platform-a', '-o',
             "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")

        memcache_lapi_one2car = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=memcache-lapi-platform-d', '-o',
             "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")

        memcache_lapi_carmudi = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=memcache-lapi-platform-b', '-o',
             "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")

        # flush redis keys
        echo("%s container flushed using %s" % (redis_crm_container, redis_crm_flush_command), 'blue')
        echo(subprocess.run(registry.term + "kubectl exec %s -- %s" % (redis_crm_container, redis_crm_flush_command),
                            shell=True,
                            stdout=subprocess.PIPE).stdout.decode('utf-8'), 'yellow')

        echo("%s container flushed using %s" % (redis_icarsuite_container, redis_icarsuite_flush_command), 'blue')
        echo(subprocess.run(
            registry.term + "kubectl exec %s -- %s" % (redis_icarsuite_container, redis_icarsuite_flush_command),
            shell=True,
            stdout=subprocess.PIPE).stdout.decode('utf-8'), 'yellow')

        echo("%s container flushed using %s" % (redis_icarsuite_container, redis_icarsuite_refresh_token_flush_command),
             'blue')
        echo(subprocess.run(
            registry.term + "kubectl exec %s -- %s" % (redis_icarsuite_container,
                                                       redis_icarsuite_refresh_token_flush_command),
            shell=True,
            stdout=subprocess.PIPE).stdout.decode('utf-8'), 'yellow')

        # flush memcached keys
        memcache_containers = [memcache_crm, memcache_lapi_mobil123, memcache_lapi_carlist, memcache_lapi_one2car,
                               memcache_lapi_carmudi]

        for container in memcache_containers:
            echo("%s container flushed using %s" % (container, memcache_flush_command), 'blue')
            echo(subprocess.run(registry.term + "kubectl exec %s -- %s" % (container, memcache_flush_command),
                                shell=True,
                                stdout=subprocess.PIPE).stdout.decode('utf-8'), 'yellow')

        # truncate <GCP_PROJECT>_CRMPortal.ContactToken table in MySQL
        connection = mysql.connector.connect(
            host=credentials.get('host'),
            user=credentials.get('user'),
            password=credentials.get('password'),
            database=credentials.get('database')
        )

        cursor = connection.cursor()
        cursor.execute("TRUNCATE TABLE ContactToken")
        connection.close()
        echo("Truncated <GCP_PROJECT>_CRMPortal.ContactToken table in MySQL", 'blue')

    @command
    @expose(help="Clear RBAC from redis")
    def rbac(self):
        echo("RBAC Flush Keys from Redis", "white", "on_blue")
        if "*" in self.app.pargs.rbac_key:
            raise ValueError("Invalid Key")
        route_key = "token:%s:route" % self.app.pargs.rbac_key
        redis_crm_container = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=redis-crm', '-o', "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")
        redis_del = "kubectl exec %s -- redis-cli DEL %s" % (redis_crm_container, route_key)
        echo(redis_del, "red")
        redis_del_call = subprocess.run(redis_del, shell=True, stdout=subprocess.PIPE)
        echo(redis_del_call.stdout.decode('utf-8'))

    @command
    @expose(help="Show RBAC routes from redis")
    def rbac_show_routes(self):
        echo("RBAC Show Routes", "white", "on_blue")
        route_key = "*route"
        redis_crm_container = subprocess.run(
            ['kubectl', 'get', 'pod', '--selector=app=redis-crm', '-o', "jsonpath='{.items..metadata.name}'"],
            stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")
        redis_keys = "kubectl exec %s -- redis-cli KEYS %s" % (redis_crm_container, route_key)
        echo(redis_keys, "blue")
        redis_keys_call = subprocess.run(redis_keys, shell=True, stdout=subprocess.PIPE)
        echo(redis_keys_call.stdout.decode('utf-8'))

    @command
    @expose(help="Remove non-running mysql pods")
    def non_running_mysql(self):
        env_prefix = self.app.pargs.environment + '-' if self.app.pargs.environment != 'preprod' else ''
        env_mysql = env_prefix + 'mysql'
        get_pods_cmd = "kubectl get po | grep ^%s | grep -vi running | awk '{print $1}' | xargs kubectl delete pod" % (env_mysql)
        echo(get_pods_cmd, "blue")
        get_pods_cmd_call = subprocess.run(get_pods_cmd, shell=True, stdout=subprocess.PIPE)
        if get_pods_cmd_call != "":
            echo("Deleted unhealthy pods:", "green")
            echo(get_pods_cmd_call.stdout.decode('utf-8'))

    @profile
    def _flush_cdn(self, cdn_ids, assets):
        # python3 icarcli flush cdn --environment production --project ubp --asset-path "/js/*"
        url = 'https://api.cdn77.com/v2.0/data/purge'
        for cdn_id in cdn_ids:
            myobj = {'cdn_id': cdn_id, 'url[]': assets, 'login': 'tools@<GCP_PROJECT_DOMAIN>',
                     'passwd': '<CDN77_API_PASSWORD>'}
            x = requests.post(url, data=myobj)
            echo(x.text, "green")

    @profile
    def _flush_cdn_standard(self, cdn_ids, assets):
        # python3 icarcli flush cdn --environment production --project ubp --asset-path standard
        url = 'https://api.cdn77.com/v2.0/data/purge'
        for cdn_id in cdn_ids:
            for asset in assets:
                myobj = {'cdn_id': cdn_id, 'url[]': asset, 'login': 'tools@<GCP_PROJECT_DOMAIN>',
                         'passwd': '<CDN77_API_PASSWORD>'}
                x = requests.post(url, data=myobj)
                echo(x.text, "green")

    @profile
    def _flush_all_cdn(self, cdn_ids):
        # python3 icarcli flush cdn --environment production --project ubp --asset-path all
        url = 'https://api.cdn77.com/v2.0/data/purge-all'
        for cdn_id in cdn_ids:
            myobj = {'cdn_id': cdn_id, 'login': 'tools@<GCP_PROJECT_DOMAIN>', 'passwd': '<CDN77_API_PASSWORD>'}
            x = requests.post(url, data=myobj)
            echo(x.text, "green")
