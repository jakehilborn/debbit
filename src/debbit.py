#!/usr/bin/env python3
import base64
import logging
import os
import random
import smtplib
import sys
import time
import traceback
import urllib.request
from datetime import datetime
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from threading import Timer, Lock, Thread

import coverage
import yaml  # PyYAML
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.firefox.options import Options
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from result import Result


def main():
    update_check()

    if CONFIG['mode'] != 'burst' and CONFIG['mode'] != 'spread':
        LOGGER.error('Set config.txt "mode" to burst or spread')
        return

    now = datetime.now()
    state = load_state(now.year, now.month)

    if not state:
        LOGGER.info('No purchases yet complete for ' + now.strftime('%B %Y'))

    for merchant_id in state:
        cur_purchase_count = state[merchant_id]['purchase_count']
        LOGGER.info(str(cur_purchase_count) + ' ' + merchant_id + ' ' + plural('purchase', cur_purchase_count) + ' complete for ' + now.strftime('%B %Y'))
    LOGGER.info('')

    for card in CONFIG:
        if card in ['mode', 'hide_web_browser', 'notify_failure']:  # global config stored at same level as cards, filter them out
            continue

        for merchant_name, merchant_conf in CONFIG[card].items():
            load_merchant(card, merchant_name, merchant_conf)


def load_state(year, month):
    padded_month = '0' + str(month) if month < 10 else str(month)
    filename = absolute_path('state', 'debbit_' + str(year) + '_' + padded_month + '.txt')

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f.read())
    except FileNotFoundError:
        return {}


def load_merchant(card, merchant_name, merchant_conf):
    try:
        web_automation = __import__('program_files.merchants.' + merchant_name, fromlist=["*"]).web_automation
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        LOGGER.error('Error loading ' + merchant_name + '.py from merchants folder')
        raise e

    merchant = Merchant(card, merchant_name, web_automation, merchant_conf)

    if CONFIG['mode'] == 'spread':
        start_spread_schedule(merchant)
    if CONFIG['mode'] == 'burst':
        Thread(target=burst_loop, args=(merchant,)).start()


def burst_loop(merchant):
    # These 3 variables are modified during each loop
    suppress_logs = False
    burst_gap = None
    skip_time = datetime.fromtimestamp(0)

    while True:
        now = datetime.now()
        state = load_state(now.year, now.month)
        this_burst_count = merchant.burst_count
        prev_burst_time = 0
        cur_purchase_count = state.get(merchant.id, {}).get('purchase_count') or 0

        if not burst_gap:  # only applies to first loop
            burst_gap = get_burst_min_gap(merchant, cur_purchase_count, now)

        if merchant.id in state:
            if len(state[merchant.id]['transactions']) >= merchant.burst_count:
                prev_burst_time = state[merchant.id]['transactions'][merchant.burst_count * -1]['unix_time']

            for transaction in state[merchant.id]['transactions'][-min(len(state[merchant.id]['transactions']), merchant.burst_count):]:
                if transaction['unix_time'] > int(now.timestamp()) - min(get_burst_min_gap(merchant, cur_purchase_count, now), 3600):
                    this_burst_count -= 1  # Program was stopped during burst within 60 minutes ago, count how many occurred within the last partial burst

        this_burst_count = min(this_burst_count, merchant.total_purchases - cur_purchase_count)

        if prev_burst_time < int(now.timestamp()) - burst_gap \
                and now.day >= merchant.min_day \
                and now.day <= (merchant.max_day if merchant.max_day else DAYS_IN_MONTH[now.month] - 1) \
                and cur_purchase_count < merchant.total_purchases \
                and now > skip_time:

            LOGGER.info('Now bursting ' + str(this_burst_count) + ' ' + merchant.id + ' ' + plural('purchase', this_burst_count))

            result = web_automation_wrapper(merchant)  # First execution outside of loop so we don't sleep before first execution and don't sleep after last execution
            cur_purchase_count += 1
            for i in range(this_burst_count - 1):
                if result != Result.success:
                    break
                sleep_time = 30
                LOGGER.info('Waiting ' + str(sleep_time) + ' seconds before next ' + merchant.id + ' purchase')
                time.sleep(sleep_time)
                result = web_automation_wrapper(merchant)
                cur_purchase_count += 1

            burst_gap = get_burst_min_gap(merchant, cur_purchase_count, now) + random.randint(0, int(merchant.burst_time_variance))

            if result == Result.skipped:
                skip_time = now + timedelta(days=1)

            suppress_logs = False
        elif not suppress_logs:
            log_next_burst_time(merchant, now, prev_burst_time, burst_gap, skip_time, cur_purchase_count)
            suppress_logs = True
        else:
            time.sleep(300)


