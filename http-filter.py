from JumpScale import j
from mitmproxy.models import HTTPResponse
from mitmproxy.script import concurrent
from netlib.http import Headers

cache = j.core.db
requests = 0

filter_denied = [
    "youtube.com",
]

long_cache = [
    ".deb", ".gz"
]

force_cache = [
    "archive.ubuntu.com"
]

def _nocache(flow):
    # flow.response.stream = True
    flow.response.headers["X-GIG-Cache"] = "not-cached"

def _cached(flow):
    flow.response.headers["X-GIG-Cache"] = "put-in-cache"

def _cache(flow):
    hkey = 'http.cache.head.%s' % flow.request.pretty_url
    bkey = 'http.cache.body.%s' % flow.request.pretty_url

    ttl = 3600

    for lng in long_cache:
        if flow.request.pretty_url.endswith(lng):
            # Caching for 1 month for long cache extensions
            ttl = 86400 * 31

    cache.setex(bkey, flow.response.raw_content, ttl)
    cache.setex(hkey, bytes(flow.response.headers), ttl)

    return _cached(flow)

def _restore(flow, rawhead):
    # Building usable headers
    headers = Headers()

    lines = rawhead.decode('utf-8')[:-2].split("\r\n")
    for line in lines:
        temp = line.split(": ")
        headers[temp[0]] = temp[1]

    body = cache.get('http.cache.body.%s' % flow.request.pretty_url)

    if len(body) == 0:
        print("Cache hit but body empty, let's doing a real request")
        cache.delete('http.cache.body.%s' % flow.request.pretty_url)
        cache.delete('http.cache.head.%s' % flow.request.pretty_url)
        return

    # Building response from cache
    response = HTTPResponse(b"HTTP/1.1", 200, b"OK", headers, body)

    print(response)
    
    response.headers["X-GIG-Cache"] = "from-cache"

    # Send forged response
    flow.reply.send(response)

def _hit(flow):
    hkey = 'http.hits.%s' % flow.request.pretty_url
    host = flow.client_conn.address.host

    cache.hincrby(hkey, host)

#
# mitmproxy events
#
@concurrent
def request(flow):
    global requests
    requests += 1

    if requests % 500 == 0:
        print("Saving cache")
        j.core.db.save()

    # Log request
    _hit(flow)

    # Drop if host is not allowed
    if flow.request.pretty_host in filter_denied:
        flow.client_conn.finish()

    # Check for cache hit
    print("Checking cache: %s" % flow.request.pretty_url)
    hithead = cache.get('http.cache.head.%s' % flow.request.pretty_url)

    if hithead:
        # Restore the page from the cache
        print("Cache hit !")
        _restore(flow, hithead)

    else:
        print("Cache miss")


@concurrent
def response(flow):
    # Let keep track on the header of our filter
    flow.response.headers["X-GIG-Filter"] = "Filtered"

    # We only cache GET contents
    if flow.request.method != 'GET':
        return _nocache(flow)

    if flow.request.pretty_host in force_cache:
        print("Cache forced !")
        return _cache(flow)

    # Check for cache
    if 'Pragma' in flow.response.headers:
        pragma = flow.response.headers["Pragma"]

        # No cache for this entry
        if 'no-' in pragma:
            return _nocache(flow)

    if 'Cache-Control' in flow.response.headers:
        control = flow.response.headers["Cache-Control"]

        if 'no-' in control:
            return _nocache(flow)

    _cache(flow)

