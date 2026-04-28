import pprint

import colorama
import pyfiglet
import termcolor

pp = pprint.PrettyPrinter(width=120, compact=True)


def setup():
    colorama.init()


def echo(string, color=None, on_color=None, attrs=None, font=None):
    # for param string can add validations in the future
    # font: http://www.figlet.org/fontdb.cgi
    string = '\n\n%s' % pyfiglet.figlet_format(str(string), font=font) if font is not None else string
    termcolor.cprint(str(string), color, on_color, attrs)


def dump(obj):
    for attr in dir(obj):
        if hasattr(obj, attr):
            echo('obj.%s = %s' % (attr, getattr(obj, attr)), 'yellow')
    print('\n\n\n')


def pprint(message):
    pp.pprint(message)
