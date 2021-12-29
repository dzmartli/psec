#! /usr/bin/env python3

import re
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
    clean_message,
    log_rotation,
    send_report,
    send_start,
    end_task,
    kill_in_mess,
    ip_list_check,
    sql_answer_check,
    find_macs_in_mess_check,
    create_sql_query,
    find_macs_in_mess,
)


def check_glob_err(main):
    """
    Декоратор
    Обработка глобальных ошибок
    """
    def wrapp_glob_err(*args, **kwargs):
        try:
            main(*args, **kwargs)
        except Exception as glob_err:
            with open(config['proj_dir'] + 'glob_err.txt', 'w') as glob_err_f:
                glob_err_f.write(traceback.format_exc())
    return wrapp_glob_err


def check_task_err(task):
    """
    Декоратор
    Обработка ошибок отдельных процессов
    """
    def wrapp_task_err(*args, **kwargs):
        try:
            task(*args, **kwargs)
        except Exception as task_err:
            with open(config['proj_dir'] + 'task_err_' +
                      datetime.datetime.today().strftime('%Y-%m-%d--%H-%M-%S') +'.txt', 'w') as task_err_f:
                task_err_f.write(traceback.format_exc())
    return wrapp_task_err


def connections(log_file_name, task_params, mac, config):
    """
    Выбор вендора
    """
    if task_params['vendor'] == 'cisco':
        cisco_connection(log_file_name, task_params, mac, config)


@check_task_err
def task(decoded_message):
    """
    Выполняет обработку одной завки
    """
    mac = find_macs_in_mess(decoded_message)
    # Настройка логгера
    if len(mac) > 12:
        log_file_name = 'task_' + str(os.getpid()) + '__' + 'nomac' + '__' + \
                        datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    else:
        log_file_name = 'task_' + str(os.getpid()) + '__' + mac.replace('.', '-') + '__' + \
                        datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logging.basicConfig(filename=config['proj_dir'] + 'logs/' + log_file_name + '.txt',
                        format='%(asctime)s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.info('\r\n=============================ОТЧЕТ=ПО=ЗАЯВКЕ=============================\r\n\r\n' +
                 log_file_name +
                 '\r\n\r\n>>>---------------------ТЕКСТ-СООБЩЕНИЯ-----------------------<<<\r\n\r\n' +
                 decoded_message +
                 '\r\n\r\n>>>-----------------------------------------------------------<<<\r\n\r\n')
    # Находит МАС в заявке
    find_macs_in_mess_check(log_file_name, mac, config)
    # Отправляет сообщение "заявка принята" с МАСом устройства
    send_start(log_file_name, mac, config)
    # Создает запрос
    sql_query = create_sql_query(mac, config)
    # Делает запрос на лог-сервер
    sql_answer = log_server_check(sql_query, log_file_name, mac, config)
    sql_answer_check(log_file_name, sql_answer, mac, config)
    # Парсит ответ от лог-сервера
    task_params = log_parse(sql_answer)
    # Проверяет есть ли коммутатор в списке исключенных
    ip_list_check(log_file_name, task_params, mac, config)
    # Подключается к устройству и выполняет настройки
    connections(log_file_name, task_params, mac, config)


def message(message_dict):
    """
    Проверка сообщения
    """
    # Внутренне или внешнее сообщение?
    if message_dict['email'].split('@')[1] != config['mail_from'].split('@')[1]:
        restriction = 'Сообщение получено из внешнего источника.'
        send_violation(message_dict, restriction, config)
    else:
        # Служебное сообщение с кнопкой <REPORT>
        if 'REPORT' in message_dict['message']:
            if message_dict['email'] == config['mailbox']:
                send_report(message_dict['email'], config)
        # Служебное сообщение с кнопкой <KILL>
        elif 'KILL' in message_dict['message']:
            if message_dict['email'] == config['mailbox']:
                kill_in_mess(message_dict, config)
        else:
            # Отправитель сотрудник информационной безопасности?
            if message_dict['email'] in config['infsec_emails']:
                proc = Process(target=task, name=task, args=(message_dict['message'],))
                proc.daemon = True
                proc.start()
            else:
                restriction = 'Заявка не принята: не сотрудник информационной безопасности.'
                send_violation(message_dict, restriction, config)


def read_mail(config):
    """
    Забирает письмо из почтового ящика
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
        # Удаление обработанного письма
        server.dele(1)
        server.quit()
        return raw_message_dict
    # Если ящик пустой
    except Exception:
        server.quit()
        return None


@check_glob_err
def main():
    """
    Обработка сообщений по одному
    """
    while True:
        log_rotation(config)
        # Кэширование декодированного сообщения
        raw_message_dict = read_mail(config)
        if raw_message_dict is not None:
            message_dict = clean_message(raw_message_dict)
            message(message_dict)
        else:
            time.sleep(60)


if __name__ == '__main__':
    # Конфигурация
    project_dir = argv[1]
    with open(project_dir + 'conf.json', 'r') as conf:
        config = json.load(conf)
    main()

