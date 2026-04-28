import string


class Formatter(string.Formatter):
    def get_value(self, key, args, kwargs):
        try:
            args = args[0]
            return args[key]
        except:
            return "<missing>"
