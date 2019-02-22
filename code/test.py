import shift
import sys
import time
import random

COMPANIES = ['MMM','AXP','AAPL','BA','CAT','CVX','CSCO','KO',
             'DIS','DWDP','XOM','GS','HD','IBM','INTC','JNJ',
             'JPM','MCD','MRK','MSFT','NKE','PFE','PG','TRV',
             'UTX','UNH','VZ','V','WMT','WBA'] #Sticker symboles of companies in the Dow Jones
NUM_COMPANIES = 30 #Number of companies in the Dow Jones
MIN_TRANSACTIONS = 10 #Minimum number of transactions that need to be included to avoid $100,000 penalty
#NUM_ARIMA = x #Size of the ARIMA dataset

account_balance = 1000000.00 #Beginning account balance, adjust as necessary

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

def demo07(trader):
    """
    This method provides information on the structure of PortfolioSummary and PortfolioItem objects:
     getPortfolioSummary() returns a PortfolioSummary object with the following data:
     1. Total Buying Power (totalBP)
     2. Total Shares (totalShares)
     3. Total Realized Profit/Loss (totalRealizedPL)
     4. Timestamp of Last Update (timestamp)

     getPortfolioItems() returns a dictionary with "symbol" as keys and PortfolioItem as values, with each providing the following information:
     1. Symbol (getSymbol())
     2. Shares (getShares())
     3. Price (getPrice())
     4. Realized Profit/Loss (getRealizedPL())
     5. Timestamp of Last Update (getTimestamp())
    :param trader:
    :return:
    """

    print("Buying Power\tTotal Shares\tTotal P&L\tTimestamp")
    print("%12.2f\t%12d\t%9.2f\t%26s" % (trader.getPortfolioSummary().getTotalBP(),
                                       trader.getPortfolioSummary().getTotalShares(),
                                       trader.getPortfolioSummary().getTotalRealizedPL(),
                                       trader.getPortfolioSummary().getTimestamp()))

    print()

    print("Symbol\t\tShares\t\tPrice\t\tP&L\t\tTimestamp")
    for item in trader.getPortfolioItems().values():
        print("%6s\t\t%6d\t%9.2f\t%7.2f\t\t%26s" %
              (item.getSymbol(), item.getShares(), item.getPrice(), item.getRealizedPL(), item.getTimestamp()))

    return

def main(argv):
    '''
    STEP 0
    '''
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

    '''
    STEP 1
    '''
    # 6.5 hours = 23400
    start = time.time()
    #Create PortfolioItems for each company?
    #Create PortfolioSummary

    '''
    STEP 2
    '''
    #EXECUTE METHODS
    while time.time() - start < 500: # 22500 corresponds to 3:45
        #Execute trades and stuff
        print("Transaction initiated")
        comp = random.randint(0,29)
        company = COMPANIES[comp]
        trader.submitOrder(shift.Order(shift.Order.MARKET_BUY,company,size=1))
        demo07(trader)
        time.sleep(60)
        trader.submitOrder(shift.Order(shift.Order.MARKET_SELL,company,size=1))
        demo07(trader)
        time.sleep(10)

    '''
    STEP 3
    '''
    num_executed_transactions = trader.getSubmittedOrdersSize() - trader.getWaitingListSize()
    if num_executed_transactions < MIN_TRANSACTIONS:
        # getSubmittedOrdersSize returns # transactions both executed & not executed, excluding cancellation requests
        # getWaitingListSize returns # transactions not executed

        for i in range(int((MIN_TRANSACTIONS - num_executed_transactions)/2)):
            #buy and then sell? (Count for 2)
            comp = random.randint(0, 29)
            company = COMPANIES[comp]
            trader.submitOrder(shift.Order(shift.Order.MARKET_BUY, company,size=1))
            time.sleep(10)
            demo07(trader)
            trader.submitOrder(shift.Order(shift.Order.MARKET_SELL, company,size=1))
            time.sleep(10)
            demo07(trader)


    for company in COMPANIES:
        # Price? Long and short?
        portfolio_item = trader.getPortfolioItem(company)
        num_shares = portfolio_item.getShares()
        trader.submitOrder(shift.Order(shift.Order.MARKET_SELL,company,size=num_shares)) #Sell at market price
        #Update log with transaction

    demo07(trader)
    #Do this at 3:59?
    if time.time() - start >= 560: # 23328 corresponds to 3:59ish
        #Need to change if statement
        #trader.cancelAllPendingOrders() #Cancel all pending orders
        demo05(trader)
        #Update log

    '''
    STEP 4
    '''
    trader.disconnect() #Disconnect

if __name__ == "__main__":
    main(sys.argv)
