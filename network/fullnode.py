import selectors
import socket
import types


def accept_wrapper(sock):
    conn, addr = sock.accept()  # Should be ready to read
    print('accepted connection from', addr)
    conn.setblocking(False)
    data = types.SimpleNamespace(addr=addr, inb=b'', outb=b'')
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data=data)


def service_connection(key, mask):
    sock = key.fileobj
    data = key.data
    if mask & selectors.EVENT_READ:  # Mask equal to read
        recv_data = sock.recv(1024)  # Should be ready to read
        if recv_data:
            data.outb += recv_data
        else:
            print('closing connection to', data.addr)
            sel.unregister(sock)
            sock.close()
    if mask & selectors.EVENT_WRITE:  # Mask equal to write
        if data.outb:
            print('echoing', repr(data.outb), 'to', data.addr)
            sent = sock.send(data.outb)  # Should be ready to write
            data.outb = data.outb[sent:]


sel = selectors.DefaultSelector()
HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 65432

listening_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listening_sock.bind((HOST, PORT))
listening_sock.listen()
print('listening on', (HOST, PORT))

listening_sock.setblocking(False)

sel.register(listening_sock, selectors.EVENT_READ, data=None)

while True:
    events = sel.select(timeout=None)
    for key, mask in events:
        if key.data is None:  # The listening sock
            accept_wrapper(key.fileobj)
        else:  # One of the clients' sock
            service_connection(key, mask)

