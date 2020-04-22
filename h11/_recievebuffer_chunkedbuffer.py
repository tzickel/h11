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
        if self._buffer.peek(2) == b'\r\n':
            self._buffer.skip(2)
            return []
        else:
            data = self.maybe_extract_until_next(b"\r\n\r\n")
            if data is None:
                return None
            lines = data.split(b"\r\n")
            assert lines[-2] == lines[-1] == b""
            del lines[-2:]
            return lines
