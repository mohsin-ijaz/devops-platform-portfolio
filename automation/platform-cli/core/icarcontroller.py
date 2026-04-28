import textwrap

from cement.core import controller

from __init__ import __version__
from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from resources.messages import messages, flag_message


class ICarController(ICarBaseController):
    """
    This is the application base controller.
    It handles icarcli when no sub-commands are given
    """

    class Meta:
        label = 'base'
        description = messages['base.info']
        # usage = icar {cmd} --option
        arguments = [
            (['--version'], dict(action='store_true',
                                 help=flag_message['base.version'])),
        ]
        epilog = messages['base.epilog']

    @command
    @controller.expose(hide=True)
    def default(self):
        # Print help if nothing is passed
        if self.app.pargs.version:
            print(messages['app.version_message'], __version__)
        else:
            self.app.args.print_help()

    #  '(Python', sys.version[0:5] + ')'

    @property
    def _help_text(self):
        """Returns the help text displayed when '--help' is passed."""
        longest = 0

        def pad(label):
            padlength = longest - len(label)
            padding = '   '
            for x in range(0, padlength):
                padding += ' '
            return padding

        cmd_txt = ''
        for label in self._visible_commands:
            # get longest command
            if len(label) > longest:
                longest = len(label)

        for label in self._visible_commands:
            cmd = self._dispatch_map[label]
            if len(cmd['aliases']) > 0 and cmd['aliases_only']:
                if len(cmd['aliases']) > 1:
                    first = cmd['aliases'].pop(0)
                    cmd_txt = cmd_txt + " %s (aliases: %s)\n" % \
                              (first, ', '.join(cmd['aliases']))
                else:
                    cmd_txt = cmd_txt + " %s\n" % cmd['aliases'][0]
            elif len(cmd['aliases']) > 0:
                cmd_txt = cmd_txt + " %s (aliases: %s)\n" % \
                          (label, ', '.join(cmd['aliases']))
            else:
                cmd_txt = cmd_txt + "   %s" % label

            if cmd['help']:
                cmd_txt = cmd_txt + pad(label) + "%s\n" % cmd['help']
            else:
                cmd_txt = cmd_txt + "\n"

        if len(cmd_txt) > 0:
            txt = '''%s
        
commands:
%s
        
        
        ''' % (self._meta.description, cmd_txt)
        else:
            txt = self._meta.description

        return textwrap.dedent(txt)
