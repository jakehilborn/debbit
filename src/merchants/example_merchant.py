import logging
import time

from selenium import common
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

import utils
from result import Result
from utils import cents_to_str

LOGGER = logging.getLogger('debbit')

'''
How to add a new merchant module to debbit

Create a new .py file in the merchants directory. Create a new block in config.txt such that the merchant name matches
the name of your new file (excluding .py). The file must have a function with the signature
`def web_automation(driver, merchant, amount):` that returns a `Result` in all possible scenarios. There is no
Result.error enum since it is expected that your web automation will throw an exception in case something does cause
an error.

For more complex scenarios, please refer to the other merchant .py files.
'''


def web_automation(driver, merchant, amount):
    driver.get('http://127.0.0.1:4000/example-merchant/login.html')

    logged_in = utils.is_logged_in(driver, timeout=90,
       logged_out_element=(By.ID, 'password'),
       logged_in_element=(By.ID, 'submit-payment')
    )

    if not logged_in:
        time.sleep(1)  # pause to let user watch what's happening - not necessary for real merchants
        driver.find_element_by_id('username').send_keys(merchant.usr)
        time.sleep(1)  # pause to let user watch what's happening - not necessary for real merchants
        driver.find_element_by_id('password').send_keys(merchant.usr)
        time.sleep(1)  # pause to let user watch what's happening - not necessary for real merchants
        driver.find_element_by_id('login').click()
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.ID, 'submit-payment')))

    cur_balance = driver.find_element_by_xpath("//span[contains(text(), '$')]").text
    if utils.str_to_cents(cur_balance) == 0:
        LOGGER.error('example_merchant balance is zero, will try again later.')
        return Result.skipped
    elif utils.str_to_cents(cur_balance) < amount:
        amount = utils.str_to_cents(cur_balance)

    time.sleep(1)  # pause to let user watch what's happening - not necessary for real merchants
    driver.find_element_by_xpath("//*[contains(text(), 'card ending in " + merchant.card + "')]").click()
    time.sleep(1)  # pause to let user watch what's happening - not necessary for real merchants
    driver.find_element_by_id('amount').send_keys(utils.cents_to_str(amount))
    time.sleep(1)  # pause to let user watch what's happening - not necessary for real merchants
    driver.find_element_by_id('submit-payment').click()

    try:
        WebDriverWait(driver, 30).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'Thank you!')]")))
    except TimeoutException:
        return Result.unverified  # Purchase command was executed, yet we are unable to verify that it was successfully executed.
        # since debbit may have spent money but isn't sure, we log the error and stop any further payments for this merchant until the user intervenes

    time.sleep(3)  # sleep for a bit to show user that payment screen is reached
    return Result.success
