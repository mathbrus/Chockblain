from network import tools
import selectors
import struct


class TransactionMessage:
    def __init__(self, selector, sock, addr):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self._recv_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.transaction_received = None

    def _read(self):
        """Internal function called by read() to manage the socket."""
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK), skipping it for now
            # select() will eventually call us again
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    def process_events(self, mask):
        """Entry point when the socket is ready for reading.
        For the full node, will both care about reading and writing."""
        if mask & selectors.EVENT_READ:
            self.read()
        # if mask & selectors.EVENT_WRITE:  # Currently not in use
        #     self.write()

    def read(self):
        """Manages the reading of the transaction through the socket, while maintaining the state. In addition,
        it interprets the different parts of the message."""
        self._read()

        if self._jsonheader_len is None:
            self.process_jsonheader_length()

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()

        if self.jsonheader:
            if self.transaction_received is None:
                self.process_transaction_message()

    def close(self):
        """Used for unregistering the selector, closing the socket and deleting
         reference to socket object for garbage collection"""

        print("closing connection to", self.addr)
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            print(
                f"error: selector.unregister() exception for",
                f"{self.addr}: {repr(e)}",
            )

        try:
            self.sock.close()
        except OSError as e:
            print(
                f"error: socket.close() exception for",
                f"{self.addr}: {repr(e)}",
            )
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def process_jsonheader_length(self):
        """Reads the 2 bytes containing the length of the header."""

        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:  # Check if we already have received enough data, or wait for more buffer.
            self._jsonheader_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_jsonheader(self):
        """Reads the json_header of the actual transaction message."""

        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen: # Check if we already have received enough data, or wait for more buffer.
            self.jsonheader = tools.json_decode(
                self._recv_buffer[:hdrlen], "utf-8"
            )
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for required_header in (
                "byteorder",
                "content-length"
            ):
                if required_header not in self.jsonheader:
                    raise ValueError(f'Missing required header "{required_header}".')

    def process_transaction_message(self):
        """Reads the transaction message."""

        content_len = self.jsonheader["content-length"]

        # Check if we already have received enough data, or wait for more buffer.
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]

        self.transaction_received = data
        print(
            f'received a transaction from',
            self.addr,
        )
        # We now have finished to read the transaction
        self.close()
