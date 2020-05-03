#!/usr/bin/env python3
import logging
import os
import random
import sys
import time
import traceback
from datetime import datetime
from datetime import timedelta
from threading import Timer, Lock, Thread

import yaml  # PyYAML
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.firefox.options import Options

from result import Result


def main():
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
        if card == 'mode' or card == 'hide_web_browser':  # global config stored at same level as cards, filter them out
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
        web_automation = __import__('merchants.' + merchant_name, fromlist=["*"]).web_automation
    except Exception as e:
        sys.exit(1)  # TODO src/binary exceptions if file not found

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
            for _ in range(this_burst_count - 1):
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

    month_end_day = merchant.max_day or DAYS_IN_MONTH[now.month] - 1
    remaining_secs_in_month = (datetime(now.year, now.month, month_end_day) - now).total_seconds()

    dynamic_burst_min_gap = int(remaining_secs_in_month / (merchant.total_purchases - cur_purchase_count) / 5)
    default_burst_min_gap = 79200  # 22 hours

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
        error_msg = 'Refer to prior log messages for error details'
        LOGGER.info('Spending ' + str(amount) + ' cents with ' + merchant.id + ' now')
        try:
            result = merchant.web_automation(driver, merchant, amount)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            result = Result.failed
            error_msg = traceback.format_exc()

        if result == Result.failed:
            LOGGER.error(merchant.id + ' error: ' + error_msg)
            failures += 1

            record_failure(driver, merchant, error_msg)
            release_webdriver(merchant, False)

            if failures < threshold:
                LOGGER.info(str(failures) + ' of ' + str(threshold) + ' ' + merchant.id + ' attempts done, trying again in ' + str(60 * failures ** 4) + ' seconds')
                time.sleep(60 * failures ** 4)  # try again in 1min, 16min, 1.3hr, 4.3hr, 10.4hr
                continue
            else:
                exit_msg = merchant.id + ' failed ' + str(failures) + ' times in a row. NOT SCHEDULING MORE ' + merchant.id + '. Stop and re-run debbit to try again.'
                LOGGER.error(exit_msg)
                release_webdriver(merchant, True)
                raise Exception(exit_msg)  # exits this merchant's thread, not entire program

        release_webdriver(merchant, False)

        if result == Result.success:
            record_transaction(merchant.id, amount)

        if result == Result.unverified:
            LOGGER.error('Unable to verify ' + merchant.id + ' purchase was successful. Just in case, NOT SCHEDULING MORE ' + merchant.id + '. Stop and re-run debbit to try again.')
            release_webdriver(merchant, True)
            sys.exit(1)  # exits this merchant's thread, not entire program

        return result


