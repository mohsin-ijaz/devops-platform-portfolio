import datetime
import os
import re
import shutil
import subprocess
from itertools import groupby
from subprocess import PIPE

import yaml
from cement.core.controller import expose
from cement.utils import shell
from google.cloud import storage

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from core.icarerrors import CommandError
from lib.io import echo
from objects import registry
from resources.messages import messages


class MongoController(ICarBaseController):
    required = {'backup': [], 'migrate': [], 'restore_data': ['source']}
    messages = {'default': 'Backup Mongo {name} for {environment}'}
    scope = 'cluster'
    config = {'bucket': 'data-backup-19anrz7d490d8mmz'}
    credentials = {
        'preprod': {
            'user': 'root_admin',
            'pass': 'gears6',
            'hosts': '<GCP_PROJECT_PREPROD>mongo0.<GCP_PROJECT_DOMAIN>:27017,<GCP_PROJECT_PREPROD>mongo1.<GCP_PROJECT_DOMAIN>:27017,<GCP_PROJECT_PREPROD>mongo2.<GCP_PROJECT_DOMAIN>:27017'
        },
        'production': {
            'user': 'root_admin',
            'pass': 'gears6',
            'hosts': 'mongo0.<GCP_PROJECT_DOMAIN>:27017,mongo1.<GCP_PROJECT_DOMAIN>:27017,mongo2.<GCP_PROJECT_DOMAIN>:27017'
        }

    }

    class Meta:
        label = 'mongo'
        description = messages['cluster.info']
        arguments = [
            (['-q', '--quite'], dict(help="Run the command without prompts")),
            (['-src', '--source'], dict(help="From what environment source was dumped")),
        ]
        usage = 'icarcli mongo <service_name> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='Migrate data')
    def migrate(self):
        """ Migrate data from old AWS server to google cloud """

        dump_path = os.path.join(registry.data_dir, 'data', self.app.pargs.environment, 'mongo')

        # load the config build file

        servers_config = None
        with open(registry.config_dir + '/servers.yaml') as f:
            servers_config = yaml.safe_load(f)

        print(servers_config)

        old_server_name = 'ubp' if self.app.pargs.environment == 'preprod' else 'mongo1'
        old_server = servers_config['instances']['old'][self.app.pargs.environment][old_server_name]

        print(registry.current_dir)
        command_dump = 'mongodump'

        if os.path.exists(dump_path + '/dump'):
            print('Dump already exists')
            shutil.rmtree(dump_path + '/dump')
            print('Delete existing dumps')

        if not os.path.exists(dump_path):
            os.makedirs(dump_path)
            print('Create dump path')

        key_file = os.path.join(registry.key_dir, 'id_rsa')

        os.system('ssh -i %s -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null admin@%s "%s"' % (
            key_file, old_server, command_dump))
        os.system('scp -r -i %s -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null admin@%s:./dump %s' % (
            key_file, old_server, dump_path + os.path.sep))

        pod = 'mongo-0'
        remote_dir = './'
        container = 'mongodb'

        command_remove = 'rm -Rf ./dump'
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_remove))

        echo(registry.term + 'kubectl cp %s %s:%s -c %s' % (
            dump_path + os.path.sep + 'dump', pod, remote_dir, container))
        os.system(registry.term + 'kubectl cp %s %s:%s -c %s' % (
            dump_path + os.path.sep + 'dump', pod, remote_dir, container))

        command_check = 'ls -al'
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_check))

        command_restore = 'mongorestore'
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_restore))

    ######################

    @command
    @expose(help='Backup data, compress and upload to GCP bucket')
    def backup(self):

        env = self.app.pargs.environment
        credential = self.credentials.get(env)
        mongo_user = credential.get('user')
        mongo_pass = credential.get('pass')
        mongo_hosts = credential.get('hosts')
        mongo_uri = "mongodb://" + mongo_user + ":" + mongo_pass + "@" + mongo_hosts + "/" + "?authSource=admin&readPreference=secondary"
        now = datetime.datetime.now()
        file = 'mongo-' + now.strftime("%A") + '.tar.gz'

        # dump
        command_dump_mongo = '%smongodump --uri %s' % (registry.term, mongo_uri)
        echo(command_dump_mongo, 'yellow')
        command_call = subprocess.run(command_dump_mongo, shell=True, stdout=PIPE, stderr=PIPE)

        # deleting admin database dump as its not needed for restore
        command_delete_admin_database = '%srm -Rf dump/admin' % (registry.term)
        os.system(command_delete_admin_database)
        echo(command_delete_admin_database, 'yellow')

        # compress backup
        command_compress = registry.term + 'tar -czvf %s dump' % (file)
        echo(command_compress, 'yellow')
        os.system(command_compress)

        bucket_name = self.config.get('bucket')
        if bucket_name is None:
            raise ValueError("Bucket config not found")

        storage_client = storage.Client()
        bucket_file = 'mongo/%s' % file
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(bucket_file)
        blob.upload_from_filename(file)

    @command
    @expose(help='Backup data from shards, compress and upload to GCP bucket')
    def backup_shards(self):

        # define mongodb credentials based on environment
        credentials = {'preprod': {'mongo_user': 'main_admin', 'mongo_pass': 'NNTi63US5INw'},
                       'production': {'mongo_user': 'main_admin', 'mongo_pass': 'NNTi63US5INw'}}
        config = credentials.get(self.app.pargs.environment)
        if config is None:
            raise ValueError('Environment not found.')
        mongo_user = config.get('mongo_user')
        mongo_pass = config.get('mongo_pass')

        # get all mongodb pods with label 'maindb' and 'configdb'
        s = subprocess.run(["kubectl", "get", "pods", "-l", "tier in (maindb, configdb)"], capture_output=True)

        # regex pattern to get just pod names
        s_pat = r"(mongod-\w+-\d{1,2})"

        # get pod names based on defined regex pattern
        data_pods = re.findall(s_pat, str(s.stdout))

        # check pods if they are secondary then add to new list
        secondary_pods = []
        for data_pod in data_pods:
            c = subprocess.run(["kubectl", "exec", data_pod, "--", "mongo", "-u", mongo_user, "-p", mongo_pass,
                                "--authenticationDatabase=admin", "--eval", "rs.isMaster().secondary"],
                               stdout=subprocess.PIPE).stdout.decode('utf-8')
            if "true" in c:
                secondary_pods.append(data_pod)

        # group pods by similar name in list
        grouped_secondary_pods = [list(i) for j, i in
                                  groupby(secondary_pods, lambda x: x.rsplit(sep='-', maxsplit=1)[0])]

        # just get the first item in each nested list and append to new list
        filtered_secondary_pods = []
        for item in grouped_secondary_pods:
            filtered_secondary_pods.append(item[0])

        router_pod = 'mongos-router-0'
        dump_path = os.path.join(registry.data_dir, 'data', self.app.pargs.environment, 'mongo')
        now = datetime.datetime.now()
        file_csrs = 'mongocsrs' + now.strftime("%A%-H") + '.tar.gz'
        local_file_csrs = os.path.join(dump_path, file_csrs)
        remote_dir = '/dump'

        if os.path.exists(local_file_csrs):
            print('Dump already exists')
            os.remove(local_file_csrs)
            print('Delete existing dump')

        for filtered_secondary_pod in filtered_secondary_pods:
            file_shard = filtered_secondary_pod + now.strftime("%A%-H") + '.tar.gz'
            local_file_shard = os.path.join(dump_path, file_shard)
            if os.path.exists(local_file_shard):
                print('Dump already exists')
                os.remove(local_file_shard)
                print('Delete existing shard dump')

        if not os.path.exists(dump_path):
            os.makedirs(dump_path)
            print('Create dump path')

        # disable balancer on mongo router
        command_disable_balancer = '%skubectl exec %s -- mongo -u %s -p %s --authenticationDatabase=admin --eval "db=db.getSiblingDB(\'config\');sh.stopBalancer()"' % (
            registry.term, router_pod, mongo_user, mongo_pass)
        echo(command_disable_balancer, 'yellow')
        os.system(command_disable_balancer)

        # lock secondary replica sets
        for filtered_secondary_pod in filtered_secondary_pods:
            command_lock_shard = '%skubectl exec %s -- mongo -u %s -p %s --authenticationDatabase=admin --eval "db.fsyncLock()"' % (
                registry.term, filtered_secondary_pod, mongo_user, mongo_pass)
            os.system(command_lock_shard)
            echo(command_lock_shard, 'yellow')

        # dump from locked secondary replica set pods
        for filtered_secondary_pod in filtered_secondary_pods:
            command_dump_shard = '%skubectl exec %s -- mongodump --oplog -u %s -p %s --authenticationDatabase=admin' % (
                registry.term, filtered_secondary_pod, mongo_user, mongo_pass)
            os.system(command_dump_shard)
            echo(command_dump_shard, 'yellow')

        # dump from mongo router to create complete backup for restore to preprod env
        command_dump_mongos = '%skubectl exec %s -- mongodump -u %s -p %s --authenticationDatabase=admin' % (
            registry.term, router_pod, mongo_user, mongo_pass)
        command_delete_admin_database = '%skubectl exec %s -- rm -Rf /dump/admin' % (registry.term, router_pod)
        command_delete_config_database = '%skubectl exec %s -- rm -Rf /dump/config' % (registry.term, router_pod)
        os.system(command_dump_mongos)
        echo(command_dump_mongos, 'yellow')
        # deleting admin and config database dump as its not needed for restore to preprod env
        os.system(command_delete_admin_database)
        echo(command_delete_admin_database, 'yellow')
        os.system(command_delete_config_database)
        echo(command_delete_config_database, 'yellow')

        # unlock secondary replica sets
        for filtered_secondary_pod in filtered_secondary_pods:
            command_unlock_shard = '%skubectl exec %s -- mongo -u %s -p %s --authenticationDatabase=admin --eval "db.fsyncUnlock()"' % (
                registry.term, filtered_secondary_pod, mongo_user, mongo_pass)
            os.system(command_unlock_shard)
            echo(command_unlock_shard, 'yellow')

        # re-enable balancer on mongo router
        command_enable_balancer = '%skubectl exec %s -- mongo -u %s -p %s --authenticationDatabase=admin --eval "db=db.getSiblingDB(\'config\');sh.setBalancerState(true)"' % (
            registry.term, router_pod, mongo_user, mongo_pass)
        echo(command_enable_balancer, 'yellow')
        os.system(command_enable_balancer)

        # compress dumps in shards
        for filtered_secondary_pod in filtered_secondary_pods:
            shard_pod_file = filtered_secondary_pod + now.strftime("%A%-H") + '.tar.gz'
            command_compress_shard = '%skubectl exec %s -- %s' % (
                registry.term, filtered_secondary_pod, 'tar -czvf %s %s' % (shard_pod_file, remote_dir))
            os.system(command_compress_shard)
            echo(command_compress_shard, 'yellow')

        # compress dump in mongo router for restore to preprod env
        mongos_pod_file = 'preprod_restore.tar.gz'
        command_compress_mongos = '%skubectl exec %s -- %s' % (
            registry.term, router_pod, 'tar -czvf %s %s' % (mongos_pod_file, remote_dir))
        os.system(command_compress_mongos)
        echo(command_compress_mongos, 'yellow')

        # copy compressed dumps from shards to local
        for filtered_secondary_pod in filtered_secondary_pods:
            shard_pod_file = filtered_secondary_pod + now.strftime("%A%-H") + '.tar.gz'
            local_file_shard = os.path.join(dump_path, shard_pod_file)
            command_copy_shard = '%skubectl cp %s:%s %s' % (
                registry.term, filtered_secondary_pod, shard_pod_file, local_file_shard)
            os.system(command_copy_shard)
            echo(command_copy_shard, 'yellow')

        # copy full backup for preprod env from mongo router to local
        mongos_pod_file = 'preprod_restore.tar.gz'
        local_file_mongos = os.path.join(dump_path, mongos_pod_file)
        command_copy_mongos = '%skubectl cp %s:%s %s' % (registry.term, router_pod, mongos_pod_file, local_file_mongos)
        os.system(command_copy_mongos)
        echo(command_copy_mongos, 'yellow')

        print(dump_path)
        os.system("ls -lh %s/" % dump_path)

        bucket_name = self.config.get('bucket')
        if bucket_name is None:
            raise ValueError("Bucket config not found")

        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)

        # upload compressed shard dumps to GCS bucket
        for filtered_secondary_pod in filtered_secondary_pods:
            shard_pod_file = filtered_secondary_pod + now.strftime("%A%-H") + '.tar.gz'
            local_file_shard = os.path.join(dump_path, shard_pod_file)
            bucket_file_shard = 'mongodb/' + now.strftime("%d%-b") + '/' + shard_pod_file
            blob_shard = bucket.blob(bucket_file_shard)
            blob_shard.upload_from_filename(local_file_shard)
            echo('Uploaded shard dump to GCS bucket', 'green')
            # delete
            command_delete = '%skubectl exec %s -- %s' % (registry.term, filtered_secondary_pod, 'rm *.tar.gz')
            os.system(command_delete)
            echo("Remove backup files - " + command_delete, 'green')

        # upload compressed preprod_restore.tar.gz to GCS bucket
        mongos_pod_file = 'preprod_restore.tar.gz'
        local_file_mongos = os.path.join(dump_path, mongos_pod_file)
        bucket_file_mongos = 'mongodb/' + now.strftime("%d%-b") + '/' + mongos_pod_file
        blob_mongos = bucket.blob(bucket_file_mongos)
        blob_mongos.upload_from_filename(local_file_mongos)
        echo('Uploaded database dump for preprod to GCS bucket', 'green')

    @command
    @expose(help='Restore data')
    def restore(self):

        pod = 'mongo-0'
        container = 'mongodb'
        dump_path = os.path.join(registry.data_dir, 'data', self.app.pargs.environment, 'mongo')

        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)

        file = 'mongo' + yesterday.strftime("%A%-H") + '.tar.gz'
        local_file = os.path.join(dump_path, file)
        remote_file = './' + file
        remote_dir = '/dump'

        if os.path.exists(local_file):
            print('Dump already exists')
            os.remove(local_file)
            # shutil.rmtree(local_file)
            print('Delete existing dump')

        if not os.path.exists(dump_path):
            os.makedirs(dump_path)
            print('Create dump path')

        os.system("ls %s/" % dump_path)

        bucket_name = self.config.get('bucket')

        if bucket_name is None:
            raise ValueError("Bucket config not found")

        storage_client = storage.Client()
        bucket_file = 'mongo/%s' % file
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(bucket_file)
        blob.download_to_filename(local_file)

        # Strip out user information if not prod environment
        # if self.pargs.environment != 'production':
        # Remove the two files, users and contact us

        echo('Restore data from GCP', 'green')

    @command
    @expose(help="Restore mongo from prod to preprod")
    def dump_data(self):
        dump_path = os.path.join(registry.data_dir, 'data', self.app.pargs.environment, 'mongo', 'refresh')

        if os.path.exists(dump_path + '/dump'):
            print('Dump already exists', 'yellow')
            shutil.rmtree(dump_path + '/dump')
            print('Deleted existing dumps', 'red')

        if not os.path.exists(dump_path):
            os.makedirs(dump_path)
            print('Create dump path')

        pod = 'mongo-0'
        remote_dir = 'dump'
        container = 'mongodb'
        local_dir = os.path.join(dump_path, 'dump')
        echo(local_dir, 'red')

        command_check = 'ls -al dump'
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_check))

        command_remove = 'rm -Rf ./dump'
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_remove))

        command_check = 'ls -al dump'
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_check))

        command_dump = 'mongodump'
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_dump))

        command_check = 'ls -al dump'
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_check))

        command_copy = registry.term + 'kubectl cp %s:%s %s -c %s' % (
            pod, remote_dir, local_dir, container)

        echo(command_copy)
        os.system(command_copy)

        os.system('ls -al %s' % local_dir)

    @command
    @expose(help="Restore mongo from prod to preprod")
    def restore_data(self):

        if self.app.pargs.quite != "true":

            p = shell.Prompt("Are you sure you want to run restore, if you proceed your %s data dump will be restored"
                             " into %s Mongo DB irreversibly" % (self.app.pargs.source, self.app.pargs.environment),
                             options=[
                                 'Yes',
                                 'no'
                             ]
                             )
            if p.input != "Yes":
                return False

        dump_path = os.path.join(registry.data_dir, 'data', self.app.pargs.source, 'mongo', 'refresh')
        pod = 'mongo-0'
        remote_dir = 'dump'
        container = 'mongodb'
        local_dir = os.path.join(dump_path, 'dump')
        echo(local_dir, 'red')

        os.system('ls -al %s' % local_dir)

        command_remove = 'rm -Rf %s' % remote_dir
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_remove))

        command_copy = registry.term + 'kubectl cp %s %s:%s -c %s' % (
            local_dir, pod, remote_dir, container)

        echo(command_copy)
        os.system(command_copy)

        command_check = 'ls -al'
        os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_check))

        # Get all dbs found during the restore
        dbs = os.listdir(local_dir)
        if len(dbs) == 0:
            raise CommandError("There is a problem with looking up dump folders, "
                               "please run icarcli dumo-data before running this command.")

        if self.app.pargs.environment == 'preprod':

            # Create mongo for all preprod cluster environments
            # loop all available environments
            for environment in self.environments:
                # loop all dbs found in dump
                for db in dbs:
                    command_restore = 'mongorestore -d %s-%s dump/%s' % (environment, db, db)
                    os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_restore))
                    # Lack of security is currently the biggest problem in our mongo implementation
                    # mongo <GCP_PROJECT_PREPROD>acoty --eval 'db.createUser({user: "dev", pwd: "dev", roles: ["readWrite"]})'

                    if db == "acoty":
                        command_create_user = "mongo %s-acoty --eval 'db.createUser({ user: \"dev\"," \
                                              " pwd: \"dev\", roles: [\"readWrite\"] })'" % environment
                        echo(command_create_user, "green")
                        os.system(
                            registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_create_user))
        else:
            command_restore = 'mongorestore'
            os.system(registry.term + 'kubectl exec -it %s -c %s -- %s' % (pod, container, command_restore))
