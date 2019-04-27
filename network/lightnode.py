import liblightnode
import sys
import socket
import selectors
import traceback

sel = selectors.DefaultSelector()


def create_transaction(text):

    return dict(
        content=bytes(text, encoding="utf-8"),
    )


def start_connection(host, port, transaction):
    addr = (host, port)
    print("starting connection to", addr)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_WRITE
    transaction_message = liblightnode.Message(sel, sock, addr, transaction)
    sel.register(sock, events, data=transaction_message)


host = '127.0.0.1'
port = 65432 
text = "lismoica"
transaction = create_transaction(text)
start_connection(host, port, transaction)

try:
    while True:
        events = sel.select(timeout=1)
        for key, mask in events:
            message = key.data
            try:
                message.process_events(mask)
            except Exception:
                print(
                    "main: error: exception for",
                    f"{message.addr}:\n{traceback.format_exc()}",
                )
                message.close()
        # Check for a socket being monitored to continue.
        if not sel.get_map():
            break
except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel.close()

