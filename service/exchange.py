# http://msdn.microsoft.com/en-us/library/office/dd877045(v=exchg.140).aspx
# https://pyexchange.readthedocs.org/en/latest/
import json
import datetime

from memoize import Memoizer
from pyexchange import Exchange2010Service
from pyexchange import ExchangeNTLMAuthConnection
from pyexchange.exceptions import FailedExchangeException, ExchangeItemNotFoundException
from sqlalchemy import or_

from service import utils


HTML_BODY = u"""<html>
    <body>
        <h1>Holiday</h1>
        Improted from <a href="https://cascadehrponline.net/">Cascade</a> by <a href="http://outcade.herokuapp.com/">Outcade</a>
    </body>
</html>"""


class Exchange(object):
    def __init__(self, db, asmx_url, domain):
        # Validate what's passed in
        if asmx_url[-5:] != '.asmx':
            possible_url = '{0}/EWS/Exchange.asmx'.format(asmx_url)
            raise Exception(
                'Exchange asmx_url must end with .asmx (did you mean "{0}"?)'.format(
                    possible_url
                )
            )

        # Save everything for later
        self.db = db
        self.asmx_url = asmx_url
        self.domain = domain

    @utils.memo(max_age=300)
    def _get_service(self, username, password):
        """
        Get the calendar for the given connection
        """
        connection = ExchangeNTLMAuthConnection(
            url=self.asmx_url,
            username='{domain}\\{username}'.format(
                domain=self.domain,
                username=username,
            ),
            password=password
        )

        service = Exchange2010Service(connection)

        return service

    def test_login(self, username, password):
        """
        Check that the given username and password can login to self.asmx_url
        """
        service = self._get_service(username, password)
        try:
            service.folder().find_folder('root')
        except FailedExchangeException:
            # Request failed; hopefully that means incorrect login
            return False
        return True

    def _get_user_updated_events(self, user):
        """
        Get all events for the user which have need to be updated
        """
        events = self.db.session.query(
            self.db.models.Event
        ).filter(
            self.db.models.Event.user == user,
            self.db.models.Event.updated == True,
        ).all()

        return events

    def _create_event(self, event, calendar):
        """
        Create the given event from Outlook
        """
        exchange_event = calendar.new_event(
            subject=u'Holiday',
            attendees=[],
            location=u'Holiday',
            start=event.start,
            end=event.end,
            html_body=HTML_BODY,
        )

        # Connect to Exchange and create the event
        exchange_event.create()

        # Save the id to the DB
        event.exchange_id = exchange_event.id

    def _update_event(self, event, calendar):
        """
        Update the given event from Outlook
        """
        raise Exception('I dont know how to update events yet!')

    def _delete_event(self, event, calendar):
        """
        Delete the given event from Outlook
        """
        try:
            # Get the event from outlook
            exchange_event = calendar.get_event(id=event.exchange_id)

            # Cancel it!
            exchange_event.cancel()
        except ExchangeItemNotFoundException:
            # Event is already gone, ignore it
            pass

    def _sync_user(self, user):
        """
        Sync the given user with Exchange
        Return stats about what happened
        """
        # Get events which have been updated
        events = self._get_user_updated_events(user)

        # Get the Exchange calendar service for this user
        service = self._get_service(
            user.exchange_username,
            user.exchange_password,
        )
        calendar = service.calendar()

        # Process the events
        result = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'deleted': 0,
        }
        for event in events:
            if not event.deleted:
                # This event is waiting to be created/updated
                if event.exchange_id is None:
                    # This event has never been created, create it now!
                    self._create_event(event, calendar)
                    result['created'] += 1
                else:
                    # This event already exists, update it!
                    self._update_event(event, calendar)
                    result['updated'] += 1
            else:
                # This event is waiting to be deleted
                if event.exchange_id is None:
                    # This event has never been created, no need to delete it!
                    result['skipped'] += 1
                else:
                    # Really delete this event
                    self._delete_event(event, calendar)
                    result['deleted'] += 1

            event.updated = False
            event.last_push = datetime.datetime.now()

        self.db.session.commit()

        return result

    @utils.record_runtime
    def sync_user(self, user):
        """
        Sync the given user with Exchange
        Return stats about what happened
        """
        try:
            result = self._sync_user(user)
            # Save success message to the user
            user.exchange_last_sync_status = 'Success! {0}'.format(
                json.dumps(result)
            )
        except Exception, ex:
            # Save the exception to the user
            result = {
                'error': str(ex),
            }
            user.exchange_last_sync_status = 'Error! {0}'.format(
                str(ex)
            )
        user.exchange_last_sync_time = datetime.datetime.now()
        self.db.session.commit()

        return result

    @utils.record_runtime
    def sync(self):
        """
        Sync all users events with Exchange
        Return stats about what happened
        """
        users = self.db.session.query(
            self.db.models.User
        ).all()
        results = {}
        for user in users:
            result = self.sync_user(user)
            results[user.exchange_username] = result
        return results
