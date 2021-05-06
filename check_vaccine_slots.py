import requests, datetime, json, pandas as pd, re, sys
from pytz import timezone

IST = timezone('asia/kolkata')
COWIN_API_PREFIX = 'https://cdn-api.co-vin.in/api/v2'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'}

def get_state_ids():
    url = f'{COWIN_API_PREFIX}/admin/location/states'
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        data = resp.json()
        state_dict = {re.sub('\s+', '', state['state_name'].lower()) : state['state_id'] for state in data['states']}
        return True, state_dict
    print(f"[{datetime.datetime.now(IST).isoformat()}] Error: {url}, {resp.status_code}, {json.dumps(resp.json())}")
    return False, {'message': 'No states found. Contact admin'}

def get_districts_by_state_id(state_id):
    url = f'{COWIN_API_PREFIX}/admin/location/districts/{state_id}'
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        data = resp.json()
        district_dict = {re.sub('\s+', '', district['district_name'].lower()) : (district['district_name'], district['district_id']) for district in data['districts']}
        return True, district_dict
    print(f"[{datetime.datetime.now(IST).isoformat()}] Error: {url}, {resp.status_code}, {json.dumps(resp.json())}")    
    return False, {'message': 'No districts found in state. Contact admin'}

def get_mail_content_for_district(district_name, district_id, doi):
    url = f'{COWIN_API_PREFIX}/appointment/sessions/public/calendarByDistrict?district_id={district_id}&date={doi}'
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[{datetime.datetime.now(IST).isoformat()}] Error: {url}, {resp.status_code}, {json.dumps(resp.json())}")    
        return False, 'ERROR', 'Couldnt retrieve vaccination slots. Contact admin'
    data = resp.json()
    centers = [[center['pincode'], session['available_capacity'], session['date'], session['vaccine'], center['block_name'], center['fee_type'], center['name'], center['address']] for center in data['centers'] for session in center['sessions'] if session['available_capacity']>=0 and session['min_age_limit']==18]

    df = pd.DataFrame(centers, columns=['pincode', 'available_capacity', 'date', 'vaccine', 'block_name', 'fee_type', 'name', 'address'])
    df.sort_values(by=['available_capacity', 'date'], ascending=[False, True], inplace=True)
    is_slot_avl = 'AVAILABLE' if (df['available_capacity']>0).any() else 'NOT AVAILABLE'
    if df.shape[0]==0:
        is_slot_avl = 'NOT OPEN YET'
    mail_header = f'18+ Slots in {district_name}: {is_slot_avl}'
    df.columns = ['Pincode', 'Total Slots', 'Date', 'Vaccine', 'Block Name', 'Fee Type', 'Center Name', 'Center Address']
    return True, mail_header, df.to_html()

def generate_mail_batches(cfg, doi):
    mail_batches = []

    is_states_successful, state_ids = get_state_ids()
    if not is_states_successful:
        recipients = [receiever for state_input in cfg for district_data in state_input['districts'] for recipient in district_data['receivers']]
        email_content, email_header = 'States info not found. Contact admin', 'Internal Error'
        mail_batches.append({'recipients': recipients, 'content': email_content, 'header': email_header})
        return mail_batches
    
    for state_input in cfg:
        state_id = state_ids[state_input['state']]
        is_successful, state_districts = get_districts_by_state_id(state_id)
        if not is_successful:
            recipients = [receiever for district_data in state_input['districts'] for receiver in district_data['receievers']]
            email_content, email_header = 'District details not found. Contact admin', 'Internal Error'
            mail_batches.append({'recipients': recipients, 'content': email_content, 'header': email_header})
            continue

        state_district_keys = state_districts.keys()
        for district_data in state_input['districts']:
            district_regex, recipients = district_data['district'], district_data['receivers']
            state_district_keys = state_districts.keys()
            distr_name, distr_id = None, None
            for distr in state_district_keys:
                if re.match(district_regex, distr):
                    distr_name, distr_id = state_districts[distr]
                    break
            if distr_id:
                status, email_header, email_content = get_mail_content_for_district(distr_name, distr_id, doi)
            else:
                email_content, email_header = 'District not found. Contact admin', 'Internal Error'
            mail_batches.append({'recipients': recipients, 'content': email_content, 'header': email_header})
    return mail_batches

import smtplib, os
from email.mime.text import MIMEText
import argparse

def main():
    parser = argparse.ArgumentParser(description='[♫♫ Jolene ♫♫] Vaccine vaccine vaccine vaccine. Please don\'t take much longer if you can.')
    parser.add_argument('config_file', help='Config file containing the districts and email ids of concern')
    parser.add_argument('--mail_iff_slot_avl',  action='store_true', help='Dispatch emails only if slots are available.')
    parser.add_argument('--test_mode', action='store_true', help='Dry run for testing.')
    
    args = parser.parse_args()
    SEND_IFF_SLOTS_AVL = args.mail_iff_slot_avl
    IS_PROD_MODE = not args.test_mode
    config_file = args.config_file

    if not os.path.exists(cfg_loc):
        print(f'{cfg_loc} doesnt contain the config file')
        sys.exit(1)
    with open(config_file) as f:
        dat = json.load(f)
        cfg = dat['cfg']
    
    tdelta = 1 if not SEND_IFF_SLOTS_AVL else 0
    doi = (datetime.date.today() + datetime.timedelta(days=tdelta)).strftime('%d-%m-%Y')
    mail_batches = generate_mail_batches(cfg, doi)
    print(f"[{datetime.datetime.now(IST).isoformat()}] TOTAL MAIL BATCHES={len(mail_batches)}, summary={[(mb['header'], mb['recipients']) for mb in mail_batches]}, Send mail only if slots={SEND_IFF_SLOTS_AVL}")
    if SEND_IFF_SLOTS_AVL:
        mail_batches = list(filter(lambda mb: mb['header'].endswith(': AVAILABLE'), mail_batches))
    print(f"[{datetime.datetime.now(IST).isoformat()}] FINAL MAIL BATCHES={len(mail_batches)}, summary={[(mb['header'], mb['recipients']) for mb in mail_batches]}, Send mail only if slots={SEND_IFF_SLOTS_AVL}")
    
    if len(mail_batches)>0:
        server = None
        mail_user = None
        if IS_PROD_MODE:
            mail_user, mail_password, server_name, port  = dat['creds']['prod_creds']['username'], dat['creds']['prod_creds']['password'], dat['creds']['prod_creds']['server'], dat['creds']['prod_creds']['port']
            server = smtplib.SMTP_SSL(server_name, port)
            server.ehlo() 
            server.login(mail_user, mail_password)
        else:
            mail_user, mail_password, server_name, port  = dat['creds']['test_creds']['username'], dat['creds']['test_creds']['password'], dat['creds']['test_creds']['server'], dat['creds']['test_creds']['port']
            server = smtplib.SMTP(server_name, port)
        
        for mail_batch in mail_batches:
            header = mail_batch['header']
            if SEND_IFF_SLOTS_AVL:
                header = '(IMPORTANT)' + header
            receivers = mail_batch['recipients']
            msg = MIMEText(mail_batch['content'], "html")
            msg['Subject'] = header
            msg['From'] = mail_user
            msg['Bcc'] = ",".join(receivers)
            server.send_message(msg)
        
        server.quit()

if __name__ == '__main__':
    main()
