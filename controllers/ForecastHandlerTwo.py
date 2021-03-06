import jinja2
import os
import webapp2
import ast
from google.appengine.api import urlfetch

from google.appengine.api import users


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname('oneclick0827'), 'templates')),
)


class ForecastTwoHandler(webapp2.RequestHandler):
    transaction_history_url = "http://api108094sandbox.gateway.akana.com/IVRCCMaintenanceREST/account/transactionHistory"
    transaction_history_hardcodedData = {
        "transactionIdentifier": "0f8fad5b-d9cb-469f-a165-70867728950e",
        "messageIdentifier": "0f8fad5b-d9cb-469f-a165-70867728950e",
        "messageDateTime": "1999-05-31T13:20:00-05:00",
        "messageSequenceIdentifier": "1",
        "requestorInfo": {
            "serverIdentifier": "IVR",
            "componentIdentifier": "IVRMISC",
            "userIdentifier": {
                "name": "CredCardActAppIDDev",
                "parameters": {
                    "nameValuePair": {
                        "name": "CertSubjectDN",
                        "value": "cn=Client,ou=USB.COM,o=ESD,l=St. Paul,st=MN,c=US"
                    }
                }
            }
        },
        "ccTranHistoryRequest": {
            "ivrIdentifierData": {
                "requestingApplicationName": "CCIVR",
                "clientSource": "I",
                "serviceVersion": "1.0",
                "requestIdentifier": "testcase10"
            },
            "ccTranHistoryRequestData": {
                "accountNumber": "4081840012169457",
                "requestType": "StatementMonth",
                "statementMonth": "10",
                "tranSequence": "Chronological",
                "authIndicator": "ExcludeAuth",
                "continueNumber": "1",
                "maxItems": "10000000"
            }
        }
    }
    bank_account_url = "http://api108087sandbox.gateway.akana.com/AccountDetailRESTService/account/details"
    bank_account_hardcodedData = {
        "transactionIdentifier": "368c07ac-3c9e-41b0-8cc9-9f3405e37fb1",
        "messageIdentifier": "5feff82f-4603-4996-a0e6-bf105654f2b3",
        "messageDateTime": "2015-11-19T20:14:33.651Z",
        "messageSequenceIdentifier": "1",
        "requestorInfo": {
            "serverIdentifier": "local",
            "componentIdentifier": "***"
        },
        "getAccountDetailRequest": {
            "getAccountDetail": {
                "accountKeyIdentifier": {
                    "operatingCompanyIdentifier": "125",
                    "productCode": "CHX",
                    "primaryIdentifier": "4444444444444444"
                },
                "returnFiveStarPackageCodeSwitch": "true",
                "includeAddressSwitch": "true"
            }
        }
    }

    # TODO: Set as POST in the end
    def get(self):
        template = JINJA_ENVIRONMENT.get_template('forecasttwo.html')

        # Transaction History
        response = urlfetch.Fetch(
            self.transaction_history_url,
            payload=str(self.transaction_history_hardcodedData),
            method=urlfetch.POST,
            headers = {
                'vary': 'Accept-Encoding',
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            allow_truncated=False,
            follow_redirects=True,
            deadline=None,
            validate_certificate=None
        )

        if response.status_code == 200:
            # Content
            content = ast.literal_eval(response.content) \
                .get('CCTranHistoryResponseData') \
                .get('TransactionDetails') \
                .get('TransactionData')
            ordered_content = self.monthly_processing(content)
            ordered_content = self.setMonetaryValue(ordered_content)
        else:
            self.response.out.write("ERROR")

        ordered_content['balance'] = self.getCurrentBalance
        ordered_content['revenue'] = 10000
        self.response.out.write(template.render(ordered_content))

    def setMonetaryValue(self, json):
        for key, value in json.iteritems():
            if isinstance(value, float) or isinstance(value, int):
                json[key] = round(value, 2)
            elif isinstance(value, dict):
                self.setMonetaryValue(value)

        return json

    def monthly_processing(self, content):
        template_values = {
            'total_debit': 0,
            'total_credit': 0,
            'type_debit': {},
            'type_credit': {},
            'graph': {
                'debit': {},
                'credit': {},
                'debit_and_credit': {}
            }
        }

        # Iteration
        for transaction in content:
            amount = float(transaction['TransactionAmount'])
            mcc_code = transaction['SICMCCCode']
            transaction_date = transaction['TransactionPostDate']

            # For graph
            if transaction_date in template_values['graph']['debit_and_credit']:
                value = template_values['graph']['debit_and_credit'][transaction_date]
                template_values['graph']['debit_and_credit'][transaction_date] = value + amount
            else:
                template_values['graph']['debit_and_credit'][transaction_date] = amount

            # Consolidate Credit / Debit
            if transaction.get('TransactionType') == 'Debit' and amount > 0:
                template_values['total_debit'] += amount

                if mcc_code in template_values['type_debit']:
                    value = template_values.get('type_debit')[mcc_code]
                    template_values.get('type_debit')[mcc_code] = value + amount
                else:
                    template_values.get('type_debit')[mcc_code] = amount

                if transaction_date in template_values['graph']['debit']:
                    value = template_values['graph']['debit'][transaction_date]
                    template_values['graph']['debit'][transaction_date] = value + amount
                else:
                    template_values['graph']['debit'][transaction_date] = amount

            elif transaction.get('TransactionType') == 'Credit' and amount > 0:
                template_values['total_credit'] += amount

                if mcc_code in template_values['type_credit']:
                    value = template_values.get('type_credit')[mcc_code]
                    template_values.get('type_credit')[mcc_code] = value + amount
                else:
                    template_values.get('type_credit')[mcc_code] = amount

                if transaction_date in template_values['graph']['credit']:
                    value = template_values['graph']['credit'][transaction_date]
                    template_values['graph']['credit'][transaction_date] = value + amount
                else:
                    template_values['graph']['credit'][transaction_date] = amount
        return template_values

    @property
    def getCurrentBalance(self):
        # Bank Account
        response = urlfetch.Fetch(self.bank_account_url,
                                  payload=str(self.bank_account_hardcodedData),
                                  method=urlfetch.POST,
                                  headers={
                                      'vary': 'Accept-Encoding',
                                      "Content-Type": "application/json",
                                      "Accept": "application/json"
                                  },
                                  allow_truncated=False,
                                  follow_redirects=True,
                                  deadline=None,
                                  validate_certificate=None)

        if response.status_code == 200:
            content = ast.literal_eval(response.content)

            current_balance = content \
                .get('DetailAccountList') \
                .get('CardAccount') \
                .get('AccountDetail') \
                .get('Amounts') \
                .get('DDAAvailableBalanceAmount')

            return current_balance
        else:
            return "Something went wrong - Please try again"