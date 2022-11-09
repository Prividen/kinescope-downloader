# kinescope-downloader
Script to download video from Kinescope

# How to use

Invocation:
```./kinescope-downloader.py <video-id> [video-name]```

`<video-id>` looks like '201234567' and can be obtain from browser network console (you can filter output for "master.mpd" file)

# How to install

This script requires:

* `ffmpeg` utility
* python3 module `xmltodict` ([PyPI](https://pypi.org/project/xmltodict/))

## Installation on ROSA Linux

This script is [packaged](https://abf.rosalinux.ru/import/kinescope-downloader) in ROSA, install it from the repository:

`sudo dnf install kinescope-downloader`

Then run it:

`kinescope-downloader <video-id> [video-name]`

## Install requirements on ALT Linux

`sudo apt-get install 'python3(xmltodict)'`

## Install requirements on Fedora, RHEL, CentOS and other RPM-based distros

`sudo dnf install python3 ffmpeg 'python3dist(xmltodict)'`

## Install requirements on Ubuntu/Debian

`sudo apt install python3 ffmpeg python3-xmltodict`
