import argparse, sys, json, os, smtplib, datetime, pandas as pd
from email.mime.text import MIMEText
import asyncio
import aiohttp
import ujson
import time
from pytz import timezone

IST = timezone('asia/kolkata')
tic = time.time()
parser = argparse.ArgumentParser(description='[♫♫ Jolene ♫♫] Vaccine vaccine vaccine vaccine. Please don\'t take much longer if you can.')
parser.add_argument('config_file', help='Config file containing the districts and email ids of concern')
parser.add_argument('--mail_iff_slot_avl',  action='store_true', help='Dispatch emails only if slots are available.')
parser.add_argument('--test_mode', action='store_true', help='Dry run for testing.')
  
args = parser.parse_args()
SEND_IFF_SLOTS_AVL = args.mail_iff_slot_avl
IS_PROD_MODE = not args.test_mode
config_file = args.config_file

if not os.path.exists(config_file):
  print(f'{cfg_loc} doesnt contain the config file')
  sys.exit(1)  
with open(config_file) as f:
  dat = json.load(f)
  cfg = dat['cfg']

tdelta = 1 if not SEND_IFF_SLOTS_AVL else 0
doi = (datetime.date.today() + datetime.timedelta(days=tdelta)).strftime('%d-%m-%Y')
URL_PREFIX = cfg["APPOINTMENT_URL_PREFIX"]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'}
async def get_slots(url, session):
  try:
    async with session.get(url=url, headers=HEADERS) as response:
      data = await response.json()
      return data
  except Exception as e:
    print(e)
  return {"centers": [], "message": url, "status": response.status}

MAIL_SERVER = None
mail_user = None
if IS_PROD_MODE:
  mail_user, mail_password, server_name, port = dat['creds']['prod_creds']['username'], dat['creds']['prod_creds']['password'], dat['creds']['prod_creds']['server'], dat['creds']['prod_creds']['port']
  MAIL_SERVER = smtplib.SMTP_SSL(server_name, port)
  MAIL_SERVER.ehlo() 
  MAIL_SERVER.login(mail_user, mail_password)
else:
  mail_user, mail_password, server_name, port  = dat['creds']['test_creds']['username'], dat['creds']['test_creds']['password'], dat['creds']['test_creds']['server'], dat['creds']['test_creds']['port']
  MAIL_SERVER = smtplib.SMTP(server_name, port)

df_cols = ['pincode', 'available_capacity', 'date', 'vaccine', 'block_name', 'fee_type', 'name', 'address']
display_cols = ['Pincode', 'Total Slots', 'Date', 'Vaccine', 'Block', 'Fee type', 'Name', 'Address']
header_prefix = '(IMPORTANT) ' if SEND_IFF_SLOTS_AVL else ''
SLOT_NOT_OPEN = 0
SLOT_NOT_AVAILABLE = 1
SLOT_AVAILABLE = 2
slot_status_dct = {SLOT_NOT_OPEN: 'NOT OPEN', SLOT_NOT_AVAILABLE: 'NOT AVAILABLE', SLOT_AVAILABLE: 'available'}

prefix_pb_map = {True: '', False: '/public'}

async def main(cfg):
  urls = [f"{URL_PREFIX}{prefix_pb_map[ddata['is_main_ok']]}/calendarByDistrict?district_id={ddata['district_id']}&date={doi}" for ddata in cfg]
  async with aiohttp.ClientSession() as session:
    data_lst = await asyncio.gather(*[get_slots(url, session) for url in urls])

  for url, data, ddict in zip(urls, data_lst, cfg):
    print(datetime.datetime.now(IST).isoformat(), url, data.keys()) 
    df = pd.DataFrame([[center['pincode'], cw_session['available_capacity'], cw_session['date'], cw_session['vaccine'], center['block_name'], center['fee_type'], center['name'], center['address']] for center in data['centers'] for cw_session in center['sessions'] if cw_session['available_capacity']>=0 and cw_session['min_age_limit']==18], columns=df_cols)
    slot_status = SLOT_NOT_AVAILABLE
    if df.shape[0]==0:
      slot_status = SLOT_NOT_OPEN
    elif (df['available_capacity']>0).any():
      slot_status = SLOT_AVAILABLE

    if SEND_IFF_SLOTS_AVL and slot_status is not SLOT_AVAILABLE:
      continue
    df.sort_values(by=['available_capacity', 'date'], ascending=[False, True], inplace=True)
    df.columns = display_cols

    msg = MIMEText(df.to_html(index_names=False), "html")
    msg['Subject'] = f"{header_prefix}18+ Slots in {ddict['district_name']}: {slot_status_dct[slot_status]}"
    msg['From'] = mail_user
    msg['Bcc'] = ",".join(ddict['recipients'])
    MAIL_SERVER.send_message(msg)

start = time.time()
loop = asyncio.get_event_loop()
loop.run_until_complete(main(cfg))
end = time.time()

MAIL_SERVER.quit()
toc = time.time()

print(datetime.datetime.now(IST).isoformat(), 'Total processing time = ', toc-tic, 'seconds')
