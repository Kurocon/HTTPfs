#!/usr/bin/env python
import sys
import logging

import argparse
import requests
import six

from fuse import FUSE, Operations, FuseOSError, ENOENT
from parser import Directory, File


class HTTPfs(Operations):
    def __init__(self, root, verify_ssl=True):
        self.root = root
        self.log = logging.getLogger(__name__)
        self.readdir_cache = {}
        self.attr_cache = {}
        self.file_cache = {}
        self.session = requests.Session()
        if not verify_ssl:
            self.log.warn("Disabling SSL verification!")
            self.session.verify = False

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


if __name__ == '__main__':
    FORMAT = "%(created)f - %(thread)d (%(name)s) - [%(levelname)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=FORMAT)

    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("http_resource", help="Target web directory index")
    p.add_argument("mountpoint", help="Target directory")
    p.add_argument("--foreground", action="store_true", help="Do not fork into background")
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    p.add_argument("--nothreads", action="store_true", help="Disable fuse threads")
    p.add_argument("--no_ssl_verify", action="store_true", help="Disable SSL Verification")
    p.add_argument("--allow_other", action="store_true", help="Allow users other than the one running the command"
                                                              "to access the directory.")

    p.add_argument("-o", type=str, default="", help="Mount-style variant of the above options (e.g. -o debug,allow_other")

    args = vars(p.parse_args(sys.argv[1:]))

    fsroot = six.text_type(args.pop("http_resource").strip("/"))
    mountpoint = args.pop("mountpoint")

    fuse_kwargs = {
        'nothreads': True if args.pop("nothreads") else False,
        'foreground': True if args.pop("foreground") else False,
        'debug': True if args.pop("debug") else False,
        'allow_other': True if args.pop("allow_other") else False,
    }

    o_args_list = [x.strip() for x in args.pop("o").split(",")]
    o_args = {}
    for x in o_args_list:
        xs = [y.strip() for y in x.split("=")]
        if len(xs) > 1:
            fuse_kwargs[xs[0]] = xs[1:]
        else:
            fuse_kwargs[x] = True

    if fuse_kwargs['debug']:
        logging.basicConfig(level=logging.DEBUG, format=FORMAT)

    FUSE(HTTPfs(fsroot, verify_ssl=False if args.pop("no_ssl_verify") else True), mountpoint, **fuse_kwargs)
