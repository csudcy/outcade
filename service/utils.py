import calendar
import datetime
import functools

from memoize import Memoizer

store = {}
memo = Memoizer(store)


def next_month(year, month):
    """
    Return the year and month of the next month
    NOTE: month is 1 based
    """
    return add_months(year, month, 1)


def add_months(year, month, months):
    """
    Return the year and month of #months after the given year and month
    NOTE: month is 1 based
    """
    month += months
    while month > 12:
        month -= 12
        year += 1
    return year, month


def record_runtime(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        start = datetime.datetime.now()
        ret = func(*args, **kwargs)
        diff = datetime.datetime.now() - start
        ret['runtime'] = diff.total_seconds()
        return ret
    return inner


def generate_calendar(db, user, start_year, start_month, months):
    """
    Generate a data structure to allow a calendar style output
    """
    # Get the period we want to show events for
    year = start_year
    month = start_month
    months = 6
    months_start = datetime.date(year=year, month=month, day=1)
    year, month = add_months(year, month, months)
    months_end = datetime.date(year=year, month=month, day=1)

    events = db.session.query(
        db.models.Event
    ).filter(
        db.models.Event.user == user,
        db.models.Event.deleted == False,
        db.models.Event.day >= months_start,
        db.models.Event.day < months_end,
        db.models.Event.deleted == False,
    )


    # Construct the calendar
    year = start_year
    month = start_month
    today = datetime.date.today()
    class Day(object):
        klass = 'calendar_cell_blank'
        text = ''
        caption = ''
        today = False
    event_calendar = []
    for x in xrange(months):
        # Generate 6 weeks of cells
        cells = [Day() for x in xrange(42)]

        # Get the days from calendar
        #monthrange
        mc = calendar.monthcalendar(year, month)
        cell_days = [item for sublist in mc for item in sublist]
        # Remove 0's at the end
        while cell_days[-1] == 0:
            cell_days = cell_days[:-1]
        if cell_days[1] != 0:
            # It looks weird if anything starts on the first few days...
            cell_days = [0]*7 + cell_days
        for i in xrange(len(cell_days)):
            if cell_days[i] != 0:
                day = datetime.date(year=year, month=month, day=cell_days[i])
                if day == today:
                    cells[i].today = True
                if day < today:
                    cells[i].klass = 'calendar_cell_old'
                else:
                    cells[i].klass = 'calendar_cell_empty'
                cells[i].text = cell_days[i]
                cells[i].caption = day.strftime('%a, %b %d')

        # Work out the start day for this month
        cell_days_pre = [cd for cd in cell_days if cd == 0]
        days_pre = len(cell_days_pre)

        # Get the row header
        first_day = datetime.date(year=year, month=month, day=1)
        header = first_day.strftime('%b %Y')

        # Add this row to the list
        event_calendar.append({
            'header': header,
            'days_pre': days_pre,
            'cells': cells,
        })

        # Move to the next month
        year, month = next_month(year, month)


    # Apply events to the calendar
    for event in events:
        # Work out the month for this event
        event_month = event.day.month - start_month
        if event_month < 0:
            # This is next year
            event_month += 12

        # Work out the day for this event
        event_day = event.day.day + event_calendar[event_month]['days_pre'] - 1

        # Update the calendar
        calendar_cell = event_calendar[event_month]['cells'][event_day]
        calendar_cell.klass = calendar_cell_ + event.event_type
        if event.period != 'AFD':
            calendar_cell.text = event.period

    # All done!
    return event_calendar
