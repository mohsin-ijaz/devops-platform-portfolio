from cement.core.controller import CementBaseController, expose

from core.icarcommand import command
from objects import registry
from objects.formatter import Formatter


class ICarBaseController(CementBaseController):
    required = {}
    missing = ' '
    environments = ['preprod', 'staging', 'stag0', 'stag1', 'stag2', 'stag3', 'stag4', 'stag5', 'production', 'new-car', 'qa']
    countries = ['my', 'id', 'th']
    messages = {}
    scope = None

    """
    This is just an abstract base class to share commands with sub-commands.
    """

    class Meta:
        label = 'abstract'
        stacked_on = 'base'
        stacked_type = 'nested'
        arguments = []
        epilog = ''
        usage = 'icarcli {cmd} [options ...]'

    # for initialization of all sub commands
    def __init__(self, *args, **kw):
        super(ICarBaseController, self).__init__(*args, **kw)

    @command
    @expose(hide=True)
    def default(self):
        return True

    def _dispatch(self):
        registry.controller = self
        super(ICarBaseController, self)._dispatch()

    def get_command_message(self):
        """"Gets the command message that is customized for each sub command"""

        formatted_message = None

        message = registry.controller.messages.get(registry.subcommand)

        locals()['command'] = registry.command
        locals()['subcommand'] = registry.subcommand

        for arg, val in registry.app.pargs.__dict__.items():
            if arg != 'debug' and arg != 'suppress_output' and val is not None and val != [] and val is not False:
                locals()[arg] = val

        if message is not None:
            formatted_message = Formatter().format(message, locals())
        return formatted_message

    def get_formatted_arguements(self):

        params = []
        for arg, val in registry.app.pargs.__dict__.items():
            if arg != 'debug' and arg != 'suppress_output' and val is not None and val != [] and val is not False:
                params.append(arg.replace('-', ' ').replace('_', ' ') + ': ' + '`%s`' % str(val))
        info = ', '.join(params)
        return '' if info == '' else info

    def validate(self, command):
        if len(self.required) > 0 and self.required.get(command) is not None:
            for field in self.required.get(command):
                if self.app.pargs.__dict__.get(field) is None or self.app.pargs.__dict__.get(field) == []:
                    self.missing = str(field)
                    raise ValueError('Missing arguments %s' % self.missing)

    def auth_cluster(self):
        if self.app.pargs.auto_auth != 'false':
            registry.cloud_auth.login_cluster()
            registry.cloud_auth.login_docker()

    def update_secrets(self):
        registry.secret_manager.update_secrets()

    def is_valid_environment(self):
        if self.app.pargs.environment not in self.environments:
            raise ValueError('Wrong environment %s' % str(self.app.pargs.environment))

    def is_valid_country(self):
        if self.app.pargs.country not in self.countries:
            raise ValueError('Wrong country %s' % str(self.app.pargs.country))
