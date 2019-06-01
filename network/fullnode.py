from network import fullnode_processing, fullnode_socket_manager as fsm
from api import database
import json
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

# ------ CONFIG PARAMETERS ------

with open('network/config.json') as cfg_file:
    cfg = json.load(cfg_file)

host = cfg["FullnodeInfo"]["host"]
clients_listening_port = cfg["FullnodeInfo"]["clients_listening_port"]
database_path = cfg["FullnodeInfo"]["database_path"]
neighbors_listening_port = cfg["FullnodeInfo"]["neighbors_listening_port"]

neighbor_address = cfg["NeighborsInfo"]["neighbor_address"]
neighbor_port = cfg["NeighborsInfo"]["neighbor_port"]


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

try:
    while True:  # As long as the full node runs

        # We start by processing all the client events
        # Client events can be a received transaction or a database request

        client_events = client_sel.select(timeout=1)  # Non-blocking mode, but with a timeout between each select call
        for key, mask in client_events:
            if key.data is None:  # A new client
                fsm.accept_client_connection(key.fileobj, client_sel)  # key.fileobj is the listening socket here
            else:
                connection = key.data  # ClientConnection object
                try:
                    # Process_events is the entry point
                    connection.process_events(mask)

                    # The fullnode processes the received data
                    fullnode_processing.process(connection, neighbors_sel)

                except Exception:
                    print(
                        "main: error: exception for",
                        f"{connection.addr}:\n{traceback.format_exc()}",
                    )
                    # It is possible that fullnode_processing encounters an exception on an already closed connection
                    if not connection.is_closed:
                        connection.close()

        # We then process all the neighbors events
        # Neighbors events can be either a received database or a database that we send

        neighbors_events = neighbors_sel.select(timeout=0)  # Here we do not want a timeout
        for key, mask in neighbors_events:
            if key.data is None:
                fsm.accept_gossip(key.fileobj, neighbors_sel)  # key.fileobj is the neighbors listening socket here
            else:
                connection = key.data  # NeighborConnection object
                try:
                    # Process_events is the entry point
                    connection.process_events(mask)

                    # The fullnode processes the received data
                    fullnode_processing.process(connection, neighbors_sel)

                except Exception:
                    print(
                        "main: error: exception for",
                        f"{connection.addr}:\n{traceback.format_exc()}",
                    )
                    print("Lost gossipping connection to neighbor !")

                    # It is possible that fullnode_processing encounters an exception on an already closed connection
                    if not connection.is_closed:
                        connection.close()

        # we have now processed all client and neighbor events


except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    client_sel.close()
    neighbors_sel.close()
