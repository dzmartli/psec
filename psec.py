#! /usr/bin/env python3
"""
Main script
"""
import datetime
import json
import logging
import os
import poplib
import time
import traceback
from email.parser import Parser
from multiprocessing import Process
from sys import argv
from typing import Callable, Dict

from cisco_conn import cisco_connection
from log_parser import log_parse
from log_serv_conn import log_server_check
from service_funcs import (clearing_message,
                           create_sql_query,
                           find_macs_in_mess,
                           find_macs_in_mess_check,
                           ip_list_check,
                           kill_task,
                           log_rotation,
                           send_report,
                           send_start,
                           send_violation,
                           sql_answer_check)


def check_glob_err(main: Callable) -> Callable:
    """
    Decorator
    Handling global errors

    Args:
        main (Callable): Main function

    Returns:
        wrapp_glob_err (Callable): Wrapper
    """
    def wrapp_glob_err(*args, **kwargs):
        try:
            main(*args, **kwargs)
        # Catch all ¯\_(ツ)_/¯
        except Exception:
            with open(config['proj_dir'] + 'glob_err.txt', 'w') as glob_err_f:
                glob_err_f.write(traceback.format_exc())
    return wrapp_glob_err


def check_task_err(task: Callable) -> Callable:
    """
    Decorator
    Error handling for individual processes

    Args:
        main (Callable): Task function

    Returns:
        wrapp_glob_err (Callable): Wrapper
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


def connect(log_file_name: str,
            task_params: Dict[str, str],
            mac: str,
            config: dict
            ) -> None:
    """
    Vendor selection

    Args:
        log_file_name (str): Log file name (for current task)
        task_params (dict): Dict with task params
        mac (str): Device MAC-address
        config (dict): Dict with config data
    Raises:
        ValueError ("task_params['vendor'] must be 'cisco'"
                    "other vendors are not yet implemented"):
            Other device vendors not supported yet
    """
    if task_params['vendor'] == 'cisco':
        cisco_connection(log_file_name, task_params, mac, config)
    else:
        raise ValueError("task_params['vendor'] must be 'cisco'"
                         "other vendors are not yet implemented")


@check_task_err
def execute_task(decoded_message: str) -> None:
    """
    Performs processing of a single task

    Args:
        decoded_message (str): Deccoded message from email
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
    task_params = log_parse(sql_answer, log_file_name, mac, config)
    # Checks if the switch is in the excluded list
    ip_list_check(log_file_name, task_params, mac, config)
    # Connects to the device and performs settings
    connect(log_file_name, task_params, mac, config)


def check_message(message_dict: Dict[str, str]) -> None:
    """
    Message check

    Args:
        message_dict (dict): Dict with message data
            (senders email, and actual data)
    """
    # Internal or external message?
    if message_dict['email'].split('@')[1] != config['mail_from'] \
            .split('@')[1]:
        external_restriction: str = 'Message received from an external source'
        send_violation(message_dict, external_restriction, config)
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
                               name='execute_task',
                               args=(message_dict['message'],))
                proc.daemon = True
                proc.start()
            else:
                sender_restriction: str = 'Request not accepted: ' \
                    'sender not from inf-sec'
                send_violation(message_dict, sender_restriction, config)


def read_mail(config: dict) -> Dict[str, str]:
    """
    Picks up mail from mailbox

    Args:
        config (dict): Dict with config data

    Returns:
        raw_message_dict (dict): Dict with message data
            (senders email, and actual data in raw format)
        (dict): {'email': 'Empty', 'message': 'No messages or other exception'}
            if mailbox is empty (or other exception)
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
            raw_mess: str = ''
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
    # If mailbox is empty or other exception ¯\_(ツ)_/¯
    except Exception:
        server.quit()
        return {'email': 'Empty', 'message': 'No messages or other exception'}


@check_glob_err
def main() -> None:
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
