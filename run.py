import sys
import requests
import redis
import json
import datetime
from dateutil.parser import parse as date_parse
from urllib import quote
from flask import Flask, request, redirect
from config import config

app = Flask(__name__)
redis_cli = redis.StrictRedis(db=config['redis_db'])


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route("/")
def redirect_to_login():
    return redirect('https://webapi.timedoctor.com/oauth/v2/auth?client_id=%s&response_type=code&redirect_uri=%s' %
                    (config['timedoctor']['client_id'], quote('http://127.0.0.1:5000/auth')))

@app.route('/auth')
def token():
    code = request.args.get('code')
    r = requests.post('https://webapi.timedoctor.com/oauth/v2/token', {
        'client_id': config['timedoctor']['client_id'],
        'client_secret': config['timedoctor']['client_secret'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'http://127.0.0.1:5000/auth'
    })

    if r.status_code != 200:
        return 'Error retrieving token'

    shutdown_server()
    data = json.loads(r.content)

    redis_cli.set('timedoctor:access_token', data['access_token'])
    redis_cli.set('timedoctor:refresh_token', data['refresh_token'])

    return 'Done! go back to the console'


def generate_timedoctor_token():
    print 'Open http://127.0.0.1:5000 on your browser'
    app.run()
    return redis_cli.get('timedoctor:access_token')


def get_timedoctor_access_token():
    token = redis_cli.get('timedoctor:access_token')
    if not token:
        token = generate_timedoctor_token()
    return token


def refresh_timedoctor_token():
    refresh_token = redis_cli.get('timedoctor:refresh_token')
    if not refresh_token:
        return generate_timedoctor_token()

    r = requests.post('https://webapi.timedoctor.com/oauth/v2/token', {
        'client_id': config['timedoctor']['client_id'],
        'client_secret': config['timedoctor']['client_secret'],
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    })

    if r.status_code // 100 != 2:
        print 'Error getting token from refresh... try from scratch'
        return generate_timedoctor_token()

    data = json.loads(r.content)

    redis_cli.set('timedoctor:access_token', data['access_token'])
    redis_cli.set('timedoctor:refresh_token', data['refresh_token'])

    return data['access_token']


def update_jira(date):
    if not date:
        last_update = redis_cli.get('jira:last_update')
        if last_update:
            date = date_parse(last_update).date()
    if not date:
        print 'Please specify a date'
        sys.exit(-1)

    return get_worklogs(date, datetime.datetime.now().date())


def timedoctor_request_with_token(method, url, **kwargs):
    url = 'https://webapi.timedoctor.com/v1.1/' + url

    headers = kwargs.pop('headers', {})
    headers['Authorization'] = 'Bearer %s' % get_timedoctor_access_token()

    response = getattr(requests, method)(url, headers=headers, **kwargs)

    if response.status_code == 401:
        # Request failed, attempt to retrieve the access token using the refresh token
        headers['Authorization'] = 'Bearer %s' % refresh_timedoctor_token()
        response = getattr(requests, method)(url, headers=headers, **kwargs)

    if response.status_code // 100 != 2:
        print 'Error %i when querying %s. Response: %s' % (response.status_code, url, response.content)
        sys.exit(-1)

    return json.loads(response.content)


def get_worklogs(start_date, end_date):
    iter = start_date
    res = {}
    while iter <= end_date:
        print 'Getting worklog for %s' % iter.strftime('%Y-%m-%d')
        params = {
            'start_date': iter.strftime('%Y-%m-%d'),
            'end_date': iter.strftime('%Y-%m-%d')
        }
        response = timedoctor_request_with_token('get', 'companies/%i/worklogs' % config['timedoctor']['company_id'],
                                                 params=params)
        if len(response['worklogs']['items']):
            res[iter.strftime('%Y-%m-%d')] = response['worklogs']['items']

        iter += datetime.timedelta(days=1)
    print json.dumps(res, indent=True)
    return res


def get_companies():
    return timedoctor_request_with_token('get', 'companies')


def main(argv):
    if len(argv) == 1:
        print 'Command missing'
        sys.exit(1)

    elif argv[1] == 'update_jira':
        date = None
        if len(argv) >= 3:
            date = date_parse(argv[2]).date()
        update_jira(date)

    elif argv[1] == 'get_companies':
        print get_companies()


if __name__ == "__main__":
    main(sys.argv)
