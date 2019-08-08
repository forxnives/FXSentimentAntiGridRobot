##########################################################################
# initializing _zmq and importing some things

_zmq = DWX_ZeroMQ_Connector()

import decimal
import time
import math
import numpy as np


##########################################################################
# REQUEST ATR FROM MT4 AND FORMAT ACCORDINGLY

def GETATR(symbol):
    atrset = 5000000000

    if (symbol[3:6]) == 'JPY':
        multiplier = 0.001

    elif (symbol[:3]) == 'XAU':
        multiplier = 0.0001

    else:
        multiplier = 0.1

    _zmq._set_response_()
    _zmq._DWX_MTX_ATR_REQUEST_(symbol)
    time.sleep(1)

    while atrset == 5000000000:
        atrset = _zmq._get_response_()
        if atrset is 5000000000:
            time.sleep(.01)

    for value in atrset:
        atr = value

    atr = atr * multiplier
    atr = int(round(atr))

    return atr


##########################################################################
# REQUEST SYMBOL TRADES FROM MT4 AND STORE IN A JSON OBJECT

def GETALLSYMBOLTRADES(symbol):
    symboltradesjson = None
    _zmq._set_response_()
    # time.sleep(1)
    _zmq._DWX_MTX_GET_ALL_SYMBOL_TRADES_(symbol)
    # time.sleep(1)

    while symboltradesjson is None:
        symboltradesjson = _zmq._get_response_()
        if symboltradesjson is None:
            time.sleep(.01)
    return symboltradesjson


##########################################################################
##REQUEST ALL TRADES FROM MT4 AND STORE IN A JSON OBJECT

def GETALLTRADES():
    opentradesjson = None
    _zmq._set_response_()
    _zmq._DWX_MTX_GET_ALL_OPEN_TRADES_()

    while opentradesjson is None:
        opentradesjson = _zmq._get_response_()
        if opentradesjson is None:
            time.sleep(.01)
    return opentradesjson


##########################################################################
# RETURNS TICKETLIST OF OPEN TRADES FOR SPECIFIED SYMBOL

def SYMBOLTICKETS(symboltradesjson, symbol):
    symboltickets = []
    for eachticket in symboltradesjson['_trades']:
        if symboltradesjson['_trades'][eachticket]['_symbol'] == symbol and (
                symboltradesjson['_trades'][eachticket]['_type'] == 0 or symboltradesjson['_trades'][eachticket][
            '_type'] == 1):
            symboltickets.append(eachticket)
    return symboltickets


##########################################################################
# RETURNS DICTIONARY OF TRADES FOR PARTICULAR SYMBOL, USING SYMBOLTICKETS

def SYMBOLJSON(opentradesjson, symboltickets):
    symboljson = {}
    for eachticket in symboltickets:
        json = (opentradesjson['_trades'][eachticket])
        symboljson.update({eachticket: json})
    return symboljson
    # note: might not be needed anymore


##########################################################################
# CALCULATES THE PNLS OF ALL TICKETS IN THE TICKETLIST

def PNLhelper(opentradesjson, symboltickets):
    pnllist = []
    for eachticket2 in symboltickets:
        pandl = opentradesjson[eachticket2]['_pnl']
        pnllist.append(pandl)

    return sum(pnllist)


##########################################################################
# COMBINING GET ALL TRADES, SYMBOLTICKETS AND PNLhelper FUNCTIONS

def PNLCALC(symbol):
    opentradesjson = GETALLTRADES()
    ticketlist = SYMBOLTICKETS(opentradesjson, symbol)
    pnl = PNLhelper(opentradesjson, ticketlist)
    return pnl
    # note: might not be needed anymore


##########################################################################
# CLOSES ALL LOSING TRADES

def CLOSELOSINGTRADES(symboljson, symboltickets):
    for eachticket in symboltickets:
        if symboljson[eachticket]['_pnl'] < 0:
            _zmq._DWX_MTX_CLOSE_TRADE_BY_TICKET_(eachticket)
            time.sleep(1)


