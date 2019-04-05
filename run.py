'''
    @authors: Aaron John, Sean Trinh, Hariharan Vijayachandran
'''
import shift
import sys
import time
#import random
#import pandas as pd
from statsmodels.tsa.arima_model import ARIMA
#import keras
from numpy.linalg import LinAlgError
#import statsmodels.api as sm

#Sticker symbols of companies in the Dow Jones
COMPANIES = ['MMM','AXP','AAPL','BA','CAT','CVX','CSCO','KO',
             'DIS','DWDP','XOM','GS','HD','IBM','INTC','JNJ',
             'JPM','MCD','MRK','MSFT','NKE','PFE','PG','TRV',
             'UTX','UNH','VZ','V','WMT','WBA']

NUM_COMPANIES = 30 # Number of companies in the Dow Jones
MIN_TRANSACTIONS = 10 # Minimum number of transactions that need to be included to avoid $100,000 penalty

account_balance = 1000000.00 # Beginning account balance, adjust as necessary
BUFFER_SIZE = 50
THRESHOLD = 0.0004
NUM_TRADES = 0
start = 0.0
TIME_TO_CLOSE = 22800.0
TIME_TO_STOP_BUY = TIME_TO_CLOSE*.92 # Equates to TIME_TO_CLOSE-15-18min on a normal trading day, calculated for when
TIME_TO_SELL = TIME_TO_CLOSE*.98

class Stock:
    def __init__(self,comp_name):
        self.name = comp_name
        self.state = 0
        self.current_price = 0.0
        self.predicted_price = 0.0
        self.BO = False
        self.SO = False
        self.H = False
        self.S = False
        self.price = []
        self.Holding = 0

    def add_data(self,prices):
        self.price += prices
        if len(self.price) > 90 :
            self.price = self.price[30:]

def zero(stk, trader):
    global NUM_TRADES
    if time.time() - start > TIME_TO_STOP_BUY:
        return
    pressure = get_pressure(stk.name, trader)
    if (-1.0/3.0) <= pressure <= (1.0/3.0):
        return
    prediction = get_prediction(stk, trader)
    purchase_size = purchasing_size(stk,trader)
    current_holding = trader.getPortfolioItem(stk.name).getShares()
    if current_holding < 0:
        purchase_size = purchase_size + abs(current_holding)
        purchase_size = int(purchase_size)
    stk.current_price = get_current_price(stk.name, trader)
    if (prediction - stk.current_price) / stk.current_price >= THRESHOLD and pressure < 0.0:
        limit_buy = shift.Order(shift.Order.LIMIT_BUY, stk.name, purchase_size, prediction)
        trader.submitOrder(limit_buy)
        stk.BO = True
        stk.predicted_price = prediction
        stk.state = 1
        return
    # SHORTING PORTION
    if (prediction - stk.current_price) / stk.current_price <= -1.5 * THRESHOLD and pressure > 0.0:
        trader.submitOrder(shift.Order(shift.Order.MARKET_SELL, stk.name, size=2))
        stk.S = True
        stk.H = True
        stk.state = 4
        stk.predicted_price = prediction
        limit_buy = shift.Order(shift.Order.LIMIT_BUY, stk.name, 3, stk.predicted_price)
        trader.submitOrder(limit_buy)
        stk.BO = True
        NUM_TRADES+=1
        return

def one(stk, trader):
    global NUM_TRADES
    if buy_order_executed(stk.name, trader):
        stk.current_price = stk.predicted_price
        stk.BO = False
        stk.H = True
        stk.state = 2
        NUM_TRADES += 1
        return
    if time.time()-start > TIME_TO_STOP_BUY:
        cancel_buy_order(stk.name,trader)
        stk.BO = False
        stk.state = 0
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
    # elif prediction>stk.current_price:
    #     cancel_buy_order(stk.name,trader)
    #     stk.BO = False
    #     stk.state = 0
    #     return

