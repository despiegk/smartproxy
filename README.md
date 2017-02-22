# dnsmasq alternative
This is a set of tools aimed to replace dnsmasq and other stuff related to network.

This was made in El Gouna, using Ubuntu 16.04.

# Setup the Network

All you need is a bridge which will contains wireless card and ethernet card and enable the router feature.

First, install the tools: `apt-get install bridge-utils nftables`

Simply add a bridge to the network configuration (`/etc/network/interfaces`):
```
auto br0
iface br0 inet static
  address 192.168.86.254
  netmask 255.255.255.0
  bridge_ports eno1

```
# install zerotier

```
curl -s https://install.zerotier.com/ | bash
```

# Firewall rules

In the PoC used in El Gouna, the firewall was setup using nftables.
The ruleset can be found on the `nftables.conf` file.

This firewall rules makes transparent redirections and some basic filtering.
Apply it at the end to make the redirections works when all the proxies are set up.

- Copy the firewall rules file to the system one: `cp /opt/dnsmasq-alt/nftables.conf /etc/`
- Set the interface correctly: `sed -i s/eth1/WAN_INTERFACE/g /etc/nftables.conf` (adapt WAN_INTERFACE)
- Run the rules: `nft -f /etc/nftables.conf`

You can check if it's applied with: `nft list ruleset`

To flush all: ```nft flush ruleset```

Add this to `/etc/rc.local` to enable routing:
```
echo 1 > /proc/sys/net/ipv4/ip_forward
nft -f /etc/nftables.conf

zerotier-one -d
zerotier-cli join e5cd7a9e1ceb010b

```

Note: replace `eno1` with your local interface of course. 
- You can (need) *reboot* now to make sur all is applied.
- do not replace if you don't have a local LAN ethernet card

# install jumpscale

- see https://github.com/Jumpscale/jumpscale_core8/tree/8.2.0_ays_noHrd  (branch can be changed by now)

```
cd $TMPDIR
rm -f install.sh
export JSBRANCH="8.2.0_ays_noHrd"
curl -k https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/$JSBRANCH/install/install.sh?$RANDOM > install.sh
bash install.sh
```

# Get This Repo

Clone this repo on the router, then to make it easy, make a symlink to access it in a safe way
(to follow this README correctly):
```
mkdir -p /opt/code/github/jumpscale
cd /opt/code/github/jumpscale
git clone https://github.com/despiegk/smartproxy
ln -s /opt/code/github/jumpscale/smartproxy /opt/dnsmasq-alt
```

It's useful to run every daemons in a tmux session to be able to watch them easier.

# DNS

The DNS server/forwarder/filter is based on dnslib.

- Start the DNS server (in a tmux): `jspython /opt/dnsmasq-alt/dns-server.py`

For now, this dns-code is a dns-forwarder with cache (using `j.core.db`) and hit count.

You can get some statistics with `/opt/dnsmasq-alt/dns-stats.py` script.

# Wifi dongle

In El Gouna, we used a `rtl871x` based usb-dongle.
Like most of realtek dongle, some patch need to be applied.

The configuration of hostapd is stored in `wifi-special-dongle/hostapd.conf`
and there is a bash script used to install drivers, compile and patch hostapd to make it works.

You can run it: `cd /opt/dnsmasq-alt/wifi-special-dongle/ && bash -x setup.sh`

For information, dongle usb ID is `0bda:818b`.

to check that the interface is there do
```
lsusb
```

need to find '0bda:818b'

- Change the interface name in the configuration file: `/opt/dnsmasq-alt/wifi-special-dongle/hostapd.conf`
- to see the interface to 'ip a'


Run hostapd (in a tmux): `/opt/netpoc/hostapd-2.6/hostapd/hostapd /opt/dnsmasq-alt/wifi-special-dongle/hostapd.conf`

Note: you will need to change the wireless interface in the config file.
Note2: it's possible that the interface doesn't join the bridge itself, if it's the case
(`brctl show` will tell you if the interface is plugged in br0), add it manually: `brctl addif br0 INTERFACE`

# HTTP/HTTPS transparent proxy

Some http(s) filtering was made with [mitmproxy](https://github.com/mitmproxy/mitmproxy).

- Install mitm

```bash
set -ex
apt-get install python-pip python-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg8-dev zlib1g-dev
pip3 install cffi
pip3 install git+https://github.com/mitmproxy/mitmproxy.git
```

- Start the server (in a tmux): 
```
source /opt/jumpscale8/env.sh
mitmdump -T -d -p 8443 -s /opt/dnsmasq-alt/http-filter.py
```

alternatives
```
#stream files +1 MB
mitmdump -T -d -d -p 8443 -s /opt/dnsmasq-alt/http-filter.py --stream 1m

#no transparant mode (without -T)
cd /opt/dnsmasq-alt
python3 mitmproxy_start.py -d -d -p 8443 -s /opt/dnsmasq-alt/http-filter.py --stream 1m
```

`http-filter.py` is in this repository and is used to make some content filtering.
When the proxy is running, go to [mitm.it](http://mitm.it) special url and install the certitifcate.

You can get some statistics via the `/opt/dnsmasq-alt/http-stats.py` script.

# DHCP

For now, we still use the mainstream dhcp server. This gonna change. But for now...

- Install the dhcp server: `apt-get install isc-dhcp-server`
- Edit `/etc/dhcp/dhcpd.conf` and add this block at the end:
```
subnet 192.168.86.0 netmask 255.255.255.0 {
  range 192.168.86.100 192.168.86.200;
  option domain-name-servers 192.168.86.254;
  option subnet-mask 255.255.255.0;
  option routers 192.168.86.254;
  option broadcast-address 192.168.86.255;
  default-lease-time 600;
  max-lease-time 7200;
}
```

- Apply some fix on the config: 
```
set -ex
sed -i 's/^option domain-name/#option domain-name/g' /etc/dhcp/dhcpd.conf
#Set interface to startup options: 
sed -i 's/INTERFACES=""/INTERFACES="br0"/g' /etc/default/isc-dhcp-server
#Restart the server: 
/etc/init.d/isc-dhcp-server restart
```


