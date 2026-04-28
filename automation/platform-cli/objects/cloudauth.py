import configparser
import os
import subprocess

from lib.io import echo
from objects import registry
from objects.profiler import profile


class CloudAuth(object):
    env_config = {
        'preprod': {'project': '<GCP_PROJECT_PREPROD>', 'cluster': '<GCP_PROJECT_PREPROD>environment'},
        'production': {'project': '<GCP_PROJECT_PROD>', 'cluster': '<GCP_CLUSTER_NAME>'},
        'new-car': {'project': '<GCP_PROJECT_NEWCAR>', 'cluster': '<GCP_CLUSTER_NEWCAR>'}
    }

    default_zones = {
        'preprod': '<GCP_REGION>-a',
        'production': '<GCP_REGION>-a',
        'new-car': '<GCP_REGION>-a'
    }

    env = ''
    config = ''
    key_path = './'
    zone = ''
    key = ''
    credentials = None
    service_account_file = ' '
    service_account = None
    default_zone = '<GCP_REGION>-a'
    current_config = None

    def __init__(self, env, zone=None, cluster=None, account=None):

        self.env = env

        if zone is None:
            zone = self.default_zones.get(env)

        self.zone = self.default_zone if zone is None else zone

        # Get environment config
        if (env != 'production') and (env != 'new-car'):
            self.config = self.env_config.get('preprod')
            self.key = 'preprod'
        else:
            self.config = self.env_config.get(env)
            self.key = str(env)

        # Use passed in cluster
        if cluster is not None:
            self.config['cluster'] = cluster

        self.service_account = account

        echo('Loading config file %s %s' % (self.env, self.config), 'green', 'on_white')
        registry.profiler.record("cloud_auth", "load_config")

    @profile
    def login_gcloud(self):
        echo("Starting Login with Google Cloud", "green")

        self.current_config = {
            'compute': {'zone': ''},
            'core': {'account': '', 'project': ''},
        }

        current_config_list = subprocess.run(['gcloud config list  2> /dev/null'], shell=True, stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE).stdout.decode('utf-8')

        if current_config_list != "":
            self.current_config = configparser.ConfigParser()
            self.current_config.read_string(current_config_list)

        self.service_account_file = '%s/%s-service-account.json' % (self.key_path, self.key)
        # disabled use of key
        # @todo: Fix Later
        if os.environ.get('ENV_ICARCLI', '') == "production":
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.service_account_file

        token_error = ''
        if self.service_account is not None:
            if self.service_account != self.current_config['core']['account']:
                echo("Auth Passed Service Account", "blue")
                os.system("gcloud auth login %s" % self.service_account)
        else:
            # Check if token is valid
            check_token = subprocess.run("gcloud auth print-access-token", shell=True, stderr=subprocess.PIPE)
            token_error = check_token.stderr.decode('utf-8')

        # @todo: Fix Later
        if os.environ.get('ENV_ICARCLI', '') == "production":
            if "<CI_SERVICE_ACCOUNT>@%s.iam.gserviceaccount.com" % self.config['project'] != self.current_config['core'][
                'account'] or \
                    token_error != '':
                echo("Auth Service Account", "blue")
                os.system(
                    "gcloud auth activate-service-account <CI_SERVICE_ACCOUNT>@%s.iam.gserviceaccount.com --key-file=%s" % (
                        self.config['project'], self.service_account_file))

        print(self.config['project'])
        print(self.current_config['core']['project'])

        if self.config['project'] != self.current_config['core']['project']:
            echo("Show Project List", "blue")
            os.system("gcloud projects list")
            echo("Set Project to use", "blue")
            os.system("gcloud config set project %s" % self.config['project'])

        # registry.profiler.record("cloud_auth", "login_gcloud")

    @profile
    def set_zone(self):
        echo("Set Zone", "blue")
        os.system("gcloud config set compute/zone %s" % self.zone)

    @profile
    def login_cluster(self):
        echo("Configure local credentials", "blue")
        os.system("gcloud container clusters get-credentials %s" % self.config['cluster'])

    @profile
    def login_docker(self):
        echo("Login Docker", "blue")
        # os.system("gcloud docker -a")
        # As gcloud docker may not be supported in future versions of docker
        os.system("gcloud auth configure-docker --quiet")
        os.system("gcloud auth configure-docker asia-docker.pkg.dev --quiet")

    @profile
    def set_key_path(self, key_path):
        self.key_path = key_path
