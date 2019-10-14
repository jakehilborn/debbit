#!/usr/bin/env python3
import logging
import os
import random
import time
import traceback
from datetime import datetime
from datetime import timedelta
from threading import Timer, Lock

import yaml
from selenium import webdriver, common
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait


def main():
    logging.basicConfig(format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)

    now = datetime.now()
    state = load_state(now.year, now.month)

    for merchant_name in state:
        cur_purchases = state[merchant_name]['purchase_count']
        purchase_pluralized = 'purchase' if cur_purchases == 1 else 'purchases'
        logging.info(str(cur_purchases) + ' ' + merchant_name + ' ' + purchase_pluralized + ' complete for ' + now.strftime('%B %Y'))
    print()

    start_schedule(now, state, amazon)
    start_schedule(now, state, xfinity)


def load_state(year, month):
    padded_month = '0' + str(month) if month < 10 else str(month)
    filename = 'state/debbit_' + str(year) + '_' + padded_month + '.txt'

    try:
        with open(filename, 'r') as f:
            return yaml.safe_load(f.read())
    except FileNotFoundError:
        return {}


def start_schedule(now, state, merchant):
    if merchant.name not in state:  # first run of the month
        if now.day >= merchant.min_day:
            retryable(merchant.function)
        else:
            start_offset = (datetime(now.year, now.month, merchant.min_day) - now).total_seconds()
            logging.info('Scheduling ' + merchant.name + ' at ' + formatted_date_of_offset(now, start_offset))
            Timer(start_offset, retryable, [merchant.function]).start()
    elif state[merchant.name]['purchase_count'] < merchant.total_purchases and now.timestamp() - state[merchant.name]['transactions'][-1]['unix_time'] > merchant.min_gap:
        retryable(merchant.function)
    else:
        schedule_next(merchant, state[merchant.name]['purchase_count'])


def schedule_next(merchant, cur_purchases):
    now = datetime.now()

    if cur_purchases < merchant.total_purchases:
        remaining_purchases = merchant.total_purchases - cur_purchases
        month_end = merchant.max_day if merchant.max_day else days_in_month[now.month]
        remaining_secs_in_month = (datetime(now.year, now.month, month_end - 1) - now).total_seconds()
        average_gap = remaining_secs_in_month / remaining_purchases

        time_variance = merchant.time_variance
        while average_gap < time_variance * 2 and time_variance > 60:
            time_variance = time_variance / 2

        range_min = average_gap - time_variance if average_gap - time_variance > merchant.min_gap else merchant.min_gap
        range_max = average_gap + time_variance if average_gap + time_variance > merchant.min_gap else merchant.min_gap
    else:  # purchases complete for current month, schedule to start purchasing on the 2nd day of next month
        if now.month == 12:
            year = now.year + 1
            month = 1
        else:
            year = now.year
            month = now.month + 1

        range_min = (datetime(year, month, merchant.min_day) - now).total_seconds()

        if range_min <= 0:
            logging.error('Fatal error, could not determine date of next month when scheduling ' + merchant.name)
            return

        range_max = range_min + merchant.time_variance

    start_offset = random.randint(int(range_min), int(range_max))
    logging.info('Scheduling next ' + merchant.name + ' at ' + formatted_date_of_offset(now, start_offset))
    print()
    Timer(start_offset, retryable, [merchant.function]).start()


