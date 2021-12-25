#! /usr/bin/env python3

from service_funcs import end_task


class Wrapp:
    """
    Класс врапперов для обработки методов подключений
    """
    @staticmethod
    def failed_check(method):
        """
        Декоратор
        Если проверка пройдена, перейти на следующую
        """
        def wrapp_failed_check(self):
            if method(self) == False:
                task_result = 'Заявка не выполнена'
                end_task(self.log_file_name, self.mac, task_result, self.config)
        return wrapp_failed_check

    @staticmethod
    def next_check(method):
        """
        Декоратор
        Если проверка не пройдена, перейти на следующую
        """
        def wrapp_next_check(self):
            if method(self) == True:
                task_result = 'Заявка выполнена'
                end_task(self.log_file_name, self.mac, task_result, self.config)
        return wrapp_next_check

    @staticmethod
    def pass_check(method):
        """
        Декоратор
        Последняя проверка
        """
        def wrapp_pass_check(self):
            if method(self) == True:
                task_result = 'Заявка выполнена'
            else:
                task_result = 'Заявка не выполнена'
            end_task(self.log_file_name, self.mac, task_result, self.config)
        return wrapp_pass_check