# RMII decoder for PulseView/sigrok (libsigrokdecode)

## Overview

RMII is a protocol to communicate Ethernet packets between an Ethernet PHY and Ethernet MAC. This repository has the "decoder" for PulseView/sigrok that allows you to visualize the transmission as nibbles/octets rather than just the raw waveforms.

## Target Software

[PulseView](https://sigrok.org/wiki/PulseView) which uses their [libsigrokdecode](https://sigrok.org/wiki/Libsigrokdecode) library. Unfortunately there doesn't seem to be a way to add per-user decoders, so you have to install it manually to the global `decoders` directory.

## Installation

```
cd /usr/share/libsigrokdecode/decoders/
sudo mkdir rmii
sudo chmod a+rwx rmii
sudo git clone https://github.com/fdarling/libsigrokdecode-rmii-decoder.git rmii
```

## Usage

Add the "RMII" decoder as you would any other!

## External Resources

* [RMII on Wikipedia](https://en.wikipedia.org/wiki/Media-independent_interface#RMII)
* [RMII Specification Rev. 1.2](http://ebook.pldworld.com/_eBook/-Telecommunications,Networks-/TCPIP/RMII/rmii_rev12.pdf)