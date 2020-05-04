import sys

from chunkedbuffer import Buffer

__all__ = ["ReceiveBuffer"]


# Operations we want to support:
# - find next \r\n or \r\n\r\n, or wait until there is one
# - read at-most-N bytes
# Goals:
# - on average, do this fast
# - worst case, do this in O(n) where n is the number of bytes processed
# Plan:
# - store bytearray, offset, how far we've searched for a separator token
# - use the how-far-we've-searched data to avoid rescanning
# - while doing a stream of uninterrupted processing, advance offset instead
#   of constantly copying
# WARNING:
# - I haven't benchmarked or profiled any of this yet.


class ReceiveBuffer(object):
    def __init__(self):
        self._buffer = Buffer()
        self._lines = []
        self._lines_len = 0

    def __bool__(self):
        if self._lines_len != 0:
            return True
        else:
            return bool(len(self))

    # for @property unprocessed_data
    def __bytes__(self):
        return bytes(self._buffer.peek())

    if sys.version_info[0] < 3:  # version specific: Python 2
        __str__ = __bytes__
        __nonzero__ = __bool__

    def __len__(self):
        return len(self._buffer) + self._lines_len

    def compress(self):
        pass

    def __iadd__(self, byteslike):
        self._buffer.extend(byteslike)
        return self

    def get_chunk(self, sizehint=-1):
        return self._buffer.get_chunk()
    
    def chunk_written(self, nbytes):
        self._buffer.chunk_written(nbytes)

    # TODO ChunkedReader uses this function to skip some data _bytes_to_discard). For backward compatability with _receivebuffer I haven't changed this yet, but we have a skip() method in self._buffer we can use instead
    def maybe_extract_at_most(self, count):
        out = self._buffer.take(count)
        if not out:
            return None
        return out

    def maybe_extract_until_next(self, needle):
        # Returns extracted bytes on success (advancing offset), or None on
        # failure
        return self._buffer.takeuntil(needle, True)

    # HTTP/1.1 has a number of constructs where you keep reading lines until
    # you see a blank one. This does that, and then returns the lines.
    def maybe_extract_lines(self):
        while True:
            line = self._buffer.takeline()
            if line is None:
                return None
            if not self._lines and not line:
                return []
            if not line:
                tmp = self._lines
                self._lines_len = 0
                self._lines = []
                return tmp
            else:
                self._lines_len += len(line)
                self._lines.append(line)
