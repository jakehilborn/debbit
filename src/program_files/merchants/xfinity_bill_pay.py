import logging
import random
import time

from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

import utils
from result import Result

LOGGER = logging.getLogger('debbit')


def web_automation(driver, merchant, amount):
    driver.get('http://payments.xfinity.com/')

    logged_in = utils.is_logged_in(driver, timeout=90,
        logged_out_element=(By.ID, 'passwd'),
        logged_in_element=(By.ID, 'customAmount')
    )

    if not logged_in:
        try:  # if first run, fill in username. If subsequent run, username already exists and filling in throws exception
            driver.find_element_by_id('user').send_keys(merchant.usr)
        except ElementNotInteractableException:
            pass
        time.sleep(random.random() * 3)  # Xfinity is using bot detection software, slow down the automation a bit to help avoid detection
        driver.find_element_by_id('passwd').send_keys(merchant.psw)
        time.sleep(random.random() * 3)
        driver.find_element_by_id('sign_in').click()

        try:  # first time run captcha
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.ID, 'nucaptcha-answer')))
            LOGGER.info('captcha detected')
            input('''
Detected first time run captcha. Please follow these one-time steps. Future runs won't need this.

1. Open the Firefox window that debbit created.
2. Enter your user, pass, and the moving characters manually.
3. Click the "Sign In" button.
4. Click on this terminal window and hit "Enter" to continue running debbit.
''')
        except TimeoutException:
            pass

        WebDriverWait(driver, 90).until(expected_conditions.element_to_be_clickable((By.ID, 'customAmount')))

    if driver.find_elements_by_id('no'):  # survey pop-up
        time.sleep(random.random() * 3)
        driver.find_element_by_id('no').click()

    cur_balance = driver.find_element_by_xpath("//span[contains(text(), '$')]").text
    if utils.str_to_cents(cur_balance) == 0:
        LOGGER.warning('xfinity balance is zero, will try again later.')
        return Result.skipped
    elif utils.str_to_cents(cur_balance) < amount:
        amount = utils.str_to_cents(cur_balance)

    time.sleep(random.random() * 3)
    driver.find_element_by_id('customAmount').send_keys(utils.cents_to_str(amount))
    time.sleep(random.random() * 3)
    driver.find_element_by_xpath("//span[contains(text(),'nding in " + merchant.card[-4:] + "')]").click()
    time.sleep(random.random() * 3)
    driver.find_element_by_xpath("//span[contains(text(),'nding in " + merchant.card[-4:] + "')]").click()
    time.sleep(random.random() * 3)
    driver.find_element_by_xpath("//button[contains(text(),'Continue')]").click()

    WebDriverWait(driver, 5).until(expected_conditions.presence_of_element_located((By.XPATH, "//button[contains(text(),'Submit Payment')]")))
    time.sleep(random.random() * 3)

    if merchant.dry_run == True:
        return Result.dry_run

    driver.find_element_by_xpath("//button[contains(text(),'Submit Payment')]").click()

    try:
        WebDriverWait(driver, 90).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'Your payment was successful')]")))
    except TimeoutException:
        return Result.unverified

    return Result.success
