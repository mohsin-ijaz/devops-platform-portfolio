import datetime
import os
import subprocess

from cement.core.controller import expose
from google.cloud import storage

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from core.icarerrors import CommandError
from lib.io import echo
from lib.measure import format_bytes
from objects import registry
from resources.messages import messages


class PostgresController(ICarBaseController):
    required = {'backup': [], 'migrate': [], 'restore_data': ['source']}
    messages = {'default': 'Backup Postgres {name} for {environment}'}
    scope = 'cluster'
    config = {'bucket': 'data-backup-19anrz7d490d8mmz'}

    class Meta:
        label = 'postgres'
        description = messages['cluster.info']
        arguments = [
            (['-q', '--quite'], dict(help="Run the command without prompts")),
            (['-src', '--source'], dict(help="From what environment source was dumped")),
            (['-svc', '--service'],
             dict(help="From which postgres source it will backup from")),
        ]
        usage = 'icarcli postgres <service_name> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='Backup data')
    def backup(self):

        svc = self.app.pargs.service

        if svc == 'icardata' and self.app.pargs.environment == 'preprod':
            pod = svc + '-postgresql-0'
            container = svc + '-postgresql'
            dump_path = os.path.join(
                registry.data_dir, 'data', self.app.pargs.environment, 'postgres')
            now = datetime.datetime.now()
            file = 'postgres' + now.strftime("%A%-H") + '.tar.gz'
            local_file = os.path.join(dump_path, file)
            remote_file = '/bitnami/postgresql/' + file
            remote_dir = '/bitnami/postgresql/dump'

            if os.path.exists(local_file):
                print('Dump already exists')
                os.remove(local_file)
                print('Delete existing dump')

            if not os.path.exists(dump_path):
                os.makedirs(dump_path)
                print('Create dump path')

            command_pg_dump = 'pg_dump --dbname=postgresql://postgres:k794ufXP57CD@127.0.0.1:5432/icardata -Fd -j 5 -f %s' % remote_dir

            command_dump = registry.term + \
                           'kubectl exec %s -c %s -- %s' % (pod,
                                                            container, command_pg_dump)
            echo(command_dump, 'yellow')
            subprocess.run([command_dump], shell=True, check=True)

            command_compress = registry.term + 'kubectl exec %s -c %s -- %s' % (
                pod, container, 'tar -czvf %s %s' % (remote_file, remote_dir))
            echo(command_compress, 'yellow')
            subprocess.run([command_compress], shell=True, check=True)

            command_copy = registry.term + \
                           'kubectl cp %s:%s %s -c %s' % (pod,
                                                          remote_file, local_file, container)
            echo(command_copy, 'yellow')
            subprocess.run([command_copy], shell=True, check=True)

            os.system("ls %s/" % dump_path)

            bucket_name = self.config.get('bucket')
            if bucket_name is None:
                raise ValueError("Bucket config not found")

            storage_client = storage.Client()
            bucket_file = 'postgres/%s/%s/%s' % (pod, now.strftime("%Y%m%d"), file)
            registry.notify.send('log', 'Copying local file %s to GCS bucket path %s/%s' %
                                 (local_file, bucket_name, bucket_file))
            bucket = storage_client.get_bucket(bucket_name)
            blob = bucket.blob(bucket_file)
            blob.upload_from_filename(local_file)

            command_delete_dump_dir = 'rm -Rf %s' % remote_dir
            echo(command_delete_dump_dir, 'yellow')
            command_delete_dump = registry.term + \
                                  'kubectl exec %s -c %s -- %s' % (pod,
                                                                   container, command_delete_dump_dir)
            echo(command_delete_dump, 'yellow')
            subprocess.run([command_delete_dump], shell=True, check=True)

            command_delete_remote_file = 'rm -Rf %s' % remote_file
            echo(command_delete_remote_file, 'yellow')
            command_delete_file = registry.term + \
                                  'kubectl exec %s -c %s -- %s' % (pod,
                                                                   container, command_delete_remote_file)
            subprocess.run([command_delete_file], shell=True, check=True)

            command_delete_local_dump = 'rm -Rf %s' % local_file
            echo(command_delete_local_dump, 'yellow')
            subprocess.run([command_delete_local_dump], shell=True, check=True)

        elif svc == 'preprod' and self.app.pargs.environment == 'preprod':
            pod = svc + '-postgres-0'
            dump_path = os.path.join(
                registry.data_dir, 'data', self.app.pargs.environment, 'postgres')
            now = datetime.datetime.now()
            remote_dir = '/dumps'
            databases = ['discourse_id', 'discourse_my', 'discourse_os', 'virtual_events',
                         'metabase', 'redash', 'superset', 'spark', 'carmudi_bi_reports']

            for database in databases:
                file = database + '-' + now.strftime("%A%-H") + '.tar.gz'
                local_file = os.path.join(dump_path, file)
                remote_file = '/' + file

                command_pg_dump = 'pg_dump --dbname=postgresql://pguser:jik23dsrwwew@127.0.0.1:5432/%s -Fd -j 5 -f %s' % (
                    database, remote_dir)
                command_dump = registry.term + \
                               'kubectl exec %s -- %s' % (pod, command_pg_dump)
                echo(command_dump, 'yellow')
                subprocess.run([command_dump], shell=True, check=True)

                command_compress = registry.term + \
                                   'kubectl exec %s -- %s' % (pod, 'tar -czvf %s %s' %
                                                              (remote_file, remote_dir))
                echo(command_compress, 'yellow')
                subprocess.run([command_compress], shell=True, check=True)

                command_copy = registry.term + \
                               'kubectl cp %s:%s %s' % (pod, remote_file, local_file)
                echo(command_copy, 'yellow')
                subprocess.run([command_copy], shell=True, check=True)

                bucket_name = self.config.get('bucket')
                if bucket_name is None:
                    raise ValueError("Bucket config not found")

                storage_client = storage.Client()
                bucket_file = 'postgres/%s/%s/%s' % (pod, now.strftime("%Y%m%d"), file)
                registry.notify.send(
                    'log', 'Copying local file %s to GCS bucket path %s/%s' % (local_file, bucket_name, bucket_file))
                bucket = storage_client.get_bucket(bucket_name)
                blob = bucket.blob(bucket_file)
                blob.upload_from_filename(local_file)

                command_delete_remote_file = 'rm %s' % remote_file
                echo(command_delete_remote_file, 'yellow')
                command_delete_file = registry.term + \
                                      'kubectl exec %s -- %s' % (pod, command_delete_remote_file)
                subprocess.run([command_delete_file], shell=True, check=True)

                command_delete_local_dump = 'rm -Rf %s' % local_file
                echo(command_delete_local_dump, 'yellow')
                subprocess.run([command_delete_local_dump], shell=True, check=True)

                command_delete_dump_dir = 'rm -Rf %s' % remote_dir
                echo(command_delete_dump_dir, 'yellow')
                command_delete_dump = registry.term + \
                                      'kubectl exec %s -- %s' % (pod, command_delete_dump_dir)
                subprocess.run([command_delete_dump], shell=True, check=True)

        else:
            pod = 'postgres-0'
            dump_path = os.path.join(
                registry.data_dir, 'data', self.app.pargs.environment, 'postgres')
            now = datetime.datetime.now()
            remote_dir = '/dumps/' + now.strftime("%Y%m%d") + '/'
            databases = ['airflow', 'spark', 'superset', 'postgres', 'virtual_events']
            global_file = 'global_' + now.strftime("%Y%m%d") + '.sql'
            command_pgdumpall = 'pg_dumpall -U postgres -g -f /tmp/' + global_file
            command_dump_general = registry.term + 'kubectl exec %s -c postgres -- %s' % (pod, command_pgdumpall)
            subprocess.run([command_dump_general], shell=True, check=True)
            command_copy_general = registry.term + 'kubectl cp %s:%s %s -c postgres' % (
                pod, '/tmp/' + global_file, '/tmp/' + global_file)
            subprocess.run([command_copy_general], shell=True, check=True)

            bucket_name = self.config.get('bucket')
            if bucket_name is None:
                raise ValueError("Bucket config not found")

            storage_client = storage.Client()
            bucket_file = 'postgres/%s/%s/%s' % (pod, now.strftime("%Y%m%d"), global_file)
            registry.notify.send('log', 'Copying local file /tmp/%s to GCS bucket path %s/%s' % (
                global_file, bucket_name, bucket_file))
            bucket = storage_client.get_bucket(bucket_name)
            blob = bucket.blob(bucket_file)
            blob.upload_from_filename('/tmp/' + global_file)

            file_stats = os.stat('/tmp/' + global_file)
            blobSize = bucket.get_blob(bucket_file)
            if blobSize.size != file_stats.st_size:
                registry.notify.send(room="monitor",
                                     message=f"FAILED: GLOBAL configuration backup failed because local and cloud size is different.")  # Slack notification.
                raise CommandError('Size of file uploaded and local size of file is not same %i' % blobSize.size)
            command_delete_remote_file = 'rm /tmp/%s' % global_file
            command_delete_file = registry.term + 'kubectl exec %s -c postgres -- %s' % (
                pod, command_delete_remote_file)
            echo(command_delete_file, 'yellow')
            subprocess.run([command_delete_file], shell=True, check=True)
            subprocess.run(['rm /tmp/%s' % (global_file)], shell=True, check=True)
            echo(f"SUCCESS: GLOBAL configuration backed up in {bucket_name}.", "blue")
            registry.notify.send(room="monitor",
                                 message=f"SUCCESS: GLOBAL configuration backed up in {bucket}.")  # Slack notification.

            for database in databases:
                command_dump = registry.term + \
                               'kubectl exec %s -c postgres -- %s' % (pod, "mkdir -p " + remote_dir)
                echo(command_dump, 'yellow')
                subprocess.run([command_dump], shell=True, check=True)
                file = database + '-' + now.strftime("%Y%m%d") + '.tar.gz'
                local_file = os.path.join(dump_path, file)
                remote_file = file

                command_pg_dump = 'pg_dump --dbname=postgresql://postgres:9yqpcxv6jyqn66y6@127.0.0.1:5432/%s -Fc --verbose -f %s' % (
                    database, remote_dir + database + ".fc")
                command_dump = registry.term + \
                               'kubectl exec %s -c postgres -- %s' % (pod, command_pg_dump)
                echo(command_dump, 'yellow')
                subprocess.run([command_dump], shell=True, check=True)

                command_compress = registry.term + 'kubectl exec %s -c postgres -- %s' % (
                    pod, 'tar -czvf %s %s' % (remote_file, remote_dir + database + ".fc"))
                echo(command_compress, 'yellow')
                subprocess.run([command_compress], shell=True, check=True)

                command_copy = registry.term + \
                               'kubectl cp %s:%s %s -c postgres' % (pod, remote_file, local_file)
                echo(command_copy, 'yellow')
                subprocess.run([command_copy], shell=True, check=True)

                bucket_name = self.config.get('bucket')
                if bucket_name is None:
                    raise ValueError("Bucket config not found")

                storage_client = storage.Client()
                bucket_file = 'postgres/%s/%s/%s' % (pod, now.strftime("%Y%m%d"), file)
                registry.notify.send(
                    'log', 'Copying local file %s to GCS bucket path %s/%s' % (local_file, bucket_name, bucket_file))
                bucket = storage_client.get_bucket(bucket_name)
                blob = bucket.blob(bucket_file)
                blob.upload_from_filename(local_file)

                file_stats = os.stat(local_file)
                blobSize = bucket.get_blob(bucket_file)
                if blobSize.size != file_stats.st_size:
                    registry.notify.send(room="monitor",
                                         message=f"FAILED: Database {database} backup failed because local and cloud size is different.")  # Slack notification.
                    raise CommandError(
                        'Size of file uploaded and local size of file is not same %i' % blobSize.size)

                command_delete_remote_file = 'rm %s' % remote_file
                echo(command_delete_remote_file, 'yellow')
                command_delete_file = registry.term + \
                                      'kubectl exec %s -c postgres -- %s' % (pod,
                                                                             command_delete_remote_file)
                subprocess.run([command_delete_file],
                               shell=True, check=True)

                command_delete_local_dump = 'rm -Rf %s' % local_file
                echo(command_delete_local_dump, 'yellow')
                subprocess.run([command_delete_local_dump],
                               shell=True, check=True)

                command_delete_dump_dir = 'rm -Rf %s' % remote_dir
                echo(command_delete_dump_dir, 'yellow')
                command_delete_dump = registry.term + \
                                      'kubectl exec %s -c postgres -- %s' % (pod,
                                                                             command_delete_dump_dir)
                subprocess.run([command_delete_dump], shell=True, check=True)
                echo("BACKUP SIZE for " + database + " is: " + str(blobSize.size) + " bytes", "green")
                blobSize2 = format_bytes(blobSize.size)
                echo(
                    f"SUCCESS: Database {database.capitalize()} backed up in '{bucket_name}'' with size {blobSize2[0]} {blobSize2[1]}.",
                    "blue")
                registry.notify.send(room="monitor",
                                     message=f"SUCCESS: Database {database.capitalize()} backed up in {bucket} with size {format_bytes(blobSize.size)}.")  # Slack notification.
