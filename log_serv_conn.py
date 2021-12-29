#! /usr/bin/env python3

import json
import time
import datetime
import logging
import subprocess
import re
from service_funcs import end_task
from netmiko import (
    ConnectHandler,
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
)


def log_server_check(sql_query, log_file_name, mac, config):
    """
    Отправляет SQL запрос к БД лог-сервера и ждет ответа в течение рабочего дня
    По истечении рабочего дня возвращает сообщение об ошибке
    """
    with open(config['proj_dir'] + 'sql_params.json', 'r') as sql_params:
        sql = json.load(sql_params)
    try:
        with ConnectHandler(**sql) as sql_ssh:
            logging.info('\r\n>>>------------------------SQL-ЗАПРОС-------------------------<<<\r\n\r\n\r\n' +
                 sql_query.split('"')[1] + '\r\n\r\nОжидание подключения устройства...............\r\n\r\n')
            while True:
                hour = int(datetime.datetime.today().strftime('%H'))
                if hour < 18:
                    answer = sql_ssh.send_command(sql_query, delay_factor=30)
                    if 'PORT_SECURITY-2-PSECURE_VIOLATION' in answer:
                        answer = {'vendor': 'cisco', 'answer': answer}
                        sql_ssh.disconnect()
                        return answer
                    time.sleep(60)
                # Конец рабочего дня
                elif hour >= 18:
                    no_connecting = '!!!NOT OK!!! События с данным устройством не найдены в базе лог-сервера в течение ' \
                                    'рабочего дня\r\n\r\nЗаявка не выполнена'
                    answer = {'answer': no_connecting}
                    sql_ssh.disconnect()
                    return answer
    except (NetmikoTimeoutException, NetmikoAuthenticationException) as error:
        logging.info('НЕ МОГУ ПОДКЛЮЧИТЬСЯ К ЛОГ-СЕРВЕРУ\r\n\r\n' + str(error) + '\r\n\r\nЗаявка не выполнена')
        task_result = 'Заявка не выполнена'
        end_task(log_file_name, mac, task_result, config)

