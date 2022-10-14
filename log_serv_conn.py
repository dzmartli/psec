#! /usr/bin/env python3

import datetime
import json
import logging
import time
from typing import Dict

from netmiko import (ConnectHandler,
                     NetmikoAuthenticationException,
                     NetmikoTimeoutException)

from service_funcs import end_task


def log_server_check(sql_query: str,
                     log_file_name: str,
                     mac: str,
                     config: dict
                     ) -> Dict[str, str]:
    """
    Sends an SQL query to the log server database
    and waits for a response during the working day
    """
    with open(config['proj_dir'] + 'sql_params.json', 'r') as sql_params:
        sql = json.load(sql_params)
    try:
        with ConnectHandler(**sql) as sql_ssh:
            logging.info('\r\n>>>------------------------SQL-QUERY---------'
                         '----------------<<<\r\n\r\n\r\n' +
                         sql_query.split('"')[1] +
                         '\r\n\r\nWaiting for device connection............'
                         '...\r\n\r\n')
            while True:
                hour = int(datetime.datetime.today().strftime('%H'))
                if hour < 18:
                    answer = sql_ssh.send_command(sql_query, delay_factor=30)
                    if 'PORT_SECURITY-2-PSECURE_VIOLATION' in answer:
                        answer = {'vendor': 'cisco', 'answer': answer}
                        sql_ssh.disconnect()
                        return answer
                    time.sleep(60)
                # End of the working day
                else:
                    no_connecting = '!!!NOT OK!!! Events with this device' \
                        'were not found in the log server database ' \
                        'during the working day\r\n\r\nTask failed'
                    answer = {'vendor': 'None', 'answer': no_connecting}
                    sql_ssh.disconnect()
                    return answer
    except (NetmikoTimeoutException, NetmikoAuthenticationException) as error:
        logging.info('LOG SERVER CONNECTION ERROR\r\n\r\n' +
                     str(error) +
                     '\r\n\r\nTask failed')
        task_result = 'Task failed'
        end_task(log_file_name, mac, task_result, config)
        raise RuntimeError("end_task() does not work properly")
