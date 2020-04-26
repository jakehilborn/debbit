import logging

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from result import Result
import utils

LOGGER = logging.getLogger('debbit')


def web_automation(driver, merchant, amount):
    driver.get('http://payments.xfinity.com/')

    logged_in = utils.is_logged_in(driver, timeout=90,
        logged_out_element=(By.ID, 'user'),
        logged_in_element=(By.ID, 'customAmount')
    )

    if not logged_in:
        driver.find_element_by_id('user').send_keys(merchant.usr)
        driver.find_element_by_id('passwd').send_keys(merchant.psw)
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
        driver.find_element_by_id('no').click()

    cur_balance = driver.find_element_by_xpath("//span[contains(text(), '$')]").text
    if utils.str_to_cents(cur_balance) == 0:
        LOGGER.error('xfinity balance is zero, will try again later.')
        return Result.skipped
    elif utils.str_to_cents(cur_balance) < amount:
        amount = utils.str_to_cents(cur_balance)

    driver.find_element_by_id('customAmount').send_keys(utils.cents_to_str(amount))
    driver.find_element_by_xpath("//span[contains(text(),'nding in " + merchant.card[-4:] + "')]").click()
    driver.find_element_by_xpath("//span[contains(text(),'nding in " + merchant.card[-4:] + "')]").click()
    driver.find_element_by_xpath("//button[contains(text(),'Continue')]").click()
    driver.find_element_by_xpath("//button[contains(text(),'Submit Payment')]").click()

    try:
        WebDriverWait(driver, 90).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'Your payment was successful')]")))
    except TimeoutException:
        return Result.unverified

    return Result.success
