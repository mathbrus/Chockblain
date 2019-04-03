import database
import handling
import verification

print(" _____ _                _   ______ _       _                __   _____\n"
      "/  __ \ |              | |  | ___ \ |     (_)              /  | |  _  |\n"
      "| /  \/ |__   ___   ___| | _| |_/ / | __ _ _ _ __   __   __`| | | |/' |\n"
      "| |   | '_ \ / _ \ / __| |/ / ___ \ |/ _` | | '_ \  \ \ / / | | |  /| |\n"
      "| \__/\ | | | (_) | (__|   <| |_/ / | (_| | | | | |  \ V / _| |_\ |_/ /\n"
      " \____/_| |_|\___/ \___|_|\_\____/|_|\__,_|_|_| |_|   \_/  \___(_)___/ "
      "\n"
      "\n")

database.init_database('database/db2')

command = input("Waiting for instructions : \n")

while command != "exit()":
      if command == "show_database":
            handling.show_blockchain_summary()
            command = input("Waiting for instructions : \n")
      elif command == "validate_block":
            block_height = input("Choose block height : \n")
            verification.validate_transactions_of_block(handling.get_last_block())
            command = input("Waiting for instructions : \n")
      else:
            print("Unknown command. Type exit() to end process.\n")
            command = input("Waiting for instructions : \n")

