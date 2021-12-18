#!/usr/bin/env python3
import base64
import logging
import os
import platform
import random
import smtplib
import ssl
import sys
import time
import traceback
import urllib.request
import zipfile
from datetime import datetime
from datetime import timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO
from threading import Timer, Lock, Thread

import coverage
import yaml  # PyYAML
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.firefox.options import Options

from result import Result


def main():
    update_check()

    now = datetime.now()
    state = load_state(now.year, now.month)

    if not state:
        LOGGER.info('No purchases yet complete for ' + now.strftime('%B %Y'))

    for merchant_id in state:
        cur_purchase_count = state[merchant_id]['purchase_count']
        LOGGER.info(str(cur_purchase_count) + ' ' + merchant_id + ' ' + plural('purchase', cur_purchase_count) + ' complete for ' + now.strftime('%B %Y'))
    LOGGER.info('')

    for card, merchants in CONFIG.cards.items():
        for merchant_name, merchant_conf in merchants.items():
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

    if CONFIG.mode == 'spread':
        start_spread_schedule(merchant)
    if CONFIG.mode == 'burst':
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
                sleep_time = merchant.burst_intra_gap
                LOGGER.info('Waiting ' + str(sleep_time) + ' ' + plural('second', sleep_time) + ' before next ' + merchant.id + ' purchase')
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
            time.sleep(merchant.burst_poll_gap)


def get_burst_min_gap(merchant, cur_purchase_count, now):
    if merchant.burst_min_gap is not None:  # Use value in config file
        return merchant.burst_min_gap

    remaining_purchase_count = merchant.total_purchases - cur_purchase_count
    default_burst_min_gap = 79200  # 22 hours

    if remaining_purchase_count < 1:
        return default_burst_min_gap

    month_end_day = merchant.max_day or DAYS_IN_MONTH[now.month] - 1
    remaining_secs_in_month = max(0, (datetime(now.year, now.month, month_end_day) - now).total_seconds())
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
        amount = choose_amount(merchant)
        driver = get_webdriver(merchant)
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
                exit_msg = merchant.id + ' failed ' + str(failures) + ' times in a row. NOT SCHEDULING MORE ' + merchant.id + '. Stop and re-run debbit to try again.'
                if not CONFIG.send_failures_to_developer:
                    exit_msg += '  To help get this issue fixed, please set send_failures_to_developer to yes in config.txt or follow instructions at https://jakehilborn.github.io/debbit/#merchant-automation-failed-how-do-i-get-it-fixed'
                LOGGER.error(exit_msg)
                notify_failure(exit_msg)
                raise Exception(exit_msg)  # exits this merchant's thread, not entire program

        if result == Result.unverified:
            record_failure(driver, merchant, 'Result.unverified', cov)
            close_webdriver(driver, merchant)
            exit_msg = 'Unable to verify ' + merchant.id + ' purchase was successful. Just in case, NOT SCHEDULING MORE ' + merchant.id + '. Stop and re-run debbit to try again.'
            if not CONFIG.send_failures_to_developer:
                exit_msg += '  To help get this issue fixed, please set send_failures_to_developer to yes in config.txt or follow instructions at https://jakehilborn.github.io/debbit/#merchant-automation-failed-how-do-i-get-it-fixed'
            LOGGER.error(exit_msg)
            notify_failure(exit_msg)
            sys.exit(1)  # exits this merchant's thread, not entire program

        close_webdriver(driver, merchant)

        if result == Result.success:
            record_transaction(merchant.id, amount)

        return result


def choose_amount(merchant):
    now = datetime.now()
    state = load_state(now.year, now.month)

    if merchant.id not in state:  # first purchase, choose any amount in config.txt range
        return random.randint(merchant.amount_min, merchant.amount_max)

    past_amounts = []
    for transaction in state[merchant.id]['transactions']:
        past_amounts.append(int(transaction['amount'][:-6]))  # '50 cents' -> 50

    # The amounts we've spent this month are stored in past_amounts. Generate the range of possible values between
    # amount_min and amount_max. Pick a random value in that range, excluding any values in past_amounts. If this
    # yields an empty set then we're forced to repeat an amount from earlier in the month. So, let's pick the amount
    # furthest in the past in case the merchant doesn't allow duplicate amounts used in some time frame. We do this by
    # repeating the same logic, but removing increasingly more elements from the beginning of the month's purchase
    # history. By gradually shortening the time frame we're inspecting we'll eventually find a value to use.
    for i in range(len(past_amounts) + 1):
        remaining_amounts = list(set(range(merchant.amount_min, merchant.amount_max + 1)) - set(past_amounts[i:]))
        if remaining_amounts:
            return random.choice(remaining_amounts)


