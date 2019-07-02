from network import json_tools
import pickle
import sys
import selectors
import struct


class FullNodeConnection:
    """This class is used to process one connection with a full node. There are two possible interactions :
        Either a we broadcast a new transaction to a full node,
        either we request the full database."""
    def __init__(self, selector, sock, addr, connection_type, transaction_bytes=None):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.connection_type = connection_type

        if self.connection_type == "database_request":
            self._recv_buffer = b""  # For when we receive the database from the full node
            self.database_received = None   # Filled when we have successfully received the database from the full node
            self._jsonheader_len = None
            self.jsonheader = None

        elif self.connection_type == "transaction_broadcast":
            self.transaction_bytes = transaction_bytes

        else:
            # Unrecognized connection_type.
            print(f'Unrecognized connection_type from : {self.addr}')
            self.close()

        self._send_buffer = b""

        self._client_message_queued = False  # To ensure we started to send the client message to the full node

    def _write(self):
        """Internal function called by write() to manage the socket."""
        if self._send_buffer:
            print("Sending...")
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK), skipping it for now
                # select() will eventually call us again
                pass
            else:  # If no errors were raised
                self._send_buffer = self._send_buffer[sent:]

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

    def _set_selector_to_read(self):
        """Set selector to listen for read events once we are ready to receive the database."""

        event = selectors.EVENT_READ
        self.selector.modify(self.sock, event, data=self)

    @staticmethod
    def _create_client_message(content_type, content_bytes=b"0"):
        """Returns the 3-parts client message, given the content to include, consistent with out application-layer
        protocol that we have defined for broadcasting messages."""

        jsonheader = {
            "byteorder": sys.byteorder,  # For the endianness of the OS
            "content-type": content_type,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = json_tools.json_encode(jsonheader, "utf-8")
        client_message_fixed_hdr = struct.pack(">H", len(jsonheader_bytes))
        client_message = client_message_fixed_hdr + jsonheader_bytes + content_bytes
        return client_message

    def _queue_client_message(self):
        """Calls _create_client_message and adds the created message (now in the
        correct formatting for broadcasting) to the send_buffer. Marks _client_message_queued as True."""

        if self.connection_type == "database_request":
            client_message = FullNodeConnection._create_client_message(
                content_type="db_request")  # Without any content since it is a request

        elif self.connection_type == "transaction_broadcast":
            client_message = FullNodeConnection._create_client_message(content_type="transaction_content",
                                                                       content_bytes=self.transaction_bytes)

        self._send_buffer += client_message
        self._client_message_queued = True

    def process_events(self, mask):
        """Entry point when the socket is ready for reading or writing."""
        if mask & selectors.EVENT_READ:  # When reading the database
            self.read()
        if mask & selectors.EVENT_WRITE:  # When sending a transaction or a database request
            self.write()

    def write(self):
        """Manages the writing of what is in the sending buffer through the socket, while maintaining the state."""
        if not self._client_message_queued:  # We have not yet init the sending process. Ensures that we init only once.
            self._queue_client_message()  # Initializes the sending process.

        self._write()

        if self._client_message_queued:
            if not self._send_buffer:  # We started AND finished the sending.

                if self.connection_type == "database_request":  # We are done sending the db_request
                    print("Database request transmitted.")
                    self._set_selector_to_read()
                elif self.connection_type == "transaction_broadcast":
                    # We are done sending the transaction, we can now call close().
                    print("Transaction transmitted.")
                    self.close()

    def read(self):
        """Manages the reading of the database from the socket, while maintaining the state. In addition,
        it interprets the different parts of the message."""
        self._read()

        if self._jsonheader_len is None:
            self.process_jsonheader_length()  # Triggers once we have received 2 bytes

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()  # Triggers once we have received jsonheader_len bytes

        if self.jsonheader:

            # Making sure we are receiving a database
            if self.jsonheader["content-type"] == "database_content":
                if self.database_received is None:
                    self.process_database_message()  # Triggers if we have recv'd jsonheader["content-length"] bytes
            else:
                # Unrecognized content-type.
                print(f'Unrecognized content-type from : {self.addr}')
                self.close()

    def close(self):
        """Used for unregistering the selector, closing the socket and deleting
         reference to socket object for garbage collection"""

        print("Closing connection to", self.addr)
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

        fixed_header_length = 2
        if len(self._recv_buffer) >= fixed_header_length:  # Check if we already have received enough data
            self._jsonheader_len = struct.unpack(
                ">H", self._recv_buffer[:fixed_header_length]
            )[0]
            self._recv_buffer = self._recv_buffer[fixed_header_length:]

    def process_jsonheader(self):
        """Reads the json_header of the actual database message."""

        if len(self._recv_buffer) >= self._jsonheader_len:  # Check if we already have received enough data
            self.jsonheader = json_tools.json_decode(
                self._recv_buffer[:self._jsonheader_len], "utf-8"
            )
            self._recv_buffer = self._recv_buffer[self._jsonheader_len:]
            for required_header in (
                "byteorder",
                "content-type",
                "content-length"
            ):
                if required_header not in self.jsonheader:
                    raise ValueError(f'Missing required header "{required_header}".')

    def process_database_message(self):
        """Reads the database message."""

        content_len = self.jsonheader["content-length"]

        # Check if we already have received enough data, or wait for more buffer.
        if len(self._recv_buffer) >= content_len:
            data = self._recv_buffer[:content_len]
            self._recv_buffer = self._recv_buffer[content_len:]

            print(
                f'Received a database from',
                self.addr,
            )

            self.database_received = pickle.loads(data)
            self.close()

