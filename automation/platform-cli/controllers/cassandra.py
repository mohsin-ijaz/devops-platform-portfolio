import os
import random
import re
import string
import subprocess
import time
import typer
from multiprocessing import Pool

from cassandra.cluster import Cluster, ExecutionProfile
from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from objects import registry
from objects.profiler import profile
from resources.messages import messages


class CassandraController(ICarBaseController):
    required = {'backup': ['name'], 'migrate': [], 'backup_nodes_v2': ['label'], 'restore_data': ['source'],
                'auditlog_stress_test': ['keyspace', 'table', 'numofrec', 'chost', 'cport'],
                'auditlog_count': ['keyspace', 'table', 'chost', 'cport'],
                }
    messages = {'default': 'Backup Cassandra'}
    scope = 'cluster'
    config = {'bucket': 'data-backup-19anrz7d490d8mmz'}

    class Meta:
        label = 'cassandra'
        description = messages['cluster.info']
        arguments = [
            (['-q', '--quite'], dict(help="Run the command without prompts")),
            (['-src', '--source'], dict(help="From what environment source was dumped")),
            (['-ks', '--keyspace'], dict(help="Cassandra keyspace name")),
            (['-t', '--table'], dict(help="Cassandra table name")),
            (['-nr', '--numofrec'], dict(help="Number of records")),
            (['-ch', '--chost'], dict(help="Cassandra host")),
            (['-cp', '--cport'], dict(help="Cassandra port")),
            (['-l', '--label'], dict(help="Cassandra pod label")),
        ]
        usage = 'icarcli cassandra <service_name> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='Backup data from Cassandra nodes, compress, and upload to GCS bucket')
    def backup_nodes(self):

        # get all cassandra pods with label app=cassandra
        get_command = 'kubectl get pods -l app=cassandra'
        s = subprocess.run(get_command, capture_output=True, shell=True)

        # regex pattern to get just pod names
        s_pat = r"(cassandra-\d)"

        # get pod names based on defined regex pattern
        pods = re.findall(s_pat, str(s.stdout))

        # backup keyspace schema
        backup_schema_command = 'kubectl exec cassandra-0 -c cassandra -- bash /etc/cassandra/schema_export.sh'
        os.system(backup_schema_command)
        echo(backup_schema_command, 'yellow')

        pool = Pool()
        pool.map(run_command, pods)
        pool.close()
        pool.terminate()
        pool.join()

    @command
    @expose(help='Backup data V2 from Cassandra nodes, compress, and upload to GCS bucket')
    def backup_nodes_v2(self):
        # COMMAND: icarcli cassandra backup-nodes-v2 --label=cassandra-ao -e preprod

        # get all cassandra pods with label app=cassandra
        pod_label = self.app.pargs.label
        get_command = 'kubectl get pods -l app=%s' % (pod_label)
        s = subprocess.run(get_command, capture_output=True, shell=True)
        stdo = s.stdout.decode('utf-8')
        stdo = stdo.splitlines()
        del stdo[0]
        sep = " "
        cassandra_pods = []
        pod_labels_list = []
        cassandra_pods_dict = {}

        for num in range(len(stdo)):
            cassandra_pods.append({'label': pod_label, 'name': stdo[num].split(sep, 1)[0]})

        print(cassandra_pods)

        # backup keyspace schema
        # backup_schema_command = 'kubectl exec %s -c cassandra -- bash /opt/backup/backup-script-preprod.sh' % cassandra_pods[0]
        # os.system(backup_schema_command)
        # echo(backup_schema_command, 'yellow')

        pool = Pool()
        pool.map(run_commandV2, cassandra_pods)
        pool.close()
        pool.terminate()
        pool.join()

    # --label cassandra-timeline
    @command
    @expose(help='Remove snapshots')
    def remove_snapshots(self):
        if self.app.pargs.label:
            label = self.app.pargs.label
        else:
            label = "cassandra"
        #get cassandra keyspaces data dir
        cmd_get_keyspace_dir = f"kubectl exec {label}-0 -c {label} -- ls /var/lib/cassandra/data/"
        print(cmd_get_keyspace_dir)
        p = subprocess.run(cmd_get_keyspace_dir, capture_output=True, shell=True)
        output = p.stdout.decode('utf-8')
        all_dirs = output.split("\n")
        dirs = []
        for ad in all_dirs:
            if "system" not in ad and "backup" not in ad and ad:
                dirs.append(ad)

        # get all cassandra pods with label app=cassandra
        get_command = f"kubectl get pods -l app={label}"
        print(get_command)
        s = subprocess.run(get_command, capture_output=True, shell=True)

        # regex pattern to get just pod names
        s_pat = rf"({label}-\d)"

        # get pod names based on defined regex pattern
        pods = re.findall(s_pat, str(s.stdout))
        if (typer.confirm(f"Are you sure you want to remove snapshots on all these pods {pods} on these keyspaces {dirs}")):
            for pod in pods:
                for dir in dirs:
                    command = f"kubectl exec {pod} -c {label} -- ls /var/lib/cassandra/data/{dir}"
                    # command = f"kubectl exec cassandra-0 -c cassandra -- ls /var/lib/cassandra/data/{dir}"
                    print("run_command: ", command)
                    p = subprocess.run(command, capture_output=True, shell=True)
                    output = p.stdout.decode('utf-8')
                    table_dirs = output.split("\n")
                    # print(table_dirs)
                    for t_dir in table_dirs:
                        if t_dir:
                            # delete all snapshots
                            command = f"kubectl exec {pod} -c {label} -- sh -c 'rm -r /var/lib/cassandra/data/{dir}/{t_dir}/snapshots/*'"
                            print("run_command: ", command)
                            subprocess.run(command, capture_output=True, shell=True)

    @command
    @expose(help='Stress test for auditlog')
    def auditlog_stress_test(self):
        registry.profiler.record("prestart", "auditlog_stress_test")
        profile_long = ExecutionProfile(request_timeout=30)
        # host = ".staging-cassandra.default.svc.cluster.local"
        # echo("%s-0%s" % (self.app.pargs.chost, host), "red")
        # ["%s-0%s" % (self.app.pargs.chost, host), "%s-1%s" % (self.app.pargs.chost, host),
        #  "%s-2%s" % (self.app.pargs.chost, host)]
        cluster = Cluster([self.app.pargs.chost], port=int(self.app.pargs.cport),
                          execution_profiles={'long': profile_long})
        session = cluster.connect(self.app.pargs.keyspace)

        registry.profiler.record("cassandra-connected", self.app.pargs.chost)

        statement = "INSERT INTO {} (source_name, source_id, service_name, id, modified_by, modified_on, new_value, old_value, source_event, source_field_name)" \
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)".format(self.app.pargs.table)

        for i in range(0, int(self.app.pargs.numofrec)):
            id = "Profile-crm-" + self.random_digits()
            seconds = time.time()
            statement_values = ["Profile", int(self.random_digits()), 'crm', id, 301, int(seconds),
                                '2016 Toyota Avanza 1.3 G', '2016 Toyota Avanza 1.3 GG', 'Create', 'Title']
            session.execute(statement, statement_values, execution_profile='long')
            echo(i, "blue")
            registry.profiler.record("cassandra-execute", id)

    @profile
    @command
    @expose(help='Row count for auditlog')
    def auditlog_count(self):
        profile_long = ExecutionProfile(request_timeout=30)
        cluster = Cluster([self.app.pargs.chost], port=int(self.app.pargs.cport),
                          execution_profiles={'long': profile_long})
        session = cluster.connect(self.app.pargs.keyspace)

        result = session.execute('select id from %s' % self.app.pargs.table)

        count = 0

        for i in result:
            count += 1

        echo("Total rows are %s" % count, "green")

    def random_string(self, string_length=10):
        """Generate a random string of fixed length """
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(string_length))

    def random_string_digits(self, string_length=6):
        """Generate a random string of letters and digits """
        letters_and_digits = string.ascii_letters + string.digits
        return ''.join(random.choice(letters_and_digits) for i in range(string_length))

    def random_digits(self, string_length=6):
        """Generate a random string of letters and digits """
        digits = string.digits
        return ''.join(random.choice(digits) for i in range(string_length))


def run_command(pod):
    command = "kubectl exec {} -c cassandra -- bash /etc/cassandra/keyspace_export.sh".format(pod)
    print("run_command", command)
    subprocess.Popen(command, shell=True)


def run_commandV2(cassandra_pods):
    # print(pod_labels_list)
    command = "kubectl exec {0} -c {1} -- bash /opt/backup/backup-script.sh".format(cassandra_pods['name'],
                                                                                    cassandra_pods['label'])
    print("run_command: ", command)
    subprocess.Popen(command, shell=True)

def run_remove_snapshot_cmd(pod):
    command = "kubectl exec {0} -- ls /var/lib/cassandra/data/".format(pod)
    print("run_command: ", command)
    stdout, stderr = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(stdout, stderr)
