import logging
from errno import ENOENT
from stat import S_IFDIR, S_IFREG
from string import strip

from datetime import datetime
import time

import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from fuse import FuseOSError, EIO


class Directory:
    def __init__(self, root, path, session):
        self.root = root
        self.path = path
        self.session = session
        self.log = logging.getLogger("Directory")
        self.log.debug("[INIT] Loading directory {}/{}".format(root, path))

    def contents(self):
        """
        Give the contents of the directory
        :return: List of Entities that are in the directory
        :rtype: list
        """
        contents = [(".", True), ("..", True)]

        # Do a request, and run it through an HTML parser.
        response = self.session.get("{}/{}/".format(self.root, self.path))
        parsed = BeautifulSoup(response.text, 'html.parser')

        # Find all of the entity elements, remove the cruft
        for x in parsed.find_all("tr"):
            if x.td is not None and x.td.img['alt'] != "[PARENTDIR]":
                is_dir = x.td.img['alt'] == "[DIR]"
                contents.append((strip(x.find_all('td')[1].a.string, "/"), is_dir))

        return contents


class File:
    def __init__(self, root, path, httpfs, session):
        self.root = root
        self.path = path
        self.session = session
        self.log = logging.getLogger("File")
        self.log.debug("[INIT] Loading file {}/{}".format(root, path))
        self.readbuffer = defaultdict(lambda: None)

        # Determine if this is a directory
        parent_dir = "/".join(self.path.split("/")[:-1])
        filename = self.path.split("/")[-1]
        if parent_dir not in httpfs.readdir_cache.keys():
            httpfs.readdir_cache[parent_dir] = Directory(self.root, parent_dir, self.session).contents()

        dirs = [x[0] for x in httpfs.readdir_cache[parent_dir] if x[1]]
        self.is_dir = (filename in dirs) or filename == ""

        # Determine file size
        self.url = "{}/{}{}".format(self.root, self.path, "/" if self.is_dir else "")
        self.r = self.session.head(self.url, allow_redirects=True)
        if self.r.status_code == 200:
            try:
                self.size = int(self.r.headers['Content-Length'])
            except KeyError:
                self.size = 0

            try:
                mtime_string = self.r.headers["Last-Modified"]
                self.mtime = time.mktime(datetime.strptime(mtime_string, "%a, %d %b %Y %H:%M:%S %Z").timetuple())
            except KeyError:
                self.mtime = time.time()
        else:
            self.log.info("[INIT] Non-200 code while getting {}: {}".format(self.url, self.r.status_code))
            self.size = 0

    def read(self, length, offset):
        """
        Reads the file.
        :param length: The length to read
        :param offset: The offset to start at
        :return: The file's bytes
        """
        self.log.debug("[READ] Reading file {}/{}".format(self.root, self.path))
        url = "{}/{}".format(self.root, self.path)

        # Calculate megabyte-section this offset/length is in
        mb_start = (offset // 1024) // 1024
        mb_end = ((offset + length) // 1024) // 1024
        offset_from_mb = (((offset // 1024) % 1024) * 1024) + (offset % 1024)
        self.log.debug("Calculated MB_Start {} MB_End {} Offset from MB: {}".format(mb_start, mb_end, offset_from_mb))
        if mb_start == mb_end:
            self.log.debug("Readbuffer filled for mb_start? {}".format(self.readbuffer[mb_start] is not None))
            if self.readbuffer[mb_start] is None:
                # Fill buffer for this MB
                bytesRange = '{}-{}'.format(mb_start * 1024 * 1024, (mb_start * 1024 * 1024) + (1023 * 1024))
                self.log.debug("Fetching byte range {}".format(bytesRange))
                headers = {'range': 'bytes=' + bytesRange}
                r = self.session.get(url, headers=headers)
                if r.status_code == 200 or r.status_code == 206:
                    self.readbuffer[mb_start] = r.content
                    # noinspection PyTypeChecker
                    self.log.debug("Read {} bytes.".format(len(self.readbuffer[mb_start])))
                else:
                    self.log.info("[INIT] Non-200 code while getting {}: {}".format(url, r.status_code))
                    raise FuseOSError(EIO)

            self.log.debug("Returning indices {} to {}".format(offset_from_mb, offset_from_mb+length))
            return self.readbuffer[mb_start][offset_from_mb:offset_from_mb+length]
        else:
            self.log.debug("Offset/Length spanning multiple MB's. Fetching normally")
            # Spanning multiple MB's, just get it normally
            # Set range
            bytesRange = '{}-{}'.format(offset, min(self.size, offset + length - 1))
            self.log.debug("Fetching byte range {}".format(bytesRange))
            headers = {'range': 'bytes=' + bytesRange}
            r = self.session.get(url, headers=headers)
            if self.r.status_code == 200 or r.status_code == 206:
                return r.content
            else:
                self.log.info("[INIT] Non-200 code while getting {}: {}".format(url, r.status_code))
                raise FuseOSError(EIO)

    def attributes(self):
        self.log.debug("[ATTR] Attributes of file {}/{}".format(self.root, self.path))

        if self.r.status_code != 200:
            raise FuseOSError(ENOENT)

        mode = (S_IFDIR | 0o777) if self.is_dir else (S_IFREG | 0o666)

        attrs = {
            'st_atime': self.mtime,
            'st_mode': mode,
            'st_mtime': self.mtime,
            'st_size': self.size,
        }

        if self.is_dir:
            attrs['st_nlink'] = 2

        return attrs


if __name__ == "__main__":

    class DummyHTTPfs:
        def __init__(self, root):
            self.root = root
            self.log = logging.getLogger(__name__)
            self.readdir_cache = {}
            self.attr_cache = {}
            self.file_cache = {}

    # Test file read
    troot = "http://spitfire.kurocon.nl/files"
    tpath = "Anime New/%5bHorribleSubs%5d%20Brave%20Witches%20-%2001%20%5b1080p%5d.mkv"
    f = File(troot, tpath, DummyHTTPfs(troot), requests)
    print("Readbuffer:")
    print(f.readbuffer)
    print("Reading 128K:")
    print(f.read(128, 0))
    print("Readbuffer:")
    print(f.readbuffer)
    print("Reading 128K:")
    print(f.read(128, 128))
    print("Readbuffer:")
    print(f.readbuffer)
