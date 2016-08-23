from JumpScale import j
import operator

cache = j.core.db.scan(0, 'dns.cache.*', 10000)
print("Cache contains: %d entries" % len(cache[1]))
print()

hits = j.core.db.hgetall('dns.hits')
plain = {}

for key, value in hits.items():
    plain[key.decode('utf-8')] = int(value)

xhits = sorted(plain.items(), key=operator.itemgetter(1), reverse=True)
xlen = 20

if len(xhits) < xlen:
    xlen = len(xhits)

print("Hits statistics:")
for i in range(0, xlen):
    print(" %-4d - %s" % (xhits[i][1], xhits[i][0]))
