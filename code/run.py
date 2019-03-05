'''
    @authors: Aaron John, Sean Trinh, Hariharan Vijayachandran

    Step 0:
        Connect

    Step 1:
	    Collect data (every few seconds for one iteration) until you get a set amount of dataset

    Step 2:
	    While it’s still earlier than (insert time here):
		    Calculate ARIMA for all 30
		    Check thresholds
			    Execute trades accordingly if thresholds are met
				    If buying, check to see if we have the correct balance
			    Insert pending and successful transactions into log (SQL)
			    Update inventory

    Step 3:
	    Once it is the specified time or later:
		    Make sure you have done the required number of trades (if not, do instant trades)
			    Execute 10 or $100,000 penalty
		    Market sell
		    Cancel all pending orders
		    Update log of market sell and cancel pending orders

    Step 4:
        Disconnect

'''


import shift
import sys
import time
import random
import pandas as pd
from statsmodels.tsa.arima_model import ARIMA
#import keras
from numpy.linalg import LinAlgError
import statsmodels.api as sm



COMPANIES = ['MMM','AXP','AAPL','BA','CAT','CVX','CSCO','KO',
             'DIS','DWDP','XOM','GS','HD','IBM','INTC','JNJ',
             'JPM','MCD','MRK','MSFT','NKE','PFE','PG','TRV',
             'UTX','UNH','VZ','V','WMT','WBA']
#Sticker symbols of companies in the Dow Jones

NUM_COMPANIES = 30 #Number of companies in the Dow Jones
MIN_TRANSACTIONS = 10 #Minimum number of transactions that need to be included to avoid $100,000 penalty
#NUM_ARIMA = x #Size of the ARIMA dataset

account_balance = 1000000.00 #Beginning account balance, adjust as necessary
BUFFER_SIZE = 50
#state 0: initial state, gather data, get prediction
#state 1: buy order is put in if the stock price increases by a certain percent
THRESHOLD = 0.015

class Stock:
    def __init__(self,comp_name):
        self.name = comp_name
        self.state = 0
        self.current_price = 0
        self.predicted_price = 0
        self.BO = False
        self.SO = False
        self.H = False
        self.price = []

    def add_data(self,price):
        self.price = price

def zero(stk, trader):
    pressure = get_pressure(stk.name, trader)
    if (-1.0/3.0) <= pressure <= (1.0/3.0):
        return

    prediction = get_prediction(stk, trader)
    stk.current_price = get_current_price(stk.name, trader)
    if (stk.current_price - prediction) / stk.current_price >= THRESHOLD and pressure < 0.0:
        limit_buy = shift.Order(shift.Order.LIMIT_BUY, stk.name, 1, prediction)
        trader.submitOrder(limit_buy)
        stk.BO = True
        stk.predicted_price = prediction
        stk.state = 1

def one(stk, trader):
    if buy_order_executed(stk.name, trader):
        stk.current_price = stk.predicted_price
        stk.BO = False
        stk.H = True
        stk.state = 2
        return

    pressure = get_pressure(stk.name, trader)
    if (-1.0 / 3.0) <= pressure <= (1.0 / 3.0):
        return

    prediction = get_prediction(stk, trader)
    stk.current_price = get_current_price(stk.name, trader)
    if prediction < stk.predicted_price and prediction < stk.current_price and pressure < 0.0:
        update_buy_order(stk, trader, prediction)
        stk.predicted_price = prediction
        return

def two(stk, trader):
    pressure = get_pressure(stk.name, trader)
    if (-1.0 / 3.0) <= pressure <= (1.0 / 3.0):
        return

    prediction = get_prediction(stk, trader)
    if (prediction - stk.current_price) / stk.current_price >= THRESHOLD and pressure > 0.0:
        limit_sell = shift.Order(shift.Order.LIMIT_SELL, stk.name, 1, prediction)
        trader.submitOrder(limit_sell)
        stk.SO = True
        stk.state = 3

