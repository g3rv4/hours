import sys
import requests
import redis
import json
import datetime
import re
import pytz
from dateutil.parser import parse as date_parse
from urllib import quote
from jira.client import JIRA
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from urlparse import urlparse
from config import config

redis_cli = redis.StrictRedis(db=config['redis_db'])
timedoctor_oauth_return_url = 'https://webapi.timedoctor.com/oauth/v2/token'
timedoctor_oauth_url = 'https://webapi.timedoctor.com/oauth/v2/auth?client_id=%s&response_type=code&redirect_uri=%s' \
                       % (config['timedoctor']['client_id'], quote(timedoctor_oauth_return_url))


def generate_timedoctor_token():
    driver = webdriver.PhantomJS(executable_path=config['phantomjs_path'])
    driver.get(timedoctor_oauth_url)
    username_field = driver.find_element_by_id('username')
    username_field.send_keys(config['timedoctor']['username'])
    password_field = driver.find_element_by_id('password')
    password_field.send_keys(config['timedoctor']['password'])
    password_field.send_keys(Keys.ENTER)

    accept_button = driver.find_element_by_id('accepted')
    accept_button.click()

    url = urlparse(driver.current_url)
    query_dict = dict([tuple(x.split('=')) for x in url.query.split('&')])
    code = query_dict['code']

    r = requests.post('https://webapi.timedoctor.com/oauth/v2/token', {
        'client_id': config['timedoctor']['client_id'],
        'client_secret': config['timedoctor']['client_secret'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': timedoctor_oauth_return_url
    })

    if r.status_code != 200:
        print 'Unable to retrieve code, token service status code %i' % r.status_code
        sys.exit(-1)

    data = json.loads(r.content)

    redis_cli.set('timedoctor:access_token', data['access_token'])
    redis_cli.set('timedoctor:refresh_token', data['refresh_token'])

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

    jira_conf = config['jira']
    jira = JIRA(jira_conf['server'], basic_auth=(jira_conf['username'], jira_conf['password']))
    company_tz = pytz.timezone(config['timezone'])
    worklogs = get_worklogs(date, datetime.datetime.now().date())
    for date in worklogs:
        for worklog in worklogs[date]:
            # get the ticket id
            current_best_position = len(worklog['task_name'])
            current_match = None
            print 'Processing: %s' % worklog['task_name']
            for regexp in jira_conf['ticket_regexps']:
                match = re.search('\\b(' + regexp + ')\\b', worklog['task_name'])
                if match is not None and match.start(1) < current_best_position:
                    current_best_position = match.start(1)
                    current_match = match.group(1)

            if current_match is None:
                print 'Match not found'
            else:
                print 'Found match %s' % current_match
                try:
                    issue = jira.issue(current_match)
                except:
                    pass
                else:
                    # found a ticket!
                    description = worklog['task_name']
                    if current_best_position == 0:
                        description = re.sub('^[^a-zA-Z0-9\\(]*', '', worklog['task_name'][len(current_match):])

                    worklog_ready = False
                    for jworklog in jira.worklogs(issue.id):
                        started = date_parse(jworklog.started).astimezone(company_tz).date()
                        if date == started and jworklog.comment == description:
                            if jworklog.timeSpentSeconds != int(worklog['length']):
                                jworklog.update(timeSpentSeconds=int(worklog['length']))
                            worklog_ready = True

                    if not worklog_ready:
                        # get the timezone suffix on the task's date (considering DST)
                        task_date_with_time = datetime.datetime.combine(date, datetime.datetime.min.time())
                        suffix = company_tz.localize(task_date_with_time).strftime('%z')

                        # make it 6pm wherever they are
                        dt = date_parse(date.strftime('%Y-%m-%dT18:00:00') + suffix)
                        jira.add_worklog(issue.id, timeSpentSeconds=int(worklog['length']), started=dt,
                                         comment=description)


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


def get_company_id():
    if 'company_id' in config['timedoctor'] and config['timedoctor']['company_id']:
        return config['timedoctor']['company_id']

    company_id = redis_cli.get('timedoctor:company_id')
    if company_id:
        return int(company_id)

    companies = get_companies()
    if len(companies['accounts']) == 1:
        redis_cli.set('timedoctor:company_id', companies['accounts'][0]['company_id'])
        return companies['accounts'][0]['company_id']

    print 'The user has %s companies, please set the company to use in the config file' % len(companies['accounts'])
    sys.exit(-1)


def get_worklogs(start_date, end_date):
    iter = start_date
    res = {}
    min_task_length = max(config['timedoctor']['min_task_length'], 60)
    while iter <= end_date:
        print 'Getting worklog for %s' % iter.strftime('%Y-%m-%d')
        params = {
            'start_date': iter.strftime('%Y-%m-%d'),
            'end_date': iter.strftime('%Y-%m-%d')
        }
        response = timedoctor_request_with_token('get', 'companies/%i/worklogs' % get_company_id(),
                                                 params=params)

        if len(response['worklogs']['items']):
            # Only add those that have a duration longer than min_task_length
            res[iter] = [i for i in response['worklogs']['items'] if int(i['length']) >= min_task_length]

        iter += datetime.timedelta(days=1)
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