##########################################################################
# DETECTS LEVEL/STATE OF ONGOING TRADE

def LEVELDETECT(symbol, symboltickets, rawsymboljson, symboljson):
    # declaring variables

    level = 5
    short = False
    long = False
    continuation = False
    nbrtrades = len(symboltickets)

    # making list of total tradeds including pendings

    totalsymboltickets = []
    for eachticket2 in rawsymboljson['_trades']:
        if rawsymboljson['_trades'][eachticket2]['_symbol'] == symbol:
            totalsymboltickets.append(eachticket2)


    # checking continuation

    for eachticket in totalsymboltickets:
        if rawsymboljson['_trades'][eachticket]['_comment'] == str(symbol + 'SHORT1') or rawsymboljson['_trades'][eachticket]['_comment'] == str(
                symbol + 'SHORT2') or rawsymboljson['_trades'][eachticket]['_comment'] == str(symbol + 'SHORT3'):
            short = True
        # if symboljson[eachticket]['_comment'] == str(symbol + 'LONG1') or str(symbol + 'LONG2'):
        if rawsymboljson['_trades'][eachticket]['_comment'] == str(symbol + 'LONG1') or rawsymboljson['_trades'][eachticket]['_comment'] == str(
                symbol + 'LONG2') or rawsymboljson['_trades'][eachticket]['_comment'] == str(symbol + 'LONG3'):
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
                if symboljson[eachticket]['_comment'] == str(symbol + 'SHORT1') or symboljson[eachticket][
                    '_comment'] == str(symbol + 'LONG1'):
                    level = 1
        else:
            level = 3
            for eachticket in symboltickets:
                if symboljson[eachticket]['_comment'] == str(symbol + 'SHORT3') or symboljson[eachticket][
                    '_comment'] == str(symbol + 'LONG3'):
                    level = 4
    return level


##########################################################################
# SOME USEFUL FUNCTIONS

def truncate(f, n):
    return math.floor(f * 10 ** n) / 10 ** n


def DECPLACES(number):
    number = str(number)
    decplaces = decimal.Decimal(number)
    decplaces = abs(decplaces.as_tuple().exponent)
    return decplaces


##########################################################################
# PRICELIST CREATOR

def PINTERVALS(price, atr, direction):
    # checking if last digit is a zero and changing to a one instead for upcoming decimalplaces function

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
    for i in range(1, 16 + 1):
        pricelist.append(decformat % price)
        price = price + atr

    return pricelist


##########################################################################
# GET ACCOUNT INFORMATION

def GETACCOUNTINFO():
    accountinfojson = None
    _zmq._set_response_()

    _zmq._DWX_MTX_GET_ACCOUNT_INFORMATION_()
    time.sleep(1)

    while accountinfojson is None:
        accountinfojson = _zmq._get_response_()
        if accountinfojson is None:
            time.sleep(.01)
    return accountinfojson


##########################################################################
# GET PRICE

def GETCURRENTPRICE(symbol):
    pricejson = None
    _zmq._set_response_()

    _zmq._DWX_MTX_PRICE_REQUEST_(symbol)
    time.sleep(1)

    while pricejson is None:
        pricejson = _zmq._get_response_()
        if pricejson is None:
            time.sleep(.01)

    bidasklist = list(pricejson)
    averageprice = sum(bidasklist)
    averageprice = averageprice / 2

    return averageprice


##########################################################################
# LOTSIZE CALCULATOR

