from network import tools
import sys
import selectors
import struct


class TransactionMessage:
    def __init__(self, selector, sock, addr, transaction):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.transaction = transaction
        self._send_buffer = b""
        self._transaction_queued = False

    def _write(self):
        """Internal function called by write() to manage the socket."""
        if self._send_buffer:
            print("sending", repr(self._send_buffer), "to", self.addr)
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK), skipping it for now
                # select() will eventually call us again
                pass
            else:  # If no errors were raised
                self._send_buffer = self._send_buffer[sent:]

    @staticmethod
    def _create_transaction_message(content_bytes):
        """Returns the 3-parts transaction message, given the transaction, consistent with out application-layer
        protocol that we have defined for broadcasting transaction messages to a full node."""

        jsonheader = {
            "byteorder": sys.byteorder,  # For the endianness of the OS
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = tools.json_encode(jsonheader, "utf-8")
        transaction_message_hdr = struct.pack(">H", len(jsonheader_bytes))
        transaction_message = transaction_message_hdr + jsonheader_bytes + content_bytes
        return transaction_message

    def process_events(self, mask):
        """Entry point when the socket is ready for writing (should normally always be the case).
        For the light node, it only cares about write-events."""
        if mask & selectors.EVENT_WRITE:
            self.write()

    def write(self):
        """Manages the writing of the transaction through the socket, while maintaining the state."""
        if not self._transaction_queued:  # We have not yet init the sending process. Ensures that we init only once.
            self._queue_transaction()  # Initializes the sending process.

        self._write()

        if self._transaction_queued:
            if not self._send_buffer:  # We started AND finished the sending.
                # We are done sending the transaction, we can now call close().
                self.close()

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

    def _queue_transaction(self):
        """Takes the transaction, calls _create_transaction_message and adds the created transaction message (now in the
        correct formatting for broadcasting) to the send_buffer. Marks _transaction_queued as True."""

        content = self.transaction
        transaction_message = TransactionMessage._create_transaction_message(content_bytes=content)  # Static method
        self._send_buffer += transaction_message
        self._transaction_queued = True
