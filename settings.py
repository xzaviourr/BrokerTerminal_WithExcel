import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BROKER_DIR = os.path.join(BASE_DIR, "Broker")
BROKER_CREDENTIALS_FILE = os.path.join(BROKER_DIR, "credentials.json")
BROKER_LOGS_FOLDER = os.path.join(BROKER_DIR, "logs")
EXCEL_DIR = os.path.join(BASE_DIR, "ExcelManager")
EXCEL_LOGS_FOLDER = os.path.join(EXCEL_DIR, "logs")
EXCEL_FILE = os.path.join(BASE_DIR, "RTP_ALGO.xlsx")
MASTER_CONTRACTS_DIR = os.path.join(BROKER_DIR, "master_contracts")
KEYS_FILE = os.path.join(EXCEL_DIR, "newkeys.json")


spreadsheetidfile=os.path.join(EXCEL_DIR,"spreadsheetid.json")
# ===========================================================
# BROKER SETTINGS
MAX_BROKER_LOGIN_ATTEMPT_COUNT = 3  # Maximum login attempts made for the broker
SLEEP_TIME_BETWEEN_ATTEMPTS = 1   # Time (in sec) for which the process will sleep before retrying
PAPER_TRADE = 0
ABOVE_BELOW_SLEEP_TIME = 1  # Time (in sec) for which the process will sleep after checking above below field
STOPLOSS_TARGET_SLEEP_TIME = 1
MAX_ORDER_PLACEMENT_RETRIES = 5

# EXCEL SETTINGS
MAX_TOKENS_IN_MARKETWATCH = 250
MARKETWATCH_REFRESH_TIME = 0.1   # Seconds
ORDER_PLACING_REFRESH_TIME = 3  # Seconds

# CREATE DIRECTORIES
for d in [BROKER_DIR, BROKER_LOGS_FOLDER, EXCEL_DIR, EXCEL_LOGS_FOLDER, MASTER_CONTRACTS_DIR]:
    print(d)
    if not os.path.exists(d):
        print(d)
        os.mkdir(d)

broker_credentials = {
    "user_id": "",
    "api_key": ""
}

spreadsheet_id = {
    "id":""
}

google_sheets_keys = {
    "web": {
        "client_id":"",
        "project_id":"",
        "auth_uri":"",
        "token_uri":"",
        "auth_provider_x509_cert_url":"",
        "client_secret":""
        }
    }

if not os.path.exists(BROKER_CREDENTIALS_FILE):
    with open(BROKER_CREDENTIALS_FILE, 'w') as file:
        json.dump(broker_credentials, file, indent=4)

if not os.path.exists(spreadsheetidfile):
    with open(spreadsheetidfile, 'w') as file:
        json.dump(spreadsheet_id, file, indent=4)

if not os.path.exists(KEYS_FILE):
    with open(KEYS_FILE, 'w') as file:
        json.dump(google_sheets_keys, file, indent=4)