def record_failure(driver, merchant, error_msg, cov):
    if not os.path.exists(absolute_path('failures')):
        os.mkdir(absolute_path('failures'))

    filename_prefix = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f') + '_' + merchant.name

    info_and_error = VERSION + ' ' + platform.system() + ' ' + error_msg  # TODO add md5 hash of merchant file to check if user modified it
    with open(absolute_path('failures', filename_prefix + '.txt'), 'w', encoding='utf-8') as f:
        f.write(info_and_error)

    try:
        driver.save_screenshot(absolute_path('failures', filename_prefix + '.png'))

        dom = driver.execute_script("return document.documentElement.outerHTML")
        dom = scrub_sensitive_data(dom, merchant)

        with open(absolute_path('failures', filename_prefix + '.html'), 'w', encoding='utf-8') as f:
            f.write(dom)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        LOGGER.error('record_failure DOM error: ' + traceback.format_exc())

    try:
        if cov:  # cov is None when a debugger is attached
            cov.html_report(directory=absolute_path('failures', filename_prefix + '_' + 'coverage'), include='*/merchants/*')
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        LOGGER.error('record_failure coverage error: ' + traceback.format_exc())

    if CONFIG.send_failures_to_developer:
        report_failure(filename_prefix, info_and_error)  # TODO put the retry number in here. If first failure, nbd, if recurring failures then it's a bigger problem.


def scrub_sensitive_data(data, merchant):
    if not data:
        return data

    return data \
        .replace(merchant.usr, '***usr***') \
        .replace(merchant.psw, '***psw***') \
        .replace(merchant.card, '***card***') \
        .replace(merchant.card[-4:], '***card***')  # last 4 digits of card


def report_failure(failure_report_filename_prefix, info_and_error):
    mem_zip = BytesIO()
    with zipfile.ZipFile(mem_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(absolute_path('failures')):
            for file in files:
                if file.startswith(failure_report_filename_prefix):
                    z.write(os.path.join(root, file), file)
                elif failure_report_filename_prefix in root:  # include all files in subdirs that comprise of this failure report
                    z.write(os.path.join(root, file), os.path.join(root.split(os.sep + 'failures' + os.sep)[1], file))

    # sendgrid is blocking delivery of many file types. Sending the zip as a "pdf" seems to work though.
    send_email('failure report for developer', 'debbit.failure.notify@gmail.com', failure_report_filename_prefix, info_and_error, 'plain', 'error_report.pdf', 'application/pdf', mem_zip.getvalue())


def notify_failure(exit_msg):
    if not CONFIG.notify_failure:
        return

    to_email = CONFIG.notify_failure
    subject = 'Debbit Failure'

    if CONFIG.send_failures_to_developer:
        body = ('{exit_msg}'
            '<br><br>'
            'This error report was also sent to the debbit developer to be investigated and fixed. Feel free to email '
            'jakehilborn@gmail.com or open an "Issue" at https://github.com/jakehilborn/debbit/issues to discuss this '
            'error.')\
            .format(exit_msg=exit_msg)
    else:
        body = ('{exit_msg}'
            '<br><br>'
            '<strong>This debbit failure was only sent to you.</strong> To help get this issue fixed, please consider '
            'changing send_<i>failures_to_developer</i> to <i>yes</i> in the config.txt file. This will automatically send '
            'future error reports to the debbit developer so the issue can be investigated and fixed. You can also share '
            'this failure manually via email. In the failures folder there are files with timestamps for names. Each '
            'timestamp has 3 files ending in .txt, .png, .html, and a folder ending in _coverage. Email these files to '
            'jakehilborn@gmail.com or open an "Issue" at https://github.com/jakehilborn/debbit/issues and attach them '
            'there. You can send one error or the whole failures folder, the more errors to inspect the more helpful.')\
            .format(exit_msg=exit_msg)

    send_email('failure notification', to_email, subject, body, 'html')


def send_email(purpose, to_email, subject, body, body_mime_type, attachment_name=None, attachment_type=None, attachment_data=None):
    d = [b'U0cueDBSVmZZeVFRRHVHRHpY',
         b'WkRsQk4xaGtaeTVYZEhOcFdsWnpRM1ZS',
         b'WWpKa2Qxb3dUbFpQVjJSU1ltdEdOV0pyVGpKa01VMHlaVzVHV2xOR1ZrdGlNbmN4WkVabk0xSXhVa1k9']
    o = ''
    for i in range(len(d)):
        s = d[i]
        for j in range(i + 1):
            s = base64.b64decode(s)
        o += s.decode('utf-8')

    from_email = 'debbit.failure@debbit.com'

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, body_mime_type))

    if attachment_name:
        attachment = MIMEBase(attachment_type.split('/')[0], attachment_type.split('/')[1])
        attachment.set_payload(attachment_data)
        attachment.add_header('Content-Disposition', 'attachment', filename=attachment_name)
        encoders.encode_base64(attachment)
        msg.attach(attachment)

    try:
        server = smtplib.SMTP_SSL('smtp.sendgrid.net', 465)
        server.ehlo()
        server.login(base64.b64decode('YXBpa2V5Cg==').decode('utf-8').strip(), o)
        server.sendmail(from_email, to_email, msg.as_string())
        server.close()
        LOGGER.info('Successfully sent ' + purpose + ' email to ' + to_email)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        LOGGER.error('Unable to send ' + purpose + ' email')
        LOGGER.error(e)


