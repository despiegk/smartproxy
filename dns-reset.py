from JumpScale import j
import operator

cache = j.core.db.scan(0, 'dns.cache.*', 10000)
print("Clearing %d DNS cache entries" % len(cache[1]))

content = cache[1]

for key in content:
    j.core.db.delete(key.decode('utf-8'))

cache = j.core.db.scan(0, 'dns.cache.*', 10000)
print("Cleared, remaining in cache: %d entries" % len(cache[1]))