def two(stk, trader):
    global THRESHOLD
    global NUM_TRADES
    price_current = get_current_price(stk.name, trader)
    if (stk.current_price - price_current) / stk.current_price >= .01:
        stop_loss(stk.name,trader)
        stk.H = False
        stk.state = 0
        NUM_TRADES += 1
        return
    pressure = get_pressure(stk.name, trader)
    if (-1.0 / 3.0) <= pressure <= (1.0 / 3.0):
        return
    prediction = get_prediction(stk, trader)

    # if time.time() - start > TIME_TO_STOP_BUY:
    #     THRESHOLD /= 1.5
    purchase_size = trader.getPortfolioItem(stk.name).getShares()
    if purchase_size < 0:
        return

    if (prediction - stk.current_price) / stk.current_price <= -1.0*THRESHOLD and pressure > 0.0:
        if expected_sell_return(stk, trader, prediction) > 0:
            limit_sell = shift.Order(shift.Order.LIMIT_SELL, stk.name, purchase_size, prediction)
            trader.submitOrder(limit_sell)
            stk.SO = True
            stk.state = 3
            return

    # if (prediction - stk.current_price) / stk.current_price <= -1.5*THRESHOLD and pressure > 0.0:
    #     # print("SHORTING "+stk.name)
    #     trader.submitOrder(shift.Order(shift.Order.MARKET_SELL, stk.name, size=2))
    #     stk.S = True
    #     stk.H = True
    #     stk.state = 4
    #     stk.predicted_price = prediction
    #     limit_buy = shift.Order(shift.Order.LIMIT_BUY, stk.name, 3, stk.predicted_price)
    #     trader.submitOrder(limit_buy)
    #     stk.BO = True
    #     NUM_TRADES+=1
    #     return

    # current_holding = trader.getPortfolioItem(stk.name).getShares()
    # if current_holding < 0:
    #     if (stk.current_price - prediction) / stk.current_price >= THRESHOLD and pressure < 0.0:
    #         limit_buy = shift.Order(shift.Order.LIMIT_BUY, stk.name, current_holding, prediction)
    #         trader.submitOrder(limit_buy)
    #         stk.BO = True
    #         stk.predicted_price = prediction
    #         stk.state = 1
    #         return


    # PURCHASE_SIZE = trader.getPortfolioItem(stk.name).getShares()
    # if (prediction - stk.current_price) / stk.current_price >= THRESHOLD and pressure > 0.0:
    #     if expected_sell_return(stk,trader,prediction) > 2:
    #         limit_sell = shift.Order(shift.Order.LIMIT_SELL, stk.name, PURCHASE_SIZE, prediction)
    #         trader.submitOrder(limit_sell)
    #         stk.SO = True
    #         stk.state = 3

    # if (prediction - stk.current_price) / stk.current_price >= 5 * THRESHOLD and pressure > 0.0:
    #     # print("SHORTING "+stk.name)
    #     trader.submitOrder(shift.Order(shift.Order.MARKET_SELL, stk.name, size=3))
    #     stk.S = True
    #     stk.H = True
    #     stk.state = 4
    #     stk.predicted_price = prediction
    #     limit_buy = shift.Order(shift.Order.LIMIT_BUY, stk.name, 2, stk.predicted_price)
    #     trader.submitOrder(limit_buy)
    #     stk.BO = True
    #     NUM_TRADES += 1
    #     return
        # print("Changed state from 2 to 3")

def three(stk, trader):
    global THRESHOLD
    if sell_order_executed(stk.name, trader):
        stk.SO = False
        stk.H = False
        stk.state = 0
        global NUM_TRADES
        NUM_TRADES += 1
        return
    price_current = get_current_price(stk.name, trader)
    if ( stk.current_price - price_current) / stk.current_price >= .25:
        stop_loss(stk.name,trader)
        stk.H = False
        stk.BO = False
        stk.state = 0
        return
    pressure = get_pressure(stk.name, trader)
    if (-1.0 / 3.0) <= pressure <= (1.0 / 3.0):
        return

    prediction = get_prediction(stk, trader)

    # if time.time() - start > TIME_TO_STOP_BUY:
    #     THRESHOLD /= 2.0
    if prediction > stk.predicted_price and prediction > stk.current_price and pressure > 0.0:
        update_sell_order(stk, trader, prediction)
        stk.predicted_price = prediction
        return

