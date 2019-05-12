from network import lightnode_connections
import pickle
import socket
import selectors
import traceback


class TransactionBroadcasting:

    def __init__(self, transaction):
        self.transaction = transaction
        self.sel = selectors.DefaultSelector()
        self._HOST = '127.0.0.1'
        self._PORT = 60010
        self._broadcasting_done = False

    def _start_connection(self, transaction_bytes):
        address_tuple = (self._HOST, self._PORT)
        print("starting connection to", address_tuple)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.connect_ex(address_tuple)
        events = selectors.EVENT_WRITE  # We only want to write to the socket in this case
        transaction_message = lightnode_connections.FullNodeConnection(self.sel, sock, address_tuple,
                                                                       connection_type="transaction_broadcast",
                                                                       transaction_bytes=transaction_bytes)
        self.sel.register(sock, events, data=transaction_message)

    def broadcast(self):

        # We start the broadcasting procedure with the serialized transaction
        transaction_bytes = pickle.dumps(self.transaction)
        self._start_connection(transaction_bytes)

        try:
            while True:
                events = self.sel.select(timeout=1)
                for key, mask in events:
                    transaction_to_send = key.data  # Transaction that has been plugged in the transaction_message obj
                    try:
                        transaction_to_send.process_events(mask)
                    except Exception:
                        print(
                            "Error occured during broadcasting of transaction : ",
                            f"{transaction_to_send.addr}:\n{traceback.format_exc()}",
                        )
                        transaction_to_send.close()
                # Check for a socket being monitored to continue.
                if not self.sel.get_map():
                    self._broadcasting_done = True
                    print("Broadcasting of transaction done.")
                    break
        except KeyboardInterrupt:
            print("caught keyboard interrupt, exiting")
        finally:
            self.sel.close()


class DatabaseRequest:

    def __init__(self):
        self.sel = selectors.DefaultSelector()
        self._HOST = '127.0.0.1'
        self._PORT = 60001
        self._database_received = False
        self.database = None

    def _start_connection(self):
        address_tuple = (self._HOST, self._PORT)
        print("starting connection to", address_tuple)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.connect_ex(address_tuple)
        events = selectors.EVENT_WRITE  # We only want to write to the socket in this case
        database_request = lightnode_connections.FullNodeConnection(self.sel, sock, address_tuple,
                                                                    connection_type="database_request", )
        self.sel.register(sock, events, data=database_request)

    def request(self):

        # We start the broadcasting procedure with the serialized transaction
        self._start_connection()

        try:
            while True:
                events = self.sel.select(timeout=1)
                for key, mask in events:
                    db_request = key.data  # Transaction that has been plugged in the transaction_message obj
                    try:
                        db_request.process_events(mask)
                    except Exception:
                        print(
                            "Error occurred during requesting of database : ",
                            f"{db_request.addr}:\n{traceback.format_exc()}",
                        )
                        db_request.close()
                # Check for a socket being monitored to continue.
                if not self.sel.get_map():
                    self._database_received = True
                    if db_request.database_received is not None:
                        self.database = db_request.database_received
                    break
        except KeyboardInterrupt:
            print("caught keyboard interrupt, exiting")
        finally:
            self.sel.close()






