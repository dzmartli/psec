#! /usr/bin/env python3
"""
Method decorators for results of procedures (device setup)
"""
from typing import Callable

from service_funcs import end_task


class Wrapp:
    """
    Class for handling connection methods
    """
    @staticmethod
    def failed_check(method: Callable) -> Callable:
        """
        Decorator
        If passed, go to the next

        Args:
            main (Callable): Method

        Returns:
            wrapp_failed_check (Callable): Wrapper
        """
        def wrapp_failed_check(self):
            if not method(self):
                task_result = 'Task failed'
                end_task(self.log_file_name,
                         self.mac,
                         task_result,
                         self.config)
        return wrapp_failed_check

    @staticmethod
    def next_check(method: Callable) -> Callable:
        """
        Decorator
        If not passed, go to the next

        rgs:
            main (Callable): Method

        Returns:
            wrapp_next_check (Callable): Wrapper
        """
        def wrapp_next_check(self):
            if method(self):
                task_result = 'Task completed'
                end_task(self.log_file_name,
                         self.mac,
                         task_result,
                         self.config)
        return wrapp_next_check

    @staticmethod
    def pass_check(method: Callable) -> Callable:
        """
        Decorator
        Last check

        rgs:
            main (Callable): Method

        Returns:
            wrapp_pass_check (Callable): Wrapper
        """
        def wrapp_pass_check(self):
            if method(self):
                task_result = 'Task completed'
            else:
                task_result = 'Task failed'
            end_task(self.log_file_name, self.mac, task_result, self.config)
        return wrapp_pass_check
