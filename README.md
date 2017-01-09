HTTPFS
===

HTTPFS is a fuse filesystem capable of mounting a typical Apache directory index as a local read-only filesystem.

Requirements
---
Python dependencies (works on both Python 2 and 3):
- requests
- fusepy
- beautifulsoup4
- six

Usage
---
```
usage: httpfs.py [-h] [--foreground] [--debug] [--nothreads] [--no_ssl_verify]
                 http_resource mountpoint

positional arguments:
  http_resource    Target web directory index
  mountpoint       Target directory

optional arguments:
  -h, --help       show this help message and exit
  --foreground     Do not fork into background (default: False)
  --debug          Enable debug logging (default: False)
  --nothreads      Disable fuse threads (default: False)
  --no_ssl_verify  Disable SSL Verification (default: False)
```

Registering mount command
---
You can register this filesystem (so it can be used in fstab or with the mount command) in the following way:
```bash
# Clone the repository
git clone https://github.com/Kurocon/HTTPfs.git

# Change into directory 
cd HTTPfs

# Make a symbolic link to /usr/sbin/
sudo ln -s `pwd`/httpfs.py /usr/sbin/mount.httpfs
```

You should now be able to use the filesystem in the following ways:
```
# In /etc/fstab
http://some.server/    /mnt/mountpoint    httpfs.py    none    0    0

# In a normal mount command
sudo mount.httpfs http://some.server/ /mnt/mountpoint
```
