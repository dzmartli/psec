#! /usr/bin/env python3

import re


def ip_addr(sql_answer):
    """
    IP-address
    """
    reg_ip = r'([0-9]{1,3}[.]){3}([0-9]{1,3})'
    answer = sql_answer['answer']
    match_ip = re.search(reg_ip, answer)
    ip = match_ip.group()
    return ip


def cisco_port_num(sql_answer):
    """
    Port number
    """
    reg_port = r'(\S+Ethernet\d+/\d+/\d+)|(\S+Ethernet\d+/\d+)|(\S+Ethernet\d+)'
    answer = sql_answer['answer']
    match_port = re.search(reg_port, answer)
    port = match_port.group()
    return port


def cisco_mac_addr(sql_answer):
    """
    MAC-address
    """
    reg_mac = r'([0-9a-f]{4}[.]){2}([0-9a-f]{4})'
    answer = sql_answer['answer']
    match_mac = re.search(reg_mac, answer)
    mac = match_mac.group()
    return mac


def log_parse(sql_answer):
    """
    Task params
    """
    if sql_answer['vendor'] == 'cisco':
        task_params = {
            'vendor': 'cisco',
            'ip_addr': ip_addr(sql_answer),
            'mac_addr': cisco_mac_addr(sql_answer),
            'port_num': cisco_port_num(sql_answer),
        }
        return task_params