def four(stk,trader):
    global THRESHOLD
    if buy_order_executed(stk.name, trader):
        stk.current_price = stk.predicted_price
        stk.BO = False
        stk.H = False
        stk.state = 0
        global NUM_TRADES
        NUM_TRADES += 1
        return
    # if time.time()-start>TIME_TO_STOP_BUY:
    #     THRESHOLD/=2.0
    pressure = get_pressure(stk.name, trader)
    if (-1.0 / 3.0) <= pressure <= (1.0 / 3.0):
        return

    prediction = get_prediction(stk, trader)
    stk.current_price = get_current_price(stk.name, trader)
    if prediction < stk.predicted_price and prediction < stk.current_price and pressure < 0.0:
        update_buy_order(stk, trader, prediction)
        stk.predicted_price = prediction
        return

STATES_TRANSITION = {0:zero, 1:one, 2:two, 3:three, 4: four}

def get_prediction(stk, trader, p=3,d=1,q=0):
    '''
    :param stk: The stock object
    :param trader: The trader object
    :param p: Default value 3
    :param d: Default value 1
    :param q: Default value 0
    :return: A prediction as a float
    '''
    actual = trader.getSamplePrices(stk.name, mid_prices=True)
    while len(actual) < 30: # Collect 30 data points
        actual = trader.getSamplePrices(stk.name, mid_prices=True)
    stk.add_data(actual)
    try:
        model = ARIMA(stk.price, order=(p,d,q))
        model_fit = model.fit(disp = 0)
        prediction = model_fit.forecast(5)[0][4]
    except (ValueError, LinAlgError):
        prediction = stk.price[-1]
    return prediction

def expected_sell_return(stk, trader, predicted_price):
    '''
    :param stk: The stock object
    :param trader: The trader object
    :param predicted_price: The predicted price
    :return: The expected return after selling
    '''
    size = trader.getPortfolioItem(stk.name).getShares()
    purchase_price = trader.getPortfolioItem(stk.name).getPrice()
    expected = size * (predicted_price - purchase_price - 0.002)
    return expected

def expected_return(predicted_price, extrapolated_price):
    '''
    :param predicted_price: Purchase Price
    :param extrapolated_price: 'Future Selling Price'
    :param size: Size of Purchase Shares
    :return: Expected Return
    '''
    purchase_price = predicted_price
    predicted_price = extrapolated_price
    expected = (predicted_price-purchase_price-.002)
    return expected

def get_extrapolated_prediction(stk, trader, p=3, d = 1, q=0):
    '''
    :param stk: The stock object
    :param trader: The trader object
    :param p: Default value 3
    :param d: Default value 1
    :param q: Default value 0
    :return: A prediction as a float
    '''
    actual = trader.getSamplePrices(stk.name, mid_prices=True)
    while len(actual) < 30: # Collect 30 data points
        actual = trader.getSamplePrices(stk.name, mid_prices=True)
    stk.add_data(actual)
    try:
        model = ARIMA(stk.price, order=(p,d,q))
        model_fit = model.fit(disp = 0)
        prediction = model_fit.forecast(10)[0][9]
    except (ValueError, LinAlgError):
        prediction = stk.price[-1]
    return prediction