def get_burst_min_gap(merchant, cur_purchase_count, now):
    if merchant.burst_min_gap is not None:  # Use value in config file
        return merchant.burst_min_gap

    remaining_purchase_count = merchant.total_purchases - cur_purchase_count
    default_burst_min_gap = 79200  # 22 hours

    if remaining_purchase_count < 1:
        return default_burst_min_gap

    month_end_day = merchant.max_day or DAYS_IN_MONTH[now.month] - 1
    remaining_secs_in_month = (datetime(now.year, now.month, month_end_day) - now).total_seconds()
    dynamic_burst_min_gap = int(remaining_secs_in_month / 4 / remaining_purchase_count * merchant.burst_count)

    return min(dynamic_burst_min_gap, default_burst_min_gap)


def log_next_burst_time(merchant, now, prev_burst_time, burst_gap, skip_time, cur_purchase_count):
    prev_burst_plus_gap_dt = datetime.fromtimestamp(prev_burst_time + burst_gap)
    cur_month_min_day_dt = datetime(now.year, now.month, merchant.min_day)

    if now.month == 12:
        year = now.year + 1
        month = 1
    else:
        year = now.year
        month = now.month + 1

    next_month_min_day_dt = datetime(year, month, merchant.min_day)

    if now.day < merchant.min_day:
        next_burst_time = prev_burst_plus_gap_dt if prev_burst_plus_gap_dt > cur_month_min_day_dt else cur_month_min_day_dt
        next_burst_count = merchant.burst_count
    elif cur_purchase_count >= merchant.total_purchases or now.day > (merchant.max_day if merchant.max_day else DAYS_IN_MONTH[now.month] - 1):
        next_burst_time = prev_burst_plus_gap_dt if prev_burst_plus_gap_dt > next_month_min_day_dt else next_month_min_day_dt
        next_burst_count = merchant.burst_count
    else:
        next_burst_time = prev_burst_plus_gap_dt
        next_burst_count = min(merchant.burst_count, merchant.total_purchases - cur_purchase_count)

    if next_burst_time < skip_time:
        next_burst_time = skip_time

    LOGGER.info('Bursting next ' + str(next_burst_count) + ' ' + merchant.id + ' ' + plural('purchase', next_burst_count) + ' after ' + next_burst_time.strftime("%Y-%m-%d %I:%M%p"))


def start_spread_schedule(merchant):
    now = datetime.now()
    state = load_state(now.year, now.month)

    if merchant.id not in state:  # first run of the month
        if now.day >= merchant.min_day:
            spread_recursion(merchant)
        else:
            start_offset = (datetime(now.year, now.month, merchant.min_day) - now).total_seconds()
            LOGGER.info('Scheduling ' + merchant.id + ' at ' + formatted_date_of_offset(now, start_offset))
            Timer(start_offset, spread_recursion, [merchant]).start()
    elif state[merchant.id]['purchase_count'] < merchant.total_purchases and now.timestamp() - state[merchant.id]['transactions'][-1]['unix_time'] > merchant.spread_min_gap:
        spread_recursion(merchant)
    else:
        schedule_next_spread(merchant)


