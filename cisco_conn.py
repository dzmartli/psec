#! /usr/bin/env python3

import json
import logging
import datetime
from cisco_class import BaseCiscoSSH
from service_funcs import end_task
from netmiko import (
    ConnectHandler,
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
)


def cisco_connection(log_file_name, task_params, mac, config):
    """
    Создает экземпляр класса подключения к коммутатору cisco, выполняет подключение, процедуры проверки и настройки
    """
    with open(config['proj_dir'] + 'cisco_params.json', 'r') as cisco_params:
        cisco = json.load(cisco_params)
    cisco.update({'host': task_params['ip_addr']})
    try:
        with BaseCiscoSSH(task_params, log_file_name, config, **cisco) as cisco_conn:
            logging.info('\r\n>>>-----------------НАСТРОЙКА-ОБОРУДОВАНИЯ--------------------<<<\r\n\r\n\r\n'
                         '!!!STARTLOG!!! ' + task_params['vendor'] + ' ' + task_params['ip_addr'] + ' ' +
                         task_params['port_num'] + ' ' +  task_params['mac_addr'] + ' !!!STARTLOG!!!\r\n\r\n')
            cisco_conn.completed_task()
            cisco_conn.access()
            cisco_conn.max()
            cisco_conn.port_stat()
            cisco_conn.check_hub()
            cisco_conn.mac_on_other_port()
            cisco_conn.already_stick()
            cisco_conn.port_sec_first_try()
            cisco_conn.port_sec_second_try()
    #except (NetmikoTimeoutException, NetmikoAuthenticationException) as error:
    #    logging.info('НЕ МОГУ ПОДКЛЮЧИТЬСЯ К УСТРОЙСТВУ\r\n\r\n' + str(error) + '\r\n\r\nЗаявка не выполнена')
    #    task_result = 'Заявка не выполнена'
    #    end_task(log_file_name, mac, task_result, config)
    # Отлавливаются все исключения (бывают специфичные ошибки netmiko)
    except Exception as error:
        logging.exception('ОШИБКА ВЫПОЛНЕНИЯ ЗАЯВКИ\r\n\r\nЗаявка не выполнена\r\n\r\n')
        task_result = 'Заявка не выполнена'
        end_task(log_file_name, mac, task_result, config)

