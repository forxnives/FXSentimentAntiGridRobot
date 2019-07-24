# initializing _zmq and importing some things

_zmq = DWX_ZeroMQ_Connector()

import decimal
import time
import math

##########################################################################
#REQUEST SYMBOL TRADES FROM MT4 AND STORE IN A JSON OBJECT

def GETALLSYMBOLTRADES (symbol):
    symboltradesjson = None

    _zmq._DWX_MTX_GET_ALL_SYMBOL_TRADES_(symbol)

    while symboltradesjson is None:
        symboltradesjson = _zmq._get_response_()
        if symboltradesjson is None:
            time.sleep(.01)
    return symboltradesjson

##########################################################################
##REQUEST ALL TRADES FROM MT4 AND STORE IN A JSON OBJECT

def GETALLTRADES ():
    opentradesjson = None

    _zmq._DWX_MTX_GET_ALL_OPEN_TRADES_()

    while opentradesjson is None:
        opentradesjson = _zmq._get_response_()
        if opentradesjson is None:
            time.sleep(.01)
    return opentradesjson

##########################################################################
#RETURNS TICKETLIST OF OPEN TRADES FOR SPECIFIED SYMBOL

def SYMBOLTICKETS(symboltradesjson, symbol):
    symboltickets = []
    for eachticket in symboltradesjson['_trades']:
        if symboltradesjson['_trades'][eachticket]['_symbol'] == symbol and (symboltradesjson['_trades'][eachticket]['_type'] == 0 or symboltradesjson['_trades'][eachticket]['_type'] == 1):
            symboltickets.append(eachticket)
    return symboltickets


##########################################################################
#RETURNS DICTIONARY OF TRADES FOR PARTICULAR SYMBOL, USING SYMBOLTICKETS

def SYMBOLJSON(opentradesjson, symboltickets):

    symboljson = {}
    for eachticket in symboltickets:
        json = (opentradesjson['_trades'][eachticket])
        symboljson.update({eachticket:json})
    return symboljson
                                                                                #note: might not be needed anymore

##########################################################################
#CALCULATES THE PNLS OF ALL TICKETS IN THE TICKETLIST

def PNLhelper(opentradesjson, symboltickets):

    pnllist = []
    for eachticket2 in symboltickets:
        pandl = opentradesjson['_trades'][eachticket2]['_pnl']
        pnllist.append(pandl)

    return sum(pnllist)

##########################################################################
#COMBINING GET ALL TRADES, SYMBOLTICKETS AND PNLhelper FUNCTIONS

def PNLCALC(symbol):
    opentradesjson = GETALLTRADES()
    ticketlist = SYMBOLTICKETS(opentradesjson, symbol)
    pnl = PNLhelper(opentradesjson, ticketlist)
    return pnl
                                                                                 # note: might not be needed anymore

##########################################################################
#CLOSES ALL LOSING TRADES

def CLOSELOSINGTRADES(symboljson, symboltickets):


    for eachticket in symboltickets:
        if symboljson[eachticket]['_pnl'] < 0:
            _zmq._DWX_MTX_CLOSE_TRADE_BY_TICKET_(eachticket)
            time.sleep(1)


##########################################################################
#DETECTS LEVEL/STATE OF ONGOING TRADE

def LEVELDETECT(symbol, symboltickets, symboljson):

    # declaring variables

    level = 5
    short = False
    long = False
    continuation = False
    nbrtrades = len(symboltickets)

    # checking continuation

    for eachticket in symboltickets:
        if symboljson[eachticket]['_comment'] == str(symbol + 'SHORT1') or symboljson[eachticket]['_comment'] == str(symbol + 'SHORT2') or symboljson[eachticket]['_comment'] == str(symbol + 'SHORT3'):
            short = True
        # if symboljson[eachticket]['_comment'] == str(symbol + 'LONG1') or str(symbol + 'LONG2'):
        if symboljson[eachticket]['_comment'] == str(symbol + 'LONG1') or symboljson[eachticket]['_comment'] == str(symbol + 'LONG2') or symboljson[eachticket]['_comment'] == str(symbol + 'LONG3'):
            long = True

    if short and long is True:
        continuation = True

    # doing level logic

    if nbrtrades == 0:
        level = 0

    elif nbrtrades > 0:
        if continuation is False:
            level = 2
            for eachticket in symboltickets:
                if symboljson[eachticket]['_comment'] == str(symbol + 'SHORT1') or symboljson[eachticket]['_comment'] == str(symbol + 'LONG1'):
                    level = 1
        else:
            level = 3
            for eachticket in symboltickets:
                if symboljson[eachticket]['_comment'] == str(symbol + 'SHORT3') or symboljson[eachticket]['_comment'] == str(symbol + 'LONG3'):
                    level = 4
    return level

