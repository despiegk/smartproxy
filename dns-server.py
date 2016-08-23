# from JumpScale import j

"""
InterceptResolver - proxy requests to upstream server
                    (optionally intercepting)

"""

# import binascii
import copy
import socket
# import struct
import sys

from dnslib import DNSRecord, RR, QTYPE, RCODE, parse_time
from dnslib.server import DNSServer, DNSHandler, BaseResolver, DNSLogger
# from dnslib.label import DNSLabel

from JumpScale import j


class OurDNSLogger(DNSLogger):

    """
            log_recv          - Raw packet received
            log_send          - Raw packet sent
            log_request       - DNS Request
            log_reply         - DNS Response
            log_truncated     - Truncated
            log_error         - Decoding error
            log_data          - Dump full request/response
    """

    def log_pass(self, *args):
        pass

    def log_prefix(self, handler):
        if self.prefix:
            return "%s [%s:%s] " % (time.strftime("%Y-%m-%d %X"),
                                    handler.__class__.__name__,
                                    handler.server.resolver.__class__.__name__)
        else:
            return ""

    def log_recv(self, handler, data):
        print("%sReceived: [%s:%d] (%s) <%d> : %s" % (
            self.log_prefix(handler),
            handler.client_address[0],
            handler.client_address[1],
            handler.protocol,
            len(data),
            binascii.hexlify(data)))

    def log_send(self, handler, data):
        print("%sSent: [%s:%d] (%s) <%d> : %s" % (
            self.log_prefix(handler),
            handler.client_address[0],
            handler.client_address[1],
            handler.protocol,
            len(data),
            binascii.hexlify(data)))

    def log_request(self, handler, request):
        print("%sRequest: [%s:%d] (%s) / '%s' (%s)" % (
            self.log_prefix(handler),
            handler.client_address[0],
            handler.client_address[1],
            handler.protocol,
            request.q.qname,
            QTYPE[request.q.qtype]))
        self.log_data(request)

    def log_reply(self, handler, reply):
        if reply.header.rcode == RCODE.NOERROR:
            print("%sReply: [%s:%d] (%s) / '%s' (%s) / RRs: %s" % (
                self.log_prefix(handler),
                handler.client_address[0],
                handler.client_address[1],
                handler.protocol,
                reply.q.qname,
                QTYPE[reply.q.qtype],
                ",".join([QTYPE[a.rtype] for a in reply.rr])))
        else:
            print("%sReply: [%s:%d] (%s) / '%s' (%s) / %s" % (
                self.log_prefix(handler),
                handler.client_address[0],
                handler.client_address[1],
                handler.protocol,
                reply.q.qname,
                QTYPE[reply.q.qtype],
                RCODE[reply.header.rcode]))
        self.log_data(reply)

    def log_truncated(self, handler, reply):
        print("%sTruncated Reply: [%s:%d] (%s) / '%s' (%s) / RRs: %s" % (
            self.log_prefix(handler),
            handler.client_address[0],
            handler.client_address[1],
            handler.protocol,
            reply.q.qname,
            QTYPE[reply.q.qtype],
            ",".join([QTYPE[a.rtype] for a in reply.rr])))
        self.log_data(reply)

    def log_error(self, handler, e):
        print("%sInvalid Request: [%s:%d] (%s) :: %s" % (
            self.log_prefix(handler),
            handler.client_address[0],
            handler.client_address[1],
            handler.protocol,
            e))

    def log_data(self, dnsobj):
        print("\n", dnsobj.toZone("    "), "\n", sep="")