def record_failure(driver, merchant, error_msg):
    if not os.path.exists(absolute_path('failures')):
        os.mkdir(absolute_path('failures'))

    filename = absolute_path('failures', datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f') + '_' + merchant.name)

    with open(filename + '.txt', 'w', encoding='utf-8') as f:
        f.write(VERSION + ' ' + error_msg)

    try:
        driver.save_screenshot(filename + '.png')

        dom = driver.execute_script('return document.documentElement.outerHTML')
        dom = scrub_sensitive_data(dom, merchant)

        with open(filename + '.html', 'w', encoding='utf-8') as f:
            f.write(dom)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        LOGGER.error('record_failure error: ' + traceback.format_exc())


def scrub_sensitive_data(data, merchant):
    if not data:
        return data

    return data\
        .replace(merchant.usr, '***usr***')\
        .replace(merchant.psw, '***psw***')\
        .replace(merchant.card, '***card***')\
        .replace(merchant.card[-4:], '***card***')  # last 4 digits of card


def get_webdriver(merchant):
    WEB_DRIVER_LOCK.acquire()  # Only execute one purchase at a time so the console log messages don't inter mix

    if merchant.id not in driver_store:
        options = Options()
        options.headless = CONFIG['hide_web_browser']
        try:
            driver_store[merchant.id] = {
                'driver': webdriver.Firefox(options=options, executable_path=absolute_path('geckodriver'), service_log_path=os.devnull),
                'window': None
            }
        except SessionNotCreatedException:
            LOGGER.error('')
            LOGGER.error('Firefox not found. Please install the latest version of Firefox and try again.')
            WEB_DRIVER_LOCK.release()
            sys.exit(1)

    if driver_store[merchant.id]['window']:  # if browser window minimized, restore to previous position/size
        driver_store[merchant.id]['driver'].set_window_rect(**driver_store[merchant.id]['window'])

    return driver_store[merchant.id]['driver']


def release_webdriver(merchant, force_release):
    if merchant.close_browser or force_release:
        try:
            driver = driver_store[merchant.id]['driver']
            del driver_store[merchant.id]
            driver.close()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass
    elif not CONFIG['hide_web_browser']:  # Since not headless mode, keep browser open but minimize the window
        driver_store[merchant.id]['window'] = driver_store[merchant.id]['driver'].get_window_rect()
        driver_store[merchant.id]['driver'].minimize_window()

    try:
        WEB_DRIVER_LOCK.release()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        pass


def absolute_path(*rel_paths):  # works cross platform when running source script or Pyinstaller binary
    script_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath('__file__')
    return os.path.join(os.path.dirname(script_path), *rel_paths)


def plural(word, count):
    if count == 1:
        return word
    return word + 's'


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
        self.close_browser = config_entry['close_browser']

        if CONFIG['mode'] == 'burst' and not config_entry.get('burst_count'):
            LOGGER.error(self.id + ' config is missing "burst_count"')
            sys.exit(1)
        self.burst_count = config_entry['burst_count']

        # Optional config default values.
        self.min_day = config_entry.get('timing', {}).get('min_day') or 2  # avoid off by one errors in all systems
        self.max_day = config_entry.get('timing', {}).get('max_day')  # calculated dynamically if None is returned
        self.burst_min_gap = config_entry.get('timing', {}).get('burst', {}).get('min_gap')  # calculated dynamically if None is returned
        self.burst_time_variance = config_entry.get('timing', {}).get('burst', {}).get('time_variance') or 14400  # 4 hours
        self.spread_min_gap = config_entry.get('timing', {}).get('spread', {}).get('min_gap') or 14400  # 4 hours
        self.spread_time_variance = config_entry.get('timing', {}).get('spread', {}).get('time_variance') or 14400  # 4 hours


if __name__ == '__main__':
    LOGGER = logging.getLogger('debbit')
    LOGGER.setLevel(logging.INFO)
    log_format = '%(levelname)s: %(asctime)s %(message)s'

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(log_format))
    LOGGER.addHandler(stdout_handler)

    file_handler = logging.FileHandler(absolute_path('debbit_log.log'))
    file_handler.setFormatter(logging.Formatter(log_format))
    LOGGER.addHandler(file_handler)

    # configure global constants
    STATE_WRITE_LOCK = Lock()
    WEB_DRIVER_LOCK = Lock()
    DAYS_IN_MONTH = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
    VERSION = 'v1.0.1-dev'

    # configure cross thread global vars
    driver_store = {}

    LOGGER.info('       __     __    __    _ __ ')
    LOGGER.info('  ____/ /__  / /_  / /_  (_) /_')
    LOGGER.info(' / __  / _ \/ __ \/ __ \/ / __/')
    LOGGER.info('/ /_/ /  __/ /_/ / /_/ / / /_  ')
    LOGGER.info('\__,_/\___/_.___/_.___/_/\__/  ' + VERSION)
    LOGGER.info('')

    files = ['config.yml', 'config.txt']
    to_open = ''

    for file in files:
        candidate_absolute_path = absolute_path(file)
        if (os.path.exists(candidate_absolute_path)):
            to_open = candidate_absolute_path
            break

    if to_open == '':  # TODO revisit
        LOGGER.error('Config file not found.')
        LOGGER.error('Copy and rename sample_config.txt to config.yml or config.txt.')
        LOGGER.error('Then, put your credentials and debit card info in the file.')
        sys.exit(1)

    with open(to_open, 'r', encoding='utf-8') as config_f:
        CONFIG = yaml.safe_load(config_f.read())  # TODO wrap with try catch due to malformed yaml?

    main()

'''
TODO

Support multiple cards per merchant
Unit test suite
Amazon captcha support
Check for internet connection post wake-up before bursting
Propagate error details to failures/ files when returning Result.failure
Result.unverified should record details to failures/ directory
Use a class for State to improve readability
'''