def record_transaction(merchant_name, amount):
    now = datetime.now()
    logging.info('Recording successful ' + merchant_name + ' purchase')

    if not os.path.exists('state'):
        os.mkdir('state')

    padded_month = '0' + str(now.month) if now.month < 10 else str(now.month)
    filename = 'state/debbit_' + str(now.year) + '_' + padded_month + '.txt'

    state_lock.acquire()
    state = load_state(now.year, now.month)

    if merchant_name not in state:
        state[merchant_name] = {
            'purchase_count': 0,
            'transactions': []
        }

    cur_purchases = state[merchant_name]['purchase_count'] + 1
    state[merchant_name]['purchase_count'] = cur_purchases
    state[merchant_name]['transactions'].append({
        'amount': str(amount) + ' cents',
        'human_time': now.strftime("%Y-%m-%d %I:%M%p"),
        'unix_time': int(now.timestamp())
    })

    with open(filename, 'w') as f:
        f.write(yaml.dump(state))

    state_lock.release()

    purchase_pluralized = 'purchase' if cur_purchases == 1 else 'purchases'
    logging.info(str(cur_purchases) + ' ' + merchant_name + ' ' + purchase_pluralized + ' complete for ' + now.strftime('%B %Y'))
    return cur_purchases


def amazon_gift_card_reload(driver):
    merchant = amazon
    logging.info('Running ' + merchant.name + ' now')

    amount = random.randint(merchant.amount_min, merchant.amount_max)

    driver.get('https://www.amazon.com/asv/reload/order?ref_=gcui_b_e_rb_c_d_b_x')

    WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In to Continue')]")))
    driver.find_element_by_xpath("//button[contains(text(),'Sign In to Continue')]").click()
    driver.find_element_by_id('ap_email').send_keys(merchant.usr)

    try:  # a/b tested new UI flow
        driver.find_element_by_id('continue').click()  # if not exists, throw exception
    except common.exceptions.NoSuchElementException:  # a/b tested old UI flow
        pass

    WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.ID, 'ap_password')))
    driver.find_element_by_id('ap_password').send_keys(merchant.psw)
    driver.find_element_by_id('signInSubmit').click()

    WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.ID, 'asv-manual-reload-amount')))
    driver.find_element_by_id('asv-manual-reload-amount').send_keys(cents_to_str(amount))
    driver.find_element_by_xpath("//span[contains(text(),'ending in " + str(merchant.card)[-4:] + "')]").click()
    driver.find_element_by_xpath("//button[contains(text(),'Reload $" + cents_to_str(amount) + "')]").click()

    time.sleep(10) # give page a chance to load
    if 'thank-you' not in driver.current_url:
        logging.info('starting amazon_gift_card_reload cc verification, waiting for input field')
        WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.XPATH, "//input[@placeholder='ending in " + str(merchant.card)[-4:] + "']")))
        elem = driver.find_element_by_xpath("//input[@placeholder='ending in " + str(merchant.card)[-4:] + "']")
        logging.info('found cc field')
        elem.send_keys(str(merchant.card))
        logging.info('entered cc number')
        elem.send_keys(Keys.TAB)
        logging.info('pressed tab')
        elem.send_keys(Keys.ENTER)
        logging.info('pressed enter')
        logging.info('waiting for Reload $ button')
        WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Reload $" + cents_to_str(amount) + "')]")))
        time.sleep(1)
        driver.find_element_by_xpath("//button[contains(text(),'Reload $" + cents_to_str(amount) + "')]").click()
        logging.info('clicked reload button')

    time.sleep(10)  # give page a chance to load
    if 'thank-you' not in driver.current_url:
        logging.error('Unexpected amazon_gift_card_reload failure, NOT scheduling any future purchases')
        return

    cur_purchases = record_transaction(merchant.name, amount)
    schedule_next(merchant, cur_purchases)


