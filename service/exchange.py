# http://msdn.microsoft.com/en-us/library/office/dd877045(v=exchg.140).aspx
# https://pyexchange.readthedocs.org/en/latest/

from memoize import Memoizer
from pyexchange import Exchange2010Service
from pyexchange import ExchangeNTLMAuthConnection
from pyexchange.exceptions import FailedExchangeException

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

    def sync(self):
        """
        Sync events into Exchange
        """
        pass
