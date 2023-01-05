import datetime
from pya3 import *
import json
import logging
from time import sleep
import os
import threading

import settings

class AboveBelowWaitingQueueElement:
    """
    Object that stores properties of element present in above below waiting queue
    """
    def __init__(self, row_id, instrument_name, transaction_type, product_type, limit_price, quantity, stoploss, target, below_or_above, future_price):
        self.row_id = row_id    
        self.instrument_name = instrument_name
        self.transaction_type = transaction_type
        self.product_type = product_type
        self.limit_price = limit_price
        self.quantity = quantity
        self.stoploss = stoploss
        self.target = target
        self.below_or_above = below_or_above
        self.future_price = future_price

class StoplossTargetWaitingQueueElement:
    """
    Object that stores properties of element present in Stoploss Target Waiting Queue
    """
    def __init__(self, row_id=None, instrument_name=None, transaction_type=None, product_type=None, limit_price=None, quantity=None, stoploss=None, target=None):
        self.row_id = row_id    
        self.instrument_name = instrument_name
        self.transaction_type = transaction_type
        self.product_type = product_type
        self.limit_price = limit_price
        self.quantity = quantity
        self.stoploss = stoploss
        self.target = target
    
    def transfer_from_above_below(self, above_or_waiting_queue_element:AboveBelowWaitingQueueElement):
        """
        Create an object from an object of AboveBelowWaitingQueue
        """
        self.row_id = above_or_waiting_queue_element.row_id
        self.instrument_name =above_or_waiting_queue_element.instrument_name
        self.transaction_type = above_or_waiting_queue_element.transaction_type
        self.product_type = above_or_waiting_queue_element.product_type
        self.limit_price = above_or_waiting_queue_element.limit_price
        self.quantity = above_or_waiting_queue_element.quantity
        self.stoploss = above_or_waiting_queue_element.stoploss
        self.target = above_or_waiting_queue_element.target

class OpenWaitingQueueElement:
    """
    Object instance of open waiting queue
    """
    def __init__(self, row_id=None, instrument_name=None, transaction_type=None, product_type=None, limit_price=None, quantity=None):
        self.row_id = row_id    
        self.instrument_name = instrument_name
        self.transaction_type = transaction_type
        self.product_type = product_type
        self.limit_price = limit_price
        self.quantity = quantity
    
    def transfer_from_above_below(self, above_or_waiting_queue_element:AboveBelowWaitingQueueElement):
        """
        Create an object from an object of AboveBelowWaitingQueue
        """
        self.row_id = above_or_waiting_queue_element.row_id
        self.instrument_name =above_or_waiting_queue_element.instrument_name
        self.transaction_type = above_or_waiting_queue_element.transaction_type
        self.product_type = above_or_waiting_queue_element.product_type
        self.limit_price = above_or_waiting_queue_element.limit_price
        self.quantity = above_or_waiting_queue_element.quantity

