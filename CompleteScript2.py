# -*- coding: utf-8 -*-

"""
    DWX_ZeroMQ_Connector_v2_0_2_RC8.py
    --
    @author: Darwinex Labs (www.darwinex.com)

    Copyright (c) 2017-2019, Darwinex. All rights reserved.

    Licensed under the BSD 3-Clause License, you may not use this file except
    in compliance with the License.

    You may obtain a copy of the License at:
    https://opensource.org/licenses/BSD-3-Clause
"""

# IMPORT zmq library
# import zmq, time
import zmq
from time import sleep
from pandas import DataFrame, Timestamp
from threading import Thread


class DWX_ZeroMQ_Connector():
    """
    Setup ZeroMQ -> MetaTrader Connector
    """

    def __init__(self,
                 _ClientID='DLabs_Python',  # Unique ID for this client
                 _host='localhost',  # Host to connect to
                 _protocol='tcp',  # Connection protocol
                 _PUSH_PORT=32768,  # Port for Sending commands
                 _PULL_PORT=32769,  # Port for Receiving responses
                 _SUB_PORT=32770,  # Port for Subscribing for prices
                 _delimiter=';',
                 _pulldata_handlers=[],  # Handlers to process data received through PULL port.
                 _subdata_handlers=[],  # Handlers to process data received through SUB port.
                 _verbose=True):  # String delimiter

        # Strategy Status (if this is False, ZeroMQ will not listen for data)
        self._ACTIVE = True

        # Client ID
        self._ClientID = _ClientID

        # ZeroMQ Host
        self._host = _host

        # Connection Protocol
        self._protocol = _protocol

        # ZeroMQ Context
        self._ZMQ_CONTEXT = zmq.Context()

        # TCP Connection URL Template
        self._URL = self._protocol + "://" + self._host + ":"

        # Ports for PUSH, PULL and SUB sockets respectively
        self._PUSH_PORT = _PUSH_PORT
        self._PULL_PORT = _PULL_PORT
        self._SUB_PORT = _SUB_PORT

        # Handlers for received data (pull and sub ports)
        self._pulldata_handlers = _pulldata_handlers
        self._subdata_handlers = _subdata_handlers

        # Create Sockets
        self._PUSH_SOCKET = self._ZMQ_CONTEXT.socket(zmq.PUSH)
        self._PUSH_SOCKET.setsockopt(zmq.SNDHWM, 1)

        self._PULL_SOCKET = self._ZMQ_CONTEXT.socket(zmq.PULL)
        self._PULL_SOCKET.setsockopt(zmq.RCVHWM, 1)

        self._SUB_SOCKET = self._ZMQ_CONTEXT.socket(zmq.SUB)

        # Bind PUSH Socket to send commands to MetaTrader
        self._PUSH_SOCKET.connect(self._URL + str(self._PUSH_PORT))
        print("[INIT] Ready to send commands to METATRADER (PUSH): " + str(self._PUSH_PORT))

        # Connect PULL Socket to receive command responses from MetaTrader
        self._PULL_SOCKET.connect(self._URL + str(self._PULL_PORT))
        print("[INIT] Listening for responses from METATRADER (PULL): " + str(self._PULL_PORT))

        # Connect SUB Socket to receive market data from MetaTrader
        self._SUB_SOCKET.connect(self._URL + str(self._SUB_PORT))

        # Initialize POLL set and register PULL and SUB sockets
        self._poller = zmq.Poller()
        self._poller.register(self._PULL_SOCKET, zmq.POLLIN)
        self._poller.register(self._SUB_SOCKET, zmq.POLLIN)

        # Start listening for responses to commands and new market data
        self._string_delimiter = _delimiter

        # BID/ASK Market Data Subscription Threads ({SYMBOL: Thread})
        self._MarketData_Thread = None

        # Begin polling for PULL / SUB data
        self._MarketData_Thread = Thread(target=self._DWX_ZMQ_Poll_Data_, args=(self._string_delimiter))
        self._MarketData_Thread.start()

        # Market Data Dictionary by Symbol (holds tick data) or Instrument (holds OHLC data)
        self._Market_Data_DB = {}  # {SYMBOL: {TIMESTAMP: (BID, ASK)}}
        # {SYMBOL: {TIMESTAMP: (TIME, OPEN, HIGH, LOW, CLOSE, TICKVOL, SPREAD, VOLUME)}}

        # Temporary Order STRUCT for convenience wrappers later.
        self.temp_order_dict = self._generate_default_order_dict()

        # Thread returns the most recently received DATA block here
        self._thread_data_output = None

        # Verbosity
        self._verbose = _verbose

    ##########################################################################

    """
    Set Status (to enable/disable strategy manually)
    """

    def _setStatus(self, _new_status=False):

        self._ACTIVE = _new_status
        print("\n**\n[KERNEL] Setting Status to {} - Deactivating Threads.. please wait a bit.\n**".format(_new_status))

    ##########################################################################

    """
    Function to send commands to MetaTrader (PUSH)
    """

    def remote_send(self, _socket, _data):

        try:
            _socket.send_string(_data, zmq.DONTWAIT)
        except zmq.error.Again:
            print("\nResource timeout.. please try again.")
            sleep(0.000000001)

    ##########################################################################

    def _get_response_(self):
        return self._thread_data_output

    ##########################################################################

    def _set_response_(self, _resp=None):
        self._thread_data_output = _resp

    ##########################################################################

    def _valid_response_(self, _input='zmq'):

        # Valid data types
        _types = (dict, DataFrame)

        # If _input = 'zmq', assume self._zmq._thread_data_output
        if isinstance(_input, str) and _input == 'zmq':
            return isinstance(self._get_response_(), _types)
        else:
            return isinstance(_input, _types)

        # Default
        return False

    ##########################################################################

    """
    Function to retrieve data from MetaTrader (PULL or SUB)
    """

    def remote_recv(self, _socket):

        try:
            msg = _socket.recv_string(zmq.DONTWAIT)
            return msg
        except zmq.error.Again:
            print("\nResource timeout.. please try again.")
            sleep(0.000001)

        return None

    ##########################################################################

    # Convenience functions to permit easy trading via underlying functions.

    # OPEN ORDER
    def _DWX_MTX_NEW_TRADE_(self, _order=None):

        if _order is None:
            _order = self._generate_default_order_dict()

        # Execute
        self._DWX_MTX_SEND_COMMAND_(**_order)

    # MODIFY ORDER
    def _DWX_MTX_MODIFY_TRADE_BY_TICKET_(self, _ticket, _SL, _TP):  # in points

        try:
            self.temp_order_dict['_action'] = 'MODIFY'
            self.temp_order_dict['_SL'] = _SL
            self.temp_order_dict['_TP'] = _TP
            self.temp_order_dict['_ticket'] = _ticket

            # Execute
            self._DWX_MTX_SEND_COMMAND_(**self.temp_order_dict)

        except KeyError:
            print("[ERROR] Order Ticket {} not found!".format(_ticket))

    # CLOSE ORDER
    def _DWX_MTX_CLOSE_TRADE_BY_TICKET_(self, _ticket):

        try:
            self.temp_order_dict['_action'] = 'CLOSE'
            self.temp_order_dict['_ticket'] = _ticket

            # Execute
            self._DWX_MTX_SEND_COMMAND_(**self.temp_order_dict)

        except KeyError:
            print("[ERROR] Order Ticket {} not found!".format(_ticket))

    # CLOSE PARTIAL
    def _DWX_MTX_CLOSE_PARTIAL_BY_TICKET_(self, _ticket, _lots):

        try:
            self.temp_order_dict['_action'] = 'CLOSE_PARTIAL'
            self.temp_order_dict['_ticket'] = _ticket
            self.temp_order_dict['_lots'] = _lots

            # Execute
            self._DWX_MTX_SEND_COMMAND_(**self.temp_order_dict)

        except KeyError:
            print("[ERROR] Order Ticket {} not found!".format(_ticket))

    # CLOSE MAGIC
    def _DWX_MTX_CLOSE_TRADES_BY_MAGIC_(self, _magic):

        try:
            self.temp_order_dict['_action'] = 'CLOSE_MAGIC'
            self.temp_order_dict['_magic'] = _magic

            # Execute
            self._DWX_MTX_SEND_COMMAND_(**self.temp_order_dict)

        except KeyError:
            pass

    # CLOSE TYPE
    def _DWX_MTX_CLOSE_TRADES_BY_TYPEANDSYMBOL_(self, _type, _symbol):

        try:
            self.temp_order_dict['_action'] = 'CLOSE_TYPE'
            self.temp_order_dict['_type'] = _type
            self.temp_order_dict['_symbol'] = _symbol

            # Execute
            self._DWX_MTX_SEND_COMMAND_(**self.temp_order_dict)

        except KeyError:
            pass

    # CLOSE ALL TRADES
    def _DWX_MTX_CLOSE_ALL_TRADES_(self):

        try:
            self.temp_order_dict['_action'] = 'CLOSE_ALL'

            # Execute
            self._DWX_MTX_SEND_COMMAND_(**self.temp_order_dict)

        except KeyError:
            pass

    # GET OPEN TRADES
    def _DWX_MTX_GET_ALL_OPEN_TRADES_(self):

        try:
            self.temp_order_dict['_action'] = 'GET_OPEN_TRADES'

            # Execute
            self._DWX_MTX_SEND_COMMAND_(**self.temp_order_dict)

        except KeyError:
            pass

    # GET OPEN TRADES
    def _DWX_MTX_GET_ALL_SYMBOL_TRADES_(self, _symbol):

        try:
            self.temp_order_dict['_action'] = 'GET_SYMBOL_TRADES'
            self.temp_order_dict['_symbol'] = _symbol
            # Execute
            self._DWX_MTX_SEND_COMMAND_(**self.temp_order_dict)


        except KeyError:
            pass

    # GET ACCOUNT INFO
    def _DWX_MTX_GET_ACCOUNT_INFORMATION_(self):

        try:

            # _msg = "{};{}".format('ACCOUNT', 0)
            #_msg = "{}".format('ACCOUNT')
            _msg = 'ACCOUNT'
            # self.remote_send(self._PUSH_SOCKET, _msg)
            #_msg = "{}".format('ACCOUNT')

            self.remote_send(self._PUSH_SOCKET, _msg)

        except KeyError:
            pass


    # DEFAULT ORDER DICT
    def _generate_default_order_dict(self):
        return ({'_action': 'OPEN',
                 '_type': 0,
                 '_symbol': 'EURUSD',
                 '_price': 0.0,
                 '_SL': 500,  # SL/TP in POINTS, not pips.
                 '_TP': 500,
                 '_comment': 'DWX_Python_to_MT',
                 '_lots': 0.01,
                 '_magic': 123456,
                 '_ticket': 0})

    # DEFAULT DATA REQUEST DICT
    def _generate_default_data_dict(self):
        return ({'_action': 'DATA',
                 '_symbol': 'EURUSD',
                 '_timeframe': 1440,  # M1 = 1, M5 = 5, and so on..
                 '_start': '2018.12.21 17:00:00',  # timestamp in MT4 recognized format
                 '_end': '2018.12.21 17:05:00'})

    # DEFAULT HIST REQUEST DICT
    def _generate_default_hist_dict(self):
        return ({'_action': 'HIST',
                 '_symbol': 'EURUSD',
                 '_timeframe': 1,  # M1 = 1, M5 = 5, and so on..
                 '_start': '2018.12.21 17:00:00',  # timestamp in MT4 recognized format
                 '_end': '2018.12.21 17:05:00'})

    ##########################################################################
    """
    Function to construct messages for sending DATA commands to MetaTrader
    """

    def _DWX_MTX_SEND_MARKETDATA_REQUEST_(self,
                                          _symbol='EURUSD',
                                          _timeframe=1,
                                          _start='2019.01.04 17:00:00',
                                          _end=Timestamp.now().strftime('%Y.%m.%d %H:%M:00')):
        # _end='2019.01.04 17:05:00'):

        _msg = "{};{};{};{};{}".format('DATA',
                                       _symbol,
                                       _timeframe,
                                       _start,
                                       _end)
        # Send via PUSH Socket
        self.remote_send(self._PUSH_SOCKET, _msg)

    ##########################################################################
    """
    Function to construct messages for sending HIST commands to MetaTrader
    """

    def _DWX_MTX_SEND_MARKETHIST_REQUEST_(self,
                                          _symbol='EURUSD',
                                          _timeframe=1,
                                          _start='2019.01.04 17:00:00',
                                          _end=Timestamp.now().strftime('%Y.%m.%d %H:%M:00')):
        # _end='2019.01.04 17:05:00'):

        _msg = "{};{};{};{};{}".format('HIST',
                                       _symbol,
                                       _timeframe,
                                       _start,
                                       _end)
        # Send via PUSH Socket
        self.remote_send(self._PUSH_SOCKET, _msg)

    ##########################################################################
    """
    Function to construct messages for sending TRACK_PRICES commands to MetaTrader
    """

    def _DWX_MTX_SEND_TRACKPRICES_REQUEST_(self,
                                           _symbols=['EURUSD']):
        _msg = 'TRACK_PRICES'
        for s in _symbols:
            _msg = _msg + ";{}".format(s)

        # Send via PUSH Socket
        self.remote_send(self._PUSH_SOCKET, _msg)

    ##########################################################################
    """
    Function to construct messages for sending TRACK_RATES commands to MetaTrader
    """

    def _DWX_MTX_SEND_TRACKRATES_REQUEST_(self,
                                          _instruments=[('EURUSD_M1', 'EURUSD', 1)]):
        _msg = 'TRACK_RATES'
        for i in _instruments:
            _msg = _msg + ";{};{}".format(i[1], i[2])

        # Send via PUSH Socket
        self.remote_send(self._PUSH_SOCKET, _msg)

    ##########################################################################
    """
    Function to construct messages for sending Trade commands to MetaTrader
    """

    def _DWX_MTX_SEND_COMMAND_(self, _action='OPEN', _type=0,
                               _symbol='EURUSD', _price=0.0,
                               _SL=50, _TP=50, _comment="Python-to-MT",
                               _lots=0.01, _magic=123456, _ticket=0):

        _msg = "{};{};{};{};{};{};{};{};{};{};{}".format('TRADE', _action, _type,
                                                         _symbol, _price,
                                                         _SL, _TP, _comment,
                                                         _lots, _magic,
                                                         _ticket)

        # Send via PUSH Socket
        self.remote_send(self._PUSH_SOCKET, _msg)

        """
         compArray[0] = TRADE or DATA
         compArray[1] = ACTION (e.g. OPEN, MODIFY, CLOSE)
         compArray[2] = TYPE (e.g. OP_BUY, OP_SELL, etc - only used when ACTION=OPEN)

         For compArray[0] == DATA, format is: 
             DATA|SYMBOL|TIMEFRAME|START_DATETIME|END_DATETIME

         // ORDER TYPES: 
         // https://docs.mql4.com/constants/tradingconstants/orderproperties

         // OP_BUY = 0
         // OP_SELL = 1
         // OP_BUYLIMIT = 2
         // OP_SELLLIMIT = 3
         // OP_BUYSTOP = 4
         // OP_SELLSTOP = 5

         compArray[3] = Symbol (e.g. EURUSD, etc.)
         compArray[4] = Open/Close Price (ignored if ACTION = MODIFY)
         compArray[5] = SL
         compArray[6] = TP
         compArray[7] = Trade Comment
         compArray[8] = Lots
         compArray[9] = Magic Number
         compArray[10] = Ticket Number (MODIFY/CLOSE)
         """
        # pass

    ##########################################################################

    """
    Function to check Poller for new reponses (PULL) and market data (SUB)
    """

    def _DWX_ZMQ_Poll_Data_(self,
                            string_delimiter=';'):

        while self._ACTIVE:

            sockets = dict(self._poller.poll())

            # Process response to commands sent to MetaTrader
            if self._PULL_SOCKET in sockets and sockets[self._PULL_SOCKET] == zmq.POLLIN:

                try:

                    msg = self._PULL_SOCKET.recv_string(zmq.DONTWAIT)

                    # If data is returned, store as pandas Series
                    if msg != '' and msg != None:

                        try:
                            _data = eval(msg)

                            self._thread_data_output = _data
                            if self._verbose:
                                print(_data)  # default logic
                            # invokes data handlers on pull port
                            for hnd in self._pulldata_handlers:
                                hnd.onPullData(_data)

                        except Exception as ex:
                            _exstr = "Exception Type {0}. Args:\n{1!r}"
                            _msg = _exstr.format(type(ex).__name__, ex.args)
                            print(_msg)

                except zmq.error.Again:
                    pass  # resource temporarily unavailable, nothing to print
                except ValueError:
                    pass  # No data returned, passing iteration.
                except UnboundLocalError:
                    pass  # _symbol may sometimes get referenced before being assigned.

            # Receive new market data from MetaTrader
            if self._SUB_SOCKET in sockets and sockets[self._SUB_SOCKET] == zmq.POLLIN:

                try:
                    msg = self._SUB_SOCKET.recv_string(zmq.DONTWAIT)

                    if msg != "":
                        _timestamp = str(Timestamp.now('UTC'))[:-6]
                        _symbol, _data = msg.split(" ")
                        if len(_data.split(string_delimiter)) == 2:
                            _bid, _ask = _data.split(string_delimiter)
                            if self._verbose:
                                print("\n[" + _symbol + "] " + _timestamp + " (" + _bid + "/" + _ask + ") BID/ASK")
                                # Update Market Data DB
                            if _symbol not in self._Market_Data_DB.keys():
                                self._Market_Data_DB[_symbol] = {}
                            self._Market_Data_DB[_symbol][_timestamp] = (float(_bid), float(_ask))

                        elif len(_data.split(string_delimiter)) == 8:
                            _time, _open, _high, _low, _close, _tick_vol, _spread, _real_vol = _data.split(
                                string_delimiter)
                            if self._verbose:
                                print(
                                    "\n[" + _symbol + "] " + _timestamp + " (" + _time + "/" + _open + "/" + _high + "/" + _low + "/" + _close + "/" + _tick_vol + "/" + _spread + "/" + _real_vol + ") TIME/OPEN/HIGH/LOW/CLOSE/TICKVOL/SPREAD/VOLUME")
                                # Update Market Rate DB
                            if _symbol not in self._Market_Data_DB.keys():
                                self._Market_Data_DB[_symbol] = {}
                            self._Market_Data_DB[_symbol][_timestamp] = (
                            int(_time), float(_open), float(_high), float(_low), float(_close), int(_tick_vol),
                            int(_spread), int(_real_vol))
                        # invokes data handlers on sub port
                        for hnd in self._subdata_handlers:
                            hnd.onSubData(msg)

                except zmq.error.Again:
                    pass  # resource temporarily unavailable, nothing to print
                except ValueError:
                    pass  # No data returned, passing iteration.
                except UnboundLocalError:
                    pass  # _symbol may sometimes get referenced before being assigned.

    ##########################################################################

    """
    Function to subscribe to given Symbol's BID/ASK feed from MetaTrader
    """

    def _DWX_MTX_SUBSCRIBE_MARKETDATA_(self, _symbol, _string_delimiter=';'):

        # Subscribe to SYMBOL first.
        self._SUB_SOCKET.setsockopt_string(zmq.SUBSCRIBE, _symbol)

        if self._MarketData_Thread is None:
            self._MarketData_Thread = Thread(target=self._DWX_ZMQ_Poll_Data, args=(_string_delimiter))
            self._MarketData_Thread.start()

        print("[KERNEL] Subscribed to {} MARKET updates. See self._Market_Data_DB.".format(_symbol))

    """
    Function to unsubscribe to given Symbol's BID/ASK feed from MetaTrader
    """

    def _DWX_MTX_UNSUBSCRIBE_MARKETDATA_(self, _symbol):

        self._SUB_SOCKET.setsockopt_string(zmq.UNSUBSCRIBE, _symbol)
        print("\n**\n[KERNEL] Unsubscribing from " + _symbol + "\n**\n")

    """
    Function to unsubscribe from ALL MetaTrader Symbols
    """

    def _DWX_MTX_UNSUBSCRIBE_ALL_MARKETDATA_REQUESTS_(self):

        self._setStatus(False)
        self._MarketData_Thread = None

    ##########################################################################