##########################################################################
#SOME USEFUL FUNCTIONS

def truncate(f, n):
    return math.floor(f * 10 ** n) / 10 ** n

def DECPLACES(number):
    number = str(number)
    decplaces = decimal.Decimal(number)
    decplaces = abs(decplaces.as_tuple().exponent)
    return decplaces

##########################################################################
#PRICELIST CREATOR

def PINTERVALS(price, atr, direction):

    #checking if last digit is a zero and changing to a one instead for upcoming decimalplaces function


    # counting decimal places and storing variable using DECPLACES function
    decplaces = DECPLACES(price)

    # adjusting atr to appropriate decimal place
    atr = atr / 10 ** (decplaces - 1)

    # converting direction into positive or negative multiplier
    if direction == 'long':
        dirvalue = 1
    elif direction == 'short':
        dirvalue = -1

    # directionalizing the atr
    atr = atr * dirvalue

    # preparing price format and decimal places to display
    price = float(price)
    decformat = '%.' + str(decplaces) + 'f'

    # declaring pricelist, doing an arithmetic series and appending values to list
    pricelist = []
    for i in range(1, 8 + 1):
        pricelist.append(decformat % price)
        price = price + atr

    return pricelist


##########################################################################
#GET ACCOUNT INFORMATION

def GETACCOUNTINFO ():
    accountinfojson = None

    _zmq._DWX_MTX_GET_ACCOUNT_INFORMATION_()
    time.sleep(1)

    while accountinfojson is None:
        accountinfojson = _zmq._get_response_()
        if accountinfojson is None:
            time.sleep(.01)
    return accountinfojson

##########################################################################
#LOTSIZE CALCULATOR

def INITIALLOTSIZE(symbol, price, stoploss, riskpercent, accountinfojson):

    # checking if symbol is a yen cross
    JPY_pair = False

    if symbol == 'USDJPY' or 'GBPJPY' or 'EURJPY' or 'CHFJPY' or 'AUDJPY' or 'CADJPY' or 'NZDJPY':
        JPY_pair = True

    # changing multiplier for yen
    if JPY_pair == True:
        multiplier = 0.01

    else:
        multiplier = 0.0001

    # determining calculation method based on USD account currency

    if (symbol[3:6]) == 'USD':
        method = 1

    elif (symbol[:3]) == 'USD':
        method = 2

    else:
        method = 3

    # floating inputs
    price = float(price)
    stoploss = float(stoploss)
    riskpercent = float(riskpercent)


    # converting account json to list and accessing balance value
    tempaccinfo = list(accountinfojson)

    accbalance = (tempaccinfo[0])
    accbalance = float(accbalance)


    # calculating pip value (risk calculator portion)

    cash_risk = accbalance * riskpercent
    stop_pips_int = abs((price - stoploss) / multiplier)
    pip_value = cash_risk / stop_pips_int

    # calculating units depending on method
    if method == 1:
        # pip_value = pip_value * price
        units = pip_value / multiplier
        units = units * 0.0000001


    elif method == 2:
        pip_value = pip_value * price
        units = pip_value / multiplier
        units = units * 0.0000001


    else:  # is method 0
        units = pip_value / multiplier
        units = units * 0.0000001

    # implementing logic for rounding up..only rounds up lotsize from 8 instead of 5.
    units = str(units)
    lotsize = 1
    if int(units[4]) > 7:
        lotsize = ('%.2f' % float(units))

    else:
        lotsize = truncate(float(units), 2)

    return lotsize