def three(stk, trader):
    if sell_order_executed(stk.name, trader):
        stk.SO = False
        stk.H = False
        stk.state = 0
        return

    pressure = get_pressure(stk.name, trader)
    if (-1.0 / 3.0) <= pressure <= (1.0 / 3.0):
        return

    prediction = get_prediction(stk, trader)
    if prediction > stk.predicted_price and prediction > stk.current_price and pressure > 0.0:
        update_sell_order(stk, trader, prediction)
        stk.predicted_price = prediction
        return

STATES_TRANSITION = {0:zero, 1:one, 2:two, 3:three}

def get_prediction(stk, trader, p=3,d=1,q=0):
    '''
    :param stk: The stock object
    :param trader: The trader object
    :param p: Default value 1
    :param d: Default value 1
    :param q: Default value 1
    :return: A prediction as a float
    '''

    actual = trader.getSamplePrices(stk.name, midPrices=True)
    while len(actual) < 30: # Collect 30 data points
        actual = trader.getSamplePrices(stk.name, midPrices=True)
    stk.add_data(actual)
    try:
        model = ARIMA(stk.price, order=(p,d,q))
        model_fit = model.fit(disp = 0)
        prediction = model_fit.forecast(5)[0][4]
    except (ValueError, LinAlgError):
        prediction = stk.price[-1]
        return prediction



def update_buy_order(stk, trader, price):
    '''
    :param stk: The stock object
    :param trader: The trader object
    :param price: The price for the new buy order
    :return: N/A
    '''
    for order in trader.getWaitingList():
        if order.symbol == stk.name and order.type == shift.Order.LIMIT_BUY:
            trader.submitCancellation(order)
            limit_buy = shift.Order(shift.Order.LIMIT_BUY, stk.name, 1, price)
            trader.submitOrder(limit_buy)
            return
    stk.current_price = stk.predicted_price
    stk.BO = False
    stk.H = True
    stk.state = 2

def update_sell_order(stk, trader, price):
    '''
    :param stk: The stock object
    :param trader: The trader object
    :param price: The price for the new sell order
    :return: N/A
    '''
    for order in trader.getWaitingList():
        if order.symbol == stk.name and order.type == shift.Order.LIMIT_SELL:
            trader.submitCancellation(order)
            limit_sell = shift.Order(shift.Order.LIMIT_SELL, stk.name, 1, price)
            trader.submitOrder(limit_sell)
            return
    stk.SO = False
    stk.H = False
    stk.state = 0

def buy_order_executed(stock, trader):
    '''
    :param stock: The stock symbol
    :param trader: The trader object
    :return: True if the buy order was executed; False if not
    '''
    for order in trader.getWaitingList():
        if order.symbol == stock and order.type == shift.Order.LIMIT_BUY:
            return False
    return True

def sell_order_executed(stock, trader):
    '''
    :param stock: The stock symbol
    :param trader: The trader object
    :return: True if the sell order was executed; False if not
    '''
    for order in trader.getWaitingList():
        if order.symbol == stock and order.type == shift.Order.LIMIT_SELL:
            return False
    return True

def get_pressure(stk_name, trader):
    '''
    :param stk_name: The stock symbol
    :param trader: The trader object
    :return: The buying/selling pressure as calculated by:
                        (B - A) / (B + A)
             where B = the highest bid size and A = the highest ask size
    '''
    bid_book = trader.getOrderBook(stk_name, shift.OrderBookType.GLOBAL_BID, 1)
    ask_book = trader.getOrderBook(stk_name, shift.OrderBookType.GLOBAL_ASK, 1)
    pressure = 0
    if len(bid_book) == 1 and len(ask_book) == 1:
        bid_size = bid_book[0].size
        ask_size = ask_book[0].size
        pressure = float(bid_size - ask_size) / float(bid_size + ask_size)
    return pressure

