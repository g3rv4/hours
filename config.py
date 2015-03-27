config = {
    'redis_db': 0,
    'timedoctor': {
        # valid values are 'api' and 'selenium'. If 'api' is selected, the client_id and client_secret
        # are required in addition to the username and password
        'method': 'selenium',

        'client_id': '',
        'client_secret': '',
        'username': '',
        'password': '',

        # min task length in seconds
        'min_task_length': 3 * 60,

        # Required if you have multiple companies in your account
        # If set, the system won't check your companies
        'company_id': 0
    },
    'jira': {
        'server': '',
        'username': '',
        'password': '',
        'ticket_regexps': [
            'DEV-[0-9]+',
            'SAL-[0-9]+',
            'AT-[0-9]+',
            'EV-[0-9]+'
        ]
    },
    'email': {
        'aws': {
            'access_key_id': '',
            'secret_access_key': ''
        },
        'from': '',
        'default_to': '',
        'template': 'clean'
    },
    'timezone': 'US/Pacific',

    # Only required if the username in the timedoctor section is set
    'selenium': {
        'browser': 'phantomjs',
        'browsers': {
            'phantomjs': {
                'driver_class': 'PhantomJS',
                'executable_path': '/usr/local/bin/phantomjs'
            },
            'chrome': {
                'driver_class': 'Chrome',
                'executable_path': '/Users/gervasio/chromedriver'
            }
        }
    }
}
