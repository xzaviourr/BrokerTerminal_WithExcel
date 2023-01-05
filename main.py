import settings
from ExcelManager.manager import ExcelManager

# from googleapiclient.discovery import build
# from google_auth_oauthlib.flow import InstalledAppFlow
import os

import sys
import signal

excel_object = None

def signal_handler(sig, frame):
    global excel_object
    if excel_object != None:
        excel_object.close_excel()
    print("APPLICATION STOPPED")
    sys.exit(1)

signal.signal(signal.SIGINT, signal_handler)

# SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
# import json 
# with open(settings.spreadsheetidfile,'r') as file:
#     SAMPLE_SPREADSHEET_ID_input=json.load(file)["id"]
# SAMPLE_RANGE_NAME = 'A1:B100'

# def check_for_live():
#     global values_input, service
#     flow = InstalledAppFlow.from_client_secrets_file(
#         os.path.join(settings.EXCEL_DIR, "newkeys.json"),
#         SCOPES)
#     creds = flow.run_local_server(port=0)
#     try:
#         service = build('sheets', 'v4', credentials=creds)
#     except:
#         DISCOVERY_SERVICE_URL = 'https://sheets.googleapis.com/$discovery/rest?version=v4'
#         service = build('sheets', 'v4', credentials=creds, discoveryServiceUrl=DISCOVERY_SERVICE_URL)

#     sheet = service.spreadsheets()
#     result_input = sheet.values().get(
#         spreadsheetId=SAMPLE_SPREADSHEET_ID_input,
#         range=SAMPLE_RANGE_NAME
#         ).execute()
#     values_input = result_input.get('values', [])

# check_for_live()

# import json
# file = open(settings.BROKER_CREDENTIALS_FILE, 'r')
# client_code = json.load(file)['user_id']
# flag = 0
# for i in range(len(values_input)):
#     if values_input[i] != []:
#         try:
#             if values_input[i][0] == client_code:
#                 flag= 1
#                 break
#         except:
#             continue

# if flag == 1:
    # CREATES OBJECT OF EXCEL MANAGER WHICH RUNS THE EXCEL OPERATIONS
    # excel_object = ExcelManager()
# else:
#     print("ERROR : ", values_input[0][1])
#     print("\n\nAPPLICATION STOPPED\n\n")

# CREATES OBJECT OF EXCEL MANAGER WHICH RUNS THE EXCEL OPERATIONS
excel_object = ExcelManager()
