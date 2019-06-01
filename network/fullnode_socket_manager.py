from network import fullnode_connections
import socket
import selectors

# --------- WRAPPERS FUNCTIONS TO MANAGE SOCKETS -----------------


def accept_client_connection(sock, selector):
    conn, address_tuple = sock.accept()  # We spawn a new socket through which the client connection will happen
    print("Client connected on : ", address_tuple)
    conn.setblocking(False)
    # We instantiate a new ClientConnection
    c_conn = fullnode_connections.ClientConnection(selector, conn, address_tuple)
    selector.register(conn, selectors.EVENT_READ, data=c_conn)  # We start by registering the socket in read mode


def accept_gossip(sock, selector):
    # Used for receiving the database from a neighbor
    conn, address_tuple = sock.accept()  # We spawn a new socket through which the neighbor connection will happen
    print("Neighbor gossipping : ", address_tuple)
    conn.setblocking(False)

    # We instantiate a new NeighborConnection, but without database_bytes, = receiving mode
    # We only want to monitor read events
    n_conn = fullnode_connections.NeighborConnection(selector, conn, address_tuple)
    selector.register(conn, selectors.EVENT_READ, data=n_conn)  # We start by registering the socket in read mode


def start_gossip(address_tuple, database_bytes, selector):
    # Used for sending the database to a neighbor
    print("Starting gossip to", address_tuple)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(address_tuple)
    # We instantiate a new NeighborConnection, this time with database_bytes, = sending mode
    # We only want to monitor write events
    database_message = fullnode_connections.NeighborConnection(selector, sock, address_tuple,
                                                               database_bytes=database_bytes)
    selector.register(sock, selectors.EVENT_WRITE, data=database_message)