def get_webdriver(merchant):
    if os.name == 'nt':
        geckodriver_file = 'geckodriver.exe'
    else:
        geckodriver_file = 'geckodriver'

    if os.path.exists(absolute_path('program_files', 'geckodriver.exe')):
        geckodriver_path = absolute_path('program_files', 'geckodriver.exe')
    elif os.path.exists(absolute_path('program_files', 'geckodriver')):
        geckodriver_path = absolute_path('program_files', 'geckodriver')
    else:
        LOGGER.error(absolute_path('program_files', geckodriver_file) + ' does not exist. Download the latest version of geckodriver from https://github.com/mozilla/geckodriver/releases and extract it. Copy ' + geckodriver_file + ' to ' + absolute_path('program_files'))
        sys.exit(1)

    WEB_DRIVER_LOCK.acquire()  # Only execute one purchase at a time so the console log messages don't inter mix
    options = Options()
    options.headless = CONFIG.hide_web_browser
    profile = webdriver.FirefoxProfile(absolute_path('program_files', 'selenium-cookies-extension', 'firefox-profile'))

    # Prevent websites from detecting Selenium via evaluating `if (window.navigator.webdriver == true)` with JavaScript
    profile.set_preference("dom.webdriver.enabled", False)
    profile.set_preference('useAutomationExtension', False)

    try:
        driver = webdriver.Firefox(options=options,
                                 service_log_path=os.devnull,
                                 executable_path=geckodriver_path,
                                 firefox_profile=profile)

    except SessionNotCreatedException as e:
        LOGGER.error(str(e) + '\n')
        LOGGER.error('There was a problem starting Firefox. Make sure the latest version of Firefox is installed. If installing/updating Firefox does not fix the issue, try downloading a newer or older version of geckodriver from https://github.com/mozilla/geckodriver/releases and extracting it. Copy ' + geckodriver_file + ' to ' + absolute_path('program_files'))
        WEB_DRIVER_LOCK.release()
        sys.exit(1)

    # Randomize viewport size to help avoid Selenium detection
    driver.set_window_size(random.randint(1050, 1350), random.randint(700, 1000))

    if merchant.use_cookies:
        restore_cookies(driver, merchant)

    return driver


def close_webdriver(driver, merchant):
    try:
        if merchant.use_cookies:
            persist_cookies(driver, merchant)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        LOGGER.error(str(e) + ' - proceeding without persisting cookies')

    try:
        driver.quit()
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


def restore_cookies(driver, merchant):
    try:
        if os.path.exists(absolute_path('program_files', 'cookies', merchant.name + '_' + merchant.usr)):
            with open(absolute_path('program_files', 'cookies', merchant.name + '_' + merchant.usr), 'r', encoding='utf-8') as f:
                cookies = f.read()
        elif os.path.exists(absolute_path('program_files', 'cookies', merchant.id)):  # legacy v2.0 - v2.0.2 cookie format
            with open(absolute_path('program_files', 'cookies', merchant.id), 'r', encoding='utf-8') as f:
                cookies = f.read()
        else:
            return

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


def persist_cookies(driver, merchant):
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

    with open(absolute_path('program_files', 'cookies', merchant.name + '_' + merchant.usr), 'w', encoding='utf-8') as f:
        f.write(cookies)

    if os.path.exists(absolute_path('program_files', 'cookies', merchant.id)):  # legacy v2.0 - v2.0.2 cookie format
        os.remove(absolute_path('program_files', 'cookies', merchant.id))


def absolute_path(*rel_paths):  # works cross platform when running source script or Pyinstaller binary
    script_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath('__file__')
    return os.path.join(os.path.dirname(script_path), *rel_paths)


def plural(word, count):
    if count == 1:
        return word
    return word + 's'


