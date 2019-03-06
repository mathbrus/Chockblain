import classes
import funcs
import pickle

# genesis_block = funcs.create_genesis_block()
my_first_element = classes.Element(100, "Cerisiers4")
my_first_tx = classes.Transaction(my_first_element, "Cerisiers7")
#
# my_first_block = classes.Block(my_first_tx)
# my_first_mined_block = funcs.mine_block(my_first_block)
# funcs.add_block_to_db(my_first_mined_block)
# my_second_block = classes.Block(my_first_tx)
# my_second_mined_block = funcs.mine_block(my_second_block)
# funcs.add_block_to_db(my_second_mined_block)
my_third_block = classes.Block(my_first_tx)
my_third_mined_block = funcs.mine_block(my_third_block)
# funcs.add_block_to_db(my_third_mined_block)
#
# list = funcs.get_list_of_blocks()
#
# test = funcs.get_last_block()

# print(utils.get_block_hash(my_third_mined_block))
# print(utils.get_block_hash(utils.get_last_block()))

print(funcs.get_block_hash(my_third_mined_block))
print(funcs.get_block_hash(funcs.get_last_block()))
# print(utils.get_block_hash(my_third_mined_block.block_content))
# print(funcs.get_block_hash(funcs.get_last_block()))
# print(utils.get_block_hash(my_first_tx.block))
# print(utils.get_block_hash(utils.get_last_block().block_content.internals))

funcs.show_blockchain_summary()