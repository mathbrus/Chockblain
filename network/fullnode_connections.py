from tools import database
from network import json_tools
import pickle
import selectors
import struct
import sys


class ClientConnection:
    """This class is used to process one connection with a client. There are two possible interactions :
    Either a client sends us a new transaction that he created,
    either it is a request for the full database."""
    def __init__(self, selector, sock, addr):
        self.selector = selector
        self.sock = sock
        self.addr = addr

        # Here we initalize all the class properties (for tx and db) as we cannot yet know which one will be the case
        self._recv_buffer = b""  # Used both for receiving transactions and request to send the database
        self._send_buffer = b""  # For when we send the database to a client

        self._jsonheader_len = None
        self.jsonheader = None

        self._database_queued = False  # To ensure we started to send the database to a client
        self.transaction_received = None  # Filled when we have successfully received a new transaction from a client

        self.is_closed = False  # To indicate that it has consciously been closed

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

    def _write(self):
        """Internal function called by write() to manage the socket."""
        if self._send_buffer:
            print("Sending database to", self.addr)
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK), skipping it for now
                # select() will eventually call us again
                pass
            else:  # If no errors were raised
                self._send_buffer = self._send_buffer[sent:]

    def _set_selector_to_write(self):
        """Set selector to listen for write events once we are ready to send the database."""

        event = selectors.EVENT_WRITE
        self.selector.modify(self.sock, event, data=self)

    def _queue_database(self):
        """Reads the database, calls _create_message_message and adds the created database message (now in the
        correct formatting for broadcasting) to the send_buffer. Marks _database_queued as True."""

        db = pickle.dumps(database.read_from_db())
        db_message = ClientConnection._create_database_message(content_bytes=db)  # Static method
        self._send_buffer += db_message
        self._database_queued = True

    @staticmethod
    def _create_database_message(content_bytes):
        """Returns the 3-parts database message, given the database, consistent with out application-layer
        protocol that we have defined for broadcasting messages between full nodes and clients."""

        jsonheader = {
            "byteorder": sys.byteorder,  # For the endianness of the OS
            "content-type": "database_content",
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = json_tools.json_encode(jsonheader, "utf-8")
        database_message_fixed_hdr = struct.pack(">H", len(jsonheader_bytes))
        database_message = database_message_fixed_hdr + jsonheader_bytes + content_bytes
        return database_message

    def process_events(self, mask):
        """Entry point when the socket is ready for reading or writing."""
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:  # When sending the database
            self.write()

    def read(self):
        """Manages the reading of the client message through the socket, while maintaining the state. In addition,
        it interprets the different parts of the message."""
        self._read()

        if self._jsonheader_len is None:
            self.process_jsonheader_length()  # Triggers once we have received 2 bytes

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()  # Triggers once we have received jsonheader_len bytes

        if self.jsonheader is not None:

            # If what we received is a database request, we change the events that the selectors is listening to write
            if self.jsonheader["content-type"] == "db_request":
                self._set_selector_to_write()

            # If what we received is a transaction
            elif self.jsonheader["content-type"] == "transaction_content":
                if self.transaction_received is None:
                    self.process_transaction_message()  # Triggers if we have recv'd jsonheader["content-length"] bytes

            else:
                # Unrecognized content-type.
                print(f'Unrecognized content-type from : {self.addr}')
                self.close()

    def write(self):
        """Manages the writing of the database through the socket, while maintaining the state."""
        if not self._database_queued:  # We have not yet init the sending process. Ensures that we init only once.
            self._queue_database()  # Initializes the sending process.

        self._write()

        if self._database_queued:
            if not self._send_buffer:  # We started AND finished the sending.
                # We are done sending the database, we can now call close().
                print(f'Finished sending the database to : {self.addr}')
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
            self.is_closed = True
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
        """Reads the json_header of the actual transaction message."""

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

    def process_transaction_message(self):
        """Reads the transaction message."""

        content_len = self.jsonheader["content-length"]

        # Check if we already have received enough data, or wait for more buffer.
        if len(self._recv_buffer) >= content_len:
            data = self._recv_buffer[:content_len]
            self._recv_buffer = self._recv_buffer[content_len:]

            print(
                f'Received a message from',
                self.addr,
            )

            self.transaction_received = data
            self.close()


class NeighborConnection:
    """This class is used to process one connection with a neighbor.
    For now, it can either send or receive the database from a neighbor."""
    def __init__(self, selector, sock, addr, database_bytes=None):
        self.selector = selector
        self.sock = sock
        self.addr = addr

        # Here we initalize all the class properties
        self._recv_buffer = b""  # Used for receiving a database
        self._send_buffer = b""  # For when we send the database to a neighbor

        self._jsonheader_len = None
        self.jsonheader = None

        self._database_queued = False  # To ensure we started to send the database to a neighbor
        self.database_received = None  # Filled when we have successfully received a new database from a neighbor
        self.database_sent = False  # Filled when we have successfully sent a database to a neighbor

        self.is_closed = False  # To indicate that it has consciously been closed

        if database_bytes is not None:  # If we are sending the database
            self.database_bytes = database_bytes

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

    @staticmethod
    def _create_database_message(content_type, content_bytes):
        """Returns the 3-parts database message, given the content to include, consistent with out application-layer
        protocol that we have defined for broadcasting messages."""

        jsonheader = {
            "byteorder": sys.byteorder,  # For the endianness of the OS
            "content-type": content_type,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = json_tools.json_encode(jsonheader, "utf-8")
        database_message_fixed_hdr = struct.pack(">H", len(jsonheader_bytes))
        database_message = database_message_fixed_hdr + jsonheader_bytes + content_bytes
        return database_message

    def _queue_database(self):
        """Calls _create_database_message and adds the created message (now in the
        correct formatting for broadcasting) to the send_buffer. Marks _database_queued as True."""

        database_message = NeighborConnection._create_database_message(content_type="database_content",
                                                                       content_bytes=self.database_bytes)
        self._send_buffer += database_message
        self._database_queued = True

    def process_events(self, mask):
        """Entry point when the socket is ready for reading or writing."""
        if mask & selectors.EVENT_READ:  # When receiving a database
            self.read()
        if mask & selectors.EVENT_WRITE:  # When sending the database
            self.write()

    def read(self):
        """Manages the reading of the neighbor message through the socket, while maintaining the state. In addition,
        it interprets the different parts of the message."""
        self._read()

        if self._jsonheader_len is None:
            self.process_jsonheader_length()  # Triggers once we have received 2 bytes

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()  # Triggers once we have received jsonheader_len bytes

        if self.jsonheader is not None:

            # Making sure we are receiving a database
            if self.jsonheader["content-type"] == "database_content":
                if self.database_received is None:
                    self.process_database_message()  # Triggers if we have recv'd jsonheader["content-length"] bytes
                    # Closes the socket
            else:
                # Unrecognized content-type.
                print(f'Unrecognized content-type from : {self.addr}')
                self.close()

    def write(self):
        """Manages the writing of what is in the sending buffer through the socket, while maintaining the state."""
        if not self._database_queued:  # We have not yet init the sending process. Ensures that we init only once.
            self._queue_database()  # Initializes the sending process.

        self._write()  # Writes what is in the sending buffer

        if self._database_queued:
            if not self._send_buffer:  # We started AND finished the sending.

                # We are done sending the database, we can now call flag database_received as true.
                print("Database transmitted to neighbor.")
                self.database_sent = True

    def close(self):
        """Used for unregistering the selector, closing the socket and deleting
         reference to socket object for garbage collection"""

        print("closing connection to neighbor : ", self.addr)
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
            self.is_closed = True
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
                "content-type",  # For the sake of consistency in the application-layer protocol
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
                f'Received a database from neighbor : ',
                self.addr,
            )

            self.database_received = data
            self.close()