def update_check():
    non_ssl_context = ssl.SSLContext()  # Having issues with Pyinstaller executables throwing SSL errors. Disabling SSL verification for GET operations to static GitHub pages.

    try:
        latest_version = int(urllib.request.urlopen('http://jakehilborn.github.io/debbit/updates/latest.txt', context=non_ssl_context).read())
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
            changelog += '\n' + urllib.request.urlopen('http://jakehilborn.github.io/debbit/updates/changelogs/' + str(i + 1) + '.txt', context=non_ssl_context).read().decode('utf-8')
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
    # This nasty patch is for coverage v5.3.1 and may break if the dependency is updated.
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
    def __init__(self, card, name, web_automation, merchant_config):
        self.id = str(card) + '_' + name
        self.name = name
        self.web_automation = web_automation

        self.total_purchases = merchant_config['total_purchases']
        self.amount_min = merchant_config['amount_min']
        self.amount_max = merchant_config['amount_max']
        self.usr = str(merchant_config['usr'])
        self.psw = str(merchant_config['psw'])
        self.card = str(merchant_config['card'])

        if CONFIG.mode == 'burst' and not merchant_config.get('burst_count'):
            LOGGER.error(self.id + ' config is missing "burst_count"')
            sys.exit(1)
        self.burst_count = merchant_config['burst_count']

        # Optional advanced config or default values.
        self.use_cookies = merchant_config.get('advanced', {}).get('use_cookies', True)
        self.min_day = merchant_config.get('advanced', {}).get('min_day', 2)  # avoid off by one errors in all systems
        self.max_day = merchant_config.get('advanced', {}).get('max_day')  # calculated dynamically if None is returned
        self.burst_min_gap = merchant_config.get('advanced', {}).get('burst', {}).get('min_gap')  # calculated dynamically if None is returned
        self.burst_time_variance = merchant_config.get('advanced', {}).get('burst', {}).get('time_variance', 14400)  # 4 hours
        self.burst_intra_gap = merchant_config.get('advanced', {}).get('burst', {}).get('intra_gap', 30)  # 30 seconds
        self.burst_poll_gap = merchant_config.get('advanced', {}).get('burst', {}).get('poll_gap', 300)  # 5 minutes
        self.spread_min_gap = merchant_config.get('advanced', {}).get('spread', {}).get('min_gap', 14400)  # 4 hours
        self.spread_time_variance = merchant_config.get('advanced', {}).get('spread', {}).get('time_variance', 14400)  # 4 hours


class Config:
    def __init__(self, config):
        if config.get('mode') != 'burst' and config.get('mode') != 'spread':
            LOGGER.error('Set config.txt "mode" to burst or spread')
            sys.exit(1)
        self.mode = config.get('mode')

        self.hide_web_browser = config.get('hide_web_browser')

        if config.get('notify_failure') == 'your.email@website.com':
            self.notify_failure = None
        else:
            self.notify_failure = config.get('notify_failure')

        self.send_failures_to_developer = config.get('send_failures_to_developer')

        self.cards = config  # The remainder of the config is cards so we can copy the whole dict. Need to remove global config that is stored at the same level though.
        for key in ['mode', 'hide_web_browser', 'notify_failure', 'send_failures_to_developer']:
            self.cards.pop(key, None)


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
    VERSION = 'v2.1.5-dev'
    VERSION_INT = 10

    LOGGER.info('       __     __    __    _ __ ')
    LOGGER.info('  ____/ /__  / /_  / /_  (_) /_')
    LOGGER.info(' / __  / _ \/ __ \/ __ \/ / __/')
    LOGGER.info('/ /_/ /  __/ /_/ / /_/ / / /_  ')
    LOGGER.info('\__,_/\___/_.___/_.___/_/\__/  ' + VERSION)
    LOGGER.info('')

    config_to_open = None
    for config_file in ['config.yml', 'config.txt']:
        if os.path.exists(absolute_path(config_file)):
            config_to_open = config_file
            break

    if config_to_open is None:
        LOGGER.error('Config file not found.')
        LOGGER.error('Copy and rename sample_config.txt to config.txt or config.yml.')
        LOGGER.error('Then, put your credentials and debit card info in the file.')
        sys.exit(1)

    with open(absolute_path(config_to_open), 'r', encoding='utf-8') as config_f:
        try:
            config_dict = yaml.safe_load(config_f.read())
        except yaml.YAMLError as yaml_e:
            config_error_msg = '\n\nFormatting error in ' + config_to_open + '. Ensure ' + config_to_open + ' has the same structure and spacing as the examples at https://jakehilborn.github.io/debbit/'
            if hasattr(yaml_e, 'problem_mark'):
                config_error_msg += '\n\n' + str(yaml_e.problem_mark)
            LOGGER.error(config_error_msg)
            sys.exit(1)

    CONFIG = Config(config_dict)

    main()
