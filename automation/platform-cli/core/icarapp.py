import os
import platform

from cement.core import foundation, handler
from cement.utils.misc import init_defaults

from controllers import *
from core import icarcontroller
from objects import registry
from objects.configmanager import ConfigManager
from objects.cloudauth import CloudAuth
from objects.secretmanager import SecretManager
from resources.messages import flag_message


def pre_hook(app):
    default_env = {
        'preprod': 'preprod',
        'stag0': 'preprod',
        'stag1': 'preprod',
        'stag2': 'preprod',
        'stag3': 'preprod',
        'stag4': 'preprod',
        'stag5': 'preprod',
        'staging': 'preprod',
        'qa': 'preprod',
        'production': 'production',
        'new-car': 'new-car'
    }

    """"Do enable authentication for the command before anything else is done"""
    if app.pargs.environment is None:
        return False

    environment = app.pargs.environment
    if environment not in default_env:
        return False

    env = default_env.get(environment)
    print("Env: " + env)

    # Create secret manager
    secret_manager = SecretManager()
    secret_manager.update_secrets()
    registry.secret_manager = secret_manager

    # Create cloud auth object
    cloud_auth = CloudAuth(env, app.pargs.zone, app.pargs.cluster, app.pargs.service_account)

    if app.pargs.auto_auth != 'false':
        cloud_auth.set_key_path(registry.key_dir)
        cloud_auth.login_gcloud()
        cloud_auth.set_zone()

    # Add it in registry for later use
    registry.cloud_auth = cloud_auth

    return True


# def post_hook(app):
#     #### Command to run before any command
#     registry.controller.post_command()
#     #############


class ICAR(foundation.CementApp):
    class Meta:

        # What to call the command
        label = 'icar'

        # Base Controller is set here
        base_controller = icarcontroller.ICarController

        # These are the defaults, not entirely sure where they are used
        defaults = init_defaults('icar', 'log.logging')
        defaults['log.logging']['level'] = 'WARNING'
        config_defaults = defaults

        # define any hooks
        hooks = [
            ('post_argument_parsing', pre_hook),
            # ('post_run', post_hook)
        ]

    def __init__(self, label=None, **kw):
        super(ICAR, self).__init__(label, **kw)
        registry.app = self

    def setup(self):

        # Detect platform (windows, mac or linux)
        registry.platform = platform.system()
        print("Platform command is running on:", registry.platform)

        registry.data_dir = '/tmp'
        if registry.platform == "Windows":
            registry.term = "winpty "
            registry.data_dir = 'C:\\tmp'

        if registry.platform == "Darwin":
            registry.data_dir = '/private/tmp'

        # Testing the new config manager
        cfg = ConfigManager()
        cfg.load_config()

        # exit(1)

        # Register all controllers
        handler.register(auth.AuthController)
        handler.register(flush.FlushController)
        handler.register(cluster.ClusterController)
        handler.register(compute.ComputeController)
        handler.register(job.JobController)
        handler.register(mongo.MongoController)
        handler.register(postgres.PostgresController)
        handler.register(redis.RedisController)
        handler.register(nodepool.NodepoolController)
        handler.register(deployment.DeploymentController)
        handler.register(git.GitController)
        handler.register(message.MessageController)
        handler.register(pod.PodController)
        handler.register(image.ImageController)
        handler.register(cicd.CicdController)
        handler.register(build.BuildController)
        handler.register(runtest.RunTestController)
        handler.register(docker.DockerController)
        handler.register(storage.StorageController)
        handler.register(solr.SolrController)
        handler.register(mysql.MysqlController)
        handler.register(debezium.DebeziumController)
        handler.register(cassandra.CassandraController)
        handler.register(kafka.KafkaController)
        handler.register(app.AppController)
        handler.register(security_policies.SecurityPoliciesController)
        handler.register(infra.InfraController)
        handler.register(copycontent.CopyContentController)
        handler.register(fresque.FresqueController)
        handler.register(image_server.ImageServerController)
        handler.register(bigquery.BigqueryController)
        handler.register(mysqlawsnap.MysqlAwSnapController)
        handler.register(gstorage.GstorageController)
        handler.register(podjob.PodJobController)
        handler.register(security_ingress.SecurityIngressController)
        handler.register(kustomize.KustomizeController)

        # Calls parent setup
        super(ICAR, self).setup()

        # Register global arguments
        self.add_arg('-e', '--environment',
                     help=flag_message['base.environment'])
        self.add_arg('-cls', '--cluster',
                     help=flag_message['base.environment'])
        self.add_arg('-z', '--zone', help=flag_message['base.environment'])
        self.add_arg('-sa', '--service_account',
                     help=flag_message['base.environment'])
        self.add_arg('--ref', help=flag_message['common.ref_number'])
        self.add_arg('-aa', '--auto_auth',
                     help="Auth auth true or false (default: true)")