def schedule_next_spread(merchant):
    now = datetime.now()
    state = load_state(now.year, now.month)
    cur_purchase_count = state[merchant.id]['purchase_count'] if merchant.id in state else 0

    if cur_purchase_count < merchant.total_purchases:
        remaining_purchase_count = merchant.total_purchases - cur_purchase_count
        month_end_day = merchant.max_day if merchant.max_day else DAYS_IN_MONTH[now.month] - 1
        remaining_secs_in_month = (datetime(now.year, now.month, month_end_day) - now).total_seconds()
        average_gap = remaining_secs_in_month / remaining_purchase_count

        time_variance = merchant.spread_time_variance
        while average_gap < time_variance * 2 and time_variance > 60:
            time_variance = time_variance / 2

        range_min = average_gap - time_variance if average_gap - time_variance > merchant.spread_min_gap else merchant.spread_min_gap
        range_max = average_gap + time_variance if average_gap + time_variance > merchant.spread_min_gap else merchant.spread_min_gap
    else:  # purchases complete for current month, schedule to start purchasing on the 2nd day of next month
        if now.month == 12:
            year = now.year + 1
            month = 1
        else:
            year = now.year
            month = now.month + 1

        range_min = (datetime(year, month, merchant.min_day) - now).total_seconds()

        if range_min <= 0:
            LOGGER.error('Fatal error, could not determine date of next month when scheduling ' + merchant.id)
            return

        range_max = range_min + merchant.spread_time_variance

    start_offset = random.randint(int(range_min), int(range_max))
    LOGGER.info('Scheduling next ' + merchant.id + ' at ' + formatted_date_of_offset(now, start_offset))
    LOGGER.info('')
    Timer(start_offset, spread_recursion, [merchant]).start()


def spread_recursion(merchant):
    web_automation_wrapper(merchant)
    schedule_next_spread(merchant)


def record_transaction(merchant_id, amount):
    now = datetime.now()
    LOGGER.info('Recording successful ' + merchant_id + ' purchase')

    if not os.path.exists(absolute_path('state')):
        os.mkdir(absolute_path('state'))

    padded_month = '0' + str(now.month) if now.month < 10 else str(now.month)
    filename = absolute_path('state', 'debbit_' + str(now.year) + '_' + padded_month + '.txt')

    STATE_WRITE_LOCK.acquire()

    state = load_state(now.year, now.month)

    if merchant_id not in state:
        state[merchant_id] = {
            'purchase_count': 0,
            'transactions': []
        }

    cur_purchase_count = state[merchant_id]['purchase_count'] + 1
    state[merchant_id]['purchase_count'] = cur_purchase_count
    state[merchant_id]['transactions'].append({
        'amount': str(amount) + ' cents',
        'human_time': now.strftime("%Y-%m-%d %I:%M%p"),
        'unix_time': int(now.timestamp())
    })

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(yaml.dump(state))

    STATE_WRITE_LOCK.release()

    LOGGER.info(str(cur_purchase_count) + ' ' + merchant_id + ' ' + plural('purchase', cur_purchase_count) + ' complete for ' + now.strftime('%B %Y'))


def formatted_date_of_offset(now, start_offset):
    return (now + timedelta(seconds=start_offset)).strftime("%Y-%m-%d %I:%M%p")


def web_automation_wrapper(merchant):
    failures = 0
    threshold = 5
    while failures < threshold:
        driver = get_webdriver(merchant)
        amount = random.randint(merchant.amount_min, merchant.amount_max)
        error_msg = None
        LOGGER.info('Spending ' + str(amount) + ' cents with ' + merchant.id + ' now')
        try:
            with Coverage() as cov:
                result = merchant.web_automation(driver, merchant, amount)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            result = Result.failed
            error_msg = traceback.format_exc()

        if result == Result.failed:
            if not error_msg:
                error_msg = 'Result.failed'
            LOGGER.error(merchant.id + ' error: ' + error_msg)
            failures += 1

            record_failure(driver, merchant, error_msg, cov)
            close_webdriver(driver, merchant)

            if failures < threshold:
                LOGGER.info(str(failures) + ' of ' + str(threshold) + ' ' + merchant.id + ' attempts done, trying again in ' + str(60 * failures ** 4) + ' seconds')
                time.sleep(60 * failures ** 4)  # try again in 1min, 16min, 1.3hr, 4.3hr, 10.4hr
                continue
            else:
                exit_msg = merchant.id + ' failed ' + str(failures) + ' times in a row. NOT SCHEDULING MORE ' + merchant.id + '. Stop and re-run debbit to try again. To help get this issue fixed, follow instructions at https://jakehilborn.github.io/debbit/#merchant-automation-failed-how-do-i-get-it-fixed'
                LOGGER.error(exit_msg)
                notify_failure(exit_msg)
                raise Exception(exit_msg)  # exits this merchant's thread, not entire program

        if result == Result.unverified:
            record_failure(driver, merchant, 'Result.unverified', cov)
            close_webdriver(driver, merchant)
            exit_msg = 'Unable to verify ' + merchant.id + ' purchase was successful. Just in case, NOT SCHEDULING MORE ' + merchant.id + '. Stop and re-run debbit to try again. To help get this issue fixed, follow instructions at https://jakehilborn.github.io/debbit/#merchant-automation-failed-how-do-i-get-it-fixed'
            LOGGER.error(exit_msg)
            notify_failure(exit_msg)
            sys.exit(1)  # exits this merchant's thread, not entire program

        close_webdriver(driver, merchant)

        if result == Result.success:
            record_transaction(merchant.id, amount)

        return result


