#!/bin/bash
set -x

add-apt-repository ppa:hanipouspilot/rtlwifi
apt-get update
apt-get install -y rtl8192eu-dkms

mkdir /opt/netpoc
cd /opt/netpoc

wget -c http://w1.fi/releases/hostapd-2.5.tar.gz
rm -rfv hostapd-2.5/
tar -xvf hostapd-2.5.tar.gz

apt-get install -y libnl-3-dev libnl-genl-3-dev pkg-config libssl-dev
git clone --depth=1 https://github.com/pritambaral/hostapd-rtl871xdrv.git

cd /opt/netpoc/hostapd-2.5/hostapd
cp defconfig .config

sed -i s/'#CONFIG_LIBNL32=y'/'CONFIG_LIBNL32=y'/g .config
make # compile first to be sur it works without patch

cd ..
patch -Np1 -i ../hostapd-rtl871xdrv/rtlxdrv.patch
cd hostapd

echo CONFIG_DRIVER_RTW=y >> .config
make clean && make

