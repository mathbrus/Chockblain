import json, pickle
from tools import classes, database, api, validation
from network import fullnode_socket_manager as fsm

# The lists that contain the transactions and databases received and not yet processed - state of the node
received_transactions_stack = []
received_databases_stack = []


def process(connection, neighbors_selector):
    """This function takes a connection as input and processes the information it yields. It manages the state of the
    fullnode. It requires the neighbors selector to instantiate the gossip."""

    global received_transactions_stack
    global received_databases_stack

    with open('network/config.json') as cfg_file:
        cfg = json.load(cfg_file)

    neighbor_address = cfg["NeighborsInfo"]["neighbor_address"]
    neighbor_port = cfg["NeighborsInfo"]["neighbor_port"]

    # ---------- Clients Processing------------------

    # Processing received transaction
    if hasattr(connection, "transaction_received"):  # Is it a ClientConnection ?
        if connection.transaction_received is not None:
            received_transactions_stack.append(pickle.loads(connection.transaction_received))
            print("New transaction received.")

    # ---------- Block Creation ------------------
    if len(received_transactions_stack) >= 1:  # A block contains 10 transactions
        print("Creating a new block")
        # We mine a block
        new_block = classes.Block(received_transactions_stack)

        # We check if the transactions of the block are valid
        if validation.validate_block(new_block):
            print("Block is valid, now mining.")
            mined_new_block = api.mine_block(new_block)
            api.add_block_to_db(mined_new_block)
            received_transactions_stack = []
        else:
            print("Invalid new block, discarding transactions")
            received_transactions_stack = []

        # We start the broadcasting procedure with the serialized database
        database_bytes = pickle.dumps(api.get_database())
        fsm.start_gossip(address_tuple=(neighbor_address, neighbor_port),
                         database_bytes=database_bytes, selector=neighbors_selector)

    # ---------- Neighbors Processing------------------

    # Processing received database
    if hasattr(connection, "database_received"):  # Is it a NeighborConnection ?
        # Every NeighborConnection has a "database_received" property but it is only different
        # from None when we have successfully received a database message
        if connection.database_received is not None:
            received_databases_stack.append(pickle.loads(connection.database_received))
            print("New database received from a neighbor.")

    # Checking if a database has been successfully sent
    if hasattr(connection, "database_sent"):
        # Every NeighborConnection has a "database_sent" property but it is only True
        # when we have successfully sent a database message
        if connection.database_sent:
            # We now know that the sending process is over, we can close the connection and empty stack
            connection.close()
            received_transactions_stack = []

    # Consensus : choosing the longest chain
    if len(received_databases_stack) == 1:
        if len(received_databases_stack[0]) > len(api.get_database()):
            # The received database replaces our database
            print("Received database is the longest chain, copying.")
            database.write_to_db(received_databases_stack[0])
        else:
            print("Received database is not the longest chain, discarding.")

        # In any case we empty the stack
        received_databases_stack = []