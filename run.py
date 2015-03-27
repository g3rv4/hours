import sys
import requests
import redis
import json
import datetime
import re
import pytz
import time
from dateutil.parser import parse as date_parse
from urllib import quote
from jira.client import JIRA
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from urlparse import urlparse
from config import config
from boto.ses import SESConnection
from email_builder import build_email

redis_cli = redis.StrictRedis(db=config['redis_db'])
timedoctor_oauth_return_url = 'https://webapi.timedoctor.com/oauth/v2/token'
timedoctor_oauth_url = 'https://webapi.timedoctor.com/oauth/v2/auth?client_id=%s&response_type=code&redirect_uri=%s' \
                       % (config['timedoctor']['client_id'], quote(timedoctor_oauth_return_url))

jira_conf = config['jira']
jira = JIRA(jira_conf['server'], basic_auth=(jira_conf['username'], jira_conf['password']))


def generate_timedoctor_token():
    driver = get_selenium_driver()
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


def get_jira_issue(task_description):
    # get the ticket id
    current_best_position = len(task_description)
    current_match = None
    print 'Retrieving issue for description: %s' % task_description
    for regexp in jira_conf['ticket_regexps']:
        match = re.search('\\b(' + regexp + ')\\b', task_description)
        if match is not None and match.start(1) < current_best_position:
            current_best_position = match.start(1)
            current_match = match.group(1)

    if current_match is None:
        print 'Match not found'
    else:
        print 'Found match %s' % current_match
        try:
            description = task_description
            if current_best_position == 0:
                description = re.sub('^[^a-zA-Z0-9\\(]*', '', task_description[len(current_match):])

            return jira.issue(current_match), description
        except:
            pass

    return None, None


def update_jira(date, worklogs=None):
    if not date:
        last_update = redis_cli.get('jira:last_update')
        if last_update:
            date = date_parse(last_update).date()
    if not date:
        print 'Please specify a date'
        sys.exit(-1)

    company_tz = pytz.timezone(config['timezone'])
    worklogs = worklogs or get_worklogs(date, datetime.datetime.now().date())

    user = jira.current_user()

    for date in worklogs:
        for worklog in worklogs[date]:
            issue, description = get_jira_issue(worklog['task_name'])
            if issue:
                # found a ticket!
                worklog_ready = False
                for jworklog in (w for w in jira.worklogs(issue.id) if w.author.name == user):
                    started = date_parse(jworklog.started).astimezone(company_tz).date()
                    if date == started and jworklog.comment == description:
                        if abs(jworklog.timeSpentSeconds - int(worklog['length'])) > 60:
                            original_td = datetime.timedelta(seconds=jworklog.timeSpentSeconds)
                            new_td = datetime.timedelta(seconds=int(worklog['length']))
                            print '  Updating worklog for ticket %s from %s to %s' % (issue.key, original_td, new_td)
                            jworklog.update(timeSpentSeconds=new_td.seconds)
                        worklog_ready = True

                if not worklog_ready:
                    # get the timezone suffix on the task's date (considering DST)
                    task_date_with_time = datetime.datetime.combine(date, datetime.datetime.min.time())
                    suffix = company_tz.localize(task_date_with_time).strftime('%z')

                    # make it 6pm wherever they are
                    dt = date_parse(date.strftime('%Y-%m-%dT18:00:00') + suffix)
                    td = datetime.timedelta(seconds=int(worklog['length']))
                    print '  Adding worklog for ticket %s for %s' % (issue.key, td)
                    jira.add_worklog(issue.id, timeSpentSeconds=td.seconds, started=dt,
                                     comment=description)

    redis_cli.set('jira:last_update', datetime.datetime.now().date().strftime('%Y-%m-%d'))


