#!/usr/bin/python3

import os
import sys
import traceback

from core.icarapp import ICAR
from lib.io import setup as output_setup
from objects import registry, notify, profiler


def main():
    output_setup()
    registry.profiler = profiler.Profiler()
    registry.notify = notify.Notify(registry)
    app = ICAR()
    try:
        app.setup()
        app.run()
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        registry.notify.send('log', "%s %s %s %s" % (str(e), exc_type, fname, exc_tb.tb_lineno), "error", True)
        traceback.print_tb(e.__traceback__)
        exit(code=1)
        # app.close(code=1)
    finally:
        app.close()


if __name__ == '__main__':
    main()
