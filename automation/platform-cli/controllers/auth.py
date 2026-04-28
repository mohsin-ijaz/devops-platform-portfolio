from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from objects import registry
from resources.messages import messages, flag_message


class AuthController(ICarBaseController):
    required = {'default': []}

    class Meta:
        label = 'auth'
        description = messages['auth.info']
        arguments = [
            (['name'], dict(
                help=flag_message['auth.type_name'], nargs='?', default=[]))
        ]
        usage = 'icarcli auth <name> --environment <environment> [options ...]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):

        if self.app.pargs.name != []:
            try:
                registry.cloud_auth.set_zone()
                registry.cloud_auth.login_cluster()
                registry.cloud_auth.login_docker()
            except Exception as e:
                self.app.args.print_help()
                return False

        return True

    @command
    @expose(help="List the current credentials if the cli is using (not working yet)"
                 " \n    Usage: icarcli auth list")
    def list(self):
        echo("List the current account with which auth is done")
