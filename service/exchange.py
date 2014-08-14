# http://msdn.microsoft.com/en-us/library/office/dd877045(v=exchg.140).aspx
# https://pyexchange.readthedocs.org/en/latest/
import json
import datetime

from memoize import Memoizer
from pyexchange import Exchange2010Service
from pyexchange import ExchangeNTLMAuthConnection
from pyexchange.exceptions import FailedExchangeException
from sqlalchemy import or_

store = {}
memo = Memoizer(store)


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

    @memo(max_age=300)
    def get_service(self, username, password):
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
        service = self.get_service(username, password)
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

    def _create_event(self, event):
        """
        Create the given event from Outlook
        """
        raise Exception('I dont know how to create events yet!')

    def _update_event(self, event):
        """
        Update the given event from Outlook
        """
        raise Exception('I dont know how to update events yet!')

    def _delete_event(self, event):
        """
        Delete the given event from Outlook
        """
        raise Exception('I dont know how to delete events yet!')

    def _sync_user(self, user):
        """
        Sync the given user with Exchange
        Return stats about what happened
        """
        # Get events which have been updated
        result = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'deleted': 0,
        }
        events = self._get_user_updated_events(user)
        for event in events:
            if not event.deleted:
                # This event is waiting to be created/updated
                if event.exchange_id is None:
                    # This event has never been created, create it now!
                    self._create_event(event)
                    result['created'] += 1
                else:
                    # This event already exists, update it!
                    self._update_event(event)
                    result['updated'] += 1
            else:
                # This event is waiting to be deleted
                if event.exchange_id is None:
                    # This event has never been created, no need to delete it!
                    result['skipped'] += 1
                else:
                    # Really delete this event
                    self._delete_event(event)
                    result['deleted'] += 1

            event.update = False
            event.last_push = datetime.datetime.now()

        self.db.session.commit()

        return result

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
            result = str(ex)
            user.exchange_last_sync_status = 'Error! {0}'.format(
                str(ex)
            )
        user.exchange_last_sync_time = datetime.datetime.now()
        self.db.session.commit()

        return result

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
