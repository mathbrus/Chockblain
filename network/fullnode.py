from network import fullnode_connections
from api import classes, database, handling, exceptions
import json
import pickle
import socket
import selectors
import traceback

print(" _____ _                _   ______ _       _                __   _____\n"
      "/  __ \ |              | |  | ___ \ |     (_)              /  | |  _  |\n"
      "| /  \/ |__   ___   ___| | _| |_/ / | __ _ _ _ __   __   __`| | | |/' |\n"
      "| |   | '_ \ / _ \ / __| |/ / ___ \ |/ _` | | '_ \  \ \ / / | | |  /| |\n"
      "| \__/\ | | | (_) | (__|   <| |_/ / | (_| | | | | |  \ V / _| |_\ |_/ /\n"
      " \____/_| |_|\___/ \___|_|\_\____/|_|\__,_|_|_| |_|   \_/  \___(_)___/ \n"
      "\n"
      "Full Node\n"
      "\n"
      "------------\n"
      "\n"
      )

# ------ PARAMETERS ------

with open('network/config.json') as cfg_file:
    cfg = json.load(cfg_file)

host = cfg["FullnodeInfo"]["host"]
clients_listening_port = cfg["FullnodeInfo"]["clients_listening_port"]
database_path = cfg["FullnodeInfo"]["database_path"]
neighbors_listening_port = cfg["FullnodeInfo"]["neighbors_listening_port"]

neighbor_address = cfg["NeighborsInfo"]["neighbor_address"]
neighbor_port = cfg["NeighborsInfo"]["neighbor_port"]


# ---------WRAPPERS FUNCTIONS TO ACCEPT TCP CONNECTIONS-----------------
# These sockets are for a single usage ; once we are done with the message, we discard it

def accept_client_connection(sock):
    conn, address_tuple = sock.accept()  # We spawn a new socket through which the client connection will happen
    print("Client connected on : ", address_tuple)
    conn.setblocking(False)
    # We instantiate a new ClientConnection
    c_conn = fullnode_connections.ClientConnection(client_sel, conn, address_tuple)
    client_sel.register(conn, selectors.EVENT_READ, data=c_conn)  # We start by registering the socket in read mode


def accept_gossip(sock):
    # Used for receiving the database from a neighbor
    conn, address_tuple = sock.accept()  # We spawn a new socket through which the neighbor connection will happen
    print("Neighbor gossipping : ", address_tuple)
    conn.setblocking(False)

    # We instantiate a new NeighborConnection, but without database_bytes, = receiving mode
    # We only want to monitor read events
    n_conn = fullnode_connections.NeighborConnection(neighbors_sel, conn, address_tuple)
    neighbors_sel.register(conn, selectors.EVENT_READ, data=n_conn)  # We start by registering the socket in read mode


def start_gossip(address_tuple, database_bytes):
    # Used for sending the database to a neighbor
    print("Starting gossip to", address_tuple)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(address_tuple)
    # We instantiate a new NeighborConnection, this time with database_bytes, = sending mode
    # We only want to monitor write events
    database_message = fullnode_connections.NeighborConnection(sending_sel, sock, address_tuple,
                                                               database_bytes=database_bytes)
    sending_sel.register(sock, selectors.EVENT_WRITE, data=database_message)


# ------------- INITIALIZING NEIGHBORS LISTENING SOCKET -----------
neighbors_sel = selectors.DefaultSelector()

# In this case we are waiting for our neighbors to connect to us
neighbors_listening_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Avoid bind() exception: OSError: [Errno 48] Address already in use
neighbors_listening_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
neighbors_listening_sock.bind((host, neighbors_listening_port))

print("Listening for neighbors on : ", (host, neighbors_listening_port))
neighbors_listening_sock.listen()
neighbors_listening_sock.setblocking(False)

# Adding the listening socket to the selector, for read events
neighbors_sel.register(neighbors_listening_sock, selectors.EVENT_READ, data=None)


# --------------------------------------