def purchasing_size(stk, trader):
    '''
    :param stk: The stock object
    :param trader: The trader object
    :return: The number of shares to purchase **returns**
    '''
    buying_power = trader.getPortfolioSummary().getTotalBP()
    current_price = get_prediction(stk, trader)
    future_price = get_extrapolated_prediction(stk,trader)
    if future_price > current_price:
        shares = buying_power/current_price
        shares = int(shares/100)
        if shares == 0:
            return 1
        #if shares > 4:
        #    shares = 4
        trend = future_price - current_price
        if trend > 0:
            expected = expected_return(current_price,future_price)
            return_size = 3/expected
            if 0 < return_size < 1.0:
                return 4
            elif 0.99 < return_size < 2:
                return 3
            elif 1.99 < return_size < 3:
                return 2
            else:
                return 1
        else:
            return 1
    else:
        return 1
        # while True:
        #     if shares == 0:
        #         return 1
        #     if shares > 4:
        #         shares = 4
            # while shares > 1:
            #     expected = 2/expected_return(stk,current_price,future_price)
            #     if 0 < expected < 0.7:
            #         return 4
            #     elif 0.69 < expected < 1.3:
            #         return 3
            #     else:
            #         return 2
                # expected = expected_return(stk,current_price,future_price,shares)
                # res = 2/expected
                # if 0 < res < 0.7:
                #     return 4
                # else:
                #     shares = 3
                #     expected = expected_return(stk, current_price, future_price, shares)
                #     res = 2/expected
                #     if 0 < res < 1.3:
                #         return 3
                #     else:
                #         return 2
    # else:
    #     return 1

def update_buy_order(stk, trader, price):
    '''
    :param stk: The stock object
    :param trader: The trader object
    :param price: The price for the new buy order
    :return: N/A
    '''
    for order in trader.getWaitingList():
        if order.symbol == stk.name and order.type == shift.Order.LIMIT_BUY:
            order.type = shift.Order.CANCEL_BID
            trader.submitOrder(order)
            purchase_size = purchasing_size(stk, trader)
            limit_buy = shift.Order(shift.Order.LIMIT_BUY, stk.name, purchase_size, price)
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
            order.type = shift.Order.CANCEL_ASK
            trader.submitOrder(order)
            purchase_size = trader.getPortfolioItem(stk.name).getShares()
            limit_sell = shift.Order(shift.Order.LIMIT_SELL, stk.name, purchase_size, price)
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

def cancel_buy_order(stock, trader):
    '''
    :param stock: The stock symbol
    :param trader: The trader object
    :return: N/A
    '''
    for order in trader.getWaitingList():
        if order.symbol == stock and order.type == shift.Order.LIMIT_BUY:
            order.type = shift.Order.CANCEL_BID
            trader.submitOrder(order)

def cancel_sell_order(stock, trader):
    '''
    :param stock: The stock symbol
    :param trader: The trader object
    :return: N/A
    '''
    for order in trader.getWaitingList():
        if order.symbol == stock and order.type == shift.Order.LIMIT_SELL:
            order.type = shift.Order.CANCEL_ASK
            trader.submitOrder(order)

def stop_loss(stock, trader):
    '''
    :param stock: The stock symbol
    :param trader: The trader object
    :return: N/A
    '''
    cancel_sell_order(stock,trader)
    portfolio_item = trader.getPortfolioItem(stock)
    num_shares = int(portfolio_item.getShares()/100)
    trader.submitOrder(shift.Order(shift.Order.MARKET_SELL, stock, size=num_shares))

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

def start_selling(trader, stock_data):
    '''
    :param trader: The trader object
    :param stock_data: The list of stock objects
    :return: N/A
    '''
    for stk in stock_data:
        global THRESHOLD
        global NUM_TRADES
        # price_current = get_current_price(stk.name, trader)
        pressure = get_pressure(stk.name, trader)
        prediction = get_prediction(stk, trader)

        # if time.time() - start > TIME_TO_STOP_BUY:
        #     THRESHOLD /= 1.5
        purchase_size = trader.getPortfolioItem(stk.name).getShares()
        if purchase_size < 0:
            continue
        if (prediction - stk.current_price) / stk.current_price <= -1.0 * THRESHOLD and pressure > 0.0:
            if expected_sell_return(stk, trader, prediction) > 0:
                limit_sell = shift.Order(shift.Order.LIMIT_SELL, stk.name, purchase_size, prediction)
                trader.submitOrder(limit_sell)
                stk.SO = True
                stk.state = 3
                continue