##########################################################################
#CALCULATES SLPOINTS

def SLPOINTCALC(price, slprice):
    multiplier = 1
    slpoints = (float(price) - float(slprice))
    if slpoints > 0:
        multiplier = -1

    decplaces1 = DECPLACES(price)
    decplaces2 = DECPLACES(slpoints)


    sldifference = abs(decplaces2 - decplaces1)


    slpoints = str(slpoints)
    points = slpoints[-1 * (decplaces2):-1 * (sldifference)]
    slpoints = float(points)*multiplier
    return slpoints


##########################################################################
#SENDS TRADE GRID DEPENDING ON LEVEL/STATE

def TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr):

    # determining order type (buy stop or sell stop)
    if direction == 'long':
        type = 4
        comment = symbol + 'LONG'
    elif direction == 'short':
        type = 5
        comment = symbol + 'SHORT'

    # calculating slpoints and tppoints..should have retroactively implemented SLPOINTCALC function but couldnt bother rework it lol..
    firstprice = pricelist[0]
    tpprice = pricelist[3]

    slpoints = abs(float(firstprice) - float(stoploss))
    tppoints = abs(float(firstprice) - float(tpprice))

    decplaces1 = DECPLACES(firstprice)
    decplaces2 = DECPLACES(slpoints)
    decplaces3 = DECPLACES(tppoints)

    sldifference = abs(decplaces2 - decplaces1)
    tpdifference = abs(decplaces3 - decplaces1)

    slpoints = str(slpoints)
    points = slpoints[-1 * (decplaces2):-1 * (sldifference)]
    slpoints = int(points)

    tppoints = str(tppoints)
    points2 = tppoints[-1 * (decplaces3):-1 * (tpdifference)]

    tppoints = float(points2)

    # splitting the pricelist in two..the first for scaling in lotsize (LEVEL 1) and the second for fixed lotsize (LEVEL 2)

    levellist1 = pricelist[:3]
    levellist2 = pricelist[3:]

    #declaring current lotsize variable for for loop
    curr_lotsize = lotsize1

    # sending trades, with appropriate comments, depending on level

    if level < 3:
        currcomment = comment + '1'

        for curr_price in levellist1:
            time.sleep(2)
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price, slpoints, tppoints, currcomment, curr_lotsize, magic, 0)
            curr_lotsize = curr_lotsize + lotsize1
            tppoints = tppoints - (10*atr)

        time.sleep(2)
        currcomment = comment + '2'
        # tppoints = tppoints * 1000

        for curr_price2 in levellist2:
            fixedlotsize = lotsize1 * 3
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price2, slpoints, 10000, currcomment, fixedlotsize, magic, 0)
            time.sleep(2)

    elif level == 3:
        currcomment = comment + '3'
        for curr_price in levellist1:
            fixedlotsize = lotsize1 * 3
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price, slpoints, 10000, currcomment, fixedlotsize, magic, 0)
            time.sleep(2)

        time.sleep(2)
        currcomment = comment + '3'

        for curr_price2 in levellist2:
            fixedlotsize = lotsize1 * 3
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price2, slpoints, 10000, currcomment, fixedlotsize, magic, 0)
            time.sleep(2)

    elif level == 4:
        currcomment = comment + '3'
        for curr_price in levellist1:
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price, slpoints, tppoints, currcomment, curr_lotsize, magic, 0)
            time.sleep(2)
            curr_lotsize = curr_lotsize + lotsize1
            tppoints = tppoints - (10*atr)

        time.sleep(2)
        currcomment = comment + '3'

        for curr_price2 in levellist2:
            fixedlotsize = lotsize1 * 3
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price2, slpoints, 10000, currcomment, fixedlotsize, magic, 0)
            time.sleep(2)


##########################################################################
# CLOSES ALL OPEN TRADES DEPENDING ON SYMBOL