def INITIALLOTSIZE(symbol, price, stoploss, riskpercent, accountinfojson):
    # checking if symbol is a yen cross
    JPY_pair = False

    if (symbol[3:6]) == 'JPY':
        JPY_pair = True

    # changing multiplier for yen
    if JPY_pair == True:
        multiplier = 0.01
        multiplier2 = 0.00001

    else:
        multiplier = 0.0001
        multiplier2 = 0.0000001

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
        if (symbol[:3]) == 'XAU':
            units = pip_value / multiplier
            units = units * 0.0001
        else:
            # pip_value = pip_value * price
            units = pip_value / multiplier
            units = units * 0.0000001


    elif method == 2:
        pip_value = pip_value * price
        units = pip_value / multiplier
        units = units * 0.0000001


    else:  # is method 0
        units = pip_value / multiplier
        units = units * multiplier2

    # implementing logic for rounding up..only rounds up lotsize from 8 instead of 5.
    units = str(units)
    lotsize = 1
    if int(units[4]) > 7:
        lotsize = ('%.2f' % float(units))
        lotsize = float(lotsize)

    else:
        lotsize = truncate(float(units), 2)

    return lotsize


##########################################################################
# CALCULATES SLPOINTS

def SLPOINTCALC(price, slprice, decplaces1):
    multiplier = 1
    slpoints = (float(price) - float(slprice))
    if slpoints > 0:
        multiplier = -1

    # decplaces1 = DECPLACES(price)
    decplaces2 = DECPLACES(slpoints)

    tempslpoints = abs(slpoints)

    tempslpoints = str(tempslpoints)
    slstrlength = len(tempslpoints)
    slpredecimalplaces = slstrlength - decplaces2
    slpredecimalplaces = slpredecimalplaces - 1

    if slpredecimalplaces == 1:
        if tempslpoints[0] == '0':
            slpredecimalplaces = 0

    slpointquotient = 10 ** slpredecimalplaces
    slpoints = float(slpoints)

    slpoints = slpoints / slpointquotient

    decplaces2 = DECPLACES(slpoints)

    sldifference = abs(decplaces2 - decplaces1)

    slpoints = str(slpoints)

    points = slpoints[-1 * (decplaces2):-1 * (sldifference)]

    slpoints = float(points)
    slpoints = (slpoints * slpointquotient) * multiplier

    # slpoints = float(points)*multiplier
    return slpoints


##########################################################################

# SENDS TRADE GRID DEPENDING ON LEVEL/STATE

def TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces1):
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

    # decplaces1 = DECPLACES(firstprice)
    decplaces2 = DECPLACES(slpoints)
    decplaces3 = DECPLACES(tppoints)

    tppoints = str(tppoints)
    tpstrlength = len(tppoints)
    slpoints = str(slpoints)
    slstrlength = len(slpoints)

    slpredecimalplaces = slstrlength - decplaces2
    slpredecimalplaces = slpredecimalplaces - 1

    tppredecimalplaces = tpstrlength - decplaces3
    tppredecimalplaces = tppredecimalplaces - 1

    if slpredecimalplaces == 1:
        if slpoints[0] == '0':
            slpredecimalplaces = 0

    if tppredecimalplaces == 1:
        if tppoints[0] == '0':
            tppredecimalplaces = 0

    tppointquotient = 10 ** tppredecimalplaces
    tppoints = float(tppoints) / tppointquotient

    slpointquotient = 10 ** slpredecimalplaces
    slpoints = float(slpoints) / slpointquotient

    decplaces2 = DECPLACES(slpoints)
    decplaces3 = DECPLACES(tppoints)

    sldifference = abs(decplaces2 - decplaces1)
    tpdifference = abs(decplaces3 - decplaces1)

    slpoints = str(slpoints)

    points = slpoints[-1 * (decplaces2):-1 * (sldifference)]

    slpoints = int(points)
    slpoints = slpoints * slpointquotient

    tppoints = str(tppoints)
    points2 = tppoints[-1 * (decplaces3):-1 * (tpdifference)]

    tppoints = float(points2)

    tppoints = tppoints * tppointquotient

    # splitting the pricelist in two..the first for scaling in lotsize (LEVEL 1) and the second for fixed lotsize (LEVEL 2)

    levellist1 = pricelist[:3]
    levellist2 = pricelist[3:]

    # declaring current lotsize variable for for loop
    curr_lotsize = lotsize1

    # sending trades, with appropriate comments, depending on level

    if level < 3:
        currcomment = comment + '1'

        for curr_price in levellist1:
            time.sleep(2)
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price, slpoints, tppoints, currcomment, curr_lotsize,
                                        magic, 0)
            curr_lotsize = curr_lotsize + lotsize1
            tppoints = tppoints - (10 * atr)

        time.sleep(2)
        currcomment = comment + '2'
        # tppoints = tppoints * 1000

        for curr_price2 in levellist2:
            fixedlotsize = lotsize1 * 3
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price2, slpoints, 10000, currcomment, fixedlotsize,
                                        magic, 0)
            time.sleep(2)

    elif level == 3:
        currcomment = comment + '3'
        for curr_price in levellist1:
            fixedlotsize = lotsize1 * 3
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price, slpoints, 10000, currcomment, fixedlotsize,
                                        magic, 0)
            time.sleep(2)

        time.sleep(2)
        currcomment = comment + '3'

        for curr_price2 in levellist2:
            fixedlotsize = lotsize1 * 3
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price2, slpoints, 10000, currcomment, fixedlotsize,
                                        magic, 0)
            time.sleep(2)

    elif level == 4:
        currcomment = comment + '3'
        for curr_price in levellist1:
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price, slpoints, tppoints, currcomment, curr_lotsize,
                                        magic, 0)
            time.sleep(2)
            curr_lotsize = curr_lotsize + lotsize1
            tppoints = tppoints - (10 * atr)

        time.sleep(2)
        currcomment = comment + '3'

        for curr_price2 in levellist2:
            fixedlotsize = lotsize1 * 3
            _zmq._DWX_MTX_SEND_COMMAND_('OPEN', type, symbol, curr_price2, slpoints, 10000, currcomment, fixedlotsize,
                                        magic, 0)
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

