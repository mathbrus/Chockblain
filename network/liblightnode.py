import sys
import selectors
import json
import io
import struct


class TransactionMessage:
    def __init__(self, selector, sock, addr, transaction):
        self.selector = selector
        self.sock = sock
        self.addr = addr
        self.transaction = transaction
        # self._recv_buffer = b""
        self._send_buffer = b""
        self._transaction_queued = False
        # self._jsonheader_len = None
        # self.jsonheader = None

    # def _set_selector_events_mask(self, mode):
    #     """Set selector to listen for events: mode is 'r', 'w', or 'rw'."""
    #
    #     if mode == "r":
    #         events = selectors.EVENT_READ
    #     elif mode == "w":
    #         events = selectors.EVENT_WRITE
    #     elif mode == "rw":
    #         events = selectors.EVENT_READ | selectors.EVENT_WRITE
    #     else:
    #         raise ValueError(f"Invalid events mask mode {mode}.")
    #     self.selector.modify(self.sock, events, data=self)

    # def _read(self):
    #     # We read one chunk of the data
    #     try:
    #         # Should be ready to read
    #         data = self.sock.recv(4096)
    #     except BlockingIOError:
    #         # Resource temporarily unavailable (errno EWOULDBLOCK)
    #         pass
    #     else:  # If no errors were raised
    #         if data:
    #             self._recv_buffer += data
    #         else:
    #             raise RuntimeError("Peer closed.")

    def _write(self):
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

    def _json_encode(self, obj, encoding):
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_transaction_message(self, content_bytes):
        """Returns the 3-parts transaction message, given the transaction, consistent with out application-layer
        protocol that we have defined for broadcasting transaction messages to a full node."""

        jsonheader = {
            "byteorder": sys.byteorder,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        transaction_message_hdr = struct.pack(">H", len(jsonheader_bytes))
        transaction_message = transaction_message_hdr + jsonheader_bytes + content_bytes
        return transaction_message

    def _process_response_json_content(self):
        content = self.response
        result = content.get("result")
        print(f"got result: {result}")

    def _process_response_binary_content(self):
        content = self.response
        print(f"got response: {repr(content)}")

    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()

    # def read(self):
    #     self._read()
    #
    #     if self._jsonheader_len is None:
    #         self.process_protoheader()
    #
    #     if self._jsonheader_len is not None:
    #         if self.jsonheader is None:
    #             self.process_jsonheader()
    #
    #     if self.jsonheader:
    #         if self.response is None:
    #             self.process_response()

    def write(self):
        if not self._transaction_queued:
            self.queue_transaction()

        self._write()

        if self._transaction_queued:
            if not self._send_buffer:
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

    def queue_transaction(self):
        """Takes the transaction, calls _create_transaction_message and adds the created transaction message (now in the
        correct formatting for broadcasting) to the send_buffer. Marks _transaction_queued as True."""

        content = self.transaction["content"]
        transaction_message = self._create_transaction_message(content_bytes=content)
        self._send_buffer += transaction_message
        self._transaction_queued = True

    # def process_protoheader(self):
    #     hdrlen = 2
    #     if len(self._recv_buffer) >= hdrlen:
    #         self._jsonheader_len = struct.unpack(
    #             ">H", self._recv_buffer[:hdrlen]
    #         )[0]
    #         self._recv_buffer = self._recv_buffer[hdrlen:]
    #
    # def process_jsonheader(self):
    #     hdrlen = self._jsonheader_len
    #     if len(self._recv_buffer) >= hdrlen:
    #         self.jsonheader = self._json_decode(
    #             self._recv_buffer[:hdrlen], "utf-8"
    #         )
    #         self._recv_buffer = self._recv_buffer[hdrlen:]
    #         for reqhdr in (
    #                 "byteorder",
    #                 "content-length",
    #                 "content-type",
    #                 "content-encoding",
    #         ):
    #             if reqhdr not in self.jsonheader:
    #                 raise ValueError(f'Missing required header "{reqhdr}".')

    # def process_response(self):
    #     content_len = self.jsonheader["content-length"]
    #     if not len(self._recv_buffer) >= content_len:
    #         return
    #     data = self._recv_buffer[:content_len]
    #     self._recv_buffer = self._recv_buffer[content_len:]
    #     if self.jsonheader["content-type"] == "text/json":
    #         encoding = self.jsonheader["content-encoding"]
    #         self.response = self._json_decode(data, encoding)
    #         print("received response", repr(self.response), "from", self.addr)
    #         self._process_response_json_content()
    #     else:
    #         # Binary or unknown content-type
    #         self.response = data
    #         print(
    #             f'received {self.jsonheader["content-type"]} response from',
    #             self.addr,
    #         )
    #         self._process_response_binary_content()
    #     # Close when response has been processed
    #     self.close()