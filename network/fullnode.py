from network import libfullnode
import socket
import selectors
import traceback

sel = selectors.DefaultSelector()


def accept_wrapper(sock):
    conn, address_tuple = sock.accept()  # Should be ready to read
    print("accepted connection from", address_tuple)
    conn.setblocking(False)
    transaction_message = libfullnode.TransactionMessage(sel, conn, address_tuple)
    sel.register(conn, selectors.EVENT_READ, data=transaction_message)


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
                accept_wrapper(key.fileobj)
            else:
                transaction_to_receive = key.data
                try:
                    transaction_to_receive.process_events(mask)
                    if transaction_to_receive.transaction_received is not None:
                        received_transactions.append(transaction_to_receive.transaction_received)
                except Exception:
                    print(
                        "main: error: exception for",
                        f"{transaction_to_receive.addr}:\n{traceback.format_exc()}",
                    )
                    transaction_to_receive.close()

except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
finally:
    sel.close()
