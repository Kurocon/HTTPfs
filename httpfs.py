#!/usr/bin/env python
import sys
import logging
import requests
import six

from logging.config import fileConfig

from fuse import FUSE, Operations, FuseOSError, ENOENT
from parser import Directory, File


class HTTPfs(Operations):
    def __init__(self, root):
        self.root = root
        self.log = logging.getLogger(__name__)
        self.readdir_cache = {}
        self.attr_cache = {}
        self.file_cache = {}
        self.session = requests.Session()

    def readdir(self, path, fh):
        path = path.strip("/")
        path = six.text_type(path)

        self.log.debug(u"[READDIR] Reading path {}".format(path))
        if path not in self.readdir_cache.keys():
            self.readdir_cache[path] = Directory(self.root, path, self.session).contents()

        return [x[0] for x in self.readdir_cache[path]]

    def read(self, path, length, offset, fh):
        path = path.strip("/")
        path = six.text_type(path)

        self.log.debug(u"[READ] Reading path {}, {} bytes from {}".format(path, length, offset))
        if path not in self.file_cache.keys():
            self.file_cache[path] = File(self.root, path, self, self.session)

        return self.file_cache[path].read(length, offset)

    def getattr(self, path, fh=None):
        path = path.strip("/")
        path = six.text_type(path)

        self.log.debug(u"[GETATTR] Path {}".format(path))
        if path not in self.attr_cache.keys():
            try:
                if path not in self.file_cache.keys():
                    self.file_cache[path] = File(self.root, path, self, self.session)
                self.attr_cache[path] = self.file_cache[path].attributes()
            except FuseOSError:
                self.attr_cache[path] = None
                raise FuseOSError(ENOENT)

        if self.attr_cache[path] is not None:
            return self.attr_cache[path]
        else:
            raise FuseOSError(ENOENT)

    # Disable unused operations:
    access = None
    flush = None
    getxattr = None
    listxattr = None
    open = None
    opendir = None
    release = None
    releasedir = None
    statfs = None


def main(mountpoint, root):
    root = root.strip("/")
    root = six.text_type(root)
    FUSE(HTTPfs(root), mountpoint, nothreads=True, foreground=True, max_read=10485760, max_write=10485760)


if __name__ == '__main__':
    fileConfig('logging.conf')
    main(sys.argv[2], sys.argv[1])
