from JumpScale import j
import operator

print("Collecting stats...")

full = {}

hits = j.core.db.scan(0, 'http.hits.*', 10000)[1]
for hit in hits:
    url = hit.decode('utf-8')[10:]
    temp = j.core.db.hgetall(hit)
    full[url] = 0

    for k, v in temp.items():
        full[url] += int(v)

# Sorting table
xhits = sorted(full.items(), key=operator.itemgetter(1), reverse=True)
xlen = 20

if len(xhits) < xlen:
    xlen = len(xhits)

print("Web traffic usage:")
for i in range(0, xlen):
    print(" %-4d - %s" % (xhits[i][1], xhits[i][0]))