def record_failure(driver, merchant, error_msg, cov):
    if not os.path.exists(absolute_path('failures')):
        os.mkdir(absolute_path('failures'))

    filename = absolute_path('failures', datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f') + '_' + merchant.name)

    with open(filename + '.txt', 'w', encoding='utf-8') as f:
        f.write(VERSION + ' ' + error_msg)

    try:
        driver.save_screenshot(filename + '.png')

        dom = driver.execute_script("return document.documentElement.outerHTML")
        dom = scrub_sensitive_data(dom, merchant)

        with open(filename + '.html', 'w', encoding='utf-8') as f:
            f.write(dom)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        LOGGER.error('record_failure DOM error: ' + traceback.format_exc())

    try:
        if cov:  # cov is None when a debugger is attached
            cov.html_report(directory=absolute_path(filename + '_' + 'coverage'), include='*/merchants/*')
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        LOGGER.error('record_failure coverage error: ' + traceback.format_exc())


def scrub_sensitive_data(data, merchant):
    if not data:
        return data

    return data \
        .replace(merchant.usr, '***usr***') \
        .replace(merchant.psw, '***psw***') \
        .replace(merchant.card, '***card***') \
        .replace(merchant.card[-4:], '***card***')  # last 4 digits of card


def notify_failure(exit_msg):
    if not CONFIG.get('notify_failure') or CONFIG['notify_failure'] == 'your.email@website.com':
        return

    from_email = 'debbit.failure@debbit.com'
    to_email = CONFIG['notify_failure']
    subject = 'Debbit Failure'
    html_content = ('{exit_msg}'
        '<br><br>'
        '<strong>This debbit failure was only sent to you.</strong> To help get this issue fixed, please consider '
        'sharing this error with the debbit developers. In the failures folder there are files with timestamps for '
        'names. Each timestamp has 3 files ending in .txt, .png, .html, and a folder ending in _coverage. Open the '
        '.png file and make sure it does not have your credit card number or password showing. Then, email these files '
        'to jakehilborn@gmail.com or open an "Issue" at https://github.com/jakehilborn/debbit/issues and attach them '
        'there. You can send one error or the whole failures folder, the more errors to inspect the more helpful.')\
        .format(exit_msg=exit_msg)

    d = [b'U0cueDBSVmZZeVFRRHVHRHpY',
         b'WkRsQk4xaGtaeTVYZEhOcFdsWnpRM1ZS',
         b'WWpKa2Qxb3dUbFpQVjJSU1ltdEdOV0pyVGpKa01VMHlaVzVHV2xOR1ZrdGlNbmN4WkVabk0xSXhVa1k9']
    o = ''
    for i in range(len(d)):
        s = d[i]
        for j in range(i + 1):
            s = base64.b64decode(s)
        o += s.decode('utf-8')

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=html_content)
    try:
        SendGridAPIClient(o).send(message)
        return
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        LOGGER.error('Unable to send failure notification email - trying again via SMTP')
        if hasattr(e, 'message'):  # SendGrid error
            LOGGER.error(e.message)
        else:  # other error
            LOGGER.error(e)

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP_SSL('smtp.sendgrid.net', 465)
        server.ehlo()
        server.login(base64.b64decode('YXBpa2V5Cg==').decode('utf-8').strip(), o)
        server.sendmail(from_email, to_email, msg.as_string())
        server.close()
        LOGGER.info('Successfully sent failure notification email via SMTP')
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        LOGGER.error('Unable to send failure notification email via SMTP')
        LOGGER.error(e)


