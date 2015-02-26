config = {
    'redis_db': 0,
    'timedoctor': {
        'client_id': '',
        'client_secret': '',
        'username': '',
        'password': '',

        # Only required / used if you have multiple companies
        'company_id': 0
    },
    'jira': {
        'server': 'http://localjira:2990/jira',
        'username': 'admin',
        'password': 'admin',
        'ticket_regexps': [
            'TEST-[0-9]+',
            'DEV-[0-9]+'
        ]
    },
    'timezone': 'US/Pacific',

    # Only required if the username in the timedoctor section is set
    'phantomjs_path': '/usr/local/bin/phantomjs'
}