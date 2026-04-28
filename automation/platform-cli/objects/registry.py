from .cloudauth import CloudAuth
from .notify import Notify
from .profiler import Profiler
from .secretmanager import SecretManager

# You can register anything here, so that can use anywhere else in the app
# Settings
current_dir = ' '
config_dir = ' '
dockers_dir = ' '
clouds_dir = ' '
kubectl_dir = ' '
kustomize_dir = ' '
docker_config_dir = ' '
key_dir = ' '
key = ' '
data_dir = ' '
is_git_module = False
incomplete_installation_warning = False
# Current Command
command = ' '
subcommand = None
passed_command = None
passed_subcommand = None
term = ' '
platform = ' '
# Objects
controller = {}  # This is the current controller been run
notify: Notify
app = {}  # This is the app instance
cloud_auth: CloudAuth
secret_manager: SecretManager
profiler: Profiler