def get_current_price(stock, trader):
    '''
    :param stock: Stock symbol
    :param trader: the trader
    :return: the current price of the given stock

    Calculated by getting the average of the highest bid price and highest ask price
    '''
    current_price = 0.00
    bid_book = trader.getOrderBook(stock, shift.OrderBookType.GLOBAL_BID, 1)
    ask_book = trader.getOrderBook(stock, shift.OrderBookType.GLOBAL_ASK, 1)
    if len(bid_book) == 1 and len(ask_book) == 1:
        bid_price = bid_book[0].price
        ask_price = ask_book[0].price
        current_price = (bid_price + ask_price) / 2.0
    return current_price

def cancelAllPendingOrders(trader):
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

def printSummary(trader):
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

def request_prices(trader):
    flag = trader.requestSamplePrices(COMPANIES) # Input needs to be a list
    while not flag:
        flag = trader.requestSamplePrices(COMPANIES)

def main(argv):
    '''
    STEP 0
    '''
    # create trader object
    trader = shift.Trader("test002") #Change this?
    #trader = shift.Trader("wolves_of_wall_street")

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
    stock_data = []
    for company in COMPANIES:
         stock_data.append(Stock(company))
    #stock_data.append(Stock(COMPANIES[1]))

    request_prices(trader) # Make the connection to get sample prices (requestSamplePrices) for all companies

    while time.time() - start < 22500: # 22500 corresponds to 3:45
        #Execute trades and stuff
        s = time.time()
        for stk in stock_data:
            STATES_TRANSITION[stk.state](stk, trader)
            # sample = trader.getSamplePrices(stk.name, midPrices=True)
            #
            # #s = time.time()
            # while(len(sample)<31): # Collect 30 data points per company
            #     sample = trader.getSamplePrices(stk.name, midPrices=True)
            #
            # #print("Received Sample: "+str(time.time()-s))
            # s = time.time()
            # stk.add_data(sample)
            # print(sample)
            # # frame = pd.DataFrame(stk.price)
            # model = ARIMA(stk.price, order = (0,1,0)) # Make ARIMA model
            # model_fit = model.fit(disp=0)
            # print("Computed ARIMA: "+str(time.time()-s))
            # print(model_fit.summary())
            # time.sleep(10)
            # (B-A)/(B+A); Close to 1 -> going up; Close to -1 -> going down
        time.sleep(10)

    '''
    STEP 3
    '''
    #Time is now past 3:45
    num_executed_transactions = trader.getSubmittedOrdersSize - trader.getWaitingListSize
    if num_executed_transactions < MIN_TRANSACTIONS:
        # getSubmittedOrdersSize returns # transactions both executed & not executed, excluding cancellation requests
        # getWaitingListSize returns # transactions not executed

        for i in range(int((MIN_TRANSACTIONS - num_executed_transactions)/2)):
            #buy and then sell, both at market price
            comp = random.randint(0, NUM_COMPANIES - 1)
            company = COMPANIES[comp]

            while get_pressure(company, trader) <= (1.0/3.0) and time.time() - start < 22900:
                company = COMPANIES[random.randint(0, NUM_COMPANIES - 1)]

            trader.submitOrder(shift.Order(shift.Order.MARKET_BUY, company, size=1))
            time.sleep(10)
            # printSummary(trader)
            trader.submitOrder(shift.Order(shift.Order.MARKET_SELL, company, size=1))
            time.sleep(10)
            # printSummary(trader)

    for company in COMPANIES:
        # Price? Long and short?
        portfolio_item = trader.getPortfolioItem(company)
        num_shares = portfolio_item.getShares()
        trader.submitOrder(shift.Order(shift.Order.MARKET_SELL,company,size=num_shares)) #Sell at market price
        #Update log with transaction

    #Do this at 3:59?
    cancelAllPendingOrders(trader)

    #Update log

    #Print summary
    printSummary(trader)

    #if time.time() - start >= 23328: # 23328 corresponds to 3:59ish
        #trader.cancelAllPendingOrders() #Cancel all pending orders
        #demo05(trader)

    '''
    STEP 4
    '''
    trader.disconnect() #Disconnect

if __name__ == "__main__":
    main(sys.argv)