def send_email(date_from, date_to, email=config['email']['default_to'], worklogs=None):
    worklogs = worklogs or get_worklogs(date_from, date_to)

    # put data into weeks
    weeks = {}
    for date in worklogs:
        # add issue date
        for worklog in worklogs[date]:
            issue, description = get_jira_issue(worklog['task_name'])
            if not issue:
                worklog['issue'] = worklog['task_name']
                worklog['comment'] = ''
                continue

            worklog['issue'] = '<a href="%s" target="_blank">%s: %s</a>' % (issue.permalink(), str(issue), issue.fields.summary)
            worklog['comment'] = description

        week = '%i-%02i' % (date.year, date.isocalendar()[1])
        if week not in weeks:
            weeks[week] = {}
        weeks[week][date] = worklogs[date]

    html = build_email(weeks, config['email']['template'])

    connection = SESConnection(aws_access_key_id=config['email']['aws']['access_key_id'],
                               aws_secret_access_key=config['email']['aws']['secret_access_key'])

    subject = 'Hours report %s - %s' % (date_from.strftime('%m/%d'), date_to.strftime('%m/%d'))

    connection.send_email(config['email']['from'], subject, html, email, format='html')


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


def get_worklogs_api(start_date, end_date):
    iter = start_date
    res = {}
    min_task_length = max(config['timedoctor']['min_task_length'], 60)
    while iter <= end_date:
        print 'Getting worklogs for %s' % iter.strftime('%Y-%m-%d')
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


def get_selenium_driver():
    browser_config = config['selenium']['browsers'][config['selenium']['browser']]
    klass = getattr(globals()['webdriver'], browser_config['driver_class'])
    return klass(executable_path=browser_config['executable_path'])


def get_worklogs(start_date, end_date):
    print 'Starting browser'
    driver = get_selenium_driver()

    print 'Opening login page'
    driver.get('https://login.timedoctor.com/v2/login.php')

    print 'Logging in'
    username_field = driver.find_element_by_id('email')
    username_field.send_keys(config['timedoctor']['username'])
    password_field = driver.find_element_by_id('password')
    password_field.send_keys(config['timedoctor']['password'])
    password_field.send_keys(Keys.ENTER)

    print 'Opening report page'
    driver.get('https://login.timedoctor.com/v2/index.php?page=time_use_report')

    min_task_length = max(config['timedoctor']['min_task_length'], 60)
    res = {}
    iter = start_date
    while iter <= end_date:
        print 'Getting worklogs for %s' % iter.strftime('%Y-%m-%d')
        driver.execute_script("$('.date-val').html('%s')" % iter.strftime('%m/%d/%Y'))
        driver.execute_script("daily_details_table();")
        while True:
            try:
                time.sleep(0.2)
                driver.find_element_by_class_name('tdLoadingOverlay')
                print '    > Waiting for the loading to complete'
            except NoSuchElementException:
                break

        for row in driver.find_elements_by_xpath('//tr[parent::tbody[@id="reports_data"]]'):
            elements = row.find_elements_by_xpath('.//td')
            print '  > %s - %s' % (elements[2].text, elements[0].text)
            task_name = elements[0].text
            task_time_parts = elements[2].text.split(':')
            task_length = int(task_time_parts[0]) * 60 * 60 + int(task_time_parts[1]) * 60 + int(task_time_parts[2])
            if task_length >= min_task_length:
                if iter not in res:
                    res[iter] = []
                res[iter].append({
                    'task_name': task_name,
                    'length': task_length
                })

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

    elif argv[1] == 'send_email':
        end_date = datetime.datetime.now().date()
        email = config['email']['default_to']

        start_date = end_date - datetime.timedelta(days=1)
        while start_date.isoweekday() > 5:
            start_date -= datetime.timedelta(days=1)

        if len(argv) > 2:
            start_date = date_parse(argv[2]).date()

            if len(argv) > 3:
                end_date = date_parse(argv[3]).date()

                if len(argv) > 4:
                    email = argv[3]

        send_email(start_date, end_date, email)

    elif argv[1] == 'get_companies':
        print get_companies()


if __name__ == "__main__":
    main(sys.argv)
