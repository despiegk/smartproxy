#!/usr/bin/env jspython

from mitmproxy.main import *
import sys
from IPython import embed
print("DEBUG NOW ")
embed()
raise RuntimeError("stop debug here")
mitmdump(args=sys.argv)