def CLOSEALLACTIVE(symbol):

    _zmq._DWX_MTX_CLOSE_TRADES_BY_TYPEANDSYMBOL_(0, symbol)
    time.sleep(2)
    _zmq._DWX_MTX_CLOSE_TRADES_BY_TYPEANDSYMBOL_(1, symbol)

##########################################################################
# DELETES ALL PENDINGS

def DELETEALLPENDINGS(symbol):

    _zmq._DWX_MTX_CLOSE_TRADES_BY_TYPEANDSYMBOL_(4, symbol)
    time.sleep(2)
    _zmq._DWX_MTX_CLOSE_TRADES_BY_TYPEANDSYMBOL_(5, symbol)

##########################################################################
# MAIN STRATEGY EXECUTION FUNCTION

def TRADELOGICMODULE(symbol, symboltradesjson, symboltickets, pricelist, magic, direction, lotsize1, stoploss, level, pnl, atr):


    # declaring commentstring for deletion of orders later
    commentstring = 'COMMENT'
    if direction == 'long':
        commentstring = 'SHORT'
    elif direction == 'short':
        commentstring = 'LONG'

    # executing strategy depending on level/state of position.  see readme for details.

    if level == 0:
        DELETEALLPENDINGS(symbol)
        time.sleep(2)
        TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr)

    elif level == 1:

        CLOSEALLACTIVE(symbol)
        time.sleep(2)
        DELETEALLPENDINGS(symbol)
        time.sleep(2)
        TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr)

    elif level == 2:
        if pnl < 0:

            CLOSEALLACTIVE(symbol)
            time.sleep(2)
            DELETEALLPENDINGS(symbol)
            time.sleep(2)
            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr)

        else:

            DELETEALLPENDINGS(symbol)
            time.sleep(2)
            CLOSELOSINGTRADES(symboltradesjson, symboltickets)
            time.sleep(2)

            # updating symbol json and ticketlist

            symboltradesjson = GETALLSYMBOLTRADES(symbol)
            time.sleep(1)
            symboltickets = SYMBOLTICKETS(symboltradesjson, symbol)
            time.sleep(1)

            # setting stoplosses of existing position to level 1 tp of new position
            newslprice = pricelist[3]

            for eachticket in symboltickets:

                curr_price = symboltradesjson['_trades'][eachticket]['_open_price']
                slpoints = SLPOINTCALC(curr_price, newslprice)
                _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket, slpoints, 10000)
                time.sleep(1)


            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr)

    elif level == 3:
        DELETEALLPENDINGS(symbol)
        time.sleep(1)

        # Closing all opposing trades 2
        for eachticket in symboltickets:

            if symboltradesjson['_trades'][eachticket]['_comment'] == (symbol + commentstring + '1') or symboltradesjson['_trades'][eachticket]['_comment'] == (symbol + commentstring + '2'):
                _zmq._DWX_MTX_CLOSE_TRADE_BY_TICKET_(eachticket)
                time.sleep(1)

        symboltradesjson = GETALLSYMBOLTRADES(symbol)
        time.sleep(1)
        symboltickets = SYMBOLTICKETS(symboltradesjson, symbol)
        time.sleep(1)


        for eachticket in symboltickets:

            curr_price = symboltradesjson['_trades'][eachticket]['_open_price']
            slpoints = SLPOINTCALC(curr_price, stoploss)
            _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket, slpoints, 10000)

        TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr)

    elif level == 4:
        pnllist = []
        for eachticket in symboltickets:
                if symboltradesjson['_trades'][eachticket]['comment'] == (symbol + commentstring + '3'):
                    curr_pnl = symboltradesjson['_trades'][eachticket]['_pnl']
                    pnllist.append(curr_pnl)
        level3pnl = sum(pnllist)

        if level3pnl < 0:
            level = 0

            CLOSEALLACTIVE(symbol)
            time.sleep(2)
            DELETEALLPENDINGS(symbol)
            time.sleep(2)

            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr)

        else:

            CLOSELOSINGTRADES(symboltradesjson, symboltickets)
            time.sleep(2)

            symboltradesjson = GETALLSYMBOLTRADES(symbol)
            time.sleep(1)
            symboltickets = SYMBOLTICKETS(symboltradesjson, symbol)
            time.sleep(1)


            newslprice = pricelist[3]

            for eachticket in symboltickets:

                curr_price = symboltradesjson['_trades'][eachticket]['_open_price']
                slpoints = SLPOINTCALC(curr_price, newslprice)
                _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket, slpoints, 10000)
                time.sleep(1)

            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr)


