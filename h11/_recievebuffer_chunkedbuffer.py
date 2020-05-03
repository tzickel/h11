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
        self._looked_for = None
        self._looked_at = 0

    def __bool__(self):
        return bool(len(self))

    # for @property unprocessed_data
    def __bytes__(self):
        return bytes(self._buffer.peek())

    if sys.version_info[0] < 3:  # version specific: Python 2
        __str__ = __bytes__
        __nonzero__ = __bool__

    def __len__(self):
        return len(self._buffer)

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
        if needle == b'\r\n':
            return self._buffer.takeline(True)
        elif needle == b'\r\n\r\n':
            if self._looked_for == needle:
                search_start = max(0, self._looked_at - len(needle) + 1)
            else:
                search_start = 0
            offset = self._buffer.find(needle, search_start)
            if offset == -1:
                offset = self._buffer.find(b'\n\n', search_start)
                if offset == -1:
                    self._looked_at = len(self._buffer)
                    self._looked_for = needle
                    return None
                else:
                    return self._buffer.take(offset + 2)
            else:
                return self._buffer.take(offset + 4)
        else:
            return self._buffer.takeuntil(needle, True)

    # HTTP/1.1 has a number of constructs where you keep reading lines until
    # you see a blank one. This does that, and then returns the lines.
    def maybe_extract_lines(self):
        if self._buffer.peek(1) == b'\n':
            self._buffer.skip(1)
            return []
        elif self._buffer.peek(2) == b'\r\n':
            self._buffer.skip(2)
            return []
        else:
            data = self.maybe_extract_until_next(b"\r\n\r\n")
            if data is None:
                return None
            lines = data.splitlines()
            assert lines[-1] == b''
            del lines[-1:]
            return lines