def get_webdriver(merchant):
    WEB_DRIVER_LOCK.acquire()  # Only execute one purchase at a time so the console log messages don't inter mix
    options = Options()
    options.headless = CONFIG['hide_web_browser']
    try:
        driver = webdriver.Firefox(options=options,
                                 service_log_path=os.devnull,
                                 executable_path=absolute_path('program_files', 'geckodriver'),
                                 firefox_profile=absolute_path('program_files', 'selenium-cookies-extension', 'firefox-profile'))
    except SessionNotCreatedException:
        LOGGER.error('')
        LOGGER.error('Firefox not found. Please install the latest version of Firefox and try again.')
        WEB_DRIVER_LOCK.release()
        sys.exit(1)

    if merchant.use_cookies:
        restore_cookies(driver, merchant.id)

    return driver


def close_webdriver(driver, merchant):
    try:
        if merchant.use_cookies:
            persist_cookies(driver, merchant.id)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        LOGGER.error(str(e) + ' - proceeding without persisting cookies')

    try:
        driver.close()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass

    try:
        WEB_DRIVER_LOCK.release()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass


def restore_cookies(driver, merchant_id):
    try:
        if not os.path.exists(absolute_path('program_files', 'cookies', merchant_id)):
            return

        with open(absolute_path('program_files', 'cookies', merchant_id), 'r', encoding='utf-8') as f:
            cookies = f.read()

        driver.get('file://' + absolute_path('program_files', 'selenium-cookies-extension', 'restore-cookies.html'))
        driver.execute_script("document.getElementById('content').textContent = '" + cookies + "'")
        driver.execute_script("document.getElementById('status').textContent = 'dom-ready'")

        seconds = 30
        for i in range(seconds * 10):
            if driver.find_element_by_id('status').text == 'done':
                return
            time.sleep(0.1)
        error_msg = 'Unable to restore cookies after ' + str(seconds) + ' seconds'
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        error_msg = str(e)

    LOGGER.error(error_msg + ' - proceeding without restoring cookies')


def persist_cookies(driver, merchant_id):
    driver.get('file://' + absolute_path('program_files', 'selenium-cookies-extension', 'persist-cookies.html'))

    seconds = 30
    for i in range(seconds * 10):
        if driver.find_element_by_id('status').text == 'dom-ready':
            break
        if i == seconds * 10 - 1:
            LOGGER.error('Unable to restore cookies after ' + str(seconds) + ' seconds - proceeding without restoring cookies')
            return
        time.sleep(0.1)

    cookies = driver.find_element_by_id('content').text

    if not os.path.exists(absolute_path('program_files', 'cookies')):
        os.mkdir(absolute_path('program_files', 'cookies'))

    with open(absolute_path('program_files', 'cookies', merchant_id), 'w', encoding='utf-8') as f:
        f.write(cookies)


def absolute_path(*rel_paths):  # works cross platform when running source script or Pyinstaller binary
    script_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath('__file__')
    return os.path.join(os.path.dirname(script_path), *rel_paths)


def plural(word, count):
    if count == 1:
        return word
    return word + 's'


def update_check():
    try:
        latest_version = int(urllib.request.urlopen('https://jakehilborn.github.io/debbit/updates/latest.txt').read())
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        LOGGER.error('Unable to check for updates. Check https://github.com/jakehilborn/debbit/releases if interested.')
        return

    if VERSION_INT >= latest_version:
        return

    changelog = '\n\nDebbit update available! Download latest release here: https://github.com/jakehilborn/debbit/releases\n'

    try:
        for i in range(VERSION_INT, latest_version):
            changelog += '\n' + urllib.request.urlopen('https://jakehilborn.github.io/debbit/updates/changelogs/' + str(i + 1) + '.txt').read().decode('utf-8')
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass

    LOGGER.info(changelog)

    return


def pyinstaller_runtime_patches():
    if not getattr(sys, 'frozen', False):
        return  # only apply runtime patches if this is a Pyinstaller binary

    # workaround so PyInstaller can dynamically load program_files/merchants/*.py
    sys.path.insert(0, absolute_path())

    # force Coverage to look for assets in program_files directory.
    # This nasty patch is for coverage v5.1 and may break if the dependency is updated.
    __import__('coverage.html', fromlist=["*"]).STATIC_PATH = [absolute_path('program_files', 'coverage-htmlfiles')]