class InterceptResolver(BaseResolver):
    """
        Intercepting resolver

        Proxy requests to upstream server optionally intercepting requests
        matching local records
    """

    def __init__(self, address, port, ttl, intercept, skip, nxdomain, timeout=0):
        """
            address/port    - upstream server
            ttl             - default ttl for intercept records
            intercept       - list of wildcard RRs to respond to (zone format)
            skip            - list of wildcard labels to skip
            nxdomain        - list of wildcard labels to retudn NXDOMAIN
            timeout         - timeout for upstream server
        """
        self.address = address
        self.port = port
        self.ttl = parse_time(ttl)
        self.skip = skip
        self.nxdomain = nxdomain
        self.timeout = timeout
        self.zone = []

        for i in intercept:
            if i == '-':
                i = sys.stdin.read()

            for rr in RR.fromZone(i, ttl=self.ttl):
                self.zone.append((rr.rname, QTYPE[rr.rtype], rr))

    def resolve(self, request, handler):
        reply = request.reply()
        qname = request.q.qname
        qtype = QTYPE[request.q.qtype]
        domain = str(qname)

        for item in self.ignore:
            if domain.find(item) != -1:
                print("%s: ignored" % domain)
                return reply

        # Try to resolve locally unless on skip list
        if not any([qname.matchGlob(s) for s in self.skip]):
            for name, rtype, rr in self.zone:
                if qname.matchGlob(name) and (qtype in (rtype, 'ANY', 'CNAME')):
                    a = copy.copy(rr)
                    a.rname = qname
                    reply.add_answer(a)

        # Check for NXDOMAIN
        if any([qname.matchGlob(s) for s in self.nxdomain]):
            reply.header.rcode = getattr(RCODE, 'NXDOMAIN')
            return reply

        # Check local cache
        cache = j.core.db.get("dns.cache.%s" % domain)
        if cache != None:
            print("cache hit: %s" % domain)
            reply.rr = RR.fromZone(cache)
            self.hit(domain)
            # print(".")
            return reply

        # print("proxy")
        # Otherwise proxy
        if not reply.rr:
            try:
                if handler.protocol == 'udp':
                    proxy_r = request.send(self.address, self.port, timeout=self.timeout)
                else:
                    proxy_r = request.send(self.address, self.port, tcp=True, timeout=self.timeout)
                reply = DNSRecord.parse(proxy_r)

            except socket.timeout:
                reply.header.rcode = getattr(RCODE, 'NXDOMAIN')

        zone = reply.toZone()

        # Caching only if the domain was resolved correctly
        if len(reply.rr) > 0:
            print("remember in cache:%s" % domain)
            j.core.db.setex("dns.cache.%s" % domain, zone, 3600)

        self.hit(domain)

        return reply

    def hit(self, domain):
        current = j.core.db.hget('dns.hits', domain)

        if not current:
            current = 0

        j.core.db.hset('dns.hits', domain, int(current) + 1)

    def reset(self):
        """
        j.core.db.delete("dns.cache")

        for item in j.core.db.keys("dns.names*"):
            j.core.db.delete(item)

        j.sal.fs.remove(self.logfile)
        """
        return


if __name__ == '__main__':
    import sys
    import time

    resolver = InterceptResolver(
        "8.8.8.8",
        53,
        "60s",
        intercept=[],
        skip=[],
        nxdomain=[],
        timeout=5.0
    )

    resolver.ignore = []
    resolver.ignore.append("microsoft.com")
    resolver.ignore.append("apple.com")
    resolver.ignore.append("dropbox.com")
    resolver.ignore.append("office365")
    resolver.ignore.append("live.com")
    resolver.ignore.append("update")
    resolver.ignore.append("download")
    resolver.ignore.append("qobuz")
    resolver.ignore.append("deezer.com")
    resolver.ignore.append("youtube")
    resolver.ignore.append("porn")
    resolver.ignore.append("icloud")
    resolver.ignore.append("bing.net")
    resolver.ignore.append("doubleclick.net")
    resolver.ignore.append("nr-data.net")
    resolver.ignore.append("markmonitor")
    resolver.ignore.append("gvt2.com")
    resolver.ignore.append("plus.google.com")
    resolver.ignore.append("windows.com")
    resolver.ignore.append("microsoft")
    resolver.ignore.append("rubiconproject")
    resolver.ignore.append("bing.com")
    resolver.ignore.append("marketo.net")
    resolver.ignore.append("msn.com")
    resolver.ignore.append("office.net")
    resolver.ignore.append("live.net")
    resolver.ignore.append("gvt1.com")
    resolver.ignore.append("vtmkzoom.be")
    resolver.ignore.append("stievie.be")
    resolver.ignore.append("medialaan.io")
    resolver.ignore.append("skype")
    resolver.ignore.append("acer.com")
    resolver.ignore.append("asus.com")
    resolver.ignore.append("asustek")

    resolver.reset()

    logger = DNSLogger("-recv,-send,-request,-reply,+error,+truncated,-data", False)

    udp_server = DNSServer(resolver, port=53, address="", logger=logger, debug=True)

    print("Starting DNS forwarding")

    # udp_server.start_thread()
    udp_server.start()
