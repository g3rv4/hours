config = {
    'redis_db': 0,
    'timedoctor': {
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
        'server': 'http://localjira:2990/jira',
        'username': 'admin',
        'password': 'admin',
        'ticket_regexps': [
            'TEST-[0-9]+',
            'DEV-[0-9]+',
            'SAL-[0-9]+'
        ]
    },
    'timezone': 'US/Pacific',

    # Only required if the username in the timedoctor section is set
    'phantomjs_path': '/usr/local/bin/phantomjs'
}