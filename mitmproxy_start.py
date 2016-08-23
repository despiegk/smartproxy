from __future__ import absolute_import, print_function, division

import os
import signal
import sys

from six.moves import _thread  # PY3: We only need _thread.error, which is an alias of RuntimeError in 3.3+

from mitmproxy import cmdline
from mitmproxy import exceptions
from mitmproxy.proxy import config
from mitmproxy.proxy import server
from netlib import version_check
from netlib import debug

from mitmproxy import dump

def mitmdump():
    version_check.check_pyopenssl_version()

    parser = cmdline.mitmdump()
    args = parser.parse_args(None)

    dump_options = dump.Options(**cmdline.get_common_options(args))

    dump_options.listen_port = 8443
    dump_options.mode = 'transparent'
    # dump_options.mode = 'regular'
    dump_options.scripts = ['/opt/dnsmasq-alt/http-filter.py']
    dump_options.verbosity = 2
    dump_options.stream_large_bodies = 1048576

    debug.register_info_dumpers()
    pconf = config.ProxyConfig(dump_options)
    srv = server.DummyServer(pconf)

    print("Starting mitmdump")
    master = dump.DumpMaster(srv, dump_options)

    def cleankill(*args, **kwargs):
        master.shutdown()

    signal.signal(signal.SIGTERM, cleankill)
    master.run()

if __name__ == '__main__':
    mitmdump()
