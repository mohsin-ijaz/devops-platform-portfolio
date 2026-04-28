import datetime
import os

import yaml

from lib.io import echo
from objects import mail, hipchat, slack, registry


class Notify(object):
    channels = {}
    command_label = ""
    command_title = ""
    command_title_label = ""
    arguments_string = ""
    notify_all = {"flush": "all", "compute": {"start": "all", "stop": "all"}, "pod": "all"}
    room_all = "cicd"
    registry = None
    levels = {"info": "blue", "warning": "yellow", "error": "red", "success": "green", "trace": None}
    counter = 0
    id = 0
    quite = False
    message_config = {}

    def __init__(self, registry):

        self.channels.update({'mail': mail.Mail()})
        self.channels.update({'hipchat': hipchat.HipChat()})
        self.channels.update({'slack': slack.Slack()})
        self.registry = registry
        self.id = datetime.datetime.now().strftime('%H%M%S')
        current_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
        with open("%s/config/message.yaml" % current_dir) as f:
            self.message_config = yaml.safe_load(f)

        if self.message_config['config']['id'] != 0:
            self.id = self.message_config['config']['id']

    def set_command_label(self, command_title, arguments_string=None):

        self.command_title = command_title
        self.arguments_string = arguments_string

        if self.message_config['config']['mode'] == 'batch':
            self.command_title = '%s %s' % (self.message_config['config']['name'], self.command_title)

        self.set_command_label_formatted()

    def set_command_label_formatted(self):

        self.command_label = self.command_title_label = "`%s` `%s` " % (self.id, self.command_title)

        if self.arguments_string is not None:
            self.command_label = "%s*_%s_* " % (self.command_title_label, self.arguments_string)

    def send(self, room, message, level='trace', notify=False, format='text', send_as_attachment=False):

        if self.is_disabled():
            return False

        color = self.levels.get(level)

        if 'now.' in message:
            self.counter = 0

        # Set message to send (follows a format)
        command_label = self.command_label if self.counter == 0 else self.command_title_label
        message = command_label + message

        # echo the notification
        echo(message, color)

        self.slack.send(room, message, level, notify, format, send_as_attachment=send_as_attachment)
        self.counter = self.counter + 1

        # If notification is set, means send to everyone and also email
        if notify is True and room != self.room_all:

            # Get the notify all room for QA and others (this is for specific commands)
            # command = registry.passed_command if registry.passed_command is not None else self.registry.command
            command = self.registry.command
            notify_all = self.notify_all.get(command)
            # If its supposed to be sent for this command, ONLY then send it there
            if notify_all is not None or registry.passed_command is not None:
                self.slack.send(self.room_all, message, level, notify, format, send_as_attachment=send_as_attachment)

    @property
    def slack(self):
        return self.channels['slack']

    @property
    def hipchat(self):
        return self.channels['hipchat']

    @property
    def mail(self):
        return self.channels['mail']

    def enable(self):
        self.quite = False

    def disable(self):
        self.quite = True

    def is_disabled(self):
        return self.quite
