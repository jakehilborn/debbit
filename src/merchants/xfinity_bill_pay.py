import logging

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from result import Result
from utils import cents_to_str
from utils import str_to_cents

LOGGER = logging.getLogger('debbit')


def web_automation(driver, merchant, amount):
    driver.get('http://payments.xfinity.com/')

    # This lambda function returns the moment either of elements are visible.
    # Returns 'logging_in' or 'logged_in' depending on the element found.
    auth_flow = WebDriverWait(driver, 90).until(
        lambda driver:
        (driver.find_elements(By.ID, 'user') and 'logging_in')
        or
        (driver.find_elements(By.ID, 'customAmount') and 'logged_in')
    )

    LOGGER.info('auth_flow=' + auth_flow)

    if auth_flow == 'logging_in':
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
    if str_to_cents(cur_balance) == 0:
        LOGGER.error('xfinity balance is zero, will try again later.')
        return Result.skipped
    elif str_to_cents(cur_balance) < amount:
        amount = str_to_cents(cur_balance)

    driver.find_element_by_id('customAmount').send_keys(cents_to_str(amount))
    driver.find_element_by_xpath("//span[contains(text(),'nding in " + merchant.card[-4:] + "')]").click()
    driver.find_element_by_xpath("//span[contains(text(),'nding in " + merchant.card[-4:] + "')]").click()
    driver.find_element_by_xpath("//button[contains(text(),'Continue')]").click()
    driver.find_element_by_xpath("//button[contains(text(),'Submit Payment')]").click()

    try:
        WebDriverWait(driver, 90).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'Your payment was successful')]")))
    except TimeoutException:
        return Result.unverified

    return Result.success
