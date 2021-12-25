#! /usr/bin/env python3

import re
import time
import logging
import datetime
from service_funcs import end_task
from wrapp_class import Wrapp
from netmiko import ConnectHandler


class BaseCiscoSSH(Wrapp):
    """
    Класс подключения к коммутатору cisco
    """
    def __init__(self, task_params, log_file_name, config, **cisco):
        self.port = task_params['port_num']
        self.date = datetime.datetime.today().strftime('%b %d')
        self.mac = task_params['mac_addr']
        self.config = config
        self.log_file_name = log_file_name
        self.ssh = ConnectHandler(**cisco)
        self.ssh.enable()
        self.logging_mac = self.ssh.send_command('sh logging | include ' + self.date, delay_factor=10)
        self.log = self.ssh.send_command('sh run interface ' + self.port, delay_factor=5)
        self.int_stat = self.ssh.send_command('sh interface ' + self.port, delay_factor=5)
        self.sh_run = self.ssh.send_command('sh run', delay_factor=5)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.ssh.disconnect()

    @Wrapp.next_check
    def completed_task(self):
        """
        Проверяет выполнялись ли настройки до выставления заявки
        """
        if self.mac in self.log:
            logging.info('<<<OK>>> Настройки выполнены ранее <<<OK>>>\r\n\r\nЗаявка выполнена')
            self.ssh.disconnect()
            return True
        else:
            logging.info('!!!OK!!!! Требуется настройка\r\n')
            return False

    @Wrapp.failed_check
    def access(self):
        """
        Проверяет является ли портом доступа (на случай ошибки IP или порта)
        """
        if 'switchport mode access' in self.log:
            logging.info('!!!OK!!! Порт доступа\r\n')
            return True
        else:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!!! НЕ ПОРТ ДОСТУПА\r\n\r\nЗаявка НЕ выполнена')
            return False

    @Wrapp.failed_check
    def max(self):
        """
        Проверяет допустимое кол-во устройств на порту
        """
        if 'maximum' not in self.log:
            logging.info('!!!OK!!! Разрешено только одно устройство на порту\r\n')
            return True
        else:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!! Настройка нескольких устройств на порту\r\n\r\nЗаявка НЕ выполнена')
            return False

    @Wrapp.failed_check
    def port_stat(self):
        """
        Проверяет состояние порта
        """
        if ' is down' in self.int_stat:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!! Состояние порта DOWN\r\n\r\nЗаявка НЕ выполнена')
            return False
        else:
            logging.info('!!!OK!!! Состояние порта UP\r\n')
            return True

    @Wrapp.failed_check
    def check_hub(self):
        """
        Проверяет подключается ли устройство через хаб
        """
        logging_mac_split = self.logging_mac.split('\n')
        logging_mac_split_all = []
        for line_log in logging_mac_split:
            if all([('%PORT_SECURITY' in line_log), (self.port in line_log)]):
                logging_mac_split_all.append(line_log)
        logging_mac_split_clean = []
        for line_log_ip in logging_mac_split_all:
            if self.mac not in line_log_ip:
                logging_mac_split_clean.append(line_log_ip)
        # Если были PSECURE_VIOLATION на этом же порту за сегодня но с другим МАСом
        if len(logging_mac_split_clean) >= 1:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!! Несколько устройств на порту, подключают хаб\r\n\r\nЗаявка НЕ выполнена')
            return False
        else:
            logging.info('!!!OK!!! Один мак на порту\r\n')
            return True

    @Wrapp.failed_check
    def mac_on_other_port(self):
        """
        Проверяет прилип ли этот МАC к другому порту этого же коммутатора
        """
        if self.mac in self.sh_run:
            int_list = re.findall(r'(\S+Ethernet\S+)', self.sh_run)
            for ints in int_list:
                sh_int = self.ssh.send_command('sh run interface ' + ints, delay_factor=10)
                # Сброс стики не делается, если этот MAC-адрес прилип к порту за котороым стоит хаб
                if self.mac in sh_int:
                    if 'maximum' in sh_int:
                        self.ssh.disconnect()
                        logging.info('!!!NOT OK!!! МАС на другом порту ' +
                             ints + ', но там подключен хаб\r\n\r\nЗаявка НЕ выполнена')
                        return False
                    else:
                        self.ssh.send_command('clear port-security sticky interface ' + ints, delay_factor=10)
                        time.sleep(5)
                        logging.info('!!!OK!!! Портстики сброшен на старом порту ' +
                                      ints + ' (МАС на другом порту)\r\n')
                        return True

    @Wrapp.next_check
    def already_stick(self):
        log = self.ssh.send_command('sh run interface ' + self.port, delay_factor=10)
        if self.mac in log:
            logging.info(log)
            self.ssh.send_command('wr mem', delay_factor=20)
            self.ssh.disconnect()
            logging.info('<<<OK>>> УСПЕШНАЯ НАСТРОЙКА <<<OK>>>\r\n\r\nЗаявка выполнена')
            return True
        else:
            logging.info('!!!OK!!! Сброс порт-стики\r\n')
            return False

    @Wrapp.next_check
    def port_sec_first_try(self):
        """
        Настройка port-security
        """
        self.ssh.send_command('clear port-security sticky interface ' + self.port, delay_factor=5)
        time.sleep(30)
        # Обновляем информацию по порту
        log = self.ssh.send_command('sh run interface ' + self.port, delay_factor=5)
        if self.mac in log:
            logging.info(log)
            self.ssh.send_command('wr mem', delay_factor=20)
            self.ssh.disconnect()
            logging.info('<<<OK>>> УСПЕШНАЯ НАСТРОЙКА <<<OK>>>\r\n\r\nЗаявка выполнена')
            return True
        else:
            logging.info('!!!OK!!! МАС не прилип, нужна вторая попытка\r\n')
            return False

    @Wrapp.pass_check
    def port_sec_second_try(self):
        # Если не хватило времени прилипнуть делается ещё одна попытка
        self.ssh.send_command('clear port-security sticky interface ' + self.port, delay_factor=5)
        time.sleep(240)
        # Обновляем информацию по порту
        log = self.ssh.send_command('sh run interface ' + self.port, delay_factor=5)
        if self.mac in log:
            logging.info(log)
            self.ssh.send_command('wr mem', delay_factor=20)
            self.ssh.disconnect()
            logging.info('<<<OK>>> УСПЕШНАЯ НАСТРОЙКА (повторный сброс) <<<OK>>>\r\n\r\nЗаявка выполнена')
            return True
        else:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!! НЕ УДАЛОСЬ НАСТРОИТЬ, '
                         'МАС НЕ ПРИЛИПАЕТ К ПОРТУ\r\n\r\nЗаявка не выполнена')
            return False