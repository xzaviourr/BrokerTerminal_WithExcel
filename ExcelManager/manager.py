import xlwings as xw
import os
import logging
from time import sleep
import pandas as pd

import settings
from Broker.alice_blue import Broker

class ExcelManager:
    """
    Manages live updates in excel
    """
    def __init__(self):
        self.logger = self.get_logger()
        self.__broker = Broker()  # Broker Object
        if self.__broker == None:
            exit(1)

        self.RUN_FLAG = 1
        self.load_excel()
        self.update_marketwatch()
    
    def get_logger(self):
        """
        Creates Alice Blue logger object
        """
        logger = logging.getLogger('Excel Logger')
        logger.setLevel(logging.DEBUG)
        stream_handler = logging.StreamHandler()
        file_handler = logging.FileHandler(os.path.join(settings.EXCEL_LOGS_FOLDER, "excel.log"))
        stream_handler.setLevel(logging.DEBUG)
        file_handler.setLevel(logging.DEBUG)
        stream_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(stream_format)
        file_handler.setFormatter(file_format)
        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)
        logger.info("logger initialized")
        return logger

    def load_excel(self):
        # CREATE OR LOAD CONNECTION OBJECT TO EXCEL FILE
        if not os.path.exists(settings.EXCEL_FILE):
            self.__workbook = xw.Book()
            self.__workbook.save(settings.EXCEL_FILE)
            self.logger.info("New excel file created and loaded")
        else:
            self.__workbook = xw.Book(settings.EXCEL_FILE)
            self.logger.info("Excel file loaded")

        sheets = ['Marketwatch', 'Orderbook', 'Profile', 'Instruments']
        for sheet in sheets:
            try:
                self.__workbook.sheets(sheet)
            except:
                self.__workbook.sheets.add(sheet)
                self.logger.info(f"New sheet added : {sheet}")
        
        # MARKETWATCH SHEET SETUP 
        # ==========================================================================
        self.__marketwatch_sheet = self.__workbook.sheets("Marketwatch")
        self.__marketwatch_sheet.range("a1:c2").merge()
        self.__marketwatch_sheet.range("l1:n1").merge()
        self.__marketwatch_sheet.range("a1:c2").value = [
            "ALICE BLUE TERMINAL"
        ]
        self.__marketwatch_sheet.range("l1:n1").value = [
            "MARKETWATCH"
        ]

        self.__marketwatch_sheet.range("a4:x4").value = [
            "S.No.", "Trading Symbol", 
            "Open", "High", "Low", "Close", "LTP",
            "Volume", "VWAP", "Best Buy", "Best Sell", "OI",
            "Transaction Type\n(BUY/SELL)", "Product Type\n(MIS/CNC/NRML)", 
            "Limit Price\n(=0 for Market order)", "Quantity\n(Lot size x No. of lots)", 
            "Stoploss", "Target", "Below or Above\n(BELOW/ABOVE)",
            "Future Price\n(Order will execute when LTP reaches this value)",
            "Entry Action\n(EXECUTE)", 
            "Order ID\n(WAITING / Order ID)", "Last Action", "Exit Action (EXIT / CANCEL / MODIFY)"
            ]

        self.__marketwatch_sheet.range(f"a5:a{5 + settings.MAX_TOKENS_IN_MARKETWATCH}").value = [[x] for x in range(settings.MAX_TOKENS_IN_MARKETWATCH)]
        # ==========================================================================

        # ORDERBOOK SHEET SETUP
        # ==========================================================================
        self.__orderbook_sheet = self.__workbook.sheets("Orderbook")
        self.__orderbook_sheet.range("a1:c2").merge()
        self.__orderbook_sheet.range("f1:g1").merge()
        self.__orderbook_sheet.range("a1:c2").value = [
            "ALICE BLUE TERMINAL"
        ]
        self.__orderbook_sheet.range("f1:g1").value = [
            "ORDER BOOK"
        ]
        self.__orderbook_sheet.range("a4:j4").value = [
            "S.No", "Date", "Order Id", "Transaction Type\n(BUY/SELL)",
            "Product Type\n(MIS/CNC/NRML)", "Trading Symbol",
            "Quantity\n(Lot size x No. of lots)", "Price", "Order Type",
            "Status\n(SUCCESS/REJECTED/CANCELLED)"
        ]

        clear_values = [[i+1, '', '', '', '', '', '', '', '', ''] for i in range(250)]
        self.__orderbook_sheet.range(f"a5:j{254}").value = clear_values

        # ==========================================================================

        # Profile SHEET SETUP
        # ==========================================================================
        self.__profile_sheet = self.__workbook.sheets("Profile")
        self.__profile_sheet.range("a1:c2").merge()
        self.__profile_sheet.range("f1:g1").merge()
        self.__profile_sheet.range("a1:c2").value = [
            "ALICE BLUE TERMINAL"
        ]
        self.__profile_sheet.range("f1:g1").value = [
            "PROFILE"
        ]
        self.__profile_sheet.range("a3:a8").value = [
            ["User ID"], ["Cash Margin"], ["Credits"], ["Exposure Margin"], ['Net'], ['Gross Exposure Value']
        ]
        # ==========================================================================
        self.logger.info("EXCEL FILE INITIALIZED AND LOADED SUCCESSFULLY")

        # Instruments SHEET SETUP
        # ==========================================================================
        self.__instrument_sheet = self.__workbook.sheets("Instruments")
        self.__instrument_sheet["A1"].options(pd.DataFrame, header=1, index=True, expand='table').value = self.__broker.instruments
        return

    def update_profile(self):
        """
        Update Profile Page
        """
        user_id, cash_margin, credits, exposure_margin, net, gross_exposure_value = self.__broker.get_margin()
        self.__profile_sheet.range("b3:b8").value = [[user_id], [cash_margin], [credits], [exposure_margin], [net], [gross_exposure_value]]

    def close_excel(self):
        self.RUN_FLAG = 0
        self.__workbook.close()

    def update_orderbook(self):
        """
        Updates order book for any new orders
        """
        orderbook = self.__broker.get_orderbook()
        l = len(orderbook)
        x = self.__broker
        for i in range(len(orderbook)):
            oid = orderbook[i][1] 
            orderbook[i][8] = self.__broker.get_status(oid)
        self.__orderbook_sheet.range(f"b5:j{4+l}").value = orderbook

    def place_orders(self, instrument_names):
        orders = self.__marketwatch_sheet.range(f"m5:x{settings.MAX_TOKENS_IN_MARKETWATCH + 5}").value
        # [Transaction type, Product Type, Limit Price, Quantity, Stoploss, Target, Below or Above, Future Price, Entry Action, Order ID, Last Action, Exit Action]
        for row_no in range(len(orders)):
            order = orders[row_no]
            current_action = ""
            if order[8] in ["EXECUTE", "execute"]:
                current_action = order[8]
            elif order[11] in ["MODIFY", "EXIT", "CANCEL"]:
                current_action = order[11]
            else:
                continue

            self.__broker.order_management(
                row_id=row_no,
                instrument_name=instrument_names[row_no],
                transaction_type=order[0],
                product_type=order[1],
                limit_price=order[2],
                quantity=order[3],
                stoploss=order[4],
                target=order[5],
                below_or_above=order[6],
                future_price=order[7],
                action=current_action
            )
            positions = self.__broker.get_positions()[row_no]
            self.__marketwatch_sheet.range(f"u{5+row_no}:x{5+row_no}").value = positions

        all_positions = [[x[1], x[2]] for x in self.__broker.get_positions()]
        self.__marketwatch_sheet.range(f"v5:w{4 + settings.MAX_TOKENS_IN_MARKETWATCH}").value = all_positions

    def update_marketwatch(self):
        order_flag = 0
        while True:
            if self.RUN_FLAG == 0:
                return
            instrument_names = self.__marketwatch_sheet.range(f"b5:b{settings.MAX_TOKENS_IN_MARKETWATCH + 5}").value
            ins = []
            for x in instrument_names:
                if self.__broker.check_if_trading_symbol_exists(x):
                    ins.append(self.__broker.get_instrument_name(x))
                else:
                    ins.append("")

            new_subscriptions = []
            remove_subscriptions = []
            
            for name in self.__broker.subscribed_list.keys():
                if name not in ins:
                    remove_subscriptions.append(name)

            for name in instrument_names:
                if name != None and name != "" and self.__broker.check_if_trading_symbol_exists(name):
                    n = self.__broker.get_instrument_name(name)
                    if n not in self.__broker.subscribed_list.keys():
                        new_subscriptions.append(n)
            
            if new_subscriptions != []:
                self.__broker.subscribe_tokens(new_subscriptions)
            # if remove_subscriptions != []:
            #     self.__broker.unsubscribe_tokens(remove_subscriptions)

            self.__broker.subscribed_list = {}
            for name in instrument_names:
                if name != None and name != "" and self.__broker.check_if_trading_symbol_exists(name):
                    n = self.__broker.get_instrument_name(name)
                    self.__broker.subscribed_list[n] = 1

            ticker_values = self.__broker.get_ticker_values(ins)
            no_of_records = len(ticker_values)
            self.__marketwatch_sheet.range(f"c5:l{no_of_records + 5}").value = ticker_values

            # Check order placements
            order_flag = (order_flag + 1)%1
            if order_flag == 0:
                self.place_orders(ins)
                self.update_orderbook()
                self.update_profile()
            sleep(settings.MARKETWATCH_REFRESH_TIME)