def xfinity_bill_pay(driver):
    merchant = xfinity
    logging.info('Running ' + merchant.name + ' now')

    amount = random.randint(merchant.amount_min, merchant.amount_max)

    driver.get('https://customer.xfinity.com/#/billing/payment')

    WebDriverWait(driver, 90).until(expected_conditions.element_to_be_clickable((By.ID, 'user')))

    driver.find_element_by_id('user').send_keys(merchant.usr)
    driver.find_element_by_id('passwd').send_keys(merchant.psw)
    driver.find_element_by_id('sign_in').click()

    WebDriverWait(driver, 90).until(expected_conditions.element_to_be_clickable((By.ID, 'customAmount')))

    try:  # survey pop-up
        driver.find_element_by_id('no').click()
    except common.exceptions.NoSuchElementException:
        pass

    cur_balance = driver.find_element_by_xpath("//span[contains(text(), '$')]").text
    if int(''.join([c for c in cur_balance if c.isdigit()])) == 0:  # $77.84 -> 7784
        logging.error('xfinity balance is zero, skipping all payments for remainder of month')
        schedule_next(merchant, 999)
    elif int(''.join([c for c in cur_balance if c.isdigit()])) < amount:
        amount = int(cur_balance[1:-3] + cur_balance[-2:])

    driver.find_element_by_id('customAmount').send_keys(cents_to_str(amount))
    driver.find_element_by_xpath("//span[contains(text(),'nding in " + str(merchant.card)[-4:] + "')]").click()
    driver.find_element_by_xpath("//span[contains(text(),'nding in " + str(merchant.card)[-4:] + "')]").click()
    driver.find_element_by_xpath("//button[contains(text(),'Continue')]").click()
    driver.find_element_by_xpath("//button[contains(text(),'Submit Payment')]").click()

    try:
        WebDriverWait(driver, 90).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'Your payment was successful')]")))
    except TimeoutException:
        logging.error('Unexpected xfinity_bill_pay failure, NOT scheduling any future purchases')
        return

    cur_purchases = record_transaction(merchant.name, amount)
    schedule_next(merchant, cur_purchases)


def formatted_date_of_offset(now, start_offset):
    return (now + timedelta(seconds=start_offset)).strftime("%Y-%m-%d %I:%M%p")


def cents_to_str(cents):
    if cents < 10:
        return '0.0' + str(cents)
    elif cents < 100:
        return '0.' + str(cents)
    else:
        return str(cents)[:-2] + '.' + str(cents)[-2:]


def retryable(function):
    driver = get_webdriver()

    failures = 0
    threshold = 5
    while failures < threshold:
        try:
            function(driver)
            driver.close()
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            logging.error(function.__name__ + ' error: ' + traceback.format_exc())
            failures += 1

            if failures < threshold:
                logging.info(str(failures) + ' of ' + str(threshold) + ' attempts done, trying again in ' + str(failures * 60) + ' seconds')
                time.sleep(failures * 60)

    driver.close()
    logging.error(function.__name__ + ' failed ' + str(failures) + ' times in a row')


def get_webdriver():
    options = Options()
    options.headless = config['hide_web_browser']
    return webdriver.Firefox(options=options, executable_path='./geckodriver')


class Merchant:
    def __init__(self, name, function, config_entry):
        self.name = name
        self.function = function

        self.total_purchases = config_entry['total_purchases']
        self.amount_min = config_entry['amount_min']
        self.amount_max = config_entry['amount_max']
        self.min_gap = config_entry['min_gap']
        self.time_variance = config_entry['time_variance']
        self.min_day = config_entry['min_day']
        self.max_day = config_entry['max_day']
        self.usr = config_entry['usr']
        self.psw = config_entry['psw']
        self.card = config_entry['card']


try:
    with open('config.txt', 'r') as f:
        config = yaml.safe_load(f.read())
except FileNotFoundError:
    logging.error('Please create a config.txt file')

amazon = Merchant('amazon_gift_card_reload', amazon_gift_card_reload, config['amazon_gift_card_reload'])
xfinity = Merchant('xfinity_bill_pay', xfinity_bill_pay, config['xfinity_bill_pay'])

state_lock = Lock()
days_in_month = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


if __name__ == '__main__':
    main()

'''
TODO

Replace Timer offset with time so computer can sleep
Add burst mode so this is usable for laptops that sleep
    specify minimum gap between bursts (+- randomness)
    scheduler executes that many purchases in succession at that clock time
    should execute directly after wake up if laptop sleeping
'''
