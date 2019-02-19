# Aaron John, Sean Trinh, Hariharan Vijayachandran

import shift
import sys
import time
def main(argv):
    print("hello world")
    # create trader object
    trader = shift.Trader("test001") #Change this?

    # connect and subscribe to all available order books
    try:
        trader.connect("initiator.cfg", "password")
        trader.subAllOrderBook()
    except shift.IncorrectPassword as e:
        print(e)
    except shift.ConnectionTimeout as e:
        print(e)

    #Execute methods

    #Disconnect
    trader.disconnect()

if __name__ == "__main__":
    main(sys.argv)