def TRADELOGICMODULE(symbol, symboltradesjson, symboltickets, pricelist, magic, direction, lotsize1, stoploss, level,
                     pnl, atr, decplaces):
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
        TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces)

    elif level == 1:

        CLOSEALLACTIVE(symbol)
        time.sleep(2)
        DELETEALLPENDINGS(symbol)
        time.sleep(2)
        TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces)

    elif level == 2:
        if pnl < 0:

            CLOSEALLACTIVE(symbol)
            time.sleep(2)
            DELETEALLPENDINGS(symbol)
            time.sleep(2)
            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces)

        else:

            DELETEALLPENDINGS(symbol)
            time.sleep(2)
            CLOSELOSINGTRADES(symboltradesjson, symboltickets)
            time.sleep(2)

            # updating symbol json and ticketlist

            newsymboltradesjson = GETALLSYMBOLTRADES(symbol)
            time.sleep(2)
            # print(newsymboltradesjson)
            symboltickets = SYMBOLTICKETS(newsymboltradesjson, symbol)
            time.sleep(1)

#   HERE WE NEED.   IF DIRECTION IS SAME AS ANCHOR TRADES, SET SL OF OTHER POSITION TO BREAKEVEN.
            newslprice = pricelist[3]
            marketprice = GETCURRENTPRICE(symbol)
            breakeven = False
            if direction == 'short':
                if float(marketprice) > float(newslprice):
                    breakeven = True
            elif direction == 'long':
                if float(marketprice) < float(newslprice):
                    breakeven = True

            if breakeven is True:
                for eachticket2 in symboltickets:
                    _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket2, 0, 10000)
                    time.sleep(1)
            else:
            # setting stoplosses of existing position to level 1 tp of new position

                for eachticket in symboltickets:
                    curr_price = symboltradesjson[eachticket]['_open_price']
                    slpoints = SLPOINTCALC(curr_price, newslprice, decplaces)
                    _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket, slpoints, 10000)
                    time.sleep(1)

            activetrades = len(symboltickets)
            for activetrade in range(activetrades):
                pricelist.pop()

            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces)

    elif level == 3:
        DELETEALLPENDINGS(symbol)
        time.sleep(1)

        # Closing all opposing trades 2
        for eachticket in symboltickets:

            if symboltradesjson['_trades'][eachticket]['_comment'] == (symbol + commentstring + '1') or \
                    symboltradesjson['_trades'][eachticket]['_comment'] == (symbol + commentstring + '2'):
                _zmq._DWX_MTX_CLOSE_TRADE_BY_TICKET_(eachticket)
                time.sleep(1)

        symboltradesjson = GETALLSYMBOLTRADES(symbol)
        # RAWSYMBOLJSON = GETALLSYMBOLTRADES(SYMBOL)
        time.sleep(1)
        symboltickets = SYMBOLTICKETS(symboltradesjson, symbol)
        time.sleep(1)

        for eachticket in symboltickets:
            curr_price = symboltradesjson['_trades'][eachticket]['_open_price']
            slpoints = SLPOINTCALC(curr_price, stoploss, decplaces)
            _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket, slpoints, 10000)

        activetrades = len(symboltickets)
        for activetrade in range(activetrades):
            pricelist.pop()

        TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces)

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

            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces)

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
                slpoints = SLPOINTCALC(curr_price, newslprice, decplaces)
                _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket, slpoints, 10000)
                time.sleep(1)

            activetrades = len(symboltickets)
            for activetrade in range(activetrades):
                pricelist.pop()

            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces)


