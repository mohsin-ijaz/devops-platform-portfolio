import slackclient

from lib.io import echo


class Slack(object):
    levels = {"info": "purple", "warning": "yellow", "error": "red", "success": "green", "trace": "gray"}
    channels = {
        "cicd":             {"id": "<SLACK_CHANNEL_ID>"},
        "testing-and-qa":   {"id": "<SLACK_CHANNEL_ID>"},
        "production":       {"id": "<SLACK_CHANNEL_ID>"},
        "preprod":          {"id": "<SLACK_CHANNEL_ID>"},
        "staging":          {"id": "<SLACK_CHANNEL_ID>"},
        "log":              {"id": "<SLACK_CHANNEL_ID>"},
        "monitor":          {"id": "<SLACK_CHANNEL_ID>"},
        # TODO: add channel IDs for each service from your Slack workspace
    }
    access_token = "<SLACK_USER_OAUTH_TOKEN>"   # xoxp-... from Slack App config
    bot_token    = "<SLACK_BOT_OAUTH_TOKEN>"    # xoxb-... from Slack App config
    host = ""
    client = None

    def __init__(self):

        self.client = slackclient.SlackClient(self.bot_token)

    def send(self, channel, message, level='trace', notify=False, format='text', send_as_attachment=False):

        try:
            channel_info = self.channels.get(channel)
            if channel_info is not None:
                if not send_as_attachment:
                    self.client.api_call('chat.postMessage', channel=channel_info['id'], text=message)
                else:
                    attachment_color = {
                        "success": "good",
                        "error": "danger"
                    }
                    attachment = [
                        {
                            "fallback": message,
                            "color": attachment_color.get(level, "warning"),
                            "text": message
                        }
                    ]
                    self.client.api_call('chat.postMessage', channel=channel_info['id'], attachments=attachment)

        except:
            return

    def get_bot_channels(self):
        """List of all public channels and only those private channels the bot is part of"""

        bot_channels = {}

        try:
            # Get the list of public channels
            channel_list = self.client.api_call(
                "channels.list"
            )

            channels = channel_list.get('channels', [])
            if channel_list.get('ok') is True and len(channels) > 0:
                for channel in channels:
                    # echo(str(channel['id']) + '-->' + str(channel['name']), 'red')
                    bot_channels[channel['id']] = {'id': channel['id'], 'name': channel['name'], 'private': False}

            # Get the list of groups (private channels) the bot is part of
            group_list = self.client.api_call(
                "groups.list"
            )

            groups = group_list.get('groups', [])
            if group_list.get('ok') is True and len(groups) > 0:
                for group in groups:
                    # echo(str(group['id']) + '-->' + str(group['name']), 'red')
                    bot_channels[group['id']] = {'id': group['id'], 'name': group['name'], 'private': True}

        except:
            return bot_channels

        return bot_channels

    def send_message_all_channels(self):

        try:
            for channel_name, channel in self.channels.items():
                echo(channel_name)
                echo(channel.get('id'))
                self.client.api_call(
                    "chat.postMessage",
                    channel=str(channel.get('id')),
                    text="Hello from icarcli! :tada:"
                )

        except:
            return
