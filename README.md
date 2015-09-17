# hours
This script was built to solve 2 problems:

* I need to provide my clients with reports of the time I have worked
* I need to keep my [JIRA](https://www.atlassian.com/software/jira) tickets updated with the time I spent working on them

I use [TimeDoctor](http://www.timedoctor.com/#545c29e26f8ab)* to keep track of what I work on, so this script goes through my TimeDoctor entries and either builds and emails a report or uses that information to update the JIRA tickets through its API.

During the development of this script I gave TimeDoctor's API a try, but it was extremely buggy. That's why it has 2 ways of operating: you can either use TimeDoctor's API or use a real browser through Selenium to retrieve that information.

<sup>*The link to TimeDoctor is an affiliate one, I get a commision if you create an account after following it :)</sup>

## Requirements
* Redis server (so that the status can be stored and when you execute "send_email" it knows what information to use)
* A web browser compatible with Selenium (I'm using both PhantomJS and Chrome. You can use PhantomJS as is, but if you want to use Chrome, you need [a driver](https://sites.google.com/a/chromium.org/chromedriver/))
* Python
* Virtualenv
* Some python knowledge... this isn't nicely packaged (yet)

## Methods to retrieve TimeDoctor's information
The behavior of the script is modified in the config.py file

### Using Selenium
If you choose to use Selenium, then all you need to do is adjust the method and set up the executable_path to the browser or driver you want to use.

Here's an example of how your config.py should look like should you use Selenium

    config = {
        ...
        'timedoctor': {
            # valid values are 'api' and 'selenium'. If 'api' is selected, the client_id and client_secret
            # are required in addition to the username and password
            'method': 'selenium',
            
            'username': '<username>',
            'password': '<password>',
        ...    
        },
        ...
        'selenium': {
            'browser': 'phantomjs',
            'browsers': {
                'phantomjs': {
                    'driver_class': 'PhantomJS',
                    'executable_path': '<path_to_phantomjs>'
                },
                'chrome': {
                    'driver_class': 'Chrome',
                    'executable_path': '<path_to_chrome_driver>'
                }
            }
        }
    }

### Using TimeDoctor's API
Their API uses OAuth (and don't provide a non-interactive way of logging in), so even if you want to use their API, the script needs Selenium to authenticate and that's why the script needs your username and password (check [my blog post](http://blog.gmc.uy/2015/02/defeating-oauth-with-phantomjs.html) about it).

I addition to your user and password, you also need a client id and client secret, you can [generate them here](https://webapi.timedoctor.com/doc/#documentation).

Here's an example of how your config.py should look like should you use the API

    config = {
        ...
        'timedoctor': {
            # valid values are 'api' and 'selenium'. If 'api' is selected, the client_id and client_secret
            # are required in addition to the username and password
            'method': 'api',
            
            'client_id': '<client_id>',
            'client_secret': '<client_secret>',
            'username': '<username>',
            'password': '<password>',
        ...    
        },
        ...
        'selenium': {
            'browser': 'phantomjs',
            'browsers': {
                'phantomjs': {
                    'driver_class': 'PhantomJS',
                    'executable_path': '<path_to_phantomjs>'
                },
                'chrome': {
                    'driver_class': 'Chrome',
                    'executable_path': '<path_to_chrome_driver>'
                }
            }
        }
    }

## Installation

    # enter into the project directory
    virtualenv env
    # activate the virtual environment
    pip install -r requirements.txt
    
Once you've done that, play with the config.py file.

## Usage
### Send email

If you don't specify start / end date, it will include every day since the last run (the first time, you need to pass it)

    # Activate the virtual environment
    python run.py send_email [start_date] [end_date] [email]

### Update Jira

If you don't specify start / end date, it will include every day since the last run (the first time, you need to pass it)

    # Activate the virtual environment
    python run.py update_jira [start_date]

   
## Next steps
* Use argparse to handle the arguments
* Add multi company support