##########################################################################

######################### RISK MANAGEMENT PORTION #########################

##########################################################################
# SETS TRADES TO BREAKEVEN AND RETURNS A LIST OF TICKETS FOR EXPOSED TRADES

def RLISTBREAKEVEN(symbol, symboljson, decplaces, atr, direction):
    # retrieving ticketlist
    symboltickets = SYMBOLTICKETS(symboljson, symbol)

    # creating double atr variable, decimal format multiplier, and declaring lists
    doubleatr = atr * 2
    multiplier = 10 ** (decplaces - 1)
    exposedtickets = []
    risktickets = []

    # designating which trade type to ignore for exposed tickets list

    ignoretradetype = 'error'
    if direction == 'long':
        ignoretradetype = 1
    elif direction == 'short':
        ignoretradetype = 0

    # checking exposed ticket criteria and appending exposed tickets to list.

    for eachticket in symboltickets:
        if symboljson['_trades'][eachticket]['_type'] == ignoretradetype:
            print(eachticket)
            print('is a hedge trade.  ignoring.')

        elif symboljson['_trades'][eachticket]['_SL'] == symboljson['_trades'][eachticket]['_open_price']:
            print(eachticket)
            print('has broken even')

        else:
            exposedtickets.append(eachticket)

    # getting current price, checking if each trade has gone over 2atr in profit, and setting to breakeven

    currentprice = GETCURRENTPRICE(symbol)
    for eachticket2 in exposedtickets:
        if symboljson['_trades'][eachticket2]['_pnl'] > 0:
            tickprice = symboljson['_trades'][eachticket2]['_open_price']
            pricediff = abs(tickprice - currentprice)
            pricediff = pricediff * multiplier
            print(pricediff)
            print(doubleatr)
            print(decplaces)
            if pricediff >= doubleatr:

                print(eachticket)
                print('should breakeven')
                _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket2, 0, 10000)
                time.sleep(1)

            # spitting out remainding trades to new risktickets list
            else:
                risktickets.append(eachticket2)

        else:
            risktickets.append(eachticket2)

    return risktickets


##########################################################################
# CREATES A LIST OF PRICES FOR EXPOSED TRADES

def RISKPRICELISTER(risktickets, symboljson):
    riskprices = []

    for eachticket in risktickets:
        price = symboljson['_trades'][eachticket]['_open_price']
        riskprices.append(price)
    return riskprices


