#! /usr/bin/env python3

import os
import time
import json
import logging
import poplib
import datetime
import traceback
from sys import argv
from log_serv_conn import log_server_check
from cisco_conn import cisco_connection
from log_parser import log_parse
from email.parser import Parser
from multiprocessing import Process
from service_funcs import (
    send_violation,
    clearing_message,
    log_rotation,
    send_report,
    send_start,
    kill_task,
    ip_list_check,
    sql_answer_check,
    find_macs_in_mess_check,
    create_sql_query,
    find_macs_in_mess,
)


def check_glob_err(main):
    """
    Decorator
    Handling global errors
    """
    def wrapp_glob_err(*args, **kwargs):
        try:
            main(*args, **kwargs)
        # Catch all ¯\_(ツ)_/¯
        except Exception:
            with open(config['proj_dir'] + 'glob_err.txt', 'w') as glob_err_f:
                glob_err_f.write(traceback.format_exc())
    return wrapp_glob_err


def check_task_err(task):
    """
    Decorator
    Error handling for individual processes
    """
    def wrapp_task_err(*args, **kwargs):
        try:
            task(*args, **kwargs)
        # Catch all ¯\_(ツ)_/¯
        except Exception:
            with open(config['proj_dir'] +
                      'task_err_' +
                      datetime.datetime .today()
                      .strftime('%Y-%m-%d--%H-%M-%S') +
                      '.txt', 'w') as task_err_f:
                task_err_f.write(traceback.format_exc())
    return wrapp_task_err


def connect(log_file_name, task_params, mac, config):
    """
    Vendor selection
    """
    if task_params['vendor'] == 'cisco':
        cisco_connection(log_file_name, task_params, mac, config)


@check_task_err
def execute_task(decoded_message):
    """
    Performs processing of a single task
    """
    mac = find_macs_in_mess(decoded_message)
    # Logger setup
    if len(mac) > 12:
        log_file_name = 'task_' + str(os.getpid()) + '__' + 'nomac' + '__' + \
            datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    else:
        log_file_name = 'task_' + str(os.getpid()) + '__' + \
            mac.replace('.', '-') + '__' + \
            datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logging.basicConfig(filename=config['proj_dir'] +
                        'logs/' +
                        log_file_name +
                        '.txt',
                        format='%(asctime)s %(message)s',
                        level=logging.INFO,
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.info(f'\r\n=============================TASK=REPORT============'
                 f'=================\r\n\r\n{log_file_name}'
                 f'\r\n\r\n>>>--------------------------MESSAGE------------'
                 f'--------------<<<\r\n\r\n{decoded_message}'
                 f'\r\n\r\n>>>---------------------------------------------'
                 f'--------------<<<\r\n\r\n')
    # Finds the MAC in the ticket
    find_macs_in_mess_check(log_file_name, mac, config)
    # Sends an "request accepted" message with the MAC of the device
    send_start(log_file_name, mac, config)
    # Create a request
    sql_query = create_sql_query(mac, config)
    # Makes a request to a log server
    sql_answer = log_server_check(sql_query, log_file_name, mac, config)
    sql_answer_check(log_file_name, sql_answer, mac, config)
    # Parses the response
    task_params = log_parse(sql_answer)
    # Checks if the switch is in the excluded list
    ip_list_check(log_file_name, task_params, mac, config)
    # Connects to the device and performs settings
    connect(log_file_name, task_params, mac, config)


def check_message(message_dict):
    """
    Message check
    """
    # Internal or external message?
    if message_dict['email'].split('@')[1] != config['mail_from'] \
            .split('@')[1]:
        restriction = 'Message received from an external source'
        send_violation(message_dict, restriction, config)
    else:
        # Service message <REPORT>
        if 'REPORT' in message_dict['message']:
            if message_dict['email'] == config['mailbox']:
                send_report(message_dict['email'], config)
        # Service message <KILL>
        elif 'KILL' in message_dict['message']:
            if message_dict['email'] == config['mailbox']:
                kill_task(message_dict, config)
        else:
            # Sender from inf-sec?
            if message_dict['email'] in config['infsec_emails']:
                proc = Process(target=execute_task,
                               name=execute_task,
                               args=(message_dict['message'],))
                proc.daemon = True
                proc.start()
            else:
                restriction = 'Request not accepted: sender not from inf-sec'
                send_violation(message_dict, restriction, config)


def read_mail(config):
    """
    Picks up mail from mailbox
    """
    server = poplib.POP3(config['mail_server'])
    server.user(config['mail_from'])
    server.pass_(config['mail_pass'])
    try:
        resp, lines, octets = server.retr(1)
        msg_content = b'\r\n'.join(lines).decode('utf-8')
        msg = Parser().parsestr(msg_content)
        email_from = (msg.get('From')).split('<')[1].replace('>', '')
        if msg.is_multipart():
            raw_mess = ''
            for part in msg.get_payload():
                charset = part.get_content_charset()
                if charset is not None:
                    mess_part = part.get_payload(decode=True).decode(charset)
            raw_mess += mess_part
        else:
            charset = msg.get_content_charset()
            raw_mess = msg.get_payload(decode=True).decode(charset)
        raw_message_dict = {'email': email_from, 'message': raw_mess}
        # Deleting a processed message
        server.dele(1)
        server.quit()
        return raw_message_dict
    # If the box is empty
    except Exception:
        server.quit()
        return {'email': 'Empty', 'message': 'No messages or other exception'}


@check_glob_err
def main():
    """
    Message processing one by one
    """
    while True:
        log_rotation(config)
        # Decoded message caching
        raw_message_dict = read_mail(config)
        if raw_message_dict['message'] != 'No messages or other exception':
            message_dict = clearing_message(raw_message_dict)
            check_message(message_dict)
        else:
            time.sleep(60)


if __name__ == '__main__':
    # Configuration
    project_dir = argv[1]
    with open(project_dir + 'conf.json', 'r') as conf:
        config = json.load(conf)
    main()
