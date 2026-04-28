from cement.ext.ext_colorlog import ColorLogHandler


class ICarLog(ColorLogHandler):
    class Meta:
        label = 'icarlog'
        # colors = {
        #    'DEBUG':    'cyan',
        #    'INFO':     'green',
        #    'WARNING':  'yellow',
        #    'ERROR':    'red',
        #    'CRITICAL': 'red,bg_white',
        # }

    def debug(self, msg, namespace=None, **kw):
        super(ICarLog, self).debug(self, msg, namespace, **kw)

    def fatal(self, msg, namespace=None, **kw):
        super(ICarLog, self).fatal(self, msg, namespace, **kw)

    def error(self, msg, namespace=None, **kw):
        super(ICarLog, self).error(self, msg, namespace, **kw)

    def warn(self, msg, namespace=None, **kw):
        super(ICarLog, self).warn(self, msg, namespace, **kw)

    def info(self, msg, namespace=None, **kw):
        super(ICarLog, self).info(self, msg, namespace, **kw)