##########################################################################
# CREATES A LIST OF LOTSIZES FOR EXPOSED TRADES
def RISKLOTLISTER(risktickets, symboljson, direction):
    risklotsizes = []
    dirvalue = 0

    if direction == 'long':
        dirvalue = 1
    elif direction == 'short':
        dirvalue = -1

    for eachticket in risktickets:
        lotsize = symboljson['_trades'][eachticket]['_lots']
        lotsize = lotsize * dirvalue
        risklotsizes.append(lotsize)
    return risklotsizes


##########################################################################
# RETURNS BREAKEVEN PRICE OF ENTIRE POSITION
def POSITIONBREAKEVENPRICE(riskprices, risklotsizes):
    lotarray = np.array(risklotsizes)
    pricearray = np.array(riskprices)

    topsum = np.sum(lotarray * pricearray)
    bottomsum = np.sum(lotarray)

    breakeven = topsum / bottomsum
    print(riskprices)
    print(breakeven)

    return breakeven


##########################################################################
# CALCULATES STOPLOSS OF ENTIRE POSITION GIVEN TOTAL LOTSIZE AND BREAKEVEN LEVELS

def XPERCENTSL(symbol, direction, lotsize, breakeven, riskpercent, accountinfojson):
    # checking if symbol is a yen cross
    JPY_pair = False

    if (symbol[3:6]) == 'JPY':
        JPY_pair = True

    # changing multiplier for yen
    if JPY_pair == True:
        multiplier = 0.01
        multiplier2 = 0.00001
    else:
        multiplier = 0.0001
        multiplier2 = 0.0000001
    # determining calculation method based on USD account currency

    if (symbol[3:6]) == 'USD':
        method = 1
    elif (symbol[:3]) == 'USD':
        method = 2
    else:
        method = 3

    # floating inputs
    breakeven = float(breakeven)
    lotsize = float(lotsize)
    riskpercent = float(riskpercent)

    # converting account json to list and accessing balance value
    tempaccinfo = list(accountinfojson)
    accbalance = (tempaccinfo[0])
    accbalance = float(accbalance)

    # doing calculation depending on method

    if method == 1:
        if (symbol[:3]) == 'XAU':
            lotsize = lotsize / 0.0001
            pip_value = lotsize * multiplier

        else:
            lotsize = lotsize / 0.0000001
            pip_value = lotsize * multiplier

    elif method == 2:
        lotsize = lotsize / 0.0000001
        pip_value = lotsize * multiplier
        pip_value = pip_value / breakeven

    else:  # is method 0
        lotsize = lotsize / multiplier2
        pip_value = lotsize * multiplier

    # completing calculation

    cash_risk = accbalance * riskpercent
    print(pip_value)
    thang = cash_risk / pip_value
    thang = thang * multiplier

    # determining direction

    if direction == 'short':
        thang = abs(thang)
    elif direction == 'long':
        thang = thang * -1
    else:
        print('ERROR GETTING DIRECTION')

    xpercentslprice = breakeven + thang

    return xpercentslprice


##########################################################################
# MODIFIES STOP LOSS OF EXPOSED TRADES TO DESIGNATED STOPLOSS (POSITIONSL)

def XPERCENTSLMODIFY(risktickets, symboljson, positionsl, decplaces):
    for eachticket in risktickets:

        if symboljson['_trades'][eachticket]['_SL'] != positionsl:
            curr_price = symboljson['_trades'][eachticket]['_open_price']
            slpoints = SLPOINTCALC(curr_price, positionsl, decplaces)
            slpoints = abs(slpoints)
            _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket, slpoints, 10000)
            time.sleep(1)


##########################################################################

##########################################################################
# INIT FUNCTION

