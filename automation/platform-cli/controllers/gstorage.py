import time

from cement.core.controller import expose
from google.cloud import storage

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from resources.messages import messages


class GstorageController(ICarBaseController):
    required = {'replaceword': ['bucket', 'prefix', 'replace', 'word']}
    messages = {'default': 'Manage Storage {name} for {environment}'}
    scope = 'cluster'

    # config = {'bucket': 'data-backup-19anrz7d490d8mmz'}

    class Meta:
        label = 'gstorage'
        description = messages['gstorage.info']
        arguments = [
            (['-p', '--prefix'], dict(help="The path of the object")),
            (['-b', '--bucket'], dict(help="The name of the bucket")),
            (['-r', '--replace'], dict(help="Word to replace")),
            (['-w', '--word'], dict(help="Word"))
        ]
        usage = 'icarcli gstorage <service_name> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='Rename the word in file name')
    def replaceword(self):
        """ Replace word in name"""

        # python3 icarcli gstorage replaceword -b aoshfan -p 0000122 -r "-123456" -w "" -e preprod

        # listings-8v7kbi3mh5dw8ngm
        bucket_name = self.app.pargs.bucket
        folder_name = self.app.pargs.prefix + "/"
        replace_word = self.app.pargs.replace
        word_replace = self.app.pargs.word
        bblist = []

        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blobs = storage_client.list_blobs(bucket_name, prefix=folder_name, delimiter="/")

        print(f'Bucket Name: {bucket_name}')
        print(f'Folder Name: {folder_name}')
        print(f'Word to Replace: {replace_word}')
        print(f'Word to inplace: {word_replace}')

        for blob in blobs:
            ori_name = blob.name
            mod_name = ori_name.replace(replace_word, word_replace)
            bucket.rename_blob(blob, mod_name)
            print(f'Renaming {ori_name} to a new name {mod_name}')
            time.sleep(10)
