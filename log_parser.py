#! /usr/bin/env python3
"""
Parser for answers from log-server
"""
import logging
import re
from typing import Dict

from service_funcs import end_task


def get_cisco_ip_addr(answer: str,
                      log_file_name: str,
                      mac: str,
                      config: dict
                      ) -> str:
    """
    IP-address

    Args:
        answer (str): Answer from log-server
        log_file_name (str): Log file name (for current task)
        mac (str): Device MAC-address
        config (dict): Dict with config data

    Raises:
        RuntimeError("end_task() does not work properly"): If end_task()
            does not end the process

    Returns:
        ip (str): Device IP-address
    """
    reg_ip: str = r'([0-9]{1,3}[.]){3}([0-9]{1,3})'
    match_ip = re.search(reg_ip, answer)
    if match_ip is None:
        logging.info('IP-address cannot be found in message\r\n\r\n'
                     '\r\n\r\nTask failed')
        task_result = 'Task failed'
        end_task(log_file_name, mac, task_result, config)
        raise RuntimeError("end_task() does not work properly")
    ip = match_ip.group()
    return ip


def get_cisco_port_num(answer: str,
                       log_file_name: str,
                       mac: str,
                       config: dict
                       ) -> str:
    """
    Port number

    Args:
        answer (str): Answer from log-server
        log_file_name (str): Log file name (for current task)
        mac (str): Device MAC-address
        config (dict): Dict with config data

    Raises:
        RuntimeError("end_task() does not work properly"): If end_task()
            does not end the process

    Returns:
        port (str): Device port number
    """
    re_port: str = r'(\S+Ethernet\d+/\d+/\d+)' \
        r'|(\S+Ethernet\d+/\d+)|(\S+Ethernet\d+)'
    match_port = re.search(re_port, answer)
    if match_port is None:
        logging.info('Port number cannot be found in message\r\n\r\n'
                     '\r\n\r\nTask failed')
        task_result = 'Task failed'
        end_task(log_file_name, mac, task_result, config)
        raise RuntimeError("end_task() does not work properly")
    port = match_port.group()
    return port


def log_parse(sql_answer: Dict[str, str],
              log_file_name: str,
              mac: str,
              config: dict
              ) -> Dict[str, str]:
    """
    Task params

    Args:
        sql_answer (dict): Answer from log-server with vendor indication
        log_file_name (str): Log file name (for current task)
        mac (str): Device MAC-address
        config (dict): Dict with config data

    Raises:
        ValueError("task_params['vendor'] must be 'cisco'"
                   "other vendors are not yet implemented"):
            Other device vendors not supported yet

    Returns:
        task_params (dict): Dict with task params
    """
    answer = sql_answer['answer']
    if sql_answer['vendor'] == 'cisco':
        task_params = {
            'vendor': 'cisco',
            'ip_addr': get_cisco_ip_addr(answer, log_file_name, mac, config),
            'mac_addr': mac[:4] + '.' + mac[4:8] + '.' + mac[8:12],
            'port_num': get_cisco_port_num(answer, log_file_name, mac, config),
        }
        return task_params
    else:
        raise ValueError("task_params['vendor'] must be 'cisco'"
                         "other vendors are not yet implemented")
