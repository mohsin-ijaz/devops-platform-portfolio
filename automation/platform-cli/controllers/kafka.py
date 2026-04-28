import subprocess
from subprocess import PIPE
import datetime

# Decorators for commands
from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from core.icarerrors import CommandError
# Library
from lib.io import echo


class KafkaController(ICarBaseController):
    required = {}
    messages = {'default': 'Manage Kafka {name} for {environment}'}
    scope = 'cluster'
    config = {}

    class Meta:
        label = 'kafka'
        description = 'Manage Kafka'
        usage: 'icarcli kafka [options]'
        epilog = 'ICar Kafka Epilog'
        arguments = [
            (['-cn', '--clustername'], dict(help="Kafka Cluster's name", nargs='?', default=[])),
        ]

    @command
    @expose(hide=True)
    def default(self):
        self.app.args.print_help()

    @command
    @expose(help='Get list of all kafka running')
    def list_topics(self):
        echo("List Kafka")
        get_command = "kubectl exec -it kafka-0 -- kafka-topics --list --zookeeper zk-kafka-svc:2181"
        get_command_call = subprocess.run(get_command, shell=True, stdout=PIPE, stderr=PIPE)

        if get_command_call.returncode != 0:
            echo(get_command_call.stderr.decode('utf-8'), 'red')
            raise CommandError('Unable to get topic list')

        echo(get_command_call.stdout.decode('utf-8'), 'green')

    @command
    @expose(help='Get connect configs for kafka topic')
    def connect_configs(self):
        echo("List Connect Configs in Kafka")

        get_command = "kubectl exec -it kafka-0 --container=k8skafka-kafka -- kafka-console-consumer " \
                      "--bootstrap-server kafka-svc:9093 --consumer-property group.id=icarcli-kafka " \
                      "--topic my_connect_configs --from-beginning"

        echo(get_command, 'yellow')
        get_command_call = subprocess.run(get_command, shell=True, stdout=PIPE, stderr=PIPE)

        if get_command_call.returncode != 0:
            echo(get_command_call.stderr.decode('utf-8'), 'red')
            raise CommandError('Unable to get connect configs for kafka topic')

        echo(get_command_call.stdout.decode('utf-8'), 'green')

    @command
    @expose(help='Get list of all consumers running')
    def list_consumer(self):
        get_command = "kubectl exec -it kafka-0 --container=k8skafka-kafka -- kafka-consumer-groups " \
                      "--bootstrap-server kafka-svc:9093 --execute --list"
        get_command_call = subprocess.run(get_command, shell=True, stdout=PIPE, stderr=PIPE)

        if get_command_call.returncode != 0:
            echo(get_command_call.stderr.decode('utf-8'), 'red')
            raise CommandError('Unable list of all consumers running')

        echo(get_command_call.stdout.decode('utf-8'), 'green')

    @command
    @expose(help='Describe icarcli consumer')
    def icarcli_consumer(self):
        get_command = "kubectl exec -it kafka-0 --container=k8skafka-kafka -- kafka-consumer-groups " \
                      "--bootstrap-server kafka-svc:9093 --group icarcli-kafka --describe --execute"
        get_command_call = subprocess.run(get_command, shell=True, stdout=PIPE, stderr=PIPE)

        if get_command_call.returncode != 0:
            echo(get_command_call.stderr.decode('utf-8'), 'red')
            raise CommandError('Unable to describe icarcli consumer')

        echo(get_command_call.stdout.decode('utf-8'), 'green')
    
    
    @command
    @expose(help='Backup _schema topic')
    # https://docs.confluent.io/platform/current/schema-registry/installation/deployment.html#backups-using-command-line-tools
    # create a kafka consumer subscribe to _schemas topic, write to schemas.log and copy to GCS
    def backup_schema(self):
        if self.app.pargs.clustername not in ('default', '<GCP_PROJECT>', 'timeline'):
            echo(f"Unknown clustername {self.app.pargs.clustername}", 'red')
            raise SystemExit

        if self.app.pargs.clustername in ('default', '<GCP_PROJECT>'):
            name = "kafka"
            bootstrap = "kafka-svc:9093"
        elif self.app.pargs.clustername == 'timeline':
            name = "kafka-timeline"
            bootstrap = "kafka-timeline-svc:9093"
        
        if self.app.pargs.environment == 'production':
            bucket_name = "datalake-94gxhsgz364j"
        else:
            bucket_name = "datalake-7erp4wuw27cd"

        current_datetime = datetime.datetime.now()
        fdate = current_datetime.strftime('%Y-%m-%d')
        fhour = current_datetime.strftime('%H:00:00')

        bucket = f"gs://{bucket_name}/kafka/_schemas/{self.app.pargs.environment}/{fdate}/{fhour}/"
        output = f"{name}_schemas_recovery.log"

        get_command = f"kubectl exec -it {name}-2 --container=k8skafka-{name} -- sh -c " \
                    f"'kafka-console-consumer --bootstrap-server {bootstrap} --topic _schemas " \
                    f"--from-beginning --property print.key=true --timeout-ms 30000 1> {output}'"

        echo("Exporting _schemas...", "yellow")
        echo(get_command, 'yellow')
        get_command_call = subprocess.run(get_command, shell=True, stdout=PIPE, stderr=PIPE)
        if get_command_call.returncode != 0:
            echo(get_command_call.stderr.decode('utf-8'), 'red')
            raise CommandError('Unable to consume _schemas topic')
        echo(get_command_call.stdout.decode('utf-8'), 'green')
        
        echo(f"Copying {output} from k8s ", "yellow")
        cp_command = f"kubectl cp --container=k8skafka-{name} {name}-2:/home/appuser/{output} {output}"
        echo(cp_command, 'yellow')
        get_cp_call = subprocess.run(cp_command, shell=True, stdout=PIPE, stderr=PIPE)
        if get_cp_call.returncode != 0:
            echo(get_cp_call.stderr.decode('utf-8'), 'red')
            raise CommandError(f"Unable to copy {output} from pod.")
        
        echo(f"Copying {output} to GCS ", "yellow")
        cp_command = f"gsutil cp {output} {bucket}"
        echo(cp_command, 'yellow')
        get_cp_call = subprocess.run(cp_command, shell=True, stdout=PIPE, stderr=PIPE)
        if get_cp_call.returncode != 0:
            echo(get_cp_call.stderr.decode('utf-8'), 'red')
            raise CommandError(f"Unable to copy {output} to {bucket}")
        echo(get_cp_call.stdout.decode('utf-8'), 'green')
        
        
        

