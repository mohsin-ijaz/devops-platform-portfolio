import os
import re
import subprocess
import uuid
from subprocess import PIPE

from cement.core.controller import expose
from fabric import Connection
from pathlib2 import Path

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from objects import registry


class SolrController(ICarBaseController):
    required = {}
    messages = {'default': 'Manage Solr {name} for {environment}'}

    config = {
        'solr-my': {
            'mysql': 'mysql-solr-slave-my',
            'inventory_dih': '/platform-a/carlist_inventory/dih.xml',
            'inventory_schema': '/platform-a/carlist_inventory/schema.xml',
            'inventory_solrconfig': '/platform-a/carlist_inventory/solrconfig.xml',
            'public_dih': '/platform-a/carlist_public/dih.xml',
            'public_schema': '/platform-a/carlist_public/schema.xml',
            'public_solrconfig': '/platform-a/carlist_public/solrconfig.xml',
            'inventory_folder': '/carlist_inventory/conf/',
            'public_folder': '/carlist_public/conf/'
        },
        'solr-cm': {
            'mysql': 'mysql-solr-slave-id',
            'inventory_dih': '/platform-b/carmudi_inventory/dih.xml',
            'inventory_schema': '/platform-b/carmudi_inventory/schema.xml',
            'inventory_solrconfig': '/platform-b/carmudi_inventory/solrconfig.xml',
            'public_dih': '/platform-b/carmudi_public/dih.xml',
            'public_schema': '/platform-b/carmudi_public/schema.xml',
            'public_solrconfig': '/platform-b/carmudi_public/solrconfig.xml',
            'inventory_folder': '/carmudi_inventory/conf/',
            'public_folder': '/carmudi_public/conf/'
        },
        'solr-id': {
            'mysql': 'mysql-solr-slave-id',
            'inventory_dih': '/platform-c/mobil123_inventory/dih.xml',
            'inventory_schema': '/platform-c/mobil123_inventory/schema.xml',
            'inventory_solrconfig': '/platform-c/mobil123_inventory/solrconfig.xml',
            'public_dih': '/platform-c/mobil123_public/dih.xml',
            'public_schema': '/platform-c/mobil123_public/schema.xml',
            'public_solrconfig': '/platform-c/mobil123_public/solrconfig.xml',
            'inventory_folder': '/mobil123_inventory/conf/',
            'public_folder': '/mobil123_public/conf/'
        },
        'solr-th': {
            'mysql': 'mysql-solr-slave-th',
            'inventory_dih': '/platform-d/one2car_inventory/dih.xml',
            'inventory_schema': '/platform-d/one2car_inventory/schema.xml',
            'inventory_solrconfig': '/platform-d/one2car_inventory/solrconfig.xml',
            'public_dih': '/platform-d/one2car_public/dih.xml',
            'public_schema': '/platform-d/one2car_public/schema.xml',
            'public_solrconfig': '/platform-d/one2car_public/solrconfig.xml',
            'inventory_folder': '/one2car_inventory/conf/',
            'public_folder': '/one2car_public/conf/'
        },
        'preprod': {
            'mysql': '<GCP_PROJECT_PREPROD>proxysql'
        },
        'staging': {
            'mysql': 'staging-proxysql'
        },
        'stag1': {
            'mysql': 'stag1-mysql'
        },
        'stag2': {
            'mysql': 'stag2-mysql'
        },
        'stag3': {
            'mysql': 'stag3-mysql'
        },
        'stag4': {
            'mysql': 'stag4-mysql'
        },
        'qa': {
            'mysql': 'qa-mysql'
        }
    }

    class Meta:
        label = 'solr'
        description = "Manage Solr"
        arguments = [
            (['-c', '--country'], dict(help="This is the country specfic solr to access")),
            (['-t', '--tag'], dict(help="This is the tag specfic solr to access")),
            (['-b', '--branch'], dict(help="Code branch name")),
        ]
        usage: 'icarcli solr [options]'
        epilog = 'ICar Solr Epilog'

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='Clone <GCP_PROJECT>_solr repo and copy files to solr production')
    def clone_production(self):

        if self.app.pargs.environment != "production":
            echo("Error: The command clone-production can only be run on production environment", "red")
            return False

        print(self.app.pargs)

        branch_name = self.app.pargs.branch

        # Project directory & config validation
        build_directory = os.path.join(registry.dockers_dir, 'project')
        docker_directory = os.path.join(build_directory, 'dockers-beta')

        unique_directory = uuid.uuid4().hex[:20]

        code_build_directory = os.path.join('code', unique_directory)
        temp_build_directory = os.path.join(registry.data_dir, code_build_directory)

        # On any error after this point we should make sure we remove temp_build_directory to clean
        os.system("mkdir -p %s" % temp_build_directory)

        print("Cloning repository <GCP_PROJECT>_solr")
        os.system("mkdir -p ~/.ssh")
        os.system("ssh-keyscan -t rsa bitbucket.org >> ~/.ssh/known_hosts")

        ssh_key = os.path.join(docker_directory, 'config', 'keys', 'id_rsa')

        os.system("chmod 400 " + ssh_key)
        echo("SSH key:" + ssh_key, "green")
        echo("Branc:" + branch_name, "green")
        clone_command = "ssh-agent bash -c 'ssh-add " + ssh_key + '; git clone' + ' --single-branch -b ' + branch_name + ' ' + 'git@bitbucket.org:<GCP_PROJECT>/<GCP_PROJECT>_solr.git' + ' ' + temp_build_directory + "'"

        echo(clone_command, "green")
        clone_command_call = subprocess.run(clone_command, shell=True, stdout=PIPE, stderr=PIPE)

        if clone_command_call.returncode != 0:
            echo(clone_command_call.stderr.decode('utf-8'), 'green')
            error_message = "Failed to clone repository <GCP_PROJECT>_solr"
            self._send_message(unique_directory, error_message, 'error')
            self._on_process_end(error_message, del_directory=temp_build_directory)

        echo(clone_command_call.stdout.decode('utf-8'), 'green')

        # end of clone repo process. Starting update to SOLR.

        env = self.app.pargs.environment
        solr_repo = temp_build_directory + '/api/v3'
        solr_home = '/var/solr/data'
        solr_deployments = ('solr-my', 'solr-id', 'solr-th', 'solr-cm')

        # update database host and database password in dih.xml

        for deployment in solr_deployments:

            solr_pod = getPod(deployment, env)
            config = self.config.get(deployment)
            mysql_host = config.get('mysql')
            mysql_password = '<SOLR_MYSQL_PASSWORD>'  # TODO: load from secret manager
            dih_list = [
                solr_repo + '/platform-a/carlist_inventory/dih.xml',
                solr_repo + '/platform-a/carlist_public/dih.xml',
                solr_repo + '/platform-b/carmudi_inventory/dih.xml',
                solr_repo + '/platform-b/carmudi_public/dih.xml',
                solr_repo + '/platform-c/mobil123_inventory/dih.xml',
                solr_repo + '/platform-c/mobil123_public/dih.xml',
                solr_repo + '/platform-d/one2car_inventory/dih.xml',
                solr_repo + '/platform-d/one2car_public/dih.xml'
            ]

            for dih in dih_list:
                echo('Replacing mysql host & mysql password in ' + dih, 'green')
                path = Path(dih)
                text = path.read_text()
                text = text.replace('<OLD_MYSQL_PASSWORD>', mysql_password)
                text = text.replace('127.0.0.1', mysql_host).replace('mysql-solr-slave-my', mysql_host).replace(
                    'mysql-solr-slave-id', mysql_host).replace('mysql-solr-slave-th', mysql_host)
                path.write_text(text)

            # copy cloned files from local to SOLR pod
            echo('Copying files to ' + deployment + ' pod', 'green')

            cmd_cp_inventory_dih = '%skubectl cp %s%s %s:%s%s' % (
                registry.term, solr_repo, config.get('inventory_dih'), solr_pod, solr_home,
                config.get('inventory_folder'))
            cmd_cp_inventory_schema = '%skubectl cp %s%s %s:%s%s' % (
                registry.term, solr_repo, config.get('inventory_schema'), solr_pod, solr_home,
                config.get('inventory_folder'))
            cmd_cp_inventory_solrconfig = '%skubectl cp %s%s %s:%s%s' % (
                registry.term, solr_repo, config.get('inventory_solrconfig'), solr_pod, solr_home,
                config.get('inventory_folder'))
            cmd_cp_public_dih = '%skubectl cp %s%s %s:%s%s' % (
                registry.term, solr_repo, config.get('public_dih'), solr_pod, solr_home, config.get('public_folder'))
            cmd_cp_public_schema = '%skubectl cp %s%s %s:%s%s' % (
                registry.term, solr_repo, config.get('public_schema'), solr_pod, solr_home, config.get('public_folder'))
            cmd_cp_public_solrconfig = '%skubectl cp %s%s %s:%s%s' % (
                registry.term, solr_repo, config.get('public_solrconfig'), solr_pod, solr_home, config.get('public_folder'))

            cmd_list = [cmd_cp_inventory_dih, cmd_cp_inventory_schema, cmd_cp_inventory_solrconfig, cmd_cp_public_dih, cmd_cp_public_schema, cmd_cp_public_solrconfig]

            for cmd in cmd_list:
                echo(cmd, 'yellow')
                os.system(cmd)

    @command
    @expose(help='Update mysql production')
    def update_production(self):

        if self.app.pargs.environment != "production":
            echo("Error: The command update-production can only be run on production environment", "red")
            return False

        sql_folder = os.path.join(registry.kubectl_dir, 'template/mysql/data')
        import_tables_file = sql_folder + '/import_indexing_tables.sql'
        import_customer_badges_data_file = sql_folder + '/import_customer_badges_data.sql'
        build_directory = os.path.join(registry.dockers_dir, 'project')
        docker_directory = os.path.join(build_directory, 'dockers-beta')
        ssh_key = os.path.join(docker_directory, 'config', 'keys', 'id_rsa')

        # copy required files to mysql-master

        echo('Copying files to mysql-master', 'green')
        copy_import_tables_file = 'gcloud compute scp %s root@mysql-master:/opt/temp' % (import_tables_file)
        copy_import_customer_badges_data_file = 'gcloud compute scp %s root@mysql-master:/opt/temp' % (
            import_customer_badges_data_file)
        copy_files = [copy_import_tables_file, copy_import_customer_badges_data_file]

        for copy in copy_files:
            echo(copy, 'yellow')
            os.system(copy)

        # run copied query files

        # run_indexing_tables = 'gcloud compute ssh mysql-master --project="<GCP_PROJECT_PROD>" --zone="<GCP_REGION>-a" --command="mysql -v < /opt/temp/import_indexing_tables.sql"'
        # run_customer_badges = 'gcloud compute ssh mysql-master --project="<GCP_PROJECT_PROD>" --zone="<GCP_REGION>-a" --command="mysql -v < /opt/temp/import_customer_badges_data.sql"'

        # commands = [run_indexing_tables, run_customer_badges]

        # for command in commands:
        #     echo(command, 'yellow')
        #     os.system(command)

        # echo("Indexing tables and data succesfully imported!", "green")

        os.system("chmod 400 " + ssh_key)
        echo("SSH key:" + ssh_key, "green")
        c = Connection(host='<PROD_SOLR_HOST>', connect_kwargs={'key_filename': ssh_key})

        echo("Create reindexing tables", "green")
        c.sudo('mysql -v -e \"source /opt/temp/import_indexing_tables.sql\"')
        echo("Import customer and badges data", "green")
        c.sudo('mysql -v -e \"source /opt/temp/import_customer_badges_data.sql\"')
        c.close()

    @command
    @expose(help='Reindex production solr cores')
    def reindex_production(self):

        if self.app.pargs.environment != "production":
            echo("Error: The command reindex-production can only be run on production environment", "red")
            return False

        # if self.app.pargs.clean == "":
        #     echo("Error: Please pass --clean true or --clean false", "red")
        #     return False

        clean = "true"
        env = self.app.pargs.environment
        solr_my_pod = getPod('solr-my', env)
        solr_id_pod = getPod('solr-id', env)
        solr_th_pod = getPod('solr-th', env)
        solr_cm_pod = getPod('solr-cm', env)

        # reload cores
        echo('Reloading all SOLR cores', 'green')

        reload_carlist_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carlist_public"' % (
            registry.term, solr_my_pod)
        reload_carlist_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carlist_inventory"' % (
            registry.term, solr_my_pod)
        reload_mobil123_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=mobil123_public"' % (
            registry.term, solr_id_pod)
        reload_mobil123_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=mobil123_inventory"' % (
            registry.term, solr_id_pod)
        reload_one2car_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=one2car_public"' % (
            registry.term, solr_th_pod)
        reload_one2car_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=one2car_inventory"' % (
            registry.term, solr_th_pod)
        reload_carmudi_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carmudi_public"' % (
            registry.term, solr_cm_pod)
        reload_carmudi_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carmudi_inventory"' % (
            registry.term, solr_cm_pod)
        reload_cores = [reload_carlist_public, reload_carlist_inventory, reload_mobil123_public,
                        reload_mobil123_inventory, reload_one2car_public,
                        reload_one2car_inventory, reload_carmudi_public, reload_carmudi_inventory]

        for reload in reload_cores:
            echo(reload, 'yellow')
            os.system(reload)

        # reindex all solr cores

        echo('Starting indexing for all SOLR cores', 'green')

        reindex_carlist_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carlist_public/dataimport?command=full-import&clean=%s"' % (
            registry.term, solr_my_pod, clean)
        reindex_carlist_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carlist_inventory/dataimport?command=full-import&clean=%s"' % (
            registry.term, solr_my_pod, clean)
        reindex_mobil123_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/mobil123_public/dataimport?command=full-import&clean=%s"' % (
            registry.term, solr_id_pod, clean)
        reindex_mobil123_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/mobil123_inventory/dataimport?command=full-import&clean=%s"' % (
            registry.term, solr_id_pod, clean)
        reindex_one2car_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/one2car_public/dataimport?command=full-import&clean=%s"' % (
            registry.term, solr_th_pod, clean)
        reindex_one2car_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/one2car_inventory/dataimport?command=full-import&clean=%s"' % (
            registry.term, solr_th_pod, clean)
        reindex_carmudi_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carmudi_public/dataimport?command=full-import&clean=%s"' % (
            registry.term, solr_cm_pod, clean)
        reindex_carmudi_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carmudi_inventory/dataimport?command=full-import&clean=%s"' % (
            registry.term, solr_cm_pod, clean)

        reindex_cores = [reindex_carlist_public, reindex_carlist_inventory, reindex_mobil123_public,
                         reindex_mobil123_inventory,
                         reindex_one2car_public, reindex_one2car_inventory, reindex_carmudi_public,
                         reindex_carmudi_inventory]

        for reindex in reindex_cores:
            echo(reindex, 'yellow')
            os.system(reindex)

    @command
    @expose(help='Update mysql on <GCP_PROJECT_PREPROD>mysql-master')
    def update_preprod(self):

        if self.app.pargs.environment != "preprod":
            echo("Error: The command update-preprod can only be run on preprod environment", "red")
            return False

        sql_folder = os.path.join(registry.kubectl_dir, 'template/mysql/data')
        import_tables_file = sql_folder + '/import_indexing_tables.sql'
        import_customer_badges_data_file = sql_folder + '/import_customer_badges_data.sql'
        build_directory = os.path.join(registry.dockers_dir, 'project')
        docker_directory = os.path.join(build_directory, 'dockers-beta')
        ssh_key = os.path.join(docker_directory, 'config', 'keys', 'id_rsa')

        # copy required files to <GCP_PROJECT_PREPROD>mysql-master

        echo('Copying files to <GCP_PROJECT_PREPROD>mysql-master', 'green')
        copy_import_tables_file = 'gcloud compute scp %s root@<GCP_PROJECT_PREPROD>mysql-master:/opt/temp' % (import_tables_file)
        copy_import_customer_badges_data_file = 'gcloud compute scp %s root@<GCP_PROJECT_PREPROD>mysql-master:/opt/temp' % (
            import_customer_badges_data_file)
        copy_files = [copy_import_tables_file, copy_import_customer_badges_data_file]

        for copy in copy_files:
            echo(copy, 'yellow')
            os.system(copy)

        # run copied query files
        os.system("chmod 400 " + ssh_key)
        echo("SSH key:" + ssh_key, "green")
        c = Connection(host='<PROD_SERVER_HOST>', user='<SSH_USER>', connect_kwargs={'key_filename': ssh_key})
        echo("Create reindexing tables", "green")
        c.sudo('mysql -v -e \"source /opt/temp/import_indexing_tables.sql\"')
        echo("Import customer and badges data", "green")
        c.sudo('mysql -v -e \"source /opt/temp/import_customer_badges_data.sql\"')

        # get max listing ref id from CRM database, increment by 10000 and insert into <GCP_PROJECT> database

        echo('Get max listing ref id from CRM database', 'green')
        get_max_listings_query = c.sudo('mysql -e \"SELECT MAX(ListingRefID) FROM <GCP_PROJECT>_CRMPortal.Listing\"')
        max_listings_pattern = r"(\d+)"
        max_listings_result = re.findall(max_listings_pattern, str(get_max_listings_query))
        max_listings = max_listings_result[1]
        max_listings_id = int(max_listings) + 10000

        # update max listings id into <GCP_PROJECT>.LISTING database

        insert_max_listings_id = 'mysql -v -e \"ALTER TABLE <GCP_PROJECT>.LISTING AUTO_INCREMENT = %s\"' % (max_listings_id)
        echo('Increment max listing ref id by 10000 and insert into <GCP_PROJECT> database', 'green')
        c.sudo(insert_max_listings_id)
        c.close()

    @command
    @expose(help='Clone <GCP_PROJECT>_solr repo and copy files to solr on development environments')
    def clone(self):

        # if self.app.pargs.environment == 'production' or self.app.pargs.environment == 'staging':
        if self.app.pargs.environment == 'production':
            echo("Error: The command clone can only be run on development environments", "red")
            return False

        print(self.app.pargs)

        branch_name = self.app.pargs.branch

        # Project directory & config validation
        build_directory = os.path.join(registry.dockers_dir, 'project')
        docker_directory = os.path.join(build_directory, 'dockers-beta')

        unique_directory = uuid.uuid4().hex[:20]

        code_build_directory = os.path.join('code', unique_directory)
        temp_build_directory = os.path.join(registry.data_dir, code_build_directory)

        # On any error after this point we should make sure we remove temp_build_directory to clean
        os.system("mkdir -p %s" % temp_build_directory)

        print("Cloning repository <GCP_PROJECT>_solr")
        os.system("mkdir -p ~/.ssh")
        os.system("ssh-keyscan -t rsa bitbucket.org >> ~/.ssh/known_hosts")

        ssh_key = os.path.join(docker_directory, 'config', 'keys', 'id_rsa')

        os.system("chmod 400 " + ssh_key)
        echo("SSH key:" + ssh_key, "green")
        clone_command = "ssh-agent bash -c 'ssh-add " + ssh_key + '; git clone' + ' --single-branch -b ' + branch_name + ' ' + 'git@bitbucket.org:<GCP_PROJECT>/<GCP_PROJECT>_solr.git' + ' ' + temp_build_directory + "'"

        echo(clone_command, "green")
        clone_command_call = subprocess.run(clone_command, shell=True, stdout=PIPE, stderr=PIPE)

        if clone_command_call.returncode != 0:
            echo(clone_command_call.stderr.decode('utf-8'), 'green')
            error_message = "Failed to clone repository <GCP_PROJECT>_solr"
            self._send_message(unique_directory, error_message, 'error')
            self._on_process_end(error_message, del_directory=temp_build_directory)

        echo(clone_command_call.stdout.decode('utf-8'), 'green')

        # end of clone repo process. Starting update to SOLR.

        env = self.app.pargs.environment
        config = self.config.get(env)
        mysql_host = config.get('mysql')
        solr_pod = getPod('solr', env)
        solr_repo = temp_build_directory + '/api/v3'
        solr_home = '/var/solr/data'

        # update database host and database password in dih.xml

        mysql_password = '<GCP_PROJECT>'
        dih_list = [
            solr_repo + '/platform-a/carlist_inventory/dih.xml',
            solr_repo + '/platform-a/carlist_public/dih.xml',
            solr_repo + '/platform-c/mobil123_inventory/dih.xml',
            solr_repo + '/platform-c/mobil123_public/dih.xml',
            solr_repo + '/platform-b/carmudi_inventory/dih.xml',
            solr_repo + '/platform-b/carmudi_public/dih.xml',
            solr_repo + '/platform-d/one2car_inventory/dih.xml',
            solr_repo + '/platform-d/one2car_public/dih.xml',
            solr_repo + '/cartimes/cartimes_inventory/dih.xml',
            solr_repo + '/cartimes/cartimes_public/dih.xml',
        ]

        for dih in dih_list:
            echo('Replacing mysql host & mysql password in ' + dih, 'green')
            path = Path(dih)
            text = path.read_text()
            text = text.replace('<OLD_MYSQL_PASSWORD>', mysql_password)
            text = text.replace('127.0.0.1', mysql_host)
            path.write_text(text)

        # copy cloned files from local to SOLR pod
        echo('Copying files to SOLR pod', 'green')

        # MY SOLR
        cmd_cp_my_inventory_dih = '%skubectl cp %s/platform-a/carlist_inventory/dih.xml %s:%s/carlist_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_my_inventory_schema = '%skubectl cp %s/platform-a/carlist_inventory/schema.xml %s:%s/carlist_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_my_inventory_solrconfig = '%skubectl cp %s/platform-a/carlist_inventory/solrconfig.xml %s:%s/carlist_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_my_public_dih = '%skubectl cp %s/platform-a/carlist_public/dih.xml %s:%s/carlist_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_my_public_schema = '%skubectl cp %s/platform-a/carlist_public/schema.xml %s:%s/carlist_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_my_public_solrconfig = '%skubectl cp %s/platform-a/carlist_public/solrconfig.xml %s:%s/carlist_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)


        # ID SOLR
        cmd_cp_id_inventory_dih = '%skubectl cp %s/platform-c/mobil123_inventory/dih.xml %s:%s/mobil123_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_id_inventory_schema = '%skubectl cp %s/platform-c/mobil123_inventory/schema.xml %s:%s/mobil123_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_id_inventory_solrconfig = '%skubectl cp %s/platform-c/mobil123_inventory/solrconfig.xml %s:%s/mobil123_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_id_public_dih = '%skubectl cp %s/platform-c/mobil123_public/dih.xml %s:%s/mobil123_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_id_public_schema = '%skubectl cp %s/platform-c/mobil123_public/schema.xml %s:%s/mobil123_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_id_public_solrconfig = '%skubectl cp %s/platform-c/mobil123_public/solrconfig.xml %s:%s/mobil123_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)

        # Platform-B
        cmd_cp_cm_inventory_dih = '%skubectl cp %s/platform-b/carmudi_inventory/dih.xml %s:%s/carmudi_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cm_inventory_schema = '%skubectl cp %s/platform-b/carmudi_inventory/schema.xml %s:%s/carmudi_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cm_inventory_solrconfig = '%skubectl cp %s/platform-b/carmudi_inventory/solrconfig.xml %s:%s/carmudi_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cm_public_dih = '%skubectl cp %s/platform-b/carmudi_public/dih.xml %s:%s/carmudi_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cm_public_schema = '%skubectl cp %s/platform-b/carmudi_public/schema.xml %s:%s/carmudi_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cm_public_solrconfig = '%skubectl cp %s/platform-b/carmudi_public/solrconfig.xml %s:%s/carmudi_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)

        # TH SOLR
        cmd_cp_th_inventory_dih = '%skubectl cp %s/platform-d/one2car_inventory/dih.xml %s:%s/one2car_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_th_inventory_schema = '%skubectl cp %s/platform-d/one2car_inventory/schema.xml %s:%s/one2car_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_th_inventory_solrconfig = '%skubectl cp %s/platform-d/one2car_inventory/solrconfig.xml %s:%s/one2car_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_th_public_dih = '%skubectl cp %s/platform-d/one2car_public/dih.xml %s:%s/one2car_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_th_public_schema = '%skubectl cp %s/platform-d/one2car_public/schema.xml %s:%s/one2car_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_th_public_solrconfig = '%skubectl cp %s/platform-d/one2car_public/solrconfig.xml %s:%s/one2car_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        
        # Cartimes SOLR
        cmd_cp_sg_inventory_dih = '%skubectl cp %s/cartimes/cartimes_inventory/dih.xml %s:%s/cartimes_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_sg_inventory_schema = '%skubectl cp %s/cartimes/cartimes_inventory/schema.xml %s:%s/cartimes_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_sg_inventory_solrconfig = '%skubectl cp %s/cartimes/cartimes_inventory/solrconfig.xml %s:%s/cartimes_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_sg_public_dih = '%skubectl cp %s/cartimes/cartimes_public/dih.xml %s:%s/cartimes_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_sg_public_schema = '%skubectl cp %s/cartimes/cartimes_public/schema.xml %s:%s/cartimes_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_sg_public_solrconfig = '%skubectl cp %s/cartimes/cartimes_public/solrconfig.xml %s:%s/cartimes_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)

        cmd_list = [cmd_cp_my_inventory_dih, cmd_cp_my_inventory_schema, cmd_cp_my_inventory_solrconfig, cmd_cp_my_public_dih, cmd_cp_my_public_schema, cmd_cp_my_public_solrconfig,
                    cmd_cp_id_inventory_dih, cmd_cp_id_inventory_schema, cmd_cp_id_inventory_solrconfig, cmd_cp_id_public_dih, cmd_cp_id_public_schema, cmd_cp_id_public_solrconfig,
                    cmd_cp_cm_inventory_dih, cmd_cp_cm_inventory_schema, cmd_cp_cm_inventory_solrconfig, cmd_cp_cm_public_dih, cmd_cp_cm_public_schema, cmd_cp_cm_public_solrconfig,
                    cmd_cp_th_inventory_dih, cmd_cp_th_inventory_schema, cmd_cp_th_inventory_solrconfig, cmd_cp_th_public_dih, cmd_cp_th_public_schema, cmd_cp_th_public_solrconfig,
                    cmd_cp_sg_inventory_dih, cmd_cp_sg_inventory_schema, cmd_cp_sg_inventory_solrconfig, cmd_cp_sg_public_dih, cmd_cp_sg_public_schema, cmd_cp_sg_public_solrconfig]

        for cmd in cmd_list:
            echo(cmd, 'yellow')
            os.system(cmd)

    @command
    @expose(help='Update mysql on staging or stags')
    def update(self):

        if self.app.pargs.environment == "preprod" or self.app.pargs.environment == 'production':
            echo("Error: The command update can only be run on staging or stags environment", "red")
            return False

        env = self.app.pargs.environment
        mysql_pod = getPod('mysql', env)

        sql_folder = os.path.join(registry.kubectl_dir, 'template/mysql/data')

        import_tables_query = sql_folder + '/import_indexing_tables.sql'
        import_customer_badges_data_query = sql_folder + '/import_customer_badges_data.sql'

        export_directory = '/var/lib/mysql'

        # copy required files to MySQL pod

        echo('Copying files to MySQL pod', 'green')

        copy_import_tables_query = '%skubectl cp %s %s:%s' % (
            registry.term, import_tables_query, mysql_pod, export_directory)
        copy_import_customer_badges_data_query = '%skubectl cp %s %s:%s' % (
            registry.term, import_customer_badges_data_query, mysql_pod, export_directory)

        copy_files = [copy_import_tables_query, copy_import_customer_badges_data_query]

        for copy in copy_files:
            echo(copy, 'yellow')
            os.system(copy)

        # run copied query files

        run_import_tables_query = '%skubectl exec %s -- mysql -e "source /var/lib/mysql/import_indexing_tables.sql"' % (
            registry.term, mysql_pod)
        run_import_customer_badges_data_query = '%skubectl exec %s -- mysql -e "source /var/lib/mysql/import_customer_badges_data.sql"' % (
            registry.term, mysql_pod)

        echo('Importing badges and customer data', 'green')

        echo(run_import_tables_query, 'yellow')
        os.system(run_import_tables_query)
        echo(run_import_customer_badges_data_query, 'yellow')
        os.system(run_import_customer_badges_data_query)

        # get max listing ref id from CRM database, increment by 10000 and insert into <GCP_PROJECT> database

        echo('Get max listing ref id from CRM database', 'green')

        get_max_listings_query = '%skubectl exec %s -- mysql -e "SELECT MAX(ListingRefID) FROM <GCP_PROJECT>_CRMPortal.Listing"' % (
            registry.term, mysql_pod)
        get_max_listings_output = subprocess.check_output(get_max_listings_query, shell=True)
        max_listings_pattern = r"(\d+)"
        max_listings_result = re.findall(max_listings_pattern, str(get_max_listings_output))
        max_listings = ", ".join(max_listings_result)
        max_listings_id = int(max_listings) + 10000

        # update max listings id into <GCP_PROJECT>.LISTING database

        echo('Increment max listing ref id by 10000 and insert into <GCP_PROJECT> database', 'green')

        update_max_listings_query = '%skubectl exec %s -- mysql -e "ALTER TABLE <GCP_PROJECT>.LISTING AUTO_INCREMENT = %s"' % (
            registry.term, mysql_pod, max_listings_id)

        echo(update_max_listings_query, 'yellow')
        os.system(update_max_listings_query)

    @command
    @expose(help='Reindex all solr cores on development environments')
    def reload(self):

        if self.app.pargs.environment == 'production' or self.app.pargs.environment == 'staging':
            echo("Error: The command reindex can only be run on development environments", "red")
            return False

        env = self.app.pargs.environment
        solr_pod = getPod('solr', env)

        # reload cores
        echo('Reloading all SOLR cores', 'green')

        reload_my_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carlist_public"' % (
            registry.term, solr_pod)
        reload_my_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carlist_inventory"' % (
            registry.term, solr_pod)
        reload_id_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=mobil123_public"' % (
            registry.term, solr_pod)
        reload_id_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=mobil123_inventory"' % (
            registry.term, solr_pod)
        reload_cm_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carmudi_public"' % (
            registry.term, solr_pod)
        reload_cm_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carmudi_inventory"' % (
            registry.term, solr_pod)
        reload_o2c_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=one2car_public"' % (
            registry.term, solr_pod)
        reload_o2c_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=one2car_inventory"' % (
            registry.term, solr_pod)
        reload_sg_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=cartimes_public"' % (
            registry.term, solr_pod)
        reload_sg_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=cartimes_inventory"' % (
            registry.term, solr_pod)
        reload_cores = [reload_my_public, reload_my_inventory, reload_id_public, reload_id_inventory, reload_cm_public,
                        reload_cm_inventory, reload_o2c_public, reload_o2c_inventory, reload_sg_public, reload_sg_inventory]

        for reload in reload_cores:
            echo(reload, 'yellow')
            os.system(reload)

    @command
    @expose(help='Reindex all solr cores on development environments')
    def reindex(self):
        # reload all solr cores
        self.reload()

        env = self.app.pargs.environment
        solr_pod = getPod('solr', env)

        # reindex all solr cores
        echo('Starting indexing for all SOLR cores', 'green')

        reindex_my_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carlist_public/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_my_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carlist_inventory/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_id_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/mobil123_public/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_id_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/mobil123_inventory/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_cm_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carmudi_public/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_cm_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carmudi_inventory/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_o2c_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/one2car_public/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_o2c_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/one2car_inventory/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_autospinn = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-g/dataimport?command=full-import&clean=true&project_id=1"' % (
            registry.term, solr_pod)
        reindex_otospirit = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-e/dataimport?command=full-import&clean=true&project_id=2"' % (
            registry.term, solr_pod)
        reindex_autospinn_my = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-g-my/dataimport?command=full-import&clean=true&project_id=3"' % (
            registry.term, solr_pod)

        reindex_cores = [reindex_my_public, reindex_my_inventory, reindex_id_public, reindex_id_inventory,
                         reindex_cm_public, reindex_cm_inventory,
                         reindex_o2c_public, reindex_o2c_inventory, reindex_autospinn, reindex_otospirit,
                         reindex_autospinn_my]

        for reindex in reindex_cores:
            echo(reindex, 'yellow')
            os.system(reindex)

    @command
    @expose(help='Clone <GCP_PROJECT>_solr repo and copy files to solr on development environments')
    def clone_staging(self):

        if self.app.pargs.environment != 'staging':
            echo("Error: The command clone can only be run on staging environment", "red")
            return False

        print(self.app.pargs)

        branch_name = self.app.pargs.branch

        # Project directory & config validation
        build_directory = os.path.join(registry.dockers_dir, 'project')
        docker_directory = os.path.join(build_directory, 'dockers-beta')

        unique_directory = uuid.uuid4().hex[:20]

        code_build_directory = os.path.join('code', unique_directory)
        temp_build_directory = os.path.join(registry.data_dir, code_build_directory)

        # On any error after this point we should make sure we remove temp_build_directory to clean
        os.system("mkdir -p %s" % temp_build_directory)

        print("Cloning repository <GCP_PROJECT>_solr")
        os.system("mkdir -p ~/.ssh")
        os.system("ssh-keyscan -t rsa bitbucket.org >> ~/.ssh/known_hosts")

        ssh_key = os.path.join(docker_directory, 'config', 'keys', 'id_rsa')

        os.system("chmod 400 " + ssh_key)
        echo("SSH key:" + ssh_key, "green")
        clone_command = "ssh-agent bash -c 'ssh-add " + ssh_key + '; git clone' + ' --single-branch -b ' + branch_name + ' ' + 'git@bitbucket.org:<GCP_PROJECT>/<GCP_PROJECT>_solr.git' + ' ' + temp_build_directory + "'"

        echo(clone_command, "green")
        clone_command_call = subprocess.run(clone_command, shell=True, stdout=PIPE, stderr=PIPE)

        if clone_command_call.returncode != 0:
            echo(clone_command_call.stderr.decode('utf-8'), 'green')
            error_message = "Failed to clone repository <GCP_PROJECT>_solr"
            self._send_message(unique_directory, error_message, 'error')
            self._on_process_end(error_message, del_directory=temp_build_directory)

        echo(clone_command_call.stdout.decode('utf-8'), 'green')

        # end of clone repo process. Starting update to SOLR.

        env = self.app.pargs.environment
        config = self.config.get(env)
        mysql_host = config.get('mysql')
        solr_pod = getPod('solr', env)
        solr_repo = temp_build_directory + '/api/v3'
        solr_home = '/var/solr/data'

        # update database host and database password in dih.xml

        mysql_password = '<GCP_PROJECT>'
        dih_list = [
            solr_repo + '/platform-a/carlist_inventory/dih.xml',
            solr_repo + '/platform-a/carlist_public/dih.xml',
            solr_repo + '/platform-b/carmudi_inventory/dih.xml',
            solr_repo + '/platform-b/carmudi_public/dih.xml',
            solr_repo + '/platform-c/mobil123_inventory/dih.xml',
            solr_repo + '/platform-c/mobil123_public/dih.xml',
            solr_repo + '/platform-d/one2car_inventory/dih.xml',
            solr_repo + '/platform-d/one2car_public/dih.xml',
            solr_repo + '/cartimes/cartimes_inventory/dih.xml',
            solr_repo + '/cartimes/cartimes_public/dih.xml',
        ]

        for dih in dih_list:
            echo('Replacing mysql host & mysql password in ' + dih, 'green')
            path = Path(dih)
            text = path.read_text()
            text = text.replace('<OLD_MYSQL_PASSWORD>', mysql_password)
            text = text.replace('127.0.0.1', mysql_host)
            path.write_text(text)

        # copy cloned files from local to SOLR pod
        echo('Copying files to SOLR pod', 'green')

        # PLATFORM_A SOLR
        cmd_cp_carlist_inventory_dih = '%skubectl cp %s/platform-a/carlist_inventory/dih.xml %s:%s/carlist_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_carlist_inventory_schema = '%skubectl cp %s/platform-a/carlist_inventory/schema.xml %s:%s/carlist_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_my_inventory_solrconfig = '%skubectl cp %s/platform-a/carlist_inventory/solrconfig.xml %s:%s/carlist_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_carlist_public_dih = '%skubectl cp %s/platform-a/carlist_public/dih.xml %s:%s/carlist_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_carlist_public_schema = '%skubectl cp %s/platform-a/carlist_public/schema.xml %s:%s/carlist_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_my_public_solrconfig = '%skubectl cp %s/platform-a/carlist_public/solrconfig.xml %s:%s/carlist_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)

        # PLATFORM_B SOLR
        cmd_cp_carmudi_inventory_dih = '%skubectl cp %s/platform-b/carmudi_inventory/dih.xml %s:%s/carmudi_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_carmudi_inventory_schema = '%skubectl cp %s/platform-b/carmudi_inventory/schema.xml %s:%s/carmudi_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cm_inventory_solrconfig = '%skubectl cp %s/platform-b/carmudi_inventory/solrconfig.xml %s:%s/carmudi_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_carmudi_public_dih = '%skubectl cp %s/platform-b/carmudi_public/dih.xml %s:%s/carmudi_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_carmudi_public_schema = '%skubectl cp %s/platform-b/carmudi_public/schema.xml %s:%s/carmudi_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cm_public_solrconfig = '%skubectl cp %s/platform-b/carmudi_public/solrconfig.xml %s:%s/carmudi_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)

        # PLATFORM_C SOLR
        cmd_cp_mobil123_inventory_dih = '%skubectl cp %s/platform-c/mobil123_inventory/dih.xml %s:%s/mobil123_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_mobil123_inventory_schema = '%skubectl cp %s/platform-c/mobil123_inventory/schema.xml %s:%s/mobil123_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_mobil123_inventory_solrconfig = '%skubectl cp %s/platform-c/mobil123_inventory/solrconfig.xml %s:%s/mobil123_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_mobil123_public_dih = '%skubectl cp %s/platform-c/mobil123_public/dih.xml %s:%s/mobil123_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_mobil123_public_schema = '%skubectl cp %s/platform-c/mobil123_public/schema.xml %s:%s/mobil123_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_mobil123_public_solrconfig = '%skubectl cp %s/platform-c/mobil123_public/solrconfig.xml %s:%s/mobil123_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)

        # PLATFORM_D SOLR
        cmd_cp_one2car_inventory_dih = '%skubectl cp %s/platform-d/one2car_inventory/dih.xml %s:%s/one2car_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_one2car_inventory_schema = '%skubectl cp %s/platform-d/one2car_inventory/schema.xml %s:%s/one2car_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_one2car_inventory_solrconfig = '%skubectl cp %s/platform-d/one2car_inventory/solrconfig.xml %s:%s/one2car_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_one2car_public_dih = '%skubectl cp %s/platform-d/one2car_public/dih.xml %s:%s/one2car_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_one2car_public_schema = '%skubectl cp %s/platform-d/one2car_public/schema.xml %s:%s/one2car_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_one2car_public_solrconfig = '%skubectl cp %s/platform-d/one2car_public/solrconfig.xml %s:%s/one2car_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        
        # CARTIMES SOLR
        cmd_cp_cartimes_inventory_dih = '%skubectl cp %s/platform-d/cartimes_inventory/dih.xml %s:%s/cartimes_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cartimes_inventory_schema = '%skubectl cp %s/platform-d/cartimes_inventory/schema.xml %s:%s/cartimes_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cartimes_inventory_solrconfig = '%skubectl cp %s/platform-d/cartimes_inventory/solrconfig.xml %s:%s/cartimes_inventory/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cartimes_public_dih = '%skubectl cp %s/platform-d/cartimes_public/dih.xml %s:%s/cartimes_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cartimes_public_schema = '%skubectl cp %s/platform-d/cartimes_public/schema.xml %s:%s/cartimes_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)
        cmd_cp_cartimes_public_solrconfig = '%skubectl cp %s/platform-d/cartimes_public/solrconfig.xml %s:%s/cartimes_public/conf/' % (
            registry.term, solr_repo, solr_pod, solr_home)

        cmd_list = [cmd_cp_carlist_inventory_dih, cmd_cp_carlist_inventory_schema, cmd_cp_my_inventory_solrconfig, 
                    cmd_cp_carlist_public_dih, cmd_cp_carlist_public_schema, cmd_cp_my_public_solrconfig,
                    cmd_cp_carmudi_inventory_dih, cmd_cp_carmudi_inventory_schema, cmd_cp_cm_inventory_solrconfig,
                    cmd_cp_carmudi_public_dih, cmd_cp_carmudi_public_schema, cmd_cp_cm_public_solrconfig,
                    cmd_cp_mobil123_inventory_dih, cmd_cp_mobil123_inventory_schema, cmd_cp_mobil123_inventory_solrconfig,
                    cmd_cp_mobil123_public_dih, cmd_cp_mobil123_public_schema, cmd_cp_mobil123_public_solrconfig,
                    cmd_cp_one2car_inventory_dih, cmd_cp_one2car_inventory_schema, cmd_cp_one2car_inventory_solrconfig,
                    cmd_cp_one2car_public_dih, cmd_cp_one2car_public_schema, cmd_cp_one2car_public_solrconfig,
                    cmd_cp_cartimes_inventory_dih, cmd_cp_cartimes_inventory_schema, cmd_cp_cartimes_inventory_solrconfig,
                    cmd_cp_cartimes_public_dih, cmd_cp_cartimes_public_schema, cmd_cp_cartimes_public_solrconfig,
                    ]

        for cmd in cmd_list:
            echo(cmd, 'yellow')
            os.system(cmd)

    @command
    @expose(help='Reindex all solr cores on staging environment')
    def reload_staging(self):

        if self.app.pargs.environment != 'staging':
            echo("Error: The command reindex can only be run on staging environment", "red")
            return False

        env = self.app.pargs.environment
        solr_pod = getPod('solr', env)

        # reload cores
        echo('Reloading all SOLR cores', 'green')

        reload_carlist_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carlist_public"' % (
            registry.term, solr_pod)
        reload_carlist_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carlist_inventory"' % (
            registry.term, solr_pod)
        reload_carmudi_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carmudi_public"' % (
            registry.term, solr_pod)
        reload_carmudi_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=carmudi_inventory"' % (
            registry.term, solr_pod)
        reload_mobil123_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=mobil123_public"' % (
            registry.term, solr_pod)
        reload_mobil123_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=mobil123_inventory"' % (
            registry.term, solr_pod)
        reload_one2car_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=one2car_public"' % (
            registry.term, solr_pod)
        reload_one2car_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=one2car_inventory"' % (
            registry.term, solr_pod)
        reload_cartimes_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=cartimes_public"' % (
            registry.term, solr_pod)
        reload_cartimes_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/admin/cores?action=RELOAD&core=cartimes_inventory"' % (
            registry.term, solr_pod)
        reload_cores = [reload_carlist_public, reload_carlist_inventory, reload_carmudi_public,
                        reload_carmudi_inventory, reload_mobil123_public, reload_mobil123_inventory,
                        reload_one2car_public, reload_one2car_inventory, reload_cartimes_public, reload_cartimes_inventory]

        for reload in reload_cores:
            echo(reload, 'yellow')
            os.system(reload)

    @command
    @expose(help='Reindex all solr cores on staging environment')
    def reindex_staging(self):
        # reload all solr cores
        self.reload_staging()

        # reindex all solr cores
        echo('Starting indexing for all SOLR cores', 'green')
        env = self.app.pargs.environment
        solr_pod = getPod('solr', env)

        reindex_carlist_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carlist_public/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_carlist_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carlist_inventory/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_carmudi_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carmudi_public/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_carmudi_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/carmudi_inventory/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_mobil123_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/mobil123_public/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_mobil123_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/mobil123_inventory/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_one2car_public = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/one2car_public/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_one2car_inventory = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/one2car_inventory/dataimport?command=full-import&clean=true"' % (
            registry.term, solr_pod)
        reindex_autospinn = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-g/dataimport?command=full-import&clean=true&project_id=1"' % (
            registry.term, solr_pod)
        reindex_otospirit = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-e/dataimport?command=full-import&clean=true&project_id=2"' % (
            registry.term, solr_pod)
        reindex_autospinn_my = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-g-my/dataimport?command=full-import&clean=true&project_id=3"' % (
            registry.term, solr_pod)

        reindex_cores = [reindex_carlist_public, reindex_carlist_inventory, reindex_carmudi_public,
                         reindex_carmudi_inventory, reindex_mobil123_public, reindex_mobil123_inventory,
                         reindex_one2car_public, reindex_one2car_inventory, reindex_autospinn, reindex_otospirit,
                         reindex_autospinn_my]

        for reindex in reindex_cores:
            echo(reindex, 'yellow')
            os.system(reindex)

    @command
    @expose(help='Reindex all CMS solr cores')
    def reindex_cms(self):
        # reindex all solr cores
        echo('Starting indexing for all SOLR cores', 'green')
        env = self.app.pargs.environment
        solr_pod = getPod('solr', env)

        reindex_autospinn = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-g/dataimport?command=full-import&clean=true&commit=true&project_id=1"' % (
            registry.term, solr_pod)
        reindex_otospirit = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-e/dataimport?command=full-import&clean=true&commit=true&project_id=2"' % (
            registry.term, solr_pod)
        reindex_autospinn_my = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-g-my/dataimport?command=full-import&clean=true&commit=true&project_id=3"' % (
            registry.term, solr_pod)
        reindex_mobil123_news = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-c-news/dataimport?command=full-import&clean=true&commit=true&project_id=6"' % (
            registry.term, solr_pod)
        reindex_one2car_news = '%skubectl exec %s -- curl "http://127.0.0.1:8983/solr/platform-d-news/dataimport?command=full-import&clean=true&commit=true&project_id=7"' % (
            registry.term, solr_pod)

        reindex_cores = [reindex_autospinn, reindex_otospirit,reindex_autospinn_my, reindex_mobil123_news, reindex_one2car_news]

        for reindex in reindex_cores:
            echo(reindex, 'yellow')
            os.system(reindex)

    @command
    @expose(help='Reindex all solr cores on staging environment')
    def clean(self):
        env = self.app.pargs.environment
        solr_pod = getPod('solr', env)

        # reload cores
        echo('Clean all SOLR cores', 'green')

        clean_carlist_public = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/carlist_public/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)
        clean_carlist_inventory = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/carlist_inventory/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)
        clean_carmudi_public = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/carmudi_public/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)
        clean_carmudi_inventory = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/carmudi_inventory/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)
        clean_mobil123_public = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/mobil123_public/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)
        clean_mobil123_inventory = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/mobil123_inventory/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)
        clean_one2car_public = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/one2car_public/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)
        clean_one2car_inventory = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/one2car_inventory/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)
        clean_cartimes_public = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/cartimes_public/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)
        clean_cartimes_inventory = '%skubectl exec %s -- curl -X POST -H "Content-Type: application/json" "http://127.0.0.1:8983/solr/cartimes_inventory/update?stream.body=<delete><query>*:*</query></delete>&commit=true"' % (
            registry.term, solr_pod)

        clean_cores = [clean_carlist_public, clean_carlist_inventory, 
                        clean_carmudi_public, clean_carmudi_inventory,
                        clean_mobil123_public, clean_mobil123_inventory,
                        clean_one2car_public, clean_one2car_inventory,
                        clean_cartimes_public, clean_cartimes_inventory]

        for clean in clean_cores:
            echo(clean, 'yellow')
            os.system(clean)



def getPod(service, env):
    if env == 'production':
        env_prefix = ''
    else:
        env_prefix = env + '-'
    # Get pod according to labels
    container = subprocess.run(
        ['kubectl', 'get', 'pod', '--selector=app=' + env_prefix + service, '-o', "jsonpath='{.items..metadata.name}'"],
        stdout=subprocess.PIPE).stdout.decode('utf-8').replace("'", "")
    return container
