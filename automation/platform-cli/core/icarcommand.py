from functools import wraps

from objects import registry


def command(f):
    """"Decorator for any subcommand to run must be called or weird things may happen"""

    @wraps(f)
    def wrapper(*args, **kwds):
        """"Wrapper for the command functions"""

        # Set actual command and subcommand labels
        registry.command = registry.controller.Meta.label
        registry.subcommand = f.__name__

        # Pre Command call
        pre_command()

        # Run the actual command
        return_data = f(*args, **kwds)

        # Run post command
        post_command()

        # Return any data from command
        return return_data

    return wrapper


def pre_command():
    """To run before any command or sub-command is run"""

    command_message = registry.controller.get_command_message()

    if registry.controller.Meta.label.title() == "Message":
        registry.notify.disable()

    if command_message is not None:
        registry.notify.set_command_label(command_message)
    else:
        registry.notify.set_command_label(registry.controller.Meta.label.title(),
                                          registry.controller.get_formatted_arguements())

    registry.notify.send('log', "*is starting now.*", "info", True)

    registry.controller.is_valid_environment()

    registry.controller.validate(registry.subcommand)

    if registry.controller.scope == "cluster":
        registry.controller.auth_cluster()


def post_command():
    """To run after any command or sub-command is run"""

    registry.notify.send('log', "*has completed now.*", "info", True)
