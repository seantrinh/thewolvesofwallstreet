# Aaron John, Sean Trinh, Hariharan Vijayachandran

import shift
import sys
import time

def demo01(trader):
    """
    This method submits a limit buy order by indicating symbol, limit price, limit size and order type.
    :param trader:
    :return:
    """

    limitBuy = shift.Order(shift.Order.LIMIT_BUY, "AAPL", 1, 10.00)
    trader.submitOrder(limitBuy)

    return

def demo05(trader):
    """
    This method cancels all the orders in the waiting list.
    :param trader:
    :return:
    """

    print("Symbol\t\t\t\t\t Type\t  Price\t\tSize\tID\t\t\t\t\t\t\t\t\t\tTimestamp")
    for order in trader.getWaitingList():
        print("%6s\t%21s\t%7.2f\t\t%4d\t%36s\t%26s" %
              (order.symbol, order.type, order.price, order.size, order.id, order.timestamp))

    print()

    print("Waiting list size: " + str(trader.getWaitingListSize()))

    print("Canceling all pending orders...", end=" ")

    # trader.cancelAllPendingOrders() also works
    for order in trader.getWaitingList():
        if order.type == shift.Order.LIMIT_BUY:
            order.type = shift.Order.CANCEL_BID
        else:
            order.type = shift.Order.CANCEL_ASK
        trader.submitOrder(order)

    i = 0
    while trader.getWaitingListSize() > 0:
        i += 1
        print(i, end=" ")
        time.sleep(1)

    print()

    print("Waiting list size: " + str(trader.getWaitingListSize()))

    return

def main(argv):
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

    #EXECUTE METHODS
    #demo01(trader)

    # Step 1 - Collect data for ARIMA, every couple of seconds (total 5 minutes)
    #   Test the ideal interval to collect data for ARIMA

    # Step 2 - Buy and selling/ Executing off the data
    # while (earlier than 3:45)
    #   buy and sell based on our parameters
    #   Make sure we have the money

    # Step 3 - 3:45
    #   Market Sell

    # Step 4 - At tne end of the day, cancel all pending orders
    trader.cancelAllPendingOrders()

    #Disconnect
    trader.disconnect()

if __name__ == "__main__":
    main(sys.argv)