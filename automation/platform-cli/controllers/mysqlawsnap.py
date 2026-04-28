import datetime
import subprocess
import time
from subprocess import PIPE

import boto3
import mysql.connector
from botocore.exceptions import ClientError
from cement.core.controller import expose
from mysql.connector import Error

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from core.icarerrors import CommandError
from objects import registry
from resources.messages import messages


class MysqlAwSnapController(ICarBaseController):
    required = {}
    messages = {'default': 'AWS MySQL Snap'}

    config = {
        'preprod': {
            'user': 'awssnapshot',
            'password': '<REDIS_PASSWORD>',
            'host': '52.221.45.79'
        }
    }

    class Meta:
        label = 'mysqlawsnap'
        description = messages['mysqlawss.desc']
        arguments = [
            (['-s', '--site'], dict(help="Specify the site you want to change the ads.txt")),
            (['-c', '--content'],
             dict(help="Enter the content you want to paste inside file ads.txt"))
        ]
        usage = 'icarcli mysqlawsnap'
        epilog = 'Please report to DevOps team if you face an errors.'

    @command
    @expose(hide=True)
    def default(self):
        config = self.config.get(self.app.pargs.environment)
        ec2_client = boto3.client(service_name="ec2", aws_access_key_id='<AWS_ACCESS_KEY_ID>',
                                  aws_secret_access_key='<AWS_SECRET_ACCESS_KEY>',
                                  region_name="<AWS_REGION>")

        vpc_id = '<VPC_ID>'

        try:
            command_get_node_ipads = "kubectl get nodes -l cloud.google.com/gke-nodepool=preprod-node-cicd-8cpu-pool -o jsonpath='{$.items[*].status.addresses[?(@.type==\"ExternalIP\")].address}'"
            print(command_get_node_ipads)
            node_ips_call = subprocess.run([command_get_node_ipads], shell=True, check=True, stdout=PIPE, stderr=PIPE)
            get_node_ips = node_ips_call.stdout.decode("utf-8")
            node_ips = get_node_ips.split()
            print(node_ips)

            ips_each = {}
            ips_list = []
            for node_ip in node_ips:
                print(node_ip)
                ips_each = {'IpProtocol': 'tcp',
                            'FromPort': 3306,
                            'ToPort': 3306,
                            'IpRanges': [{'CidrIp': node_ip + '/32'}]}
                ips_list.append(ips_each)

            print(ips_list)
            response = ec2_client.create_security_group(GroupName="KUBERNETES-JENKINS-JOBS-MYSQL",
                                                        Description='DESCRIPTION', VpcId=vpc_id)
            print(response)
            security_group_id = response['GroupId']
            print('Security Group Created %s in vpc %s.' % (security_group_id, vpc_id))

            data = ec2_client.authorize_security_group_ingress(
                GroupId=security_group_id,
                IpPermissions=ips_list)
            print('Ingress Successfully Set %s' % data)
        except ClientError as e:
            print(e)

        response = ec2_client.modify_instance_attribute(InstanceId='i-08e8b17d576030e4e',
                                                        Groups=['sg-6a5b710d', 'sg-e1b54c84', security_group_id])
        print(response)
        time.sleep(10)

        try:
            connection = mysql.connector.connect(host=config.get('host'), user=config.get('user'),
                                                 password=config.get('password'))
            if connection.is_connected():
                db_info = connection.get_server_info()
                print("Connected to MySQL Server version ", db_info)
                cursor = connection.cursor()
                cursor.execute("show slave status;")
                record = cursor.fetchone()
                print(record[0])
                if record[0] == "Waiting for master to send event":
                    print("Slave is running, need to stop")
                    cursor.execute("stop slave;")
                    record = cursor.fetchone()
                else:
                    print("Slave already stop")

        except Error as e:
            print(e)

        list_of_volids = []
        f_prod_bkp = {'Name': 'tag:data', 'Values': ['mysql']}
        paginator = ec2_client.get_paginator('describe_volumes')
        for each_page in paginator.paginate(Filters=[f_prod_bkp]):
            for each_vol in each_page['Volumes']:
                list_of_volids.append(each_vol['VolumeId'])

        print("The list of volids are:", list_of_volids)

        cursor.execute("show slave status;")
        record = cursor.fetchone()
        snapids = []
        if (record[10] == "Yes" and record[11] == "Yes"):
            raise CommandError('Slave not stopping')

        for each_volid in list_of_volids:
            print("Taking snap of {}".format(each_volid))
            res = ec2_client.create_snapshot(
                Description='Taking MySQL Slave Snapshot',
                VolumeId=each_volid,
                TagSpecifications=[
                    {
                        'ResourceType': 'snapshot',
                        'Tags': [
                            {
                                'Key': 'Delete-on',
                                'Value': '5'
                            }
                        ]
                    }
                ]
            )
            snapids.append(res.get('SnapshotId'))

        print("The snap ids are: ", snapids)

        waiterdelay = {'Delay': 15, 'MaxAttempts': 240}  # Attempt check eery 15 second, total 360 seconds 1 hours.
        waiter = ec2_client.get_waiter('snapshot_completed')
        waiter
        waiter.wait(SnapshotIds=snapids, WaiterConfig=waiterdelay)

        print("Successfully completed snaps for the volumes of {}", list_of_volids)
        registry.notify.send(room="monitor", message=f"SUCCESS: AWS-MYSQL-SLAVE snapshot completed. {list_of_volids}")

        try:
            connection = mysql.connector.connect(host=config.get('host'), user=config.get('user'),
                                                 password=config.get('password'))
            if connection.is_connected():
                db_info = connection.get_server_info()
                print("Connected to MySQL Server version ", db_info)
                cursor = connection.cursor()
                cursor.execute("start slave;")
                cursor.execute("show slave status;")
                record2 = cursor.fetchone()
                print(record2)
                if (record2[0] != "Waiting for master to send event"):
                    raise CommandError('Slave not starting.')
                print("Slave started & ", record2[0])
        except Error as e:
            print(e)

        filter = {'Name': 'tag:Delete-on', 'Values': ['5']}
        snapshots = ec2_client.describe_snapshots(Filters=[filter])
        for snapshot in snapshots['Snapshots']:
            a = snapshot['StartTime']
            b = a.date()
            c = datetime.datetime.now().date()
            d = c - b
            try:
                if d.days > 5:
                    print("Delete snapshot more than 5 days.")
                    id = snapshot['SnapshotId']
                    print(id)
                    ec2_client.delete_snapshot(SnapshotId=id)
            except Exception as e:
                print(e)

        print("# UNATTACH SG TO INSTANCE")
        try:
            response = ec2_client.modify_instance_attribute(InstanceId='i-08e8b17d576030e4e',
                                                            Groups=['sg-6a5b710d', 'sg-e1b54c84'])
            print(response)
            print("Unattached SG from instance successful")
        except ClientError as e:
            print(e)

        print("# DELETE SG %s" % security_group_id)
        try:
            response = ec2_client.delete_security_group(GroupId=security_group_id)
            print(response)
            print('Security Group Deleted')
        except ClientError as e:
            print(e)