# ------------- INITIALIZING CLIENT LISTENING SOCKET -----------
client_sel = selectors.DefaultSelector()
database.init_database(database_path)

clients_listening_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Avoid bind() exception: OSError: [Errno 48] Address already in use
clients_listening_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
clients_listening_sock.bind((host, clients_listening_port))

clients_listening_sock.listen()
print("Listening for clients on", (host, clients_listening_port))
clients_listening_sock.setblocking(False)

# Adding the listening socket to the selector, for read events
client_sel.register(clients_listening_sock, selectors.EVENT_READ, data=None)
# --------------------------------------


# The lists that contain the transactions and databases received and not yet processed
received_transactions_stack = []
received_databases_stack = []

try:
    while True:

        # We start by processing all the client events
        # Client events can be a received transaction or a database request

        client_events = client_sel.select(timeout=1)  # Non-blocking mode, but with a timeout between each select call
        for key, mask in client_events:
            if key.data is None:  # A new client
                accept_client_connection(key.fileobj)  # key.fileobj is the listening socket here
            else:
                connection = key.data  # ClientConnection object
                try:
                    # Process_events is the entry point
                    connection.process_events(mask)

                    # Full node processes received transaction
                    if hasattr(connection, "transaction_received"):
                        if connection.transaction_received is not None:
                            received_transactions_stack.append(pickle.loads(connection.transaction_received))
                            print("New transaction received.")
                except Exception:
                    print(
                        "main: error: exception for",
                        f"{connection.addr}:\n{traceback.format_exc()}",
                    )
                    connection.close()

        # We then process all the neighbors events
        # Neighbors events can be either a received database or a database that we send

        neighbors_events = neighbors_sel.select(timeout=0)  # Here we do not want a timeout
        for key, mask in neighbors_events:
            if key.data is None:
                accept_gossip(key.fileobj)  # key.fileobj is the peering socket here
            else:
                connection = key.data  # NeighborConnection object
                try:
                    # Process_events is the entry point
                    connection.process_events(mask)

                    # Full node processes received database
                    if hasattr(connection, "database_received"):
                        # Every NeighborConnection has a "database_received" property but it is only different
                        # from None when we have successfully received a database message
                        if connection.database_received is not None:
                            received_databases_stack.append(pickle.loads(connection.database_received))
                            print("New database received from a neighbor.")
                except Exception:
                    print(
                        "main: error: exception for",
                        f"{connection.addr}:\n{traceback.format_exc()}",
                    )
                    print("Lost gossipping connection to neighbor !")
                    connection.close()

        # we have now processed all client and neighbor events
        # Dirty code, for testing purposes
        if len(received_transactions_stack) == 5:
            print("5 transactions received ! Yay")
            # We mine a block
            new_block = classes.Block(received_transactions_stack)
            mined_new_block = handling.mine_block(new_block)

            handling.add_block_to_db(mined_new_block)

            # We start the broadcasting procedure with the serialized database
            sending_sel = selectors.DefaultSelector()
            database_bytes = pickle.dumps(handling.get_list_of_blocks())
            start_gossip(address_tuple=(neighbor_address, neighbor_port), database_bytes=database_bytes)
            _broadcasting_done = False

            try:
                while True:
                    events = sending_sel.select(timeout=1)
                    for key, mask in events:
                        database_to_send = key.data  # Database that has been plugged in the database_message obj
                        try:
                            database_to_send.process_events(mask)
                        except Exception:
                            print(
                                "Error occured during broadcasting of database : ",
                                f"{database_to_send.addr}:\n{traceback.format_exc()}",
                            )
                            database_to_send.close()
                    # Check for a socket being monitored to continue.
                    if not sending_sel.get_map():
                        _broadcasting_done = True
                        received_transactions_stack = []
                        print("Broadcasting of database done.")
                        break
            except KeyboardInterrupt:
                print("Caught keyboard interrupt, exiting sending process")
            finally:
                sending_sel.close()

except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    client_sel.close()
    neighbors_sel.close()
