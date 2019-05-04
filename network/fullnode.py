from network import libfullnode
from api import database
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

sel = selectors.DefaultSelector()
database.init_database('database/db2')


def accept_wrapper(sock):
    conn, address_tuple = sock.accept()  # We spawn a new socket through which the client connection will happen
    print("accepted new connection from", address_tuple)
    conn.setblocking(False)
    c_conn = libfullnode.ClientConnection(sel, conn, address_tuple)  # We instantiate a new ClientConnection
    sel.register(conn, selectors.EVENT_READ, data=c_conn)  # We start by registering the socket in read mode


host = '127.0.0.1'
port = 60001
listening_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Avoid bind() exception: OSError: [Errno 48] Address already in use
listening_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listening_sock.bind((host, port))
listening_sock.listen()
print("listening on", (host, port))
listening_sock.setblocking(False)
sel.register(listening_sock, selectors.EVENT_READ, data=None)

received_transactions=[]

try:
    while True:
        events = sel.select(timeout=None)
        for key, mask in events:
            if key.data is None:
                accept_wrapper(key.fileobj)  # key.fileobj is the listening socket here
            else:
                client_connection = key.data
                try:
                    client_connection.process_events(mask)
                    if client_connection.transaction_received is not None:
                        received_transactions.append(pickle.loads(client_connection.transaction_received))
                except Exception:
                    print(
                        "main: error: exception for",
                        f"{client_connection.addr}:\n{traceback.format_exc()}",
                    )
                    client_connection.close()

except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel.close()
