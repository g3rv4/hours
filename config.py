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
        'server': '',
        'username': '',
        'password': '',
        'ticket_regexps': [
            'DEV-[0-9]+',
            'SAL-[0-9]+',
            'AT-[0-9]+',
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
    'phantomjs_path': '/usr/local/bin/phantomjs'
}