class Coverage:
    def __init__(self):
        if sys.gettrace():
            LOGGER.warning('Debugger detected. Not attaching coverage module to merchant automation since it disables the debugger.')
            self.cov = None
        else:
            self.cov = coverage.Coverage(data_file=None, branch=True)

    def __enter__(self):
        if self.cov:
            self.cov.start()
        return self.cov

    def __exit__(self, type, value, traceback):
        if self.cov:
            self.cov.stop()


class Merchant:
    def __init__(self, card, name, web_automation, config_entry):
        self.id = str(card) + '_' + name
        self.name = name
        self.web_automation = web_automation

        self.total_purchases = config_entry['total_purchases']
        self.amount_min = config_entry['amount_min']
        self.amount_max = config_entry['amount_max']
        self.usr = str(config_entry['usr'])
        self.psw = str(config_entry['psw'])
        self.card = str(config_entry['card'])

        if CONFIG['mode'] == 'burst' and not config_entry.get('burst_count'):
            LOGGER.error(self.id + ' config is missing "burst_count"')
            sys.exit(1)
        self.burst_count = config_entry['burst_count']

        # Optional advanced config or default values.
        self.use_cookies = config_entry.get('advanced', {}).get('use_cookies', True)
        self.min_day = config_entry.get('advanced', {}).get('min_day', 2)  # avoid off by one errors in all systems
        self.max_day = config_entry.get('advanced', {}).get('max_day')  # calculated dynamically if None is returned
        self.burst_min_gap = config_entry.get('advanced', {}).get('burst', {}).get('min_gap')  # calculated dynamically if None is returned
        self.burst_time_variance = config_entry.get('advanced', {}).get('burst', {}).get('time_variance', 14400)  # 4 hours
        self.spread_min_gap = config_entry.get('advanced', {}).get('spread', {}).get('min_gap', 14400)  # 4 hours
        self.spread_time_variance = config_entry.get('advanced', {}).get('spread', {}).get('time_variance', 14400)  # 4 hours


if __name__ == '__main__':
    LOGGER = logging.getLogger('debbit')
    LOGGER.setLevel(logging.INFO)
    log_format = '%(levelname)s: %(asctime)s %(message)s'

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(log_format))
    LOGGER.addHandler(stdout_handler)

    file_handler = logging.FileHandler(absolute_path('program_files', 'debbit_log.log'))
    file_handler.setFormatter(logging.Formatter(log_format))
    LOGGER.addHandler(file_handler)

    pyinstaller_runtime_patches()

    # configure global constants
    STATE_WRITE_LOCK = Lock()
    WEB_DRIVER_LOCK = Lock()
    DAYS_IN_MONTH = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    VERSION = 'v1.0.2-dev'
    VERSION_INT = 2

    LOGGER.info('       __     __    __    _ __ ')
    LOGGER.info('  ____/ /__  / /_  / /_  (_) /_')
    LOGGER.info(' / __  / _ \/ __ \/ __ \/ / __/')
    LOGGER.info('/ /_/ /  __/ /_/ / /_/ / / /_  ')
    LOGGER.info('\__,_/\___/_.___/_.___/_/\__/  ' + VERSION)
    LOGGER.info('')

    config_to_open = None
    for file in ['config.yml', 'config.txt']:
        if os.path.exists(absolute_path(file)):
            config_to_open = file
            break

    if config_to_open is None:
        LOGGER.error('Config file not found.')
        LOGGER.error('Copy and rename sample_config.txt to config.yml or config.txt.')
        LOGGER.error('Then, put your credentials and debit card info in the file.')
        sys.exit(1)

    with open(absolute_path(config_to_open), 'r', encoding='utf-8') as config_f:
        try:
            CONFIG = yaml.safe_load(config_f.read())
        except yaml.YAMLError as yaml_e:
            config_error_msg = '\n\nFormatting error in ' + config_to_open + '. Ensure ' + config_to_open + ' has the same structure and spacing as the examples at https://jakehilborn.github.io/debbit/'
            if hasattr(yaml_e, 'problem_mark'):
                config_error_msg += '\n\n' + str(yaml_e.problem_mark)
            LOGGER.error(config_error_msg)
            sys.exit(1)

    main()