class Broker:
    def __init__(self):
        # Application logger
        self.logger = self.get_logger()
        
        # Broker objects
        self.__conn = self.do_login()
        self.instruments = self.load_master_contracts()

        # Live streaming socket objects
        self.socket_active = False  # Is socket active or not
        self.subscribed_list = {}  # Dictionary of all the active tickers - {instrument_name: isactive}
        self.real_time_values = {}  # Dictionary of live streaming values - {instrument_token: [open, high, low, close, ltp, volume, VWAP, best_buy, best_sell, oi]}

        # Order management
        self.stoploss_target_waiting_queue = [] # [StoplossTargetWaitingQueueElement]
        self.above_below_waiting_queue = []    # [AboveBelowWaitingQueueElement]
        self.open_waiting_queue = []  # [OpenWaitingQueueElement]
        self.all_positions = [[None, None, None, None] for i in range(settings.MAX_TOKENS_IN_MARKETWATCH)] # [Entry Action, Order Id, Last Action, Exit Action]
        self.order_book = []    # [Date, OrderId, transaction type, product type, instrument name, Quantity, price, order type, status]

        # Thread
        self.thread_lock = threading.Lock()

        # Start websocket in the background
        self.__conn.start_websocket(
            socket_open_callback=self.socket_open, 
            socket_close_callback=self.socket_close,
                      socket_error_callback=self.socket_error, 
                      subscription_callback=self.feed_data, 
                      run_in_background=True,
                      market_depth=True)

        while self.socket_active == False:  # Wait for the socket to start
            self.logger.info("Waiting for socket streaming to start ...")
            sleep(settings.SLEEP_TIME_BETWEEN_ATTEMPTS) 

        # ==============================================================================================
        # Threads for order management
        self.above_below_thread = threading.Thread(target=self.manage_above_below)
        self.stoploss_target_thread = threading.Thread(target=self.manage_stoploss_target)
        self.above_below_thread.start()
        self.stoploss_target_thread.start()
    
    def get_logger(self):
        """
        Creates Alice Blue logger object
        """
        logger = logging.getLogger('Alice Blue Logger')
        logger.setLevel(logging.DEBUG)
        stream_handler = logging.StreamHandler()
        file_handler = logging.FileHandler(os.path.join(settings.BROKER_LOGS_FOLDER, "alice_blue.log"))
        stream_handler.setLevel(logging.DEBUG)
        file_handler.setLevel(logging.DEBUG)
        stream_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(stream_format)
        file_handler.setFormatter(file_format)
        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)
        logger.info("Logger initialized")
        return logger

    def load_master_contracts(self):
        """
        Downlaod and loads all the master contracts files
        """
        try:
            contract_types = ["BSE", "NFO", "MCX", "NSE", "CDS", "BFO", "INDICES"]
            columns = ['Exch', 'Exchange Segment', "Symbol", "Token", "Instrument Name", "Trading Symbol", "Option Type", "Expiry Date", "Strike Price", "Lot Size"]
            subcolumns = ['Exch', 'Exchange Segment', "Symbol", "Token", "Instrument Name", "Trading Symbol", 'Lot Size']
            instruments = pd.DataFrame(columns=columns)
            
            for contract in contract_types: 
                self.__conn.get_contract_master(contract)   # Download contract file
                if os.path.exists(os.path.join(settings.MASTER_CONTRACTS_DIR, f"{contract}.csv")):  # Remove file if exists
                    os.remove(os.path.join(settings.MASTER_CONTRACTS_DIR, f"{contract}.csv"))
                os.replace(os.path.join(settings.BASE_DIR, f"{contract}.csv"), os.path.join(settings.MASTER_CONTRACTS_DIR, f"{contract}.csv"))  # Move the file in the directory

                with open(os.path.join(settings.MASTER_CONTRACTS_DIR, f"{contract}.csv")) as file:
                    contract_data = pd.read_csv(file)
                    if contract == "INDICES":
                        contract_data = contract_data.rename({"exch": "Exch", "symbol": "Symbol", "token": "Token"}, axis=1)
                        contract_data['Instrument Name'] = contract_data['Symbol']
                        contract_data['Trading Symbol'] = contract_data['Symbol']
                        contract_data['Exch'] = "INDICES"
                    else:
                        if contract in ['NFO', 'MCX', 'BFO', 'CDS']:
                            contract_data = contract_data[columns]
                        else:
                            contract_data = contract_data[subcolumns]
                    instruments = pd.concat([instruments, contract_data])  
        except Exception as e:
            self.logger.error("MASTER CONTRACT LOADING FAILED")
            exit(1)
        return instruments

    def get_instrument_token(self, instrument_name):
        """
        Returns instrument token for the corresponding trading symbol
        """
        try:
            return int(self.instruments[self.instruments['Instrument Name'] == instrument_name].iloc[0]['Token'])
        except:
            self.logger.error(f"Instrument {instrument_name} cannot be found in the master contracts")
            return None

    def get_exch(self, instrument_name):
        """
        Returns Exchange for the corresponding trading symbol
        """
        try:
            return self.instruments[self.instruments['Instrument Name'] == instrument_name].iloc[0]['Exch']
        except:
            self.logger.error(f"Instrument {instrument_name} cannot be found in the master contracts")
            return None

    def do_login(self):
        """
        Performs broker authentication and returns the client object
        """
        try:
            with open(settings.BROKER_CREDENTIALS_FILE) as file:
                credentials = json.load(file)
        except Exception as e:
            self.logger.critical("Broker credentials file not found. Application exiting ..", exc_info=True)
            exit(1)

        LOGIN_RETRY_COUNT = 0
        while LOGIN_RETRY_COUNT < settings.MAX_BROKER_LOGIN_ATTEMPT_COUNT:
            LOGIN_RETRY_COUNT += 1
            try:
                conn = Aliceblue(
                    user_id=credentials['user_id'],
                    api_key=credentials['api_key']
                )
                session_id = conn.get_session_id()
                self.logger.info("Broker login successful")
                return conn
            except Exception as e:
                self.logger.error("Broker login failed. Retrying ..", exc_info=True)
            sleep(settings.SLEEP_TIME_BETWEEN_ATTEMPTS)
        self.logger.critical("Broker login max retries exceeded. Application exiting ..")
        exit(1)
        
    def check_if_instrument_exists(self, instrument_name):
        """
        Returns True if instrument name is valid
        """
        try:
            _ = self.instruments[self.instruments['Instrument Name'] == instrument_name].iloc[0]
            return True
        except:
            return False

    def check_if_trading_symbol_exists(self, trading_symbol):
        """
        Returns True if trading_symbol is valid
        """
        try:
            _ = self.instruments[self.instruments['Trading Symbol'] == trading_symbol].iloc[0]
            return True
        except:
            return False

    def get_instrument_name(self, trading_symbol):
        """
        Returns instrument name for the corresponding trading symbol
        """
        try:
            return str(self.instruments[self.instruments['Trading Symbol'] == trading_symbol].iloc[0]['Instrument Name'])
        except:
            self.logger.error(f"Instrument {trading_symbol} cannot be found in the master contracts")
            return None

    def get_trading_symbol(self, instrument_name):
        """
        Returns instrument name for the corresponding trading symbol
        """
        try:
            return str(self.instruments[self.instruments['Instrument Name'] == instrument_name].iloc[0]['Trading Symbol'])
        except:
            self.logger.error(f"Instrument {instrument_name} cannot be found in the master contracts")
            return None

    def get_status(self, oid):
        try:
            status = self.__conn.get_order_history(oid)
            if "Emsg" in status.keys():
                return ""
            else:
                s = status['Status']
                if s == "rejected":
                    s = f"Rejected due to - {status['RejReason']}"
            return s
        except:
            return ""

    def get_margin(self):
        try:
            margins = self.__conn.get_balance()
            profile = self.__conn.get_profile()
            account_id = profile['accountId']
            cash_margin = margins[0]['cashmarginavailable']
            credits = margins[0]['credits']
            exposure_margin = margins[0]['exposuremargin']
            net = margins[0]['net']
            gross_exposure_value = margins[0]['grossexposurevalue']
        except Exception as e:
            self.logger.error('Exception caught in fetching margin')
            cash_margin = -1
            credits = -1
            exposure_margin = -1
            account_id = -1
            net = -1
            gross_exposure_value = -1
        return account_id, cash_margin, credits, exposure_margin, net, gross_exposure_value
            
    # =======================================================================================
    # Order Management
    def manage_above_below(self):
        """
        Manages all orders which are waiting to reach the stage mentioned in the above below future price
        """
        while True:
            self.thread_lock.acquire()
            waiting_queue = self.above_below_waiting_queue.copy()
            self.thread_lock.release()

            for ind in range(len(waiting_queue)):
                try:
                    element = waiting_queue[ind] # AboveBelowWaitingQueueElement
                    ins_token = self.get_instrument_token(element.instrument_name)
                    if ins_token == None:
                        self.all_positions[element.row_id][2] = "ERROR"
                        del waiting_queue[ind]
                        continue

                    ltp = float(self.real_time_values[str(ins_token)][4])
                    if element.below_or_above == "ABOVE" and ltp >= element.future_price or element.below_or_above == "BELOW" and ltp <= element.future_price:
                        order_id = self.place_order(
                            instrument_name=element.instrument_name,
                            transaction_type=element.transaction_type,
                            product_type=element.product_type,
                            limit_price=element.limit_price,
                            quantity=element.quantity
                        )
                        self.thread_lock.acquire()
                        self.all_positions[element.row_id][1] = order_id
                        self.thread_lock.release()
                        
                        if element.stoploss != None or element.target != None:
                            new_element = StoplossTargetWaitingQueueElement()
                            new_element.transfer_from_above_below(element)
                        else:
                            new_element = OpenWaitingQueueElement()
                            new_element.transfer_from_above_below(element)

                        self.thread_lock.acquire()
                        if element.stoploss != None or element.target != None:
                            self.logger.info(f"Trade with Row ID {element.row_id} moved to StoplossTarget Queue")
                            self.stoploss_target_waiting_queue.append(new_element)
                            self.all_positions[element.row_id][2] = "WAITING_SL_T"
                        else:
                            self.logger.info(f"Trade with Row Id {element.row_id} moved to Open Queue")
                            self.open_waiting_queue.append(new_element)
                            self.all_positions[element.row_id][2] = "OPEN" 

                        del waiting_queue[ind]
                        self.thread_lock.release()
                except Exception as e:
                    self.logger.error(f"Exception caught in processing trade with row id : {element.row_id}, {e}")
            
            self.thread_lock.acquire()
            self.above_below_waiting_queue = waiting_queue
            self.thread_lock.release()

            sleep(settings.ABOVE_BELOW_SLEEP_TIME)

    def manage_stoploss_target(self):
        """
        Manages all orders which are waiting to close on stoploss or target
        """
        while True:
            self.thread_lock.acquire()
            waiting_queue = self.stoploss_target_waiting_queue.copy()
            self.thread_lock.release()

            for ind in range(len(waiting_queue)):
                try:
                    element = waiting_queue[ind] # StoplossTargetWaitingQueueElement
                    ins_token = self.get_instrument_token(element.instrument_name)
                    if ins_token == None:
                        self.all_positions[element.row_id][2] = "ERROR"
                        del waiting_queue[ind]
                        continue

                    ltp = float(self.real_time_values[str(ins_token)][4])
                    if element.transaction_type == "BUY" and element.stoploss != None and ltp <= element.stoploss or element.transaction_type == "BUY" and element.target != None and ltp >= element.target:
                        self.place_order(
                            instrument_name=element.instrument_name,
                            transaction_type="BUY" if element.transaction_type == "SELL" else "SELL",
                            product_type=element.product_type,
                            limit_price=None,
                            quantity=element.quantity
                        )
                        if element.stoploss != None and ltp <= element.stoploss:
                            self.logger.info(f"Trade with Row ID {element.row_id} closed on reaching Stoploss")
                        else:
                            self.logger.info(f"Trade with Row ID {element.row_id} closed on reaching Target")

                        self.thread_lock.acquire()
                        self.all_positions[element.row_id][2] = "CLOSED"
                        self.thread_lock.release()

                        del waiting_queue[ind]
                    
                    elif element.transaction_type == "SELL" and element.stoploss != None and ltp >= element.stoploss or element.transaction_type == "SELL" and element.target != None and ltp <= element.target:
                        self.place_order(
                            instrument_name=element.instrument_name,
                            transaction_type="BUY" if element.transaction_type == "SELL" else "SELL",
                            product_type=element.product_type,
                            limit_price=None,
                            quantity=element.quantity
                        )
                        if element.stoploss != None and ltp >= element.stoploss:
                            self.logger.info(f"Trade with Row ID {element.row_id} closed on reaching Stoploss")
                        else:
                            self.logger.info(f"Trade with Row ID {element.row_id} closed on reaching Target")

                        self.thread_lock.acquire()
                        self.all_positions[element.row_id][2] = "CLOSED"
                        self.thread_lock.release()

                        del waiting_queue[ind]
                except Exception as e:
                    self.logger.error(f"Exception caught in processing trade with row ID {element.row_id}")

            self.thread_lock.acquire()
            self.stoploss_target_waiting_queue = waiting_queue
            self.thread_lock.release()
            sleep(settings.STOPLOSS_TARGET_SLEEP_TIME)

    def place_order(self, instrument_name, transaction_type, product_type, limit_price, quantity):
        """
        Places order with the given parameters
        """
        if limit_price in ["", None, 0]:
            limit_price = 0.0

        ORDER_PLACEMENT_TRY_COUNTER = 0
        while ORDER_PLACEMENT_TRY_COUNTER < settings.MAX_ORDER_PLACEMENT_RETRIES:
            ORDER_PLACEMENT_TRY_COUNTER += 1
            try:
                order_type = OrderType.Market if limit_price == 0 else OrderType.Limit
                instrument = self.__conn.get_instrument_by_token(self.get_exch(instrument_name), self.get_instrument_token(instrument_name))
                trans_type = TransactionType.Buy if transaction_type == "BUY" else TransactionType.Sell
                prod_matching = {
                    "MIS": ProductType.Intraday,
                    "CNC": ProductType.Delivery,
                    "NRML": ProductType.Normal
                    }
                order_id = "PAPER TRADE"
                if settings.PAPER_TRADE == 0:
                    order_id = self.__conn.place_order(
                        transaction_type = trans_type,
                        instrument = instrument,
                        quantity = int(quantity),
                        order_type = order_type,
                        product_type = prod_matching[product_type],
                        price = limit_price
                    )['NOrdNo']

                ot = "LIMIT"
                if limit_price in [0, "", None]:
                    ot = "MARKET"
                    limit_price = self.real_time_values[str(self.get_instrument_token(instrument_name))][4]
                trading_symbol = self.get_trading_symbol(instrument_name)
                self.logger.info(f"""
                =======================================================
                ORDER PLACED 
                =======================================================
                Order Id : {order_id}
                Trading Symbol : {trading_symbol}
                Transaction Type : {transaction_type}
                Quantity : {quantity}
                Price : {limit_price}
                Product Type : {product_type}
                Order Type : {order_type}
                """)

                # [Date, OrderId, transaction type, product type, instrument name, Quantity, price, status]
                self.thread_lock.acquire()
                self.order_book.append([
                    datetime.now().strftime("%Y-%m-%d %H-%M-%S"),
                    order_id,
                    transaction_type,
                    product_type,
                    trading_symbol,
                    quantity,
                    limit_price,
                    ot,
                    ""
                ])
                self.thread_lock.release()
                return order_id
            except Exception as e:
                self.logger.error("order placement failed. Retrying ...", e)
                sleep(settings.ORDER_PLACING_REFRESH_TIME)

        self.logger.critical("Max retires for order placement exceeded. Application exiting ...")
        exit(1)

    def modify_order(self, instrument_name, transaction_type, product_type, limit_price, quantity, order_id):
        """
        Modify an already placed order
        """
        if limit_price in ["", None, 0]:
            limit_price = 0.0

        try:
            order_type = OrderType.Market if limit_price == 0 else OrderType.Limit
            instrument = self.__conn.get_instrument_by_token(self.get_exch(instrument_name), self.get_instrument_token(instrument_name))
            trans_type = TransactionType.Buy if transaction_type == "BUY" else TransactionType.Sell
            prod_matching = {
                "MIS": ProductType.Intraday,
                "CNC": ProductType.Delivery,
                "NRML": ProductType.Normal
                }

            if settings.PAPER_TRADE == 0:
                status = self.__conn.modify_order(
                    transaction_type = trans_type,
                    instrument = instrument,
                    order_id = order_id,
                    quantity = int(quantity),
                    order_type = order_type,
                    product_type = prod_matching[product_type],
                    price = limit_price
                    )

                if "Emsg" in status.keys():
                    status = status['Emsg']
                    print("ORDER NOT MODIFIED : ", status["Emsg"])
                    return status
            
            ot = "LIMIT"
            if limit_price in [0, "", None]:
                limit_price = self.real_time_values[str(self.get_instrument_token(instrument_name))][4]
                ot = "MARKET"
            trading_symbol = self.get_trading_symbol(instrument_name)

            self.logger.info(f"""
            =======================================================
            ORDER MODIFIED
            =======================================================
            Order Id : {order_id}
            Instrument Name : {instrument_name}
            Trading Symbol : {trading_symbol}
            Quantity : {quantity}
            Price : {limit_price}
            Product Type : {product_type}
            Order Type : {order_type}
            """)

            # [Date, OrderId, transaction type, product type, instrument name, Quantity, price, status]
            self.thread_lock.acquire()
            self.order_book.append([
                datetime.now().strftime("%Y-%m-%d %H-%M-%S"),
                order_id,
                transaction_type,
                product_type,
                trading_symbol,
                quantity,
                limit_price,
                ot,
                ""
            ])
            self.thread_lock.release()
            return order_id
        except Exception as e:
            self.logger.error("Order modification failed ...", e)
            return -1
        
    def cancel_order(self, order_id):
        """
        Cancel a placed order
        """
        try:
            if settings.PAPER_TRADE == 0:
                status = self.__conn.cancel_order(order_id)
                if "Emsg" in status.keys():
                    status = status['Emsg']
                else:
                    status = order_id
                return status
            else:
                return "PAPER TRADE"
        except Exception as e:
            self.logger.error("Exception caught while canelling an order", e)
            return -1

    def order_management(self, row_id, instrument_name, transaction_type, product_type, limit_price, quantity, stoploss, target, below_or_above, future_price, action):
        """
        Executes user action based on the parameters set by him. Executes orders, shifts order to various waiting queues, and manages results. 
        """
        if limit_price in [None, ""]:
            limit_price = 0.0

        if instrument_name in ["", None] or transaction_type in ["", None] or product_type in ["", None] or quantity in ["", None]:
            self.thread_lock.acquire()
            self.all_positions[row_id][2] = "INVALID"
            self.thread_lock.release()
            return

        if action == "EXECUTE":
            if below_or_above in [None, ""]:    # Not an above or below order
                order_id = self.place_order(
                    instrument_name=instrument_name,
                    transaction_type=transaction_type,
                    product_type=product_type,
                    limit_price=limit_price,
                    quantity=quantity
                )
                self.thread_lock.acquire()
                self.all_positions[row_id][1] = order_id    # Assigning Order ID
                self.thread_lock.release()

                if stoploss != None or target != None:  # If order is of type stoploss or target
                    new_element = StoplossTargetWaitingQueueElement(
                        row_id=row_id,
                        instrument_name=instrument_name,
                        transaction_type=transaction_type,
                        product_type=product_type,
                        limit_price=limit_price,
                        quantity=quantity,
                        stoploss=stoploss,
                        target=target
                    )
                    self.thread_lock.acquire()
                    self.stoploss_target_waiting_queue.append(new_element)  # Add to stoploss target waiting queue
                    self.all_positions[row_id][2] = "WAITING_SL_T"
                    self.thread_lock.release()

                else:
                    new_element = OpenWaitingQueueElement(
                        row_id=row_id,
                        instrument_name=instrument_name,
                        transaction_type=transaction_type,
                        product_type=product_type,
                        limit_price=limit_price,
                        quantity=quantity,
                    )
                    self.thread_lock.acquire()
                    self.open_waiting_queue.append(new_element)
                    self.all_positions[row_id][2] = "OPEN"
                    self.thread_lock.release()

            elif below_or_above != None:
                new_element = AboveBelowWaitingQueueElement(
                    row_id=row_id,
                    instrument_name=instrument_name,
                    transaction_type=transaction_type,
                    product_type=product_type,
                    limit_price=limit_price,
                    quantity=quantity,
                    stoploss=stoploss,
                    target=target,
                    below_or_above=below_or_above,
                    future_price=future_price
                )
                self.thread_lock.acquire()
                self.above_below_waiting_queue.append(new_element)
                self.all_positions[row_id][2] = "WAITING_AB"
                self.thread_lock.release()

        elif action == "CANCEL":
            self.thread_lock.acquire()
            current_status = self.all_positions[row_id][2]
            if current_status in ["WAITING_AB", "MODIFIED_WAITING_AB"]:
                self.above_below_waiting_queue = [x for x in self.above_below_waiting_queue if x.row_id != row_id]
                self.all_positions[row_id][2] = "CANCELLED"

            elif current_status in ["WAITING_SL_T", "MODIFIED_WAITING_SL_T"]:
                self.stoploss_target_waiting_queue = [x for x in self.stoploss_target_waiting_queue if x.row_id != row_id]
                status = self.cancel_order(self.all_positions[row_id][1])
                self.all_positions[row_id][1] = status
                self.all_positions[row_id][2] = "CANCELLED"

            elif current_status in ["OPEN", "MODIFIED_OPEN"]:
                ord_id = self.all_positions[row_id][1]
                status = self.cancel_order(ord_id)
                if status != ord_id:
                    self.all_positions[row_id][1] = ord_id
                    self.all_positions[row_id][2] = "NOT CANCELLED"
                else:
                    self.all_positions[row_id][1] = ord_id
                    self.all_positions[row_id][2] = "CANCELLED"
                self.open_waiting_queue = [x for x in self.open_waiting_queue if x.row_id != row_id]

            elif current_status == "CLOSED":
                # Do Nothing
                pass
        
            self.logger.info(f"Trade with Row ID {row_id} Cancelled")
            self.thread_lock.release()

        elif action == "MODIFY":
            self.thread_lock.acquire()
            current_status = self.all_positions[row_id][2]
            self.thread_lock.release()
            status = "MODIFIED"

            if current_status in ["WAITING_AB", "MODIFIED_WAITING_AB"]:
                self.thread_lock.acquire()
                for i in range(len(self.above_below_waiting_queue)):
                    if self.above_below_waiting_queue[i].row_id == row_id:   
                        self.above_below_waiting_queue[i].instrument_name = instrument_name
                        self.above_below_waiting_queue[i].transaction_type = transaction_type
                        self.above_below_waiting_queue[i].product_type = product_type
                        self.above_below_waiting_queue[i].limit_price = limit_price
                        self.above_below_waiting_queue[i].quantity = quantity
                        self.above_below_waiting_queue[i].stoploss = stoploss
                        self.above_below_waiting_queue[i].target = target
                        self.above_below_waiting_queue[i].below_or_above = below_or_above
                        self.above_below_waiting_queue[i].future_price = future_price
                        break
                status = "MODIFIED_WAITING_AB"
                self.thread_lock.release()

            elif current_status in ["WAITING_SL_T", "MODIFIED_WAITING_SL_T"]:
                self.thread_lock.acquire()
                for i in range(len(self.stoploss_target_waiting_queue)):
                    if self.stoploss_target_waiting_queue[i].row_id == row_id:
                        self.stoploss_target_waiting_queue[i].stoploss = stoploss
                        self.stoploss_target_waiting_queue[i].target = target
                        break
                status = "MODIFIED_WAITING_SL_T"
                self.thread_lock.release()

            elif current_status in ["OPEN", "MODIFIED_OPEN"]:
                self.thread_lock.acquire()
                oid = self.all_positions[row_id][1]
                self.thread_lock.release()

                s = self.modify_order(
                    instrument_name=instrument_name,
                    transaction_type=transaction_type,
                    product_type=product_type,
                    limit_price=limit_price,
                    quantity=quantity,
                    order_id=oid
                )
                if s == oid:
                    status = "MODIFIED_OPEN"
                else:
                    status = "NOT_MODIFIED_OPEN"

            elif current_status == "CLOSED":
                status = "CLOSED"
                pass

            self.thread_lock.acquire()
            self.all_positions[row_id][2] = status
            self.thread_lock.release()
            self.logger.info(f"Trade with Row ID {row_id} modified")

        elif action == "EXIT":
            self.thread_lock.acquire()
            current_status = self.all_positions[row_id][2]
            self.thread_lock.release()

            if current_status in ["WAITING_AB", "MODIFIED_WAITING_AB"]:
                self.thread_lock.acquire()
                self.above_below_waiting_queue = [x for x in self.above_below_waiting_queue if x.row_id != row_id]
                self.thread_lock.release()

            elif current_status in ["WAITING_SL_T", "MODIFIED_WAITING_SL_T"]:
                self.thread_lock.acquire()
                for i in range(len(self.stoploss_target_waiting_queue)):
                    print(self.stoploss_target_waiting_queue[i])
                    if self.stoploss_target_waiting_queue[i].row_id == row_id:
                        self.thread_lock.release()
                        self.place_order(
                            instrument_name=self.stoploss_target_waiting_queue[i].instrument_name,
                            transaction_type="BUY" if self.stoploss_target_waiting_queue[i].transaction_type == "SELL" else "SELL",
                            product_type=self.stoploss_target_waiting_queue[i].product_type,
                            limit_price=None,
                            quantity=self.stoploss_target_waiting_queue[i].quantity
                        )
                        break
                self.above_below_waiting_queue = [x for x in self.stoploss_target_waiting_queue if x.row_id != row_id]

            elif current_status in ["OPEN", "MODIFIED_OPEN"]:
                ord_id = self.all_positions[row_id][1]
                status = self.__conn.get_order_history(ord_id)
                if "Emsg" in status.keys():
                    pass
                else:
                    status = status['Status']

                if status == "open":
                    self.cancel_order(ord_id)
                    status = ord_id
                elif status == "complete":
                    status = self.place_order(
                        instrument_name=instrument_name,
                        transaction_type="SELL" if transaction_type == "BUY" else "BUY",
                        product_type=product_type,
                        limit_price=None,
                        quantity=quantity
                    )
                self.thread_lock.acquire()
                self.all_positions[row_id][1] = status
                self.open_waiting_queue = [x for x in self.open_waiting_queue if x.row_id != row_id]
                self.thread_lock.release()

            elif current_status == "CLOSED":
                # Do Nothing
                pass

            self.thread_lock.acquire()
            self.all_positions[row_id][2] = "EXITED"
            self.thread_lock.release()
            
            self.logger.info(f"Trade with Row ID {row_id} exited")

    def get_positions(self):
        self.thread_lock.acquire()
        positions = self.all_positions.copy()
        self.thread_lock.release()
        return positions
    
    def get_orderbook(self):
        self.thread_lock.acquire()
        orderbook = self.order_book.copy()
        self.thread_lock.release()
        return orderbook
    # =======================================================================================
    # Live Ticker
    def socket_open(self):
        """
        Called as soon as the socket is opened
        """
        self.logger.info("Live streaming ticker connected.")
        self.socket_active = True

    def socket_close(self):
        """
        Called as soon as the socket is closed
        """
        self.logger.info("Live streaming ticker closed.")
        self.socket_active = False

    def socket_error(self, err):
        """
        Called as soon as the socket catches any error
        """
        self.logger.error(f"Error caught while live streaming\n{err}")

    def feed_data(self, msg):
        """
        Called whenever server sends any new message in the stream
        """
        message = json.loads(msg)
        if message["t"] == "ck":
            self.logger.info(f"Connection Acknowledgement status : {message['s']} (Websocket Connected)")
        elif message["t"] == "tk":
            self.logger.info(f"Token Acknowledgement status : {message}")
        elif message["t"] in ["dk", "df"]:
            token = message["tk"]
            last_val = self.real_time_values[token] if token in self.real_time_values.keys() else [0,0,0,0,0,0,0,0,0,0]
            open_val = message['o'] if 'o' in message.keys() else last_val[0]
            high_val = message['h'] if 'h' in message.keys() else last_val[1]
            low_val = message['l'] if 'l' in message.keys() else last_val[2]
            close_val = message['c'] if 'c' in message.keys() else last_val[3]
            ltp = message['lp'] if 'lp' in message.keys() else last_val[4]
            volume = message['v'] if 'v' in message.keys() else last_val[5]
            vwap = message['ap'] if 'ap' in message.keys() else last_val[6]
            best_buy = message['bp1'] if 'bp1' in message.keys() else last_val[7]
            best_sell = message['sp1'] if 'sp1' in message.keys() else last_val[8]
            oi = message['oi'] if 'oi' in message.keys() else last_val[9]

            self.real_time_values[token] = [open_val, high_val, low_val, close_val, ltp, volume, vwap, best_buy, best_sell, oi]

    def subscribe_tokens(self, instrument_names:list):
        """
        Subscribes list of given instrument names
        """
        subscribe_list = []
        for name in instrument_names:
            print(f"SUBSCRIBED : {self.get_trading_symbol(name)}")
            subscribe_list.append(self.__conn.get_instrument_by_token(self.get_exch(name), self.get_instrument_token(name)))
        self.__conn.subscribe(subscribe_list)
    
    def unsubscribe_tokens(self, instrument_names:list):
        """
        Unsubscribes list of given instrument names
        """
        unsubscribe_list = []
        for name in instrument_names:
            unsubscribe_list.append(self.__conn.get_instrument_by_token(self.get_exch(name), self.get_instrument_token(name)))
        self.__conn.unsubscribe(unsubscribe_list)
    
    def get_ticker_values(self, instrument_names):
        """
        Return live ticker values of the given instrument names
        """
        ticker_values = []
        for name in instrument_names:
            if name == "" or name == None or not self.check_if_instrument_exists(name):
                ticker_values.append(["","","","","","","","","",""])
            else:
                token = self.get_instrument_token(name)
                try:
                    ticker_values.append(self.real_time_values[str(token)])
                except:
                    ticker_values.append([0,0,0,0,0,0,0,0,0,0])
        return ticker_values