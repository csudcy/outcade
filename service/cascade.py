# https://www.cascadehrponline.net/planner.asp?planneropts=3&startyear=2014&startmonth=8
from urlparse import urljoin
import datetime
import json
import logging
import time

import requests
from pyquery import PyQuery as pq
from sqlalchemy.orm.exc import NoResultFound

from service import utils


class Cascade(object):
    base_url = 'https://www.cascadehrponline.net/'

    def __init__(self, db, company):
        # Save everything for later
        self.db = db
        self.company = company

    @utils.memo(max_age=60)
    def _get_session(self, user):
        """
        Login to Cascade & setup a cookie session
        """
        # Create a new session
        session = requests.Session()

        # Call the login function
        logging.debug('Logging in to Cascade...')
        login_url = urljoin(
            self.base_url,
            'logon_funct.asp'
        )
        login_response = session.post(
            login_url,
            allow_redirects=False,
            data={
                'COMPANY': self.company,
                'User ID': user.cascade_username,
                'Password': user.cascade_password,
            },
        )

        if login_response.status_code != 200:
            raise Exception('Received non-200 from Cascade! Got {status_code}.'.format(
                status_code=login_response.status_code,
            ))
        if 'The username or password is incorrect.' in login_response.text:
            raise Exception('Incorrect username or password for Cascade!')

        # Return the logged in session
        return session

    def _get_calendar_html(self, session, year, month, months=1):
        """
        Get the calendar for the user in session for the given year and month.
        NOTE: month is 1 based
        """
        # https://www.cascadehrponline.net/planner.asp?startyear=2014&startmonth=0&monthstoshow=1
        calendar_url = urljoin(
            self.base_url,
            'planner.asp'
        )
        calendar_response = session.get(
            calendar_url,
            params={
                'startyear': year,
                'startmonth': month-1,
                'monthstoshow': months,
            }
        )
        return calendar_response.text

    def _parse_calendar_html(self, calendar_html):
        """
        Get the calendar for the user in session for the given year and month.
        """
        events = []

        # Extract the cells
        dom = pq(calendar_html)
        cells = dom('#planner_content table tr td[cd]')

        # Extract the date cells
        for cell in cells:
            # Check if this is a date cell
            current_date = cell.attrib.get('cd')
            if current_date is None:
                continue

            # Check if this cell is a holiday
            if cell.attrib.get('bgcolor') not in ('Purple', 'Yellow'):
                continue

            # Check if this is AM, PM or the whole day
            start_hour = 8
            end_hour = 20
            cell_text = cell.text_content()
            if cell_text == 'AM':
                # Morning only
                end_hour = 14
            elif cell_text == 'PM':
                # Afternoon only
                start_hour = 14

            # Add an event
            events.append({
                'date': current_date,
                'start_hour': start_hour,
                'end_hour': end_hour,
            })

        return events

    @utils.record_runtime
    def _update_events(self, year, month, user, events):
        """
        Update events in the database based on the given information
        NOTE: month is 1 based!
        Return stats about what happened
        """

        now = datetime.datetime.now()
        results = {
            'created': 0,
            'updated': 0,
            'deleted': 0,
        }

        for event_info in events:
            # Get proper datetimes
            current_datetime = datetime.datetime.strptime(
                event_info['date'],
                '%d/%m/%Y',
            )
            start_datetime = current_datetime + datetime.timedelta(
                hours=event_info['start_hour']
            )
            end_datetime = current_datetime + datetime.timedelta(
                hours=event_info['end_hour']
            )

            # Find or create this event
            try:
                # Find an existing event
                event = self.db.session.query(
                    self.db.models.Event
                ).filter(
                    self.db.models.Event.user == user,
                    self.db.models.Event.start == start_datetime,
                    self.db.models.Event.end == end_datetime,
                    self.db.models.Event.deleted == False,
                ).one()
                results['updated'] += 1
            except NoResultFound, ex:
                # Create a new event
                event = self.db.models.Event(
                    user=user,
                    start=start_datetime,
                    end=end_datetime,
                    updated=True,
                )
                self.db.session.add(event)
                results['created'] += 1

            # Record that we updated/created the event
            event.last_update = now

        # Have to commit now or the last_update changes don't take effect!
        self.db.session.commit()

        # Set any events in the current period that we havent updated to be deleted
        month_start = datetime.datetime(year=year, month=month, day=1)
        year, month = utils.next_month(year, month)
        month_end = datetime.datetime(year=year, month=month, day=1) - datetime.timedelta(seconds=1)

        events_to_delete = self.db.session.query(
            self.db.models.Event
        ).filter(
            self.db.models.Event.user == user,
            self.db.models.Event.start >= month_start,
            self.db.models.Event.start <= month_end,
            self.db.models.Event.deleted == False,
            self.db.models.Event.last_update < now,
        )
        results['deleted'] = events_to_delete.count()
        events_to_delete.update({
            'updated': True,
            'deleted': True,
        })

        self.db.session.commit()

        return results

    def _sync_user(self, user):
        """
        Sync the given user with Cascade
        Return stats about what happened
        """
        # Get the current year and month
        now = datetime.datetime.now()
        year = now.year
        month = now.month

        # Get the info from cascade
        cascade_session = self._get_session(user)
        calendar_html = self._get_calendar_html(
            cascade_session,
            year,
            month,
            months=6,
        )
        events = self._parse_calendar_html(calendar_html)

        # Save it to DB
        result = self._update_events(year, month, user, events)

        return result

    @utils.record_runtime
    def sync_user(self, user):
        """
        Sync the given user with Cascade
        Return stats about what happened
        """
        try:
            # Try to sync the user
            result = self._sync_user(user)
        except Exception, ex:
            # Save the exception to the user
            result = {
                'error': str(ex),
            }

        return result

    @utils.record_runtime
    def sync(self):
        """
        Sync all users events with Cascade
        Return stats about what happened
        """
        users = self.db.session.query(
            self.db.models.User
        ).filter(
            self.db.models.User.sync_enabled == True
        ).all()
        results = {}
        for user in users:
            # Sync the user
            result = self.sync_user(user)

            # Record status on the user
            user.cascade_last_sync_status = json.dumps(result)
            user.cascade_last_sync_time = datetime.datetime.now()
            self.db.session.commit()

            # Record in the full list of results too
            results[user.cascade_username] = result
        return results
