#! /usr/bin/env python3

import re
import sys
import os
import subprocess
import logging
import smtplib
import datetime
import glob
from typing import Dict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication


def log_rotation(config: dict) -> None:
    """
    Log rotation
    """
    if not os.path.exists(config['log_dir'] + 'logs/'):
        os.mkdir(config['log_dir'] + 'logs/')
    if not os.path.exists(config['log_dir'] + 'log_archive/'):
        os.mkdir(config['log_dir'] + 'log_archive/')
    if len(glob.glob1(config['log_dir'] + 'log_archive/', '*.txt')) >= 50:
        tar = 'tar czf ' + config['log_dir'] + 'log_archive/log_archive_' + \
              datetime.datetime.today().strftime('%Y-%m-%d') + \
              '.tar.gz ' + config['log_dir'] + 'log_archive/*.txt'
        subprocess.Popen(tar, shell=True, stderr=subprocess.DEVNULL)
        for log in glob.glob(config['log_dir'] + 'log_archive/*.txt'):
            os.remove(log)


def send_report(email: str, config: dict) -> None:
    """
    Sends logs of current requests
    Executed if the <REPORT> key is present in the message text
    """
    files_list = os.listdir(config['log_dir'] + 'logs/')
    # There are open requests
    if len(files_list) >= 1:
        msg = MIMEMultipart()
        msg['Subject'] = 'Logs of current requests in an attachment'
        send = smtplib.SMTP(config['mail_server'])
        for f in files_list:
            file_path = os.path.join(config['log_dir'] + 'logs/', f)
            attachment = MIMEApplication(open(file_path, 'rb').read(),
                                         _subtype='txt')
            attachment.add_header('Content-Disposition',
                                  'attachment',
                                  filename=f)
            msg.attach(attachment)
        msg.attach(MIMEText('Logs of current requests in an attachment'))
        send.sendmail(config['mail_from'], [email], msg.as_string())
        send.quit()
    # No open requests
    else:
        msg = MIMEMultipart()
        msg['Subject'] = 'There are currently no requests being processed'
        send = smtplib.SMTP(config['mail_server'])
        send.sendmail(config['mail_from'], [email], msg.as_string())
        send.quit()


def send_start(log_file_name: str, mac: str, config: dict) -> None:
    """
    Sends a message about the opening of the ticket,
    indicating the MAC address of the device and the ticket tracker
    """
    msg = MIMEMultipart()
    msg['Subject'] = mac + ' request accepted'
    send = smtplib.SMTP(config['mail_server'])
    msg.attach(MIMEText(mac + ' request accepted, TRACKER: ' + log_file_name))
    send.sendmail(config['mail_from'], [config['mailbox']], msg.as_string())
    send.quit()


def send_end(log_file_name: str,
             mac: str,
             task_result: str,
             config: dict
             ) -> None:
    """
    Sends a message about the closing of the request
    with an indication of its status and a log of its execution
    """
    msg = MIMEMultipart()
    msg['Subject'] = task_result + ' ' + mac
    send = smtplib.SMTP(config['mail_server'])
    with open(config['log_dir'] + 'logs/' + log_file_name + '.txt', 'r') as f:
        log = f.read()
    msg.attach(MIMEText(log))
    send.sendmail(config['mail_from'], [config['mailbox']], msg.as_string())
    send.quit()


def send_violation(message_dict: Dict[str, str],
                   restriction: str,
                   config: dict
                   ) -> None:
    """
    Security message
    """
    msg = MIMEMultipart()
    msg['Subject'] = 'Security notice. Message from: ' + message_dict['email']
    send = smtplib.SMTP(config['mail_server'])
    msg.attach(MIMEText(restriction +
                        '\r\n\r\n----------MESSAGE----------\r\n\r\n' +
                        message_dict['message']))
    send.sendmail(config['mail_from'], [config['mailbox']], msg.as_string())
    send.quit()


def send_error(message_dict: Dict[str, str], error: str, config: dict) -> None:
    """
    Error message
    """
    msg = MIMEMultipart()
    msg['Subject'] = 'Error, such request does not exist'
    send = smtplib.SMTP(config['mail_server'])
    msg.attach(MIMEText(error +
                        '\r\n\r\n----------MESSAGE----------\r\n\r\n' +
                        message_dict['message']))
    send.sendmail(config['mail_from'], message_dict['email'], msg.as_string())
    send.quit()


def kill_task(message_dict: Dict[str, str], config: dict) -> None:
    """
    Forces the request to end if the <KILL> key is present in the message
    After the specified key in the message,
    the ticket tracker must be indicated
    """
    try:
        reg_kill: str = r'(task_\S+)'
        decoded_message = message_dict['message']
        task_match = re.search(reg_kill, decoded_message)
        assert task_match is not None
        log_file_name = task_match.groups()[0]
        kill_proc = int(log_file_name.split('_')[1])
        try:
            os.kill(kill_proc, 9)
            mac = log_file_name.split('__')[1].replace('-', '.')
            task_result = log_file_name + ' terminated'
            send_end(log_file_name, mac, task_result, config)
            mv = 'mv ' + config['log_dir'] + 'logs/' + \
                log_file_name + '.txt ' + \
                config['log_dir'] + 'log_archive/' + log_file_name + '.txt'
            subprocess.Popen(mv, shell=True)
        except Exception as error:
            send_error(message_dict, str(error), config)
    except Exception as error:
        send_error(message_dict, str(error), config)


