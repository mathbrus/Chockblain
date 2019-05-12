from network import fullnode_connections
from api import database, exceptions
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
with open('config.json') as cfg_file:
    cfg = json.load(cfg_file)

host = cfg["FullnodeInfo"]["host"]
clients_port = cfg["FullnodeInfo"]["clients_port"]
database_path = cfg["FullnodeInfo"]["database_path"]
neighbors_connection_mode = cfg["FullnodeInfo"]["neighbors_connection_mode"]

if neighbors_connection_mode == "passive":
    neighbors_listening_port = cfg["NeighborsInfo"]["neighbors_listening_port"]
elif neighbors_connection_mode == "active":
    neighbor_address = cfg["NeighborsInfo"]["neighbor_address"]
    neighbor_port = cfg["NeighborsInfo"]["neighbor_port"]
else:
    raise exceptions.FullnodeError("Invalid neighbors connection mode.")
# --------------------------


def accept_client_connection(sock):
    conn, address_tuple = sock.accept()  # We spawn a new socket through which the client connection will happen
    print("Client connected on : ", address_tuple)
    conn.setblocking(False)
    c_conn = fullnode_connections.ClientConnection(client_sel, conn, address_tuple)  # We instantiate a new ClientConnection
    client_sel.register(conn, selectors.EVENT_READ, data=c_conn)  # We start by registering the socket in read mode


def accept_neighbor_connection(sock):
    conn, address_tuple = sock.accept()  # We spawn a new socket through which the neighbor connection will happen
    print("Neighbor connected on : ", address_tuple)
    conn.setblocking(False)
    n_conn = fullnode_connections.NeighborConnection(neighbors_sel, conn, address_tuple)  # We instantiate a new NeighborConnection
    neighbors_sel.register(conn, selectors.EVENT_READ, data=n_conn)  # We start by registering the socket in read mode


def connect_to_neighbor(address, port):
    neighbor_connection_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    neighbor_connection_sock.setblocking(False)
    neighbor_connection_sock.connect_ex((address, port))
    print("Connected to neighbor on : ", (address, port))
    n_conn = fullnode_connections.NeighborConnection(neighbors_sel, neighbor_connection_sock,
                                                     addr=(address, port))
    neighbors_sel.register(n_conn, selectors.EVENT_READ, data=n_conn)  # We start by registering the socket in read mode


# ------------- CONNECTING TO NEIGHBORS (blocking methods before being initialized) -----------
neighbors_sel = selectors.DefaultSelector()

if neighbors_connection_mode == "passive":
    # In this case we are waiting for our neighbors to connect to us
    neighbors_listening_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Avoid bind() exception: OSError: [Errno 48] Address already in use
    neighbors_listening_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    neighbors_listening_sock.bind((host, neighbors_listening_port))

    print("Waiting for neighbors on : ", (host, neighbors_listening_port))
    neighbors_listening_sock.listen()

    accept_neighbor_connection(neighbors_listening_sock)

elif neighbors_connection_mode == "active":
    # In this case we are actively seeking connection to our neighbors
    connect_to_neighbor(neighbor_address, neighbor_port)


else:
    print("Error in the neighbors connection mode.")
# --------------------------------------

# ------------- INITIALIZING CLIENT LISTENING SOCKET -----------
client_sel = selectors.DefaultSelector()
database.init_database(database_path)

clients_listening_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Avoid bind() exception: OSError: [Errno 48] Address already in use
clients_listening_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
clients_listening_sock.bind((host, clients_port))

clients_listening_sock.listen()
print("Listening for clients on", (host, clients_port))
clients_listening_sock.setblocking(False)

# Adding the listening socket to the selector, for read events
client_sel.register(clients_listening_sock, selectors.EVENT_READ, data=None)
# --------------------------------------


# The lists that contain the transactions and databases received and not yet processed
received_transactions_stack = []
received_databases_stack = []

try:
    while True:
        events = client_sel.select(timeout=1)  # Non-blocking mode, but with a timeout between each select call
        for key, mask in events:
            if key.data is None:
                accept_client_connection(key.fileobj)  # key.fileobj is the listening socket here
            else:
                connection = key.data  # Either a client or a neighbor event
                try:
                    # Here we want compatilibity in the method names
                    # between a client connection and a neighbor connection
                    connection.process_events(mask)

                    # FULL NODE PROCESSES RECEIVED DATA
                    # TODO
                    if hasattr(connection, "transaction_received"):
                        if connection.transaction_received is not None:
                            received_transactions_stack.append(pickle.loads(connection.transaction_received))
                    if hasattr(connection, "database_received"):
                        if connection.databse_received is not None:
                            received_transactions_stack.append(pickle.loads(connection.transaction_received))
                except Exception:
                    print(
                        "main: error: exception for",
                        f"{connection.addr}:\n{traceback.format_exc()}",
                    )
                    connection.close()

except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    client_sel.close()
    neighbors_sel.close()