##########################################################################

def INIT():

    # SYMBOL = input('SYMBOL?')
    # PRICE = input('input price')
    # STOPLOSS = input('input stoploss price')
    # ATR = input('input ATR')
    # PERCENT = input('total risk percent')

    #                        (skipping questionnaire for expedited testing rn, might have to do some formatting)
    SYMBOL = 'AUDUSD'
    PRICE = '0.69620'       #made price and stoploss strings to avoid losing potential trailing 0s with float.
    STOPLOSS = '0.70857'
    ATR = 15            # tried  to auto-import ATR in a few ways, including putting the indicator in the EA code but I didn't know what I was doing lol. must be possible though.
    PERCENT = 2         #(percent per symbol)

    # getting direction
    DIRECTION = ''
    if PRICE > STOPLOSS:
        DIRECTION = 'long'
    if PRICE < STOPLOSS:
        DIRECTION = 'short'

    # declaring/formatting variables

    MAGIC = 0
    LEVEL = 0
    PERCENT = float(PERCENT)
    PERCENT = PERCENT / 4               # using a fourth of designated percent for starting lotsize

    # assigning appropriate magic number..might be useful later

    if SYMBOL == 'EURUSD':
        MAGIC = 1
    elif SYMBOL =='GBPUSD':
        MAGIC = 2
    elif SYMBOL =='EURGBP':
        MAGIC = 3
    elif SYMBOL =='USDCHF':
        MAGIC = 4
    elif SYMBOL =='USDCAD':
        MAGIC = 5
    elif SYMBOL =='USDJPY':
        MAGIC = 6
    elif SYMBOL =='GBPJPY':
        MAGIC = 7
    elif SYMBOL =='AUDUSD':
        MAGIC = 8
    elif SYMBOL =='NZDUSD':
        MAGIC = 9

    elif SYMBOL =='XAUUSD':          # going to have to rework the code a little bit for gold..getting a SL/TP-related error
        MAGIC = 10
    else:
        MAGIC = 11

    # getting pricelist for new order
    PRICELIST = PINTERVALS(PRICE, ATR, DIRECTION)

    # creating symbol json dictionary for existing position
    RAWSYMBOLJSON = GETALLSYMBOLTRADES(SYMBOL)

    # creating ticketlist for existing position
    SYMBTICKETS = SYMBOLTICKETS(RAWSYMBOLJSON, SYMBOL)

    # creating useable symbol json for existing position
    SYMBOLTRADESJSON = SYMBOLJSON(RAWSYMBOLJSON, SYMBTICKETS)

    # getting account balance info for lotsize calculation
    ACCOUNTINFOJSON = GETACCOUNTINFO()

    # calculating starting lotsize for new order
    LOTSIZE1 = INITIALLOTSIZE(SYMBOL, float(PRICE), float(STOPLOSS), PERCENT, ACCOUNTINFOJSON)

    # calculating existing position's pnl
    PNL = PNLhelper(SYMBOLTRADESJSON, SYMBTICKETS)

    # detecting level/state of existing position
    LEVELDETECT(SYMBOL, SYMBTICKETS, SYMBOLTRADESJSON)

    # plugging everything into main strategy function
    TRADELOGICMODULE(SYMBOL, SYMBOLTRADESJSON, SYMBTICKETS, PRICELIST, MAGIC, DIRECTION, LOTSIZE1, float(STOPLOSS),
                         LEVEL, PNL, ATR)