def ip_list_check(log_file_name: str,
                  task_params: Dict[str, str],
                  mac: str,
                  config: dict
                  ) -> None:
    """
    Checks if a host is on the banned list
    """
    if task_params['ip_addr'] not in config['bad_ips']:
        logging.info('!!!OK!!! This host is not in the list '
                     'of excluded addresses\r\n\r\n')
    else:
        logging.info('!!!NOT OK!!! This host is in the list '
                     'of excluded addresses\r\n\r\nTask failed')
        task_result: str = 'Task failed'
        end_task(log_file_name, mac, task_result, config)


def sql_answer_check(log_file_name: str,
                     sql_answer: Dict[str, str],
                     mac: str,
                     config: dict
                     ) -> None:
    """
    Checks the response from the log server DB
    """
    if 'Task failed' in sql_answer['answer']:
        logging.info(sql_answer['answer'])
        task_result: str = 'Task failed'
        end_task(log_file_name, mac, task_result, config)
    else:
        logging.info('SQL_ANSWER: ' + sql_answer['answer'] + '\r\n')


def clearing_message(raw_message_dict: Dict[str, str]) -> Dict[str, str]:
    """
    Message clearing
    """
    reg_mess: str = r'<[\s\S|.]*?>|&nbsp;|&quot;|.*?;}'
    clean_mess = re.sub(reg_mess, '', raw_message_dict['message'])
    reg_line_break = r'(\r\n){5,}'
    clean_mess = re.sub(reg_line_break, '\r\n', clean_mess)
    raw_message_dict.update({'message': clean_mess})
    return raw_message_dict


def find_macs_in_mess(decoded_message: str) -> str:
    """
    Finding the MAC address in a message
    """
    reg = re.compile('\s(?P<mac>([0-9A-Fa-fАаВСсЕеOО]{2}[\s:.-]){5}'
                     '([0-9A-Fa-fАаВСсЕеOО]{2})'
                     '|([0-9A-Fa-fАаВСсЕеOО]{3}[\s:.-]){3}'
                     '([0-9A-Fa-fАаВСсЕеOО]{3})'
                     '|([([0-9A-Fa-fАаВСсЕеOО]{4}[\s:.-]){2}'
                     '([0-9A-Fa-fАаВСсЕеOО]{4})'
                     '|([0-9A-Fa-fАаВСсЕеOО]{12}))\s')
    m = reg.finditer(decoded_message)
    matches: list = []
    for mat in m:
        matches.append(mat.group('mac'))
    format_matches: list = []
    for match in matches:
        match = match.replace(':', "").replace('-', "").replace('.', "") \
                     .replace(' ', "").replace('\n', "").replace('\t', "")
        match = match.lower()
        # Replace Cyrillic characters
        match = match.replace('а', 'a').replace('в', 'b').replace('с', 'c') \
                     .replace('е', 'e').replace('о', '0').replace('o', '0')
        format_matches.append(match)
    if len(format_matches) == 1:
        new_mac = format_matches[0]
        return new_mac
    elif len(format_matches) == 0:
        no_mac = 'No MAC addresses found\r\n\r\nTask failed'
        return no_mac
    else:
        too_much_mac = 'Too many matches\r\n\r\nTask failed'
        return too_much_mac


def find_macs_in_mess_check(log_file_name: str,
                            mac: str,
                            config: dict
                            ) -> None:
    """
    Is there a MAC address in the message?
    """
    task_result: str = 'Task failed'
    if 'No MAC addresses found' in mac:
        logging.info(mac)
        no_mac: str = 'No MAC addresses found'
        end_task(log_file_name, no_mac, task_result, config)
    elif 'Too many matches' in mac:
        logging.info(mac)
        to_many_mac: str = 'Too many matches'
        end_task(log_file_name, to_many_mac, task_result, config)
    else:
        pass


def create_sql_query(mac: str, config: dict) -> str:
    """
    Creates a SQL query for the log server
    """
    mac_cisco = mac[:4] + '.' + mac[4:8] + '.' + mac[8:12]
    match_sql = ('''mysql -u ''' +
                 config['db_user'] +
                 ''' -p''' +
                 config['db_pass'] +
                 ''' -D Syslog -e "SELECT FromHost, Message FROM '''
                 '''SystemEvents WHERE DeviceReportedTime LIKE '%''' +
                 datetime.datetime.today().strftime('%Y-%m-%d') +
                 '''%' AND Message REGEXP '.*(''' +
                 mac_cisco +
                 ''').*' ORDER BY ID DESC LIMIT 1;"''')
    return match_sql


def end_task(log_file_name: str,
             mac: str,
             task_result: str,
             config: dict
             ) -> None:
    """
    Ends a request
    """
    send_end(log_file_name, mac, task_result, config)
    mv = 'mv ' + config['log_dir'] + 'logs/' + log_file_name + '.txt ' + \
        config['log_dir'] + 'log_archive/' + log_file_name + '.txt'
    subprocess.Popen(mv, shell=True)
    sys.exit()
