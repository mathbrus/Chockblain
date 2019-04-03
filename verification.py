import crypto
import handling


def _is_spendable(tx_hash, position):
    """Controls whether the input can be spent. The tx_hash corresponds to the previous transaction
    from which we want to spend the output."""
    # Returns true if we can spend the input, false otherwise
    # We test two things : Does the input exist, and is the reference to it unique ?

    # Does the input exist as output of another transaction ?
    previous_tx = handling.get_transaction_by_txhash(tx_hash)
    if previous_tx is not False:
        # We have found the transaction
        try:
            list(previous_tx.internals["dict_of_outputs"].items())[position]
        except IndexError:
            print("BlockTransactionsValidator : Reference to an unexisting output.")
            return False
    else:
        return False

    # Is the reference unique ?
    nb_of_matches = 0

    list_of_blocks = handling.get_list_of_blocks()
    for b in list_of_blocks[1:]:
        for t in b.block_content:
            for current_tx_hash, current_position in t.internals["dict_of_inputs"].items():
                if (current_tx_hash, current_position) == (tx_hash, position):
                    nb_of_matches += 1

    if nb_of_matches > 0:
        return False

    return True


def _has_valid_signature(tx):
    """Controls whether the signature of the block is valid."""
    # Returns true if the signature is valid, false otherwise.

    if crypto.verify_signing(tx.txhash, tx.signature, tx.verifying_key):
        pass
    else:
        print("TransactionSignatureValidator : invalid signature detected.")
        return False


def _is_owned(tx_hash, position, verifying_key):
    """Controls whether the signature of the block proves ownership of the inputs. The tx_hash corresponds
    to the previous transaction from which we want to spend the output."""
    # Returns true if the signature corresponds, false otherwise.

    previous_tx = handling.get_transaction_by_txhash(tx_hash)

    # We do not need to check the existence of the previous_tx since we call the function after _is_spendable.
    address_of_output = list(previous_tx.internals["dict_of_outputs"].keys())[position]

    return crypto.verify_address(address_of_output, verifying_key)


def validate_transactions_of_block(block):
    """Validates the transactions in the given block, using 4 checking mechanisms."""

    # The first block is by definition always valid.
    if block.metadata["id"] == 1:
        return True

    # There are 4 sources in invalidity for a tx :
    # [1] The signature of the block does not correspond to its verifying key
    # [2] The verifying key does not correspond to the addresses that we are trying to spend from
    # [3] The outputs we are trying to spend are not spendable
    # [4] The amounts do not match

    block_tx_no = 0

    for t in block.block_content:

        # We control the signature [check 1]
        if not _has_valid_signature(t):
            print("BlockTransactionValidator : Invalid signature detected in transaction with hash : {} ."
                  .format(t.txhash))
            return False

        # For each transaction in the block, we keep record of the input and output amounts
        input_amount = 0
        output_amount = 0

        # Remember : inputs of a transaction are of format (hash of tx where we find the spendable output, its position)
        tx_input_no = 0
        for tx_hash, position in t.internals["dict_of_inputs"].items():

            # We control the ownership [check 2]. We can trust the verifying key since we are after [1]
            if not _is_owned(tx_hash, position, t.verifying_key):
                print("BlockTransactionValidator : Unproven ownership detected in input no. {} of transaction "
                      "no. {} detected."
                      .format(tx_input_no, block_tx_no))
                return False

            # For each input element of a given tx, we check if it is spendable [check 3]
            if _is_spendable(tx_hash, position):
                input_amount += handling.get_amount_from_input(tx_hash, position)
                tx_input_no += 1
            else:
                print("BlockTransactionValidator : Inconsistency in input no. {} of transaction no. {} detected."
                      .format(tx_input_no, block_tx_no))
                return False

        # Outputs of a transaction are of format (destination address, amount)
        for amount in t.internals["dict_of_outputs"].values():
            output_amount += amount

        # Last thing to check : does the input total match the output total ? [check 4]
        if input_amount != output_amount:
            print("BlockTransactionValidator : Unbalanced input and output amounts in transaction "
                  "no. {} detected. Inputs : {}, Outputs : {}."
                  .format(block_tx_no, input_amount, output_amount))
            return False

        block_tx_no += 1

    # Now we are sure the block is valid
    print("Valid block !")
    return True