def cancel_all_buy_sell(trader):
    '''
    :param trader: The trader object
    :return: N/A
    '''
    for order in trader.getWaitingList():
        if order.type == shift.Order.LIMIT_BUY:
            order.type = shift.Order.CANCEL_BID
            trader.submitOrder(order)
        elif order.type == shift.Order.LIMIT_SELL:
            order.type = shift.Order.CANCEL_ASK
            trader.submitOrder(order)

def market_close_positions(trader):
    '''
    :param trader: The trader object
    :return: N/A
    '''
    for company in COMPANIES:
        # For all holdings, market sell them
        # For all short positions, market buy
        # If no holdings for a particular company, do nothing
        portfolio_item = trader.getPortfolioItem(company)
        num_shares = int(portfolio_item.getShares()/100)
        bid_book = trader.getOrderBook(company, shift.OrderBookType.GLOBAL_BID, 1)
        print(bid_book[0].price)
        global NUM_TRADES
        if num_shares > 0:
            trader.submitOrder(shift.Order(shift.Order.MARKET_SELL,company,size = num_shares)) #Sell at market price
            NUM_TRADES += 1
        elif num_shares < 0:
            trader.submitOrder(shift.Order(shift.Order.MARKET_BUY, company, size = -1 * num_shares))
            NUM_TRADES += 1
        #Update log with transaction

def main(argv):
    '''
    STEP 0
    '''
    # create trader object
    #trader = shift.Trader("test002") #Change this?
    trader = shift.Trader("wolves_of_wall_street")

    # connect and subscribe to all available order books
    try:
        #trader.connect("initiator.cfg", "password")
        trader.connect("initiator.cfg", "ubd7w26JahGS9p4A")
        trader.subAllOrderBook()
    except shift.IncorrectPassword as e:
        print(e)
    except shift.ConnectionTimeout as e:
        print(e)

    '''
    STEP 1
    '''
    # 6.5 hours = 23400
    global start
    start = time.time()

    '''
    STEP 2
    '''
    #EXECUTE METHODS
    stock_data = []
    for company in COMPANIES:
       stock_data.append(Stock(company))

    request_prices(trader) # Make the connection to get sample prices (requestSamplePrices) for all companies

    while time.time() - start < TIME_TO_STOP_BUY:
        for stk in stock_data:
            STATES_TRANSITION[stk.state](stk, trader) # Execute the state diagram for each stock
        printSummary(trader)

    '''
    STEP 3
    '''
    while time.time() - start < TIME_TO_SELL:
        start_selling(trader, stock_data) # Start trying to sell at a profit before the end of the day

    print("DONE BUYING")

    trader.cancelAllSamplePricesRequests() # Cancel the sample prices connection

    cancel_all_buy_sell(trader) # Cancel all buy orders and sell orders
    print("CANCELLED ALL BUY/SELL ORDERS")

    for order in trader.getWaitingList():
        print("%6s\t%21s\t%7.2f\t\t%4d\t%36s\t%26s" %
              (order.symbol, order.type, order.price, order.size, order.id, order.timestamp))

    while trader.getWaitingListSize() != 0: # Wait for the orders to go through
        print("Waiting")
        time.sleep(3)

    # Close all positions
    # Market sell inventory and market buy shorted positions
    market_close_positions(trader)
    print("SUBMITTED MARKET ORDERS")

    print("Printing submitted orders")
    for order in trader.getSubmittedOrders():
        print("%6s\t%21s\t%7.2f\t\t%4d\t%36s\t%26s" %
              (order.symbol, order.type, order.price, order.size, order.id, order.timestamp))

    for company in COMPANIES:
        portfolio_item = trader.getPortfolioItem(company)
        num_shares = portfolio_item.getShares()
        while num_shares != 0:
            portfolio_item = trader.getPortfolioItem(company)
            num_shares = portfolio_item.getShares()

    #Update log

    #Print summary
    printSummary(trader)
    time.sleep(10)
    print(trader.getPortfolioSummary().getTotalBP())

    '''
    STEP 4
    '''
    trader.disconnect() #Disconnect

if __name__ == "__main__":
    main(sys.argv)
