from network import liblightnode
import socket
import selectors
import traceback

sel = selectors.DefaultSelector()


def start_connection(host, port, transaction):
    address_tuple = (host, port)
    print("starting connection to", address_tuple)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(address_tuple)
    events = selectors.EVENT_WRITE
    transaction_message = liblightnode.TransactionMessage(sel, sock, address_tuple, transaction)
    sel.register(sock, events, data=transaction_message)


host = '127.0.0.1'
port = 60001
transaction = dict(content=bytes("lismoica", encoding="utf-8"))
start_connection(host, port, transaction)

try:
    while True:
        events = sel.select(timeout=1)
        for key, mask in events:
            transaction_to_send = key.data  # Transaction that has been plugged in the transaction_message object
            try:
                transaction_to_send.process_events(mask)
            except Exception:
                print(
                    "main: error: exception for",
                    f"{transaction_to_send.addr}:\n{traceback.format_exc()}",
                )
                transaction_to_send.close()
        # Check for a socket being monitored to continue.
        if not sel.get_map():
            break
except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel.close()

