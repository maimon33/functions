#!/bin/python

import calendar

from datetime import date, datetime


def _format_date(date_string, format):
    if format == "day":
        return date_string.strftime('%Y-%m-%d')
    elif format == "month":
        return date_string.strftime('%Y-%m')


def _get_yesterdays_date():
    current = date.today()
    if current.day == 1:
        return _format_date(date(current.year,
                                 current.month-1,
                                 (calendar.monthrange(
                                     current.year,
                                     current.month-1)[1])), "day")
    else:
        return _format_date(date(current.year,
                                 current.month,
                                 current.day-1), "day")


def _get_last_month():
    current = date.today()
    return _format_date(date(
        current.year,
        current.month-1,
        (calendar.monthrange(current.year,
                             current.month-1)[1])), "month")