from cement.core.controller import expose
from google.cloud import storage

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from lib.measure import format_bytes
from resources.messages import messages


class StorageController(ICarBaseController):
    required = {'zero_files': ['bucket', 'prefix'], 'check_access_key': ['bucket']}
    messages = {'default': 'Manage Storage {name} for {environment}'}
    scope = 'cluster'
    config = {'bucket': 'data-backup-19anrz7d490d8mmz'}

    class Meta:
        label = 'storage'
        description = messages['cluster.info']
        arguments = [
            (['-p', '--prefix'], dict(help="The path of the object")),
            (['-b', '--bucket'], dict(help="The name of the bucket")),
        ]
        usage = 'icarcli storage <service_name> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='Get zero files')
    def zero_files(self):
        """ Zero files from a storage """

        # icarcli storage zero-files -e production -b listings-8v7kbi3mh5dw8ngm -p th/video_thumb/

        # listings-8v7kbi3mh5dw8ngm
        bucket_name = self.app.pargs.bucket
        storage_client = storage.Client()

        bucket = storage_client.get_bucket(bucket_name)
        # id/video_thumb/
        blobs = bucket.list_blobs(prefix=self.app.pargs.prefix)
        files = []
        zero_files = []
        echo('Summary of Zero Files:', 'green')
        for blob in blobs:
            files.append(blob.name)
            if blob.size < 1:
                zero_files.append(blob.name)
                blob_size = format_bytes(blob.size)
                echo('%s [%f %s]' % (blob.name, blob_size[0], blob_size[1]), 'blue')
        echo('Files: %s / %s' % (len(zero_files), len(files)), 'green')

    @command
    @expose(help='List objects in the bucket')
    def list(self):

        bucket_name = self.app.pargs.bucket

        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blobs = bucket.list_blobs()

        echo('Files inside the bucket')

        for blob in blobs:
            blob_size = format_bytes(blob.size)
            echo('%s [%f %s]' % (blob.name, blob_size[0], blob_size[1]), 'blue')

    @command
    @expose(help='Check access key for bucket')
    def check_access_key(self):
        # icardata-stats-6e9b9qkzd
        bucket_name = self.app.pargs.bucket
        storage_client = storage.Client()

        bucket = storage_client.get_bucket(bucket_name)

        blobs = bucket.list_blobs(prefix=self.app.pargs.prefix)

        files = []
        zero_files = []
        echo('Summary of Files:', 'green')
        for blob in blobs:
            files.append(blob.name)
            # echo('%s [%f %s]' % (blob.name, blob_size[0], blob_size[1]), 'blue')
        echo('Files: %s / %s' % (len(zero_files), len(files)), 'green')

        # bucket_name = self.app.pargs.bucket
        # storage_client = storage.Client()
        # 
        # buckets = storage_client.list_buckets()
        # 
        # bucket_list = [];
        # for bucket in buckets:
        #     bucket_list.append(bucket.name)
        #     echo(bucket.name, 'yellow')
        # echo('Buckets: %s' % len(bucket_list))
