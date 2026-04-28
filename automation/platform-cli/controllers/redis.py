import datetime
import json
import os
import pickle
import subprocess

import redis as server
from cement.core.controller import expose
from google.cloud import storage

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from core.icarerrors import CommandError
from lib.io import echo
from objects import registry, lzma
from resources.messages import messages, flag_message


class RedisController(ICarBaseController):
    required = {'backup': ['name', 'country']}
    messages = {'backup': 'Backup Redis {name} for {environment} {country}'}
    scope = "cluster"
    config = {"stats": {"path": "/var/lib/redis/data/dump.rdb", "bucket": "data-backup-19anrz7d490d8mmz",
                        "server": "redis-server-stats"}}
    port = 6379
    db = 0

    class Meta:
        label = 'redis'
        description = messages['redis.info']
        arguments = [
            (['name'], dict(
                help=flag_message['redis.name'], nargs='?', default=[])),
            (['-c', '--country'], dict(help=flag_message['common.country'])),
            (['--host'], dict(help="Host for redis server")),
            (['-f', '--file'], dict(help="File for import/export (default: export.ljson)"))
        ]
        usage = ICarBaseController.Meta.usage.replace('{cmd}', label)
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help="Backup redis server")
    def backup(self):

        self.is_valid_country()

        config = self.config.get(self.app.pargs.name)
        if config is None:
            raise ValueError("Redis server name does not have a backup policy")

        path = config.get('path')
        bucket_name = config.get('bucket')
        server_name = config.get('server')

        server = "%s-%s" % (server_name, self.app.pargs.country)

        now = datetime.datetime.now()
        day_file = now.strftime("%A") + ".rdb"
        tmp_dir = "/tmp/" + server
        os.system("mkdir -p %s" % tmp_dir)

        # Remove Old backup files as it was causing disk space issue issue in /tmp folder
        os.system("rm -f %s/*.rdb " % tmp_dir)
        file_name = tmp_dir + "/" + day_file

        copy_command = 'gcloud compute scp icarcli@%s:%s %s --ssh-key-file %s/keys/id_rsa --strict-host-key-checking no' % (
            server, path, file_name, registry.docker_config_dir)

        try:
            os.remove("%s/%s" % (registry.data_dir, day_file))
        except OSError:
            pass

        echo(copy_command, 'green')

        # proco = subprocess.run([copy_command + ' --dry-run'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # cmd = proco.stdout.decode('utf-8')
        # echo(cmd, 'red')
        proc = subprocess.run(copy_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        error = proc.stderr.decode('utf-8')
        output = proc.stdout.decode('utf-8')

        if error != '' and 'Warning' not in error:
            raise CommandError('Copy command exited with the following error %s' % error)

        echo(output, 'green')
        echo(error, 'green')

        storage_client = storage.Client()
        bucket_file = 'redis-stats/%s/%s' % (self.app.pargs.country, day_file)
        registry.notify.send('log', '%s to %s' % (file_name, bucket_file))
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(bucket_file)
        blob.upload_from_filename(file_name)

    @command
    @expose(help="Hot backup")
    def hot_backup(self):
        compressor = lzma.LzmaCompressor()
        redis = server.StrictRedis(host=self.apps.pargs.host, port=self.port, db=self.db, decode_responses=True)
        filename = self.app.pargs.file
        with open(filename, 'w') as ljson:
            for key in redis.scan_iter():
                value = compressor.decompress(redis.get(key))
                value = pickle.loads(value)
                ljson.write(json.dumps({key: value}) + "\n")

    @command
    @expose(help="Hot restore")
    def hot_restore(self):
        compressor = lzma.LzmaCompressor()
        redis = server.StrictRedis(host=self.apps.pargs.host, port=self.port, db=self.db, decode_responses=True)
        filename = self.app.pargs.file
        with open(filename, 'r') as ljson:
            for line in ljson:
                print(line)
                obj = json.loads(line)
                for key, value in obj.items():
                    value = compressor.compress(pickle.dumps(value))
                    redis.set(key, value, px=None, nx=False, xx=False)

    @command
    @expose(help="Migrate server")
    def migrate(self):

        now = datetime.datetime.now()
        day_file = now.strftime("%A") + ".rdb"
        file_name = "/tmp/" + day_file

        key_file = os.path.join(registry.key_dir, 'id_rsa')
        old_server = '54.254.229.200'
        dump_path = '/home/admin/dump.rdb'

        command_copy = 'scp -r -i %s -P 61 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null admin@%s:%s ' \
                       './ ' % (key_file, old_server, dump_path)
        echo(command_copy)
        os.system(command_copy)

    @command
    @expose(help="Clear CRM RBAC")
    def clear_crm_rbac(self):
        env = self.app.pargs.environment
        redis_pod = getPod('redis-crm', env)
        echo(redis_pod)
        run_command = 'kubectl exec %s -- redis-cli KEYS "token:*:route"' % (redis_pod)
        echo(run_command)
        run_command_call =subprocess.run(run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            echo(run_command_call.stdout.decode('utf-8'))

    @command
    @expose(help="Flush redis-listing")
    def flush_listing(self):
        env = self.app.pargs.environment
        if env == "preprod":
            redis_pods = [
                    getPod('redis-listing-platform-a', env),
                    getPod('redis-listing-platform-b', env),
                    getPod('redis-listing-acme-ph', env),
                    getPod('redis-listing-platform-c', env),
                    getPod('redis-listing-platform-d', env)
                ]
        else:
            redis_pods = [getPod('redis-listing', env)]
        echo(redis_pods)
        for redis_pod in redis_pods:
            run_command = 'kubectl exec %s -- redis-cli FLUSHALL' % (redis_pod)
            echo(run_command)
            run_command_call =subprocess.run(run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if run_command_call.returncode == 0:
                echo(run_command_call.stdout.decode('utf-8'))
                
    @command
    @expose(help="Flush redis-api")
    def flush_api(self):
        env = self.app.pargs.environment
        redis_pod = getPod('redis-api', env)
        # echo(redis_pod)
        run_command = 'kubectl exec %s -- redis-cli FLUSHALL' % (redis_pod)
        echo(run_command)
        run_command_call =subprocess.run(run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if run_command_call.returncode == 0:
            echo(run_command_call.stdout.decode('utf-8'))

def getPod(service, env):
    if env == "preprod":
        env_prefix = ""
    else:
        env_prefix = env + '-'

    echo(env_prefix)
    echo(service)
    # Get pod according to labels
    container = subprocess.run(['kubectl', 'get', 'pod', '--selector=app=' + env_prefix + service, '-o',
                                "jsonpath='{.items[0].metadata.name}'"], stdout=subprocess.PIPE).stdout.decode(
        'utf-8').replace("'", "")
    echo("getpod")
    echo(container)
    return container