########################END OF DARWINEX SCRIPT############################

##########################################################################
# initializing _zmq and importing some things

_zmq = DWX_ZeroMQ_Connector()

import decimal
import time
import math

##########################################################################
#REQUEST SYMBOL TRADES FROM MT4 AND STORE IN A JSON OBJECT

def GETALLSYMBOLTRADES (symbol):
    symboltradesjson = None
    _zmq._set_response_()
    _zmq._DWX_MTX_GET_ALL_SYMBOL_TRADES_(symbol)
    time.sleep(3)

    while symboltradesjson is None:
        symboltradesjson = _zmq._get_response_()
        if symboltradesjson is None:
            time.sleep(.01)
    return symboltradesjson

##########################################################################
##REQUEST ALL TRADES FROM MT4 AND STORE IN A JSON OBJECT

def GETALLTRADES ():
    opentradesjson = None
    _zmq._set_response_()
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
        pandl = opentradesjson[eachticket2]['_pnl']
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
    for i in range(1, 15 + 1):
        pricelist.append(decformat % price)
        price = price + atr

    return pricelist


##########################################################################
#GET ACCOUNT INFORMATION

def GETACCOUNTINFO ():
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
#LOTSIZE CALCULATOR

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
#CALCULATES SLPOINTS

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


#SENDS TRADE GRID DEPENDING ON LEVEL/STATE

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

def TRADELOGICMODULE(symbol, symboltradesjson, symboltickets, pricelist, magic, direction, lotsize1, stoploss, level, pnl, atr, decplaces):


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

            # setting stoplosses of existing position to level 1 tp of new position
            newslprice = pricelist[3]

            for eachticket in symboltickets:

                curr_price = symboltradesjson[eachticket]['_open_price']
                slpoints = SLPOINTCALC(curr_price, newslprice, decplaces)
                _zmq._DWX_MTX_MODIFY_TRADE_BY_TICKET_(eachticket, slpoints, 10000)
                time.sleep(1)


            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces)

    elif level == 3:
        DELETEALLPENDINGS(symbol)
        time.sleep(1)

        # Closing all opposing trades 2
        for eachticket in symboltickets:

            if symboltradesjson['_trades'][eachticket]['_comment'] == (symbol + commentstring + '1') or symboltradesjson['_trades'][eachticket]['_comment'] == (symbol + commentstring + '2'):
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

            TRADELOOP(symbol, pricelist, lotsize1, stoploss, direction, magic, level, atr, decplaces)


##########################################################################

def INIT():

    # SYMBOL = input('SYMBOL?')
    # PRICE = input('input price')
    # STOPLOSS = input('input stoploss price')
    # ATR = input('input ATR')
    # PERCENT = input('total risk percent')

    #                        (skipping questionnaire for expedited testing rn, might have to do some formatting)
    SYMBOL = 'XAUUSD'
    PRICE = '1407.48'       #made price and stoploss strings to avoid losing potential trailing 0s with float.
    STOPLOSS = '1432.76'
    ATR = 66            # tried  to auto-import ATR in a few ways, including putting the indicator in the EA code but I didn't know what I was doing lol. must be possible though.
    PERCENT = 2         #(percent per symbol)

    #storing decimal places for later to avoid losing trailing 0.
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
    elif SYMBOL =='XAUUSD':
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
    print(LOTSIZE1)

    # calculating existing position's pnl
    PNL = PNLhelper(SYMBOLTRADESJSON, SYMBTICKETS)

    # detecting level/state of existing position
    LEVEL = LEVELDETECT(SYMBOL, SYMBTICKETS, SYMBOLTRADESJSON)
    print(LEVEL)

    # plugging everything into main strategy function
    TRADELOGICMODULE(SYMBOL, SYMBOLTRADESJSON, SYMBTICKETS, PRICELIST, MAGIC, DIRECTION, LOTSIZE1, float(STOPLOSS), LEVEL, PNL, ATR, DECPLACES)

INIT()