def INIT():
    # SYMBOL = input('SYMBOL?')
    # PRICE = input('input price')
    # STOPLOSS = input('input stoploss price')

    #                        (skipping questionnaire for expedited testing rn, might have to do some formatting)
    SYMBOL = 'USDCAD'
    PRICE = '1.32641'  # made price and stoploss strings to avoid losing potential trailing 0s with float.
    STOPLOSS = '1.34257'
    PERCENT = 2  # (percent per symbol)

    # storing decimal places for later to avoid losing trailing 0.
    DECPLACES = decimal.Decimal(PRICE)
    DECPLACES = abs(DECPLACES.as_tuple().exponent)

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
    STARTPERCENT = PERCENT / 4  # using a fourth of designated percent for starting lotsize

    # assigning appropriate magic number..might be useful later

    if SYMBOL == 'EURUSD':
        MAGIC = 1
    elif SYMBOL == 'GBPUSD':
        MAGIC = 2
    elif SYMBOL == 'EURGBP':
        MAGIC = 3
    elif SYMBOL == 'USDCHF':
        MAGIC = 4
    elif SYMBOL == 'USDCAD':
        MAGIC = 5
    elif SYMBOL == 'USDJPY':
        MAGIC = 6
    elif SYMBOL == 'GBPJPY':
        MAGIC = 7
    elif SYMBOL == 'AUDUSD':
        MAGIC = 8
    elif SYMBOL == 'NZDUSD':
        MAGIC = 9
    elif SYMBOL == 'XAUUSD':
        MAGIC = 10
    else:
        MAGIC = 11

    # getting ATR
    ATR = GETATR(SYMBOL)

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
    LOTSIZE1 = INITIALLOTSIZE(SYMBOL, float(PRICE), float(STOPLOSS), STARTPERCENT, ACCOUNTINFOJSON)
    print(LOTSIZE1)

    # calculating existing position's pnl
    PNL = PNLhelper(SYMBOLTRADESJSON, SYMBTICKETS)

    # detecting level/state of existing position
    LEVEL = LEVELDETECT(SYMBOL, SYMBTICKETS, RAWSYMBOLJSON, SYMBOLTRADESJSON)
    print(LEVEL)

    # plugging everything into main strategy function
    TRADELOGICMODULE(SYMBOL, SYMBOLTRADESJSON, SYMBTICKETS, PRICELIST, MAGIC, DIRECTION, LOTSIZE1, float(STOPLOSS),
                     LEVEL, PNL, ATR, DECPLACES)


                                             #### RISK PORTION ####
    # this process is to loop over and over, setting trades to breakeven and trailing stoploss for exposed trades
    time.sleep(1)
    while True:

    # getting raw symbol json
        RAWSYMBOLJSON = GETALLSYMBOLTRADES(SYMBOL)

    # setting trades to breakeven and returning list of exposed tickets
        RISKTICKETS = RLISTBREAKEVEN(SYMBOL, RAWSYMBOLJSON, DECPLACES, ATR, DIRECTION)

        TRADEQUANTITY = len(RISKTICKETS)
        if TRADEQUANTITY > 0:

    # creating lists of prices and lots for exposed trades and calculating their breakeven level
            RISKPRICES = RISKPRICELISTER(RISKTICKETS, RAWSYMBOLJSON)
            RISKLOTSIZES = RISKLOTLISTER(RISKTICKETS, RAWSYMBOLJSON, DIRECTION)
            BREAKEVEN = POSITIONBREAKEVENPRICE(RISKPRICES, RISKLOTSIZES)

    # adding up all lotsizes
            tlotsize = np.array(RISKLOTSIZES)
            TOTALLOTSIZE = np.sum(tlotsize)

    # calculating and formatting exposed position's stop loss level
            ACCOUNTINFOJSON = GETACCOUNTINFO()
            POSITIONSL = XPERCENTSL(SYMBOL, DIRECTION, TOTALLOTSIZE, BREAKEVEN, PERCENT, ACCOUNTINFOJSON)

            DFORMAT = '%.' + str(DECPLACES) + 'f'
            POSITIONSL = (DFORMAT % POSITIONSL)
            print(POSITIONSL)

    # modifying stoplosses for exposed trades (position trailing stop)
            XPERCENTSLMODIFY(RISKTICKETS, RAWSYMBOLJSON, POSITIONSL, DECPLACES)

        else:
            time.sleep(.05)
