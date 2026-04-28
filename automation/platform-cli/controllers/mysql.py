import json
import os
import re
import subprocess
import time
from datetime import date, datetime
from subprocess import PIPE

import mysql.connector
from cement.core.controller import expose
from fabric import Connection
from tabulate import tabulate

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from core.icarerrors import CommandError
from lib.io import echo
from objects import registry
from objects.profiler import profile


class MysqlController(ICarBaseController):
    required = {}
    messages = {'default': 'Manage Mysql {name} for {environment}'}
    # scope = 'cluster'
    config = {
        'preprod': {
            'user': 'jenkins',
            'password': '<REDIS_PASSWORD>'
        },
        'production': {
            'user': 'jenkins',
            'password': '<REDIS_PASSWORD>'
        }

    }

    class Meta:
        label = 'mysql'
        description = "Manage Mysql"
        arguments = [
            (['-c', '--country'], dict(help="This is the country specfic solr to access")),
            (['-t', '--tag'], dict(help="This is the tag specfic solr to access")),
            (['-lang', '--language'], dict(help="Language")),
            (['-type', '--type'], dict(help="Type")),
        ]
        usage: 'icarcli mysql [options]'
        epilog = 'ICar Mysql Epilog'

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='Get list of all solr running')
    def list(self):
        list_command = 'gcloud compute instances list --filter="labels.server=database AND labels.type=mysql"' \
                       ' --format=json'
        instances_data = subprocess.run(list_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        instances = json.loads(instances_data.stdout.decode('utf-8'))

        echo(self.app.pargs.environment, 'white', 'on_blue')
        config = self.config.get(self.app.pargs.environment)

        mysql_instances = {}
        mysql_instances_basic = []
        mysql_instances_adv = {
            'master': [],
            'slave': []
        }

        for instance in instances:

            mysql_instance = {}
            mysql_instance_basic = {}

            name = instance.get('name')
            ips = self.get_ips(instance)

            mysql_instance['name'] = name
            mysql_instance['ip_internal'] = ips['internal']
            mysql_instance['ip_external'] = ips['external']

            if instance.get('status') != 'RUNNING':
                continue

            # connect to the host
            try:
                connection = mysql.connector.connect(host=ips['external'], user=config.get('user'),
                                                     password=config.get('password'))
                cursor = connection.cursor(dictionary=True)

                # get version
                cursor.execute("SELECT VERSION() as version")
                data = cursor.fetchone()
                mysql_instance['version'] = data.get('version', 0)

                # get binlog
                cursor.execute(
                    "SELECT COUNT(1) as binlog FROM information_schema.processlist WHERE command = 'binlog dump'")
                data = cursor.fetchone()
                mysql_instance['binlog'] = data.get('binlog', 0)
                mysql_instance['state'] = instance.get('labels', {}).get('state', 'Unknown')

                # get read only
                cursor.execute("SELECT @@global.read_only as read_only")
                data = cursor.fetchone()
                mysql_instance['read_only'] = data.get('read_only', -1)

                # get read only
                cursor.execute("SHOW STATUS WHERE variable_name = 'Threads_connected'")
                data = cursor.fetchone()
                mysql_instance['connections'] = data.get('Value', -1)

                mysql_instance_basic = mysql_instance.copy()

                # get master status
                cursor.execute("SHOW MASTER STATUS")
                data = cursor.fetchone()
                mysql_instance['master'] = data

                if data is not None:
                    data_inst = {'name': mysql_instance['name'], 'state': mysql_instance['state']}
                    data_inst.update(data)
                    mysql_instances_adv['master'].append(data_inst)

                # get slave status
                cursor.execute("SHOW SLAVE STATUS")
                data = cursor.fetchone()
                if data is not None:
                    summary = {
                        'Seconds_Behind_Master': data.get('Seconds_Behind_Master'),
                        'Slave_IO_Running': data.get('Slave_IO_Running'),
                        # 'Slave_IO_State': data.get('Slave_IO_State'),
                        'Slave_SQL_Running': data.get('Slave_SQL_Running'),
                        # 'Slave_SQL_Running_State': data.get('Slave_SQL_Running_State'),
                        # 'Last_IO_Errno': data.get('Last_IO_Errno'),
                        # 'Last_IO_Error': data.get('Last_IO_Error'),
                        # 'Last_IO_Error_Timestamp': data.get('Last_IO_Error_Timestamp'),
                        # 'Last_SQL_Errno': data.get('Last_SQL_Errno'),
                        # 'Last_SQL_Error': data.get('Last_SQL_Error'),
                        # 'Last_SQL_Error_Timestamp': data.get('Last_SQL_Error_Timestamp'),
                        'Master_Host': data.get('Master_Host')
                    }
                else:
                    summary = data

                if summary is not None:
                    data_inst = {'name': mysql_instance['name'], 'state': mysql_instance['state']}
                    data_inst.update(summary)
                    mysql_instances_adv['slave'].append(data_inst)

                mysql_instance['slave'] = data
                mysql_instances_basic.append(mysql_instance_basic)
                mysql_instances[name] = mysql_instance
            except Exception as e:
                echo('DB Server[%s] gave the following error: %s' % (name, e), 'red')

        mysql_instances_basic_sorted = sorted(mysql_instances_basic, key=lambda k: k.get('state'))
        mysql_instances_master_sorted = sorted(mysql_instances_adv['master'], key=lambda k: k.get('state'))
        mysql_instances_slave_sorted = sorted(mysql_instances_adv['slave'], key=lambda k: k.get('state'))

        echo(tabulate(mysql_instances_basic_sorted, headers="keys"))
        echo("\nMaster:", "green")
        echo(tabulate(mysql_instances_master_sorted, headers="keys"))
        echo("\nSlaves:", "green")
        echo(tabulate(mysql_instances_slave_sorted, headers="keys"))

    def get_ips(self, instance):
        network_interfaces = instance.get('networkInterfaces')
        ips = {'internal': None, 'external': None}
        for network_interface in network_interfaces:
            ips['internal'] = network_interface.get('networkIP')
            access_configs = network_interface.get('accessConfigs')
            for access_config in access_configs:
                if access_config.get('kind') == 'compute#accessConfig' and access_config.get('type') and \
                        access_config.get('networkTier'):
                    ips['external'] = access_config.get('natIP')
        return ips

    @profile
    @command
    @expose(help='Create snapshot from MySQL production and restore on preprod environment')
    def refresh_preprod(self):

        current_date = date.today()
        current_date = current_date.strftime('%d%m%y')
        env = self.app.pargs.environment
        source = 'mysql-slave-4-20220415'
        snapshot = source + '-' + current_date
        disk = env + '-mysql-' + current_date
        disk_slave = env + '-mysql-slave-' + current_date

        # check if snapshot already exists
        check_snapshot_command = "gcloud compute snapshots list --project=<GCP_PROJECT_PROD> --filter=%s" % (snapshot)
        echo("Checking if existing snapshot exists: " + check_snapshot_command, "green")
        check_snapshot_command_call = subprocess.run(check_snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)
        check_snapshot_command_call_stderr = len(check_snapshot_command_call.stderr)

        if check_snapshot_command_call_stderr == 0:
            echo(check_snapshot_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Snapshot already exists. Please delete it before running data refresh.")

        echo(check_snapshot_command_call.stdout.decode('utf-8'), "green")

        # check if persistent disk already exists
        check_disk_command = "gcloud compute disks list --project=<GCP_PROJECT_PREPROD> --filter=%s" % (disk)
        echo("Checking if existing persistent disk exists: " + check_disk_command, "green")
        check_disk_command_call = subprocess.run(check_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
        check_disk_command_call_stderr = len(check_disk_command_call.stderr)

        if check_disk_command_call_stderr == 0:
            echo(check_disk_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Persistent disk already exists. Please delete it before running data refresh.")

        echo(check_disk_command_call.stdout.decode('utf-8'), "green")

        # get currently attached mysql data disk on <GCP_PROJECT_PREPROD>mysql-master
        current_disk_command = "gcloud compute instances describe <GCP_PROJECT_PREPROD>mysql-master --format=\'value(disks[1].deviceName)\'"
        echo("Get currently attached MySQL data disk on <GCP_PROJECT_PREPROD>mysql-master: " + current_disk_command, "green")
        current_disk_command_call = subprocess.run(current_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
        current_disk = current_disk_command_call.stdout.decode('utf-8')
        echo(current_disk, "green")

        # get currently attached mysql data disk on <GCP_PROJECT_PREPROD>mysql-solr-slave1
        current_disk_command = "gcloud compute instances describe <GCP_PROJECT_PREPROD>mysql-solr-slave1 --format=\'value(disks[1].deviceName)\'"
        echo("Get currently attached MySQL data disk on <GCP_PROJECT_PREPROD>mysql-solr-slave: " + current_disk_command, "green")
        current_disk_command_call = subprocess.run(current_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
        current_disk_slave = current_disk_command_call.stdout.decode('utf-8')
        echo(current_disk_slave, "green")

        # dump current configurations
        build_directory = os.path.join(registry.dockers_dir, 'project')
        docker_directory = os.path.join(build_directory, 'dockers-beta')
        ssh_key = os.path.join(docker_directory, 'config', 'keys', 'id_rsa')

        os.system("chmod 400 " + ssh_key)
        echo("SSH key:" + ssh_key, "green")

        c = Connection(host='<PROD_SERVER_HOST>', user='<SSH_USER>', connect_kwargs={'key_filename': ssh_key})  # Master
        w = Connection(host='<PROD_SERVER_HOST>', user='<SSH_USER>', connect_kwargs={'key_filename': ssh_key})  # Slave

        # NEED TO STOP SLAVE, STOP MYSQL SERVICE, AND UNMOUNT /VAR/LIB/MYSQL
        echo("Stopping the MySQL Slave now")
        w.sudo('systemctl stop mysql')
        echo("Slave MySQL Stopped successfully", "green")
        w.sudo('umount -v /var/lib/mysql')
        echo("Unmount /var/lib/mysql successfull", "green")
        w.close()

        echo(
            "Dumping mysql, <GCP_PROJECT>_CRMPortal.Configuration, carmudi_journal.wp_options & icarsuite_accounts.application tables",
            "green")
        c.sudo('rm -f /opt/temp/<GCP_PROJECT>_CRMPortal_Configuration.sql')
        c.sudo('rm -f /opt/temp/icarsuite_accounts_application.sql')
        c.sudo('rm -f /opt/temp/carmudi_journal_wp_options.sql')
        c.sudo('rm -f /opt/temp/mysql.sql')
        c.sudo('mysqldump <GCP_PROJECT>_CRMPortal Configuration > /opt/temp/<GCP_PROJECT>_CRMPortal_Configuration.sql')
        c.sudo('mysqldump icarsuite_accounts application > /opt/temp/icarsuite_accounts_application.sql')
        c.sudo('mysqldump carmudi_journal wp_options > /opt/temp/carmudi_journal_wp_options.sql')
        c.sudo('mysqldump mysql > /opt/temp/mysql.sql')
        echo("Stopping MySQL service...", "green")
        c.sudo('systemctl stop mysql')
        echo("Unmounting /var/lib/mysql", "green")
        c.sudo('umount /var/lib/mysql')
        c.close()

        # take snapshot from production
        snapshot_command = "gcloud compute disks snapshot %s --project=<GCP_PROJECT_PROD> --zone=<GCP_REGION>-a --storage-location=ASIA-SOUTHEAST1 --snapshot-names=%s" % (
            source, snapshot)
        echo("Taking snapshot: " + snapshot_command, "green")
        snapshot_command_call = subprocess.run(snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)

        if snapshot_command_call.returncode != 0:
            echo(snapshot_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to take snapshot")

        echo(snapshot_command_call.stdout.decode('utf-8'), "green")

        # create persistent disk from snapshot on preprod
        create_disk_command = "gcloud compute disks create --labels=provisioned=icarcli --project=<GCP_PROJECT_PREPROD> --zone=<GCP_REGION>-a --type=pd-standard %s --source-snapshot=https://www.googleapis.com/compute/v1/projects/<GCP_PROJECT_PROD>/global/snapshots/%s" % (
            disk, snapshot)
        echo("Creating persistent disk from snapshot: " + create_disk_command, "green")
        create_disk_command_call = subprocess.run(create_disk_command, shell=True, stdout=PIPE, stderr=PIPE)

        if create_disk_command_call.returncode != 0:
            echo(create_disk_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to create persistent disk")

        echo(create_disk_command_call.stdout.decode('utf-8'), "green")

        # NEED TO CREATE ANOTHER PERSISTENT DISK FOR SLAVE FROM PRODUCTION SNAPSHOT
        create_disk_command = "gcloud compute disks create --labels=provisioned=icarcli --project=<GCP_PROJECT_PREPROD> --zone=<GCP_REGION>-a --type=pd-standard %s --source-snapshot=https://www.googleapis.com/compute/v1/projects/<GCP_PROJECT_PROD>/global/snapshots/%s" % (
            disk_slave, snapshot)
        echo("Creating persistent disk from snapshot: " + create_disk_command, "green")
        create_disk_command_call = subprocess.run(create_disk_command, shell=True, stdout=PIPE, stderr=PIPE)

        if create_disk_command_call.returncode != 0:
            echo(create_disk_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to create persistent disk for slave")

        echo(create_disk_command_call.stdout.decode('utf-8'), "green")

        # detach existing mysql data disk from <GCP_PROJECT_PREPROD>mysql-master
        detach_disk_command = "gcloud compute instances detach-disk <GCP_PROJECT_PREPROD>mysql-master --device-name=%s" % (
            current_disk)
        echo("Detaching current MySQL data disk from <GCP_PROJECT_PREPROD>mysql-master: " + detach_disk_command, "green")
        detach_disk_command_call = subprocess.run(detach_disk_command, shell=True, stdout=PIPE, stderr=PIPE)

        if detach_disk_command_call.returncode != 0:
            echo(detach_disk_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to detach current MySQL data disk on <GCP_PROJECT_PREPROD>mysql-master")

        # NEED TO DETACH EXISTING MYSQL DATA DISK FROM PREPROD-MYSQL-SOLR-SLAVE1
        detach_disk_command = "gcloud compute instances detach-disk <GCP_PROJECT_PREPROD>mysql-solr-slave1 --device-name=%s" % (
            current_disk_slave)
        echo("Detaching current MySQL data disk from <GCP_PROJECT_PREPROD>mysql-solr-slave1: " + detach_disk_command, "green")
        detach_disk_command_call = subprocess.run(detach_disk_command, shell=True, stdout=PIPE, stderr=PIPE)

        if detach_disk_command_call.returncode != 0:
            echo(detach_disk_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to detach current MySQL data disk on <GCP_PROJECT_PREPROD>mysql-solr-slave1")

        # attach newly created mysql data disk
        attach_disk_command = "gcloud compute instances attach-disk <GCP_PROJECT_PREPROD>mysql-master --disk=%s --device-name=%s --mode=rw --zone <GCP_REGION>-a" % (
            disk, disk)
        echo("Attaching new MySQL data disk on <GCP_PROJECT_PREPROD>mysql-master: " + attach_disk_command, "green")
        attach_disk_command_call = subprocess.run(attach_disk_command, shell=True, stdout=PIPE, stderr=PIPE)

        if attach_disk_command_call.returncode != 0:
            echo(detach_disk_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to attach new MySQL data disk on <GCP_PROJECT_PREPROD>mysql-master")

        add_fstab_command = "echo \"UUID=`sudo blkid -s UUID -o value /dev/sdb` /var/lib/mysql ext4 discard,defaults,nofail 0 2\" | sudo tee -a /etc/fstab"

        echo("Removing old fstab entry from /etc/fstab", "green")
        c.sudo('sed -i \'/mysql/d\' /etc/fstab')
        c.sudo(
            'mount -av')  # need to do this to refresh fstab otherwise systemd will think disk is not ready and auto unmount
        echo("Adding new fstab entry into /etc/fstab", "green")
        c.sudo(add_fstab_command)
        echo("Mounting newly attached disk", "green")
        c.sudo('mount -av; ls -li /var/lib/mysql')
        echo("Changing ownership of /var/lib/mysql", "green")
        c.sudo('chown -R mysql:mysql /var/lib/mysql')
        echo("Remove /var/lib/mysql/auto.cnf",
             "green")  # need to do this to ensure no clash of server uuids. Mysql will generate new file with its own server uuid upon start.
        c.sudo('rm -f /var/lib/mysql/auto.cnf')
        echo("Starting MySQL service", "green")
        c.sudo('systemctl start mysql')

        # GET CURRENT MASTER BINLOG FILE AND POSITION
        file_binlog = c.sudo("mysql -e 'show master status;' | awk '{print $1}' | grep -v File", hide=True)
        post_binlog = c.sudo("mysql -e 'show master status;' | awk '{print $2}' | grep -v Position", hide=True)
        file_binlog = file_binlog.stdout.strip()
        post_binlog = post_binlog.stdout.strip()
        c.close()

        # NEED TO ATTACH NEWLY CREATED MYSQL SLAVE DATA DISK TO PREPROD-MYSQL-SOLR-SLAVE1
        attach_disk_command = "gcloud compute instances attach-disk <GCP_PROJECT_PREPROD>mysql-solr-slave1 --disk=%s --device-name=%s --mode=rw --zone <GCP_REGION>-a" % (
            disk_slave, disk_slave)
        echo("Attaching new MySQL data disk on <GCP_PROJECT_PREPROD>mysql-solr-slave1: " + attach_disk_command, "green")
        attach_disk_command_call = subprocess.run(attach_disk_command, shell=True, stdout=PIPE, stderr=PIPE)

        if attach_disk_command_call.returncode != 0:
            echo(detach_disk_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to attach new MySQL data disk on <GCP_PROJECT_PREPROD>mysql-solr-slave1")

        add_fstab_command = "echo \"UUID=`sudo blkid -s UUID -o value /dev/sdb` /var/lib/mysql ext4 discard,defaults,nofail 0 2\" | sudo tee -a /etc/fstab"

        echo("Removing old fstab entry from /etc/fstab", "green")
        w.sudo('sed -i \'/mysql/d\' /etc/fstab')
        w.sudo(
            'mount -av')  # need to do this to refresh fstab otherwise systemd will think disk is not ready and auto unmount
        echo("Adding new fstab entry into /etc/fstab", "green")
        w.sudo(add_fstab_command)
        echo("Mounting newly attached disk", "green")
        w.sudo('mount -av; ls -li /var/lib/mysql')
        echo("Changing ownership of /var/lib/mysql", "green")
        w.sudo('chown -R mysql:mysql /var/lib/mysql')
        echo("Remove /var/lib/mysql/auto.cnf",
             "green")  # need to do this to ensure no clash of server uuids. Mysql will generate new file with its own server uuid upon start.
        w.sudo('rm -f /var/lib/mysql/auto.cnf')

        # NEED TO START MYSQL SERVICE ON PREPROD-MYSQL-SOLR-SLAVE1
        echo("Starting MySQL service", "green")
        w.sudo('systemctl start mysql')
        w.close()

        # copy configuration files to server
        echo("Copying MySQL configuration files to <GCP_PROJECT_PREPROD>mysql-master", "green")

        sql_folder = os.path.join(registry.kubectl_dir, 'template/mysql/data')
        config = sql_folder + '/configuration.sql'

        copy_config = 'gcloud compute scp %s root@<GCP_PROJECT_PREPROD>mysql-master:/opt/temp' % (config)

        copy_files = [copy_config]

        for copy in copy_files:
            echo(copy, 'yellow')
            os.system(copy)

        # need replication user so import users and grants
        echo("Importing MySQL database", "green")
        c.sudo('mysql mysql < /opt/temp/mysql.sql')
        c.sudo("mysql -e 'FLUSH PRIVILEGES;'")

        # NEED TO JOIN PREPROD-MYSQL-SOLR-SLAVE1 TO MASTER AND ENSURE REPLICATION IS OK
        w.sudo("mysql -e 'stop slave;'")
        w.sudo(
            "mysql -e \"CHANGE MASTER TO MASTER_HOST='<MASTER_DB_HOST>',MASTER_USER='<REPLICATION_USER>', MASTER_PASSWORD='<REPLICATION_PASSWORD>', MASTER_LOG_FILE='%s', MASTER_LOG_POS=%s;\"" % (
                file_binlog, post_binlog))
        w.sudo("mysql -e 'start slave;'")
        time.sleep(10)
        # slave_status = w.sudo("mysql -e 'show slave status;'", hide=True).stdout.strip()
        # print(slave_status)
        # result = slave_status.find('Slave has read all relay log; waiting for more updates')
        while True:
            slave_status = w.sudo("mysql -e 'show slave status;'", hide=True).stdout.strip()
            print(slave_status)
            result = slave_status.find('Slave has read all relay log; waiting for more updates')
            print('Find at index: ' + str(result))
            if result == -1:
                echo('Please check slave status, sleeping for 10 seconds.')
                time.sleep(10)
            else:
                break
        print("Slave successfully connected with master")
        echo("Importing icarsuite_accounts configurations", "green")
        c.sudo('mysql icarsuite_accounts -v -e \"source /opt/temp/icarsuite_accounts_application.sql\"')
        echo("Importing <GCP_PROJECT>_CRMPortal configurations", "green")
        c.sudo('mysql <GCP_PROJECT>_CRMPortal -v -e \"source /opt/temp/<GCP_PROJECT>_CRMPortal_Configuration.sql\"')
        echo("Importing carmudi_journal configurations", "green")
        c.sudo('mysql carmudi_journal -v -e \"source /opt/temp/carmudi_journal_wp_options.sql\"')
        echo("Making changes in <GCP_PROJECT>_CRMPortal.Contact & icarsuite_accounts.user tables", "green")
        c.sudo('mysql -v -e \"source /opt/temp/configuration.sql\"')  # this will take approximately 1 hour to complete
        c.close()

        # TO DO - Delete snapshot
        # TO DO - Delete old mysql disk

    @profile
    @command
    @expose(help='Trigger SOLR reindex for data refresh')
    def trigger_solr_reindex_data_refresh(self):
        sql_query = "USE <GCP_PROJECT>;TRUNCATE TABLE trigger_listing_solr_reindex;INSERT INTO trigger_listing_solr_reindex (listing_id, seller_id) SELECT id, '' FROM LISTING WHERE STATUS = 'Published';INSERT INTO trigger_listing_solr_reindex (listing_id, seller_id) SELECT id, '' FROM LISTING WHERE STATUS NOT IN ('Archived','Published');"
        env = self.app.pargs.environment
        if (env == 'preprod'):
            build_directory = os.path.join(registry.dockers_dir, 'project')
            docker_directory = os.path.join(build_directory, 'dockers-beta')
            ssh_key = os.path.join(docker_directory, 'config', 'keys', 'id_rsa')

            os.system("chmod 400 " + ssh_key)
            echo("SSH key:" + ssh_key, "green")

            c = Connection(host='<PROD_SERVER_HOST>', user='<SSH_USER>', connect_kwargs={'key_filename': ssh_key})  # Master
            c.sudo('mysql -u root -e "%s"' % (sql_query))
            c.close()
        else:
            mysql_pod = getPod('mysql', env)
            echo(mysql_pod)
            run_command = 'kubectl exec %s -- mysql -e \"%s\"' % (mysql_pod, sql_query)
            echo(run_command)
            run_command_call =subprocess.run(run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if run_command_call.returncode == 0:
                echo(run_command_call.stdout.decode('utf-8'))

    @profile
    @command
    @expose(help='CMS migration for platform-c or platform-d')
    def cms_cover_image_migrate(self):
        env = self.app.pargs.environment
        lang = self.app.pargs.language
        type = self.app.pargs.type

        # guards
        if lang not in ("id-id", "th-th") or lang is None:
            raise SystemExit("Language is not supported")
        if type not in ("cover", "gallery") or type is None:
            raise SystemExit("Type is not supported")
        if env not in ("staging", "production"):
            raise SystemExit("Env is not supported")

        if lang == "id-id":
            image_dir = "platform-c-news"
        elif lang == "th-th":
            image_dir = "platform-d-news"

        if type == "cover":
            sub_query = "<GCP_PROJECT>_news.drup_field_data_field_image_cover drupcover ON drupcover.entity_id = article.nid JOIN <GCP_PROJECT>_news.drup_file_managed drupfile ON drupfile.fid = drupcover.field_image_cover_fid"
            article_type = "article"
        elif type == "gallery":
            sub_query = "<GCP_PROJECT>_news.drup_field_data_field_gallery_images drupcover ON drupcover.entity_id = article.nid JOIN <GCP_PROJECT>_news.drup_file_managed drupfile ON drupfile.fid = drupcover.field_gallery_images_fid"
            article_type = "gallery"

        sql_query = """
                    use <GCP_PROJECT>_news;
                    select concat( 'gsutil cp -n gs://<GCS_TMP_BUCKET>/', replace(uri, 's3://' ,''), ' gs://<GCP_PROJECT>-test-images-w7kfszzqaqsk24x5/%s/%s/',REPLACE(SUBSTRING_INDEX(uri,'/',-3),'/','_')) as gsutil_command
                    from drup_node article JOIN
                    %s
                    where  article.language = '%s'
                    and  drupcover.language = '%s'
                    and article.type = '%s'
                    and article.status = 1
                    and FROM_UNIXTIME(created) >= '2023-01-01'
                    order by article.nid desc;
                    """ % (image_dir, type, sub_query, lang, lang, article_type)
        
        if env == "production":
            mysql_pod = getPod('mysql-slave-4', env)
        elif env == "staging":
            mysql_pod = getPod('mysql', env)
        echo("Running query", "yellow")
        run_query = '%skubectl exec %s -- mysql mysql -e "%s"' % (registry.term, mysql_pod, sql_query)
        echo(run_query)
        query_run = subprocess.run(run_query, shell=True, stdout=PIPE, stderr=PIPE)
        output = query_run.stdout.decode('utf-8')
        gsutil_cmds = output.split("\n")
        n = 0
        for cmd in gsutil_cmds[1:]:
            print(n, cmd)
            n = n + 1
            cmd_run = subprocess.run(cmd, shell=True, stdout=PIPE, stderr=PIPE)
            if cmd_run.returncode == 0:
                echo(cmd_run.stdout.decode('utf-8'))
            else:
                echo('Command exited with the following error %s' % cmd_run.stderr.decode('utf-8'), "red")


    @profile
    @command
    @expose(help='CMS migration for platform-c or platform-d')
    def cms_body_image_migrate(self):
        import re
        import mysql.connector
        from urllib.parse import urlparse
        env = self.app.pargs.environment
        lang = self.app.pargs.language
        # type = self.app.pargs.type
        # guards
        if lang not in ("id-id", "th-th") or lang is None:
            raise SystemExit("Language is not supported")
        if env not in ("staging", "production"):
            raise SystemExit("Env is not supported")

        if lang == "id-id":
            image_dir = "platform-c-news"
        elif lang == "th-th":
            image_dir = "platform-d-news"
        
        # change to production credential
        if env == "production":
            connection = mysql.connector.connect(host="<PROD_DB_HOST>", user="<DB_MIGRATION_USER>", password="<DB_MIGRATION_PASSWORD>", database="<DB_NAME>_news")
        elif env == "staging":
            # <GCP_IP>
            connection = mysql.connector.connect(host="10.148.0.75", user="<GCP_PROJECT>", password="<GCP_PROJECT>", database="<GCP_PROJECT>_news")
        cursor = connection.cursor(dictionary=True)
        query = f"""
                select nid, body_value, FROM_UNIXTIME(t2.created) as created_on from drup_field_data_body t1
                join drup_node t2 on t1.`entity_id` = t2.`nid` and t2.status = 1 
                where t2.language = '{lang}'
                and t2.type = 'article'
                and t1.body_value like "%content.icarcdn.com%" 
                having created_on >= '2023-01-01'
                order by nid;
                """
        echo(query, "yellow")
        cursor.execute(query)
        rows = cursor.fetchall()

        regex = r"\bhttps?://[content.icarcdn.com][^,\s()<>]+(?:\([\w\d]+\)|(|\s]|/))"
        n = 0
        for row in rows:
            # matches = re.search(regex, row['body_value'])
            matches = re.finditer(regex, row['body_value'], re.IGNORECASE)

            for matchNum, match in enumerate(matches, start=1):
                # remove trailing "
                image_url = match.group().replace('"', "")
                path = urlparse(image_url).path
                path_parts = path.split("/")
                cmd = f"gsutil cp -n gs://<GCS_TMP_BUCKET>{path} gs://<GCP_PROJECT>-test-images-w7kfszzqaqsk24x5/{image_dir}/body/{row['nid']}-{path_parts[-1]}"
                print(n, cmd)
                n = n + 1
                cmd_run = subprocess.run(cmd, shell=True, stdout=PIPE, stderr=PIPE)
                if cmd_run.returncode == 0:
                    echo(cmd_run.stdout.decode('utf-8'))
                else:
                    echo('Command exited with the following error %s' % cmd_run.stderr.decode('utf-8'), "red")

    @profile
    @command
    @expose(help='Restart MySQL instance')
    def restart(self):
        env = self.app.pargs.environment
        if (env == 'preprod'):
            run_command = 'gcloud compute ssh <GCP_PROJECT_PREPROD>mysql-master --project="<GCP_PROJECT_PREPROD>" --zone="<GCP_REGION>-a" --command="sudo systemctl restart mysql"'
            echo(run_command)
            os.system(run_command)
        else:
            mysql_pod = getPod('mysql', env)
            echo(mysql_pod)
            run_command = "kubectl exec %s -- service mysql restart" % (mysql_pod)
            echo(run_command)
            run_command_call =subprocess.run(run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if run_command_call.returncode == 0:
                echo(run_command_call.stdout.decode('utf-8'))
     
    @profile
    @command
    @expose(help='Create snapshot from MySQL-timeline production and restore on preprod')
    def refreshTimeline(self):
        current_date = date.today()
        current_date = current_date.strftime('%d%m%y')
        env = self.app.pargs.environment
        source = 'mysql-timeline-data'
        snapshot = source + '-' + current_date
        disk = 'mysql-timeline-data-refresh-' + current_date
        deployment = 'mysql-timeline-data-refresh'
        default_disk = 'null-disk'

        # scale down mysql-timeline-data-refresh pod to zero, to enable disk deletion
        scale_command = "kubectl scale deployment %s --replicas=0" % (deployment)
        echo("Scaling in Deployment: " + scale_command, "green")
        scale_command_call = subprocess.run(scale_command, shell=True, stdout=PIPE, stderr=PIPE)

        # check if snapshot already exists
        check_snapshot_command = "gcloud compute snapshots list --project=<GCP_PROJECT_PROD> --filter=%s" % (snapshot)
        echo("Checking if existing snapshot exists: " + check_snapshot_command, "green")
        check_snapshot_command_call = subprocess.run(check_snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)
        check_snapshot_command_call_stderr = len(check_snapshot_command_call.stderr)

        # delete snapshot if exist
        if check_snapshot_command_call_stderr == 0:
            echo(check_snapshot_command_call.stderr.decode('utf-8'), 'red')
            echo("Snapshot already exists. Please delete it before running data refresh.", "yellow")
            delete_snapshot_command = "gcloud compute snapshots delete projects/<GCP_PROJECT_PROD>/global/snapshots/%s --quiet" % (snapshot)
            echo("Deleting snapshot: " + delete_snapshot_command, "green")
            delete_snapshot_command_call = subprocess.run(delete_snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)
        echo(check_snapshot_command_call.stdout.decode('utf-8'), "green")

        # check if persistent disk already exists
        check_disk_command = "gcloud compute disks list --project=<GCP_PROJECT_PREPROD> --filter=%s" % (disk)
        echo("Checking if existing persistent disk exists: " + check_disk_command, "green")
        check_disk_command_call = subprocess.run(check_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
        check_disk_command_call_stderr = len(check_disk_command_call.stderr)

        # delete snapshot if exist
        if check_disk_command_call_stderr == 0:
            echo(check_disk_command_call.stderr.decode('utf-8'), 'red')
            echo("Persistent disk already exists. Please delete it before running data refresh.", "yellow")
            delete_disk_command = "gcloud compute disks delete %s --project=<GCP_PROJECT_PREPROD> --quiet" % (disk)
            echo("Deleting disk: " + delete_disk_command, "green")
            delete_disk_command_call = subprocess.run(delete_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
        echo(check_disk_command_call.stdout.decode('utf-8'), "green")

        # take snapshot from production
        snapshot_command = "gcloud compute disks snapshot %s --project=<GCP_PROJECT_PROD> --zone=<GCP_REGION>-a --storage-location=ASIA-SOUTHEAST1 --snapshot-names=%s" % (
            source, snapshot)
        echo("Taking snapshot: " + snapshot_command, "green")
        snapshot_command_call = subprocess.run(snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)

        if snapshot_command_call.returncode != 0:
            echo(snapshot_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to take snapshot")
        echo(snapshot_command_call.stdout.decode('utf-8'), "green")

        # create persistent disk from snapshot on preprod
        create_disk_command = "gcloud compute disks create --labels=provisioned=icarcli --project=<GCP_PROJECT_PREPROD> --zone=<GCP_REGION>-a --type=pd-standard %s --source-snapshot=https://www.googleapis.com/compute/v1/projects/<GCP_PROJECT_PROD>/global/snapshots/%s" % (
            disk, snapshot)
        echo("Creating persistent disk from snapshot: " + create_disk_command, "green")
        create_disk_command_call = subprocess.run(create_disk_command, shell=True, stdout=PIPE, stderr=PIPE)

        if create_disk_command_call.returncode != 0:
            echo(create_disk_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to create persistent disk")
        echo(create_disk_command_call.stdout.decode('utf-8'), "green")

        # get current attached disk so that we can delete it at end of script
        current_disk_command = "kubectl get deploy %s -o=jsonpath=\'{.spec.template.spec.volumes[0].gcePersistentDisk.pdName}\'" % (deployment)
        echo(current_disk_command)
        subprocess.run(current_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
        # current_disk_command_call = subprocess.run(current_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
        # pattern = r"(stag\w+-mysql-\w+)"
        # current_disk = re.findall(pattern, str(current_disk_command_call.stdout))[0]
        # current_disk = current_disk_command_call.stdout.decode('utf-8')

        # patch mysql deployment with new disk
        patch_command = "kubectl patch deployment %s --type=json -p='[{\"op\": \"replace\", \"path\": \"/spec/template/spec/volumes/0/gcePersistentDisk/pdName\", \"value\":\"%s\"}]'" % (
            deployment, disk)
        echo("Applying patch for Deployment: " + patch_command, "green")
        patch_command_call = subprocess.run(patch_command, shell=True, stdout=PIPE, stderr=PIPE)

        if patch_command_call.returncode != 0:
            echo(patch_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to patch deployment")

        echo(patch_command_call.stdout.decode('utf-8'), "green")

        # scale out mysql-timeline-data-refresh pod to 1
        scale_command = "kubectl scale deployment %s --replicas=1" % (deployment)
        echo("Scaling in Deployment: " + scale_command, "green")
        scale_command_call = subprocess.run(scale_command, shell=True, stdout=PIPE, stderr=PIPE)

        if scale_command_call.returncode != 0:
            echo(scale_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to Scale Out")

        # check deployment state, needs about 3 mins for mysql to do self checks and repairs.
        echo("Check deployment state for %s:" % deployment, "blue")
        while True:
            time.sleep(10)
            get_status_commmand = "kubectl get pods --selector=app=%s -o jsonpath=\"{.items[*].status.phase}\"" % deployment
            get_status_commmand_call = subprocess.run(get_status_commmand, shell=True, stdout=PIPE, stdin=PIPE)
            command_result = get_status_commmand_call.stdout.decode('utf-8')
            if "Running" in command_result:
                echo("Deployment done!", "green")
                break

        while True:
            # get pod everytime as the previous pod might crashed and no longer exist
            mysql_pod = getPodTimeline('mysql-timeline-data-refresh', env)
            sql_query = "select 'mysqld running';"
            echo("Check if mysqld is running...", "yellow")
            run_query = '%skubectl exec %s -- mysql mysql -e "%s"' % (registry.term, mysql_pod, sql_query)
            echo(run_query)
            query_run = subprocess.run(run_query, shell=True, stdout=PIPE, stderr=PIPE)
            output = query_run.stdout.decode('utf-8')
            echo(output)
            if "running" in output:
                echo("Yes it is running")
                break
            time.sleep(10)

        # run configuration files on MySQL
        dumpPodTimeline(env)
        time.sleep(10)
        # copy the files from local to MYSQL_timeline pod
        copyFilesTimeline(env)
        # sorce the mysql databases
        sourceTimeLine(env)
        # Cleaning up files 
        cleanUpTimeline(env)

        # delete snapshot
        delete_snapshot_command = "gcloud compute snapshots delete projects/<GCP_PROJECT_PROD>/global/snapshots/%s --quiet" % (
            snapshot)
        echo("Deleting snapshot: " + delete_snapshot_command, "green")
        delete_snapshot_command_call = subprocess.run(delete_snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)

        if delete_snapshot_command_call.returncode != 0:
            echo(delete_snapshot_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to delete snapshot")
        echo(delete_snapshot_command_call.stdout.decode('utf-8'), "green")

        # to unmount the disk from the mysql-timeline-data-refresh deployment 
        patch_command = "kubectl patch deployment %s --type=json -p='[{\"op\": \"replace\", \"path\": \"/spec/template/spec/volumes/0/gcePersistentDisk/pdName\", \"value\":\"%s\"}]'" % (
            deployment, default_disk)
        echo("Applying patch for Deployment: " + patch_command, "green")

        # scale down mysql-timeline-data-refresh pod to zero 
        scale_command = "kubectl scale deployment %s --replicas=0" % (deployment)
        echo("Scaling in Deployment: " + scale_command, "green")
        scale_command_call = subprocess.run(scale_command, shell=True, stdout=PIPE, stderr=PIPE)

        if scale_command_call.returncode != 0:
            echo(scale_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to patch Scale in")

        echo("Napping for 30s... I am tired")
        time.sleep(30)

        # check if pod scaled to 0 before deleting the disk
        get_status_commmand = "kubectl get pods --selector=app=%s -o jsonpath=\"{.items[*].status.phase}\"" % deployment
        while True:
            echo(f"Checking if {deployment} is scaled to 0...")
            get_status_commmand_call = subprocess.run(get_status_commmand, shell=True, stdout=PIPE, stdin=PIPE)
            command_result = get_status_commmand_call.stdout.decode('utf-8')
            if command_result == "":
                # remove the persistent disk
                delete_disk_command = "gcloud compute disks delete --project=<GCP_PROJECT_PREPROD> %s --quiet" % (disk)
                echo("Deleting old persistent disk: " + delete_disk_command, "green")
                delete_disk_command_call = subprocess.run(delete_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
                if delete_disk_command_call.returncode != 0:
                    echo(delete_disk_command_call.stderr.decode('utf-8'), 'red')
                    self._on_process_end("Failed to delete persistent disk")
                echo(delete_disk_command_call.stdout.decode('utf-8'), "green")
                break
            time.sleep(10)

    @profile
    @command
    @expose(help='Create snapshot from MySQL production and restore on staging environments')
    def refresh(self):
        current_date = date.today()
        current_date = current_date.strftime('%d%m%y')
        # to bypass disk already exist sticky situation that creates chicken and egg problem
        # now = datetime.now()
        # current_date = now.strftime('%d%m%y_%H:%M:%S')
        env = self.app.pargs.environment
        source = 'mysql-slave-4-20220415'
        snapshot = source + '-' + current_date
        disk = env + '-mysql-' + current_date
        deployment = env + '-mysql'

        # check if snapshot already exists
        check_snapshot_command = "gcloud compute snapshots list --project=<GCP_PROJECT_PROD> --filter=%s" % (snapshot)
        echo("Checking if existing snapshot exists: " + check_snapshot_command, "green")
        check_snapshot_command_call = subprocess.run(check_snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)
        check_snapshot_command_call_stderr = len(check_snapshot_command_call.stderr)

        if check_snapshot_command_call_stderr == 0:
            echo(check_snapshot_command_call.stderr.decode('utf-8'), 'red')
            echo("Snapshot already exists. Please delete it before running data refresh.")
            delete_snapshot_command = "gcloud compute snapshots delete projects/<GCP_PROJECT_PROD>/global/snapshots/%s --quiet" % (snapshot)
            echo("Deleting snapshot: " + delete_snapshot_command, "green")
            delete_snapshot_command_call = subprocess.run(delete_snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)

        echo(check_snapshot_command_call.stdout.decode('utf-8'), "green")

        # check if persistent disk already exists
        check_disk_command = "gcloud compute disks list --project=<GCP_PROJECT_PREPROD> --filter=%s" % (disk)
        echo("Checking if existing persistent disk exists: " + check_disk_command, "green")
        check_disk_command_call = subprocess.run(check_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
        check_disk_command_call_stderr = len(check_disk_command_call.stderr)

        if check_disk_command_call_stderr == 0:
            # scale down mysql pod to zero, to enable disk deletion
            scale_command = "kubectl scale deployment %s --replicas=0" % (deployment)
            echo("Scaling in Deployment: " + scale_command, "green")
            subprocess.run(scale_command, shell=True, stdout=PIPE, stderr=PIPE)
            echo(check_disk_command_call.stderr.decode('utf-8'), 'red')
            echo("Persistent disk already exists. Please delete it before running data refresh.")
            # check if pod scaled to 0 before deleting the disk
            get_status_commmand = "kubectl get pods --selector=app=%s -o jsonpath=\"{.items[*].status.phase}\"" % deployment
            while True:
                echo(f"Checking if {deployment} is scaled to 0...")
                get_status_commmand_call = subprocess.run(get_status_commmand, shell=True, stdout=PIPE, stdin=PIPE)
                command_result = get_status_commmand_call.stdout.decode('utf-8')
                if command_result == "":
                    delete_disk_command = "gcloud compute disks delete %s --project=<GCP_PROJECT_PREPROD> --quiet" % (disk)
                    echo("Deleting disk: " + delete_disk_command, "green")
                    subprocess.run(delete_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
                    break
                time.sleep(10)
            # scale down mysql pod to 1
            scale_command = "kubectl scale deployment %s --replicas=1" % (deployment)
            echo("Scaling in Deployment: " + scale_command, "green")
            subprocess.run(scale_command, shell=True, stdout=PIPE, stderr=PIPE)
            echo("Check deployment state for %s:" % deployment, "blue")
            while True:
                time.sleep(10)
                get_status_commmand = "kubectl get pods --selector=app=%s -o jsonpath=\"{.items[*].status.phase}\"" % deployment
                get_status_commmand_call = subprocess.run(get_status_commmand, shell=True, stdout=PIPE, stdin=PIPE)
                command_result = get_status_commmand_call.stdout.decode('utf-8')
                if "Running" in command_result:
                    echo("Deployment done!", "green")
                    break
            
            while True:
                # get pod everytime as the previous pod might crashed and no longer exist
                mysql_pod = getPod('mysql', env)
                sql_query = "select 'mysqld running';"
                echo("Check if mysqld is running...", "yellow")
                run_query = '%skubectl exec %s -- mysql mysql -e "%s"' % (registry.term, mysql_pod, sql_query)
                echo(run_query)
                query_run = subprocess.run(run_query, shell=True, stdout=PIPE, stderr=PIPE)
                output = query_run.stdout.decode('utf-8')
                echo(output)
                if "running" in output:
                    echo("Yes it is running")
                    break
                time.sleep(10)
        echo(check_disk_command_call.stdout.decode('utf-8'), "green")
        
        # dump configuration tables from mysql, <GCP_PROJECT>_CRMPortal & icarsuite_accounts databases
        dumpPod(env)

        # take snapshot from production
        snapshot_command = "gcloud compute disks snapshot %s --project=<GCP_PROJECT_PROD> --zone=<GCP_REGION>-a --storage-location=ASIA-SOUTHEAST1 --snapshot-names=%s" % (
            source, snapshot)
        echo("Taking snapshot: " + snapshot_command, "green")
        snapshot_command_call = subprocess.run(snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)

        if snapshot_command_call.returncode != 0:
            echo(snapshot_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to take snapshot")

        echo(snapshot_command_call.stdout.decode('utf-8'), "green")

        # create persistent disk from snapshot on preprod
        create_disk_command = "gcloud compute disks create --labels=provisioned=icarcli --project=<GCP_PROJECT_PREPROD> --zone=<GCP_REGION>-a --type=pd-standard %s --source-snapshot=https://www.googleapis.com/compute/v1/projects/<GCP_PROJECT_PROD>/global/snapshots/%s" % (
            disk, snapshot)
        echo("Creating persistent disk from snapshot: " + create_disk_command, "green")
        create_disk_command_call = subprocess.run(create_disk_command, shell=True, stdout=PIPE, stderr=PIPE)

        if create_disk_command_call.returncode != 0:
            echo(create_disk_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to create persistent disk")

        echo(create_disk_command_call.stdout.decode('utf-8'), "green")

        # get current attached disk so that we can delete it at end of script
        current_disk_command = "kubectl get deploy %s -o=jsonpath=\'{.spec.template.spec.volumes[0].gcePersistentDisk.pdName}\'" % (
            deployment)
        current_disk_command_call = subprocess.run(current_disk_command, shell=True, stdout=PIPE, stderr=PIPE)
        # pattern = r"(stag\w+-mysql-\w+)"
        # current_disk = re.findall(pattern, str(current_disk_command_call.stdout))[0]
        current_disk = current_disk_command_call.stdout.decode('utf-8')

        # patch mysql deployment with new disk
        patch_command = "kubectl patch deployment %s --type=json -p='[{\"op\": \"replace\", \"path\": \"/spec/template/spec/volumes/0/gcePersistentDisk/pdName\", \"value\":\"%s\"}]'" % (
            deployment, disk)
        echo("Applying patch for Deployment: " + patch_command, "green")
        patch_command_call = subprocess.run(patch_command, shell=True, stdout=PIPE, stderr=PIPE)

        if patch_command_call.returncode != 0:
            echo(patch_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to patch deployment")

        echo(patch_command_call.stdout.decode('utf-8'), "green")

        # check deployment state, needs about 3 mins for mysql to do self checks and repairs.
        echo("Check deployment state for %s:" % deployment, "blue")
        while True:
            time.sleep(10)
            get_status_commmand = "kubectl get pods --selector=app=%s -o jsonpath=\"{.items[*].status.phase}\"" % deployment
            get_status_commmand_call = subprocess.run(get_status_commmand, shell=True, stdout=PIPE, stdin=PIPE)
            command_result = get_status_commmand_call.stdout.decode('utf-8')
            if "Running" in command_result:
                echo("Deployment done!", "green")
                break
        
        while True:
            # get pod everytime as the previous pod might crashed and no longer exist
            mysql_pod = getPod('mysql', env)
            sql_query = "select 'mysqld running';"
            echo("Check if mysqld is running...", "yellow")
            run_query = '%skubectl exec %s -- mysql mysql -e "%s"' % (registry.term, mysql_pod, sql_query)
            echo(run_query)
            query_run = subprocess.run(run_query, shell=True, stdout=PIPE, stderr=PIPE)
            output = query_run.stdout.decode('utf-8')
            echo(output)
            if "running" in output:
                echo("Yes it is running")
                break
            time.sleep(10)

        while True:
            # get pod everytime as the previous pod might crashed and no longer exist
            mysql_pod = getPod('mysql', env)
            sql_query = "select 'mysqld running';"
            echo("Check if mysqld is running...", "yellow")
            run_query = '%skubectl exec %s -- mysql mysql -e "%s"' % (registry.term, mysql_pod, sql_query)
            echo(run_query)
            query_run = subprocess.run(run_query, shell=True, stdout=PIPE, stderr=PIPE)
            output = query_run.stdout.decode('utf-8')
            echo(output)
            if "running" in output:
                echo("Yes it is running")
                break
            time.sleep(10)

        # copy configuration files to MySQL
        echo("Copying MySQL configuration files to pod", "green")
        copyFiles(env)

        while True:
            # get pod everytime as the previous pod might crashed and no longer exist
            mysql_pod = getPod('mysql', env)
            sql_query = "select 'mysqld running';"
            echo("Check if mysqld is running...", "yellow")
            run_query = '%skubectl exec %s -- mysql mysql -e "%s"' % (registry.term, mysql_pod, sql_query)
            echo(run_query)
            query_run = subprocess.run(run_query, shell=True, stdout=PIPE, stderr=PIPE)
            output = query_run.stdout.decode('utf-8')
            echo(output)
            if "running" in output:
                echo("Yes it is running")
                break
            time.sleep(10)

        # run configuration files on MySQL
        echo("Running MySQL configuration files", "green")
        mysql_pod = getPod('mysql', env)
        run_import_mysql_config_query = '%skubectl exec %s -- mysql mysql -e "source /var/lib/mysql/mysql.sql"' % (
            registry.term, mysql_pod)
        run_import_icarsuite_config_query = '%skubectl exec %s -- mysql icarsuite_accounts -e "source /var/lib/mysql/icarsuite_accounts_application.sql"' % (
            registry.term, mysql_pod)
        run_import_crm_config_query = '%skubectl exec %s -- mysql <GCP_PROJECT>_CRMPortal -e "source /var/lib/mysql/<GCP_PROJECT>_CRMPortal_Configuration.sql"' % (
            registry.term, mysql_pod)
        run_import_config_query = '%skubectl exec %s -- mysql -e "source /var/lib/mysql/configuration.sql"' % (
            registry.term, mysql_pod)
        import_queries = [run_import_mysql_config_query, run_import_icarsuite_config_query, run_import_crm_config_query,
                          run_import_config_query]

        for query in import_queries:
            echo(query, 'yellow')
            os.system(query)

        # delete snapshot
        delete_snapshot_command = "gcloud compute snapshots delete projects/<GCP_PROJECT_PROD>/global/snapshots/%s --quiet" % (
            snapshot)
        echo("Deleting snapshot: " + delete_snapshot_command, "green")
        delete_snapshot_command_call = subprocess.run(delete_snapshot_command, shell=True, stdout=PIPE, stderr=PIPE)

        if delete_snapshot_command_call.returncode != 0:
            echo(delete_snapshot_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to delete snapshot")

        echo(delete_snapshot_command_call.stdout.decode('utf-8'), "green")

        # delete old unattached persistent disk
        delete_disk_command = "gcloud compute disks delete --project=<GCP_PROJECT_PREPROD> %s --quiet" % (current_disk)
        echo("Deleting old persistent disk: " + delete_disk_command, "green")
        delete_disk_command_call = subprocess.run(delete_disk_command, shell=True, stdout=PIPE, stderr=PIPE)

        if delete_disk_command_call.returncode != 0:
            echo(delete_disk_command_call.stderr.decode('utf-8'), 'red')
            # self._on_process_end("Failed to delete old persistent disk")
        else:
            echo(delete_disk_command_call.stdout.decode('utf-8'), "green")

    @profile
    @command
    @expose(help='Dump <GCP_PROJECT>_rbac database from preprod and restore to production')
    def refresh_rbac(self):

        dump = 'gcloud compute ssh <GCP_PROJECT_PREPROD>mysql-solr-slave1 --project="<GCP_PROJECT_PREPROD>" --zone="<GCP_REGION>-a" --command="mysqldump <GCP_PROJECT>_rbac > /opt/temp/<GCP_PROJECT>_rbac.sql"'
        copy_from_preprod = 'gcloud compute scp root@<GCP_PROJECT_PREPROD>mysql-solr-slave1:/opt/temp/<GCP_PROJECT>_rbac.sql <GCP_PROJECT>_rbac.sql'
        copy_to_prod = 'gcloud compute scp --project="<GCP_PROJECT_PROD>" --zone="<GCP_REGION>-a" <GCP_PROJECT>_rbac.sql root@mysql-master:/opt/temp'
        run_restore = 'gcloud compute ssh mysql-master --project="<GCP_PROJECT_PROD>" --zone="<GCP_REGION>-a" --command="mysql <GCP_PROJECT>_rbac < /opt/temp/<GCP_PROJECT>_rbac.sql"'

        commands = [dump, copy_from_preprod, copy_to_prod, run_restore]

        for command in commands:
            echo(command, 'yellow')
            os.system(command)

        echo("<GCP_PROJECT>_rbac database succesfully restoredon production!", "green")


def copyFiles(env):
    mysql_pod = getPod('mysql', env)
    sql_folder = os.path.join(registry.kubectl_dir, 'template/mysql/data')

    mysql_config = sql_folder + '/mysql.sql'
    icarsuite_config = sql_folder + '/icarsuite_accounts_application.sql'
    journal_config = sql_folder + '/carmudi_journal_wp_options.sql.sql'
    crm_config = sql_folder + '/<GCP_PROJECT>_CRMPortal_Configuration.sql'
    config = sql_folder + '/configuration.sql'
    directory = '/var/lib/mysql'

    copy_mysql_config = '%skubectl cp %s %s:%s' % (registry.term, mysql_config, mysql_pod, directory)
    copy_icarsuite_config = '%skubectl cp %s %s:%s' % (registry.term, icarsuite_config, mysql_pod, directory)
    copy_journal_config = '%skubectl cp %s %s:%s' % (registry.term, journal_config, mysql_pod, directory)
    copy_crm_config = '%skubectl cp %s %s:%s' % (registry.term, crm_config, mysql_pod, directory)
    copy_config = '%skubectl cp %s %s:%s' % (registry.term, config, mysql_pod, directory)

    copy_files = [copy_mysql_config, copy_icarsuite_config, copy_journal_config, copy_crm_config, copy_config]

    for copy in copy_files:
        echo(copy, 'yellow')
        os.system(copy)


def getPod(service, env):
    if env == "production":
        env_prefix = ""
    else:
        env_prefix = env + '-'
    echo(env_prefix)
    echo(service)
    # Get pod according to labels
    container = subprocess.run(['kubectl', 'get', 'pod', '--selector=app=' + env_prefix + service,
                                '--field-selector=status.phase=Running', '-o',
                                "jsonpath='{.items[0].metadata.name}'"], stdout=subprocess.PIPE).stdout.decode(
        'utf-8').replace("'", "")
    echo("getpod")
    echo(container)
    return container


def dumpPod(env):
    mysql_pod = getPod('mysql', env)
    sql_folder = os.path.join(registry.kubectl_dir, 'template/mysql/data')
    echo("dumppod")
    echo(mysql_pod)
    dump_crm_config = "kubectl exec %s -- bash -c \"mysqldump <GCP_PROJECT>_CRMPortal Configuration > /<GCP_PROJECT>_CRMPortal_Configuration.sql\"" % (
        mysql_pod)
    dump_accounts_config = "kubectl exec %s -- bash -c \"mysqldump icarsuite_accounts application > /icarsuite_accounts_application.sql\"" % (
        mysql_pod)
    dump_carmudi_config = "kubectl exec %s -- bash -c \"mysqldump carmudi_journal wp_options > /carmudi_journal_wp_options.sql\"" % (
        mysql_pod)
    dump_mysql_config = "kubectl exec %s -- bash -c \"mysqldump mysql > /mysql.sql\"" % (mysql_pod)

    copy_crm_config = "kubectl cp %s:/<GCP_PROJECT>_CRMPortal_Configuration.sql %s/<GCP_PROJECT>_CRMPortal_Configuration.sql" % (
        mysql_pod, sql_folder)
    copy_accounts_config = "kubectl cp %s:/icarsuite_accounts_application.sql %s/icarsuite_accounts_application.sql" % (
        mysql_pod, sql_folder)
    copy_carmudi_config = "kubectl cp %s:/carmudi_journal_wp_options.sql %s/carmudi_journal_wp_options.sql.sql" % (
        mysql_pod, sql_folder)
    copy_mysql_config = "kubectl cp %s:/mysql.sql %s/mysql.sql" % (mysql_pod, sql_folder)

    echo(
        'Dumping <GCP_PROJECT>_CRMPortal.Configuration + icarsuite_accounts.application + mysql tables and copying to local',
        'green')

    echo(dump_crm_config, 'yellow')
    os.system(dump_crm_config)
    echo(dump_accounts_config, 'yellow')
    os.system(dump_accounts_config)
    echo(dump_mysql_config, 'yellow')
    os.system(dump_mysql_config)
    echo(dump_carmudi_config, 'yellow')
    os.system(dump_carmudi_config)

    echo(copy_crm_config, 'yellow')
    os.system(copy_crm_config)
    echo(copy_accounts_config, 'yellow')
    os.system(copy_accounts_config)
    echo(copy_mysql_config, 'yellow')
    os.system(copy_mysql_config)
    echo(copy_carmudi_config, 'yellow')
    os.system(copy_carmudi_config)


def getPodTimeline(service, env):
    # Get pod according to labels
    container = subprocess.run(['kubectl', 'get', 'pod', '--selector=app=' + service, 
                                '--field-selector=status.phase=Running', '-o',
                                "jsonpath='{.items[0].metadata.name}'"], stdout=subprocess.PIPE).stdout.decode(
        'utf-8').replace("'", "")
    echo(container)
    return container


def dumpPodTimeline(env):
    mysql_pod = getPodTimeline('mysql-timeline-data-refresh', env)
    sql_folder = os.path.join(registry.kubectl_dir, 'template/mysql/data')
    dump_chatbot = "kubectl exec %s -- bash -c \"mysqldump --routines chatbot > /chatbot.sql\"" % (
        mysql_pod)
    dump_intentio = "kubectl exec %s -- bash -c \"mysqldump --routines intentio > /intentio.sql\"" % (
        mysql_pod)
    dump_timeline = "kubectl exec %s -- bash -c \"mysqldump --routines timeline > /timeline.sql\"" % (
        mysql_pod)
    copy_chatbot = "kubectl cp --retries=10 %s:chatbot.sql %s/chatbot.sql" % (
        mysql_pod, sql_folder)
    copy_intentio = "kubectl cp --retries=10 %s:intentio.sql %s/intentio.sql" % (
        mysql_pod, sql_folder)
    copy_timeline = "kubectl cp --retries=10 %s:timeline.sql %s/timeline.sql" % (
        mysql_pod, sql_folder)

    echo(
        'Dumping chatbot + intentio + timeline db to local',
        'green')

    echo(dump_chatbot, 'yellow')
    os.system(dump_chatbot)
    echo(dump_intentio, 'yellow')
    os.system(dump_intentio)
    echo(dump_timeline, 'yellow')
    os.system(dump_timeline)

    echo(
        'Copy chatbot + intentio + timeline db to local',
        'green')
    

    echo(copy_chatbot, 'yellow')
    os.system(copy_chatbot)
    echo(copy_intentio, 'yellow')
    os.system(copy_intentio)
    echo(copy_timeline, 'yellow')
    os.system(copy_timeline)


def copyFilesTimeline(env):
    mysql_pod = getPodTimeline('mysql-timeline', env)
    sql_folder = os.path.join(registry.kubectl_dir, 'template/mysql/data')

    chatbot_dump = sql_folder + '/chatbot.sql'
    intentio_dump = sql_folder + '/intentio.sql'
    timeline_dump = sql_folder + '/timeline.sql'
    directory = '/var/lib/mysql'

    echo('Copy files from local to mysql_timeline', 'green')

    copy_chatbot = '%skubectl cp --retries=10 %s %s:%s' % (registry.term, chatbot_dump, mysql_pod, directory)
    copy_intentio = '%skubectl cp --retries=10 %s %s:%s' % (registry.term, intentio_dump, mysql_pod, directory)
    copy_timeline = '%skubectl cp --retries=10 %s %s:%s' % (registry.term, timeline_dump, mysql_pod, directory)
    copy_files = [ copy_chatbot, copy_intentio, copy_timeline]

    for copy in copy_files:
        echo(copy, 'yellow')
        status = os.system(copy)
        if status != 0:
            echo(status.stderr.decode('utf-8'), 'red')


def sourceTimeLine(env):
    if env == 'preprod':
        db_prefix = ''
    else:
        db_prefix = env + '_'
    mysql_pod = getPodTimeline('mysql-timeline', env)
    echo('Sourcing Dbs', 'green')
    run_import_chatbot = '%skubectl exec %s -- mysql %schatbot -e "source /var/lib/mysql/chatbot.sql"' % (
        registry.term, mysql_pod, db_prefix)
    run_import_intentio = '%skubectl exec %s -- mysql %sintentio -e "source /var/lib/mysql/intentio.sql"' % (
        registry.term, mysql_pod, db_prefix)
    run_import_timeline = '%skubectl exec %s -- mysql %stimeline -e "source /var/lib/mysql/timeline.sql"' % (
        registry.term, mysql_pod, db_prefix)
    import_queries = [run_import_chatbot, run_import_intentio, run_import_timeline]

    for query in import_queries:
        echo(query, 'yellow')
        os.system(query)

def cleanUpTimeline(env):
    mysql_pod = getPodTimeline('mysql-timeline', env)
    echo('Clean up mysql-timeline', 'green')
    run_clean_chatbot = '%skubectl exec %s -- bash -c \"rm -rf /var/lib/mysql/chatbot.sql\"' % (
        registry.term, mysql_pod)
    run_clean_intentio = '%skubectl exec %s -- bash -c \"rm -rf /var/lib/mysql/intentio.sql\"' % (
        registry.term, mysql_pod)
    run_clean_timeline = '%skubectl exec %s -- bash -c \"rm -rf /var/lib/mysql/timeline.sql\"' % (
        registry.term, mysql_pod)
    import_queries = [run_clean_chatbot, run_clean_intentio, run_clean_timeline]

    for query in import_queries:
        echo(query, 'yellow')
        os.system(query)