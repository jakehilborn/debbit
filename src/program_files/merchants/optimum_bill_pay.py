import logging

from selenium import common
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from result import Result
import utils

LOGGER = logging.getLogger('debbit')

# Written by reddit user reddit.com/u/TNSepta, PM for any bugs or issues.


def web_automation(driver, merchant, amount):
    driver.get('https://www.optimum.net/pay-bill/payment-options/')

    logged_in = utils.is_logged_in(driver, timeout=90,
        logged_out_element=(By.ID, 'loginPagePassword'),
        logged_in_element=(By.ID, 'otherAmountInput')
    )

    if not logged_in:
        try:  # if first run, fill in username. If subsequent run, username may already be filled in.
            driver.find_element_by_id('loginPageUsername').send_keys(merchant.usr)
        except ElementNotInteractableException:
            pass

        driver.find_element_by_id('loginPagePassword').send_keys(merchant.psw)
        driver.find_element_by_xpath("//button[contains(text(),'Sign in to Optimum.net')]").click()
        WebDriverWait(driver, 90).until(expected_conditions.element_to_be_clickable((By.ID, 'otherAmountInput')))

    cur_balance = driver.find_element_by_xpath("//span[@class='payment--radio--bold ng-binding']").text
    LOGGER.info('Current Optimum balance is ' + cur_balance)

    if utils.str_to_cents(cur_balance) < 100:
        LOGGER.warning('Optimum account balance is less than minimum $1 payment, will try again later.')
        return Result.skipped
    elif utils.str_to_cents(cur_balance) < amount:
        LOGGER.info('Adjusting spend to ' + utils.str_to_cents(cur_balance) + ' cents since current balance is less than ' + amount + ' cents')
        amount = utils.str_to_cents(cur_balance)

    driver.find_element_by_id('otherAmountInput').send_keys(utils.cents_to_str(amount))  # Enter the amount
    driver.find_element_by_xpath("//span[contains(text(),'Other amount')]/preceding-sibling::div").click()  # Select the radio button
    driver.find_element_by_xpath("//div[contains(text(),'Payment Method')]/following-sibling::div").click()  # Open the selector dropdown box
    try:
        driver.find_element_by_xpath("//span[contains(text(),'" + merchant.card + "')]").click()  # Select the payment method
    except common.exceptions.NoSuchElementException:
        LOGGER.error('Failed to find payment method with name ' + merchant.card)
        return Result.failed

    button_str = driver.find_element_by_id('otpSubmit').get_attribute('value')
    expect_str = "Pay $" + utils.cents_to_str(amount) + " now with " + merchant.card

    if merchant.dry_run == True:
        return Result.dry_run

    if button_str == expect_str:
        driver.find_element_by_id('otpSubmit').click()
        LOGGER.info('Submitting purchase: ' + button_str)
    else:
        LOGGER.error('Failed to find valid pay button.')
        LOGGER.info('Detected: ' + button_str)
        LOGGER.info('Expected: ' + expect_str)
        return Result.failed

    # Check if the payment succeeded.
    try:
        WebDriverWait(driver, 90).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'Confirmation Number:')]")))
        LOGGER.info("Successful payment: " + driver.find_element_by_xpath("//*[contains(text(),'Confirmation Number:')]").text)
        return Result.success
    except TimeoutException:
        # Check if there was an error, if so log the error.
        try:
            WebDriverWait(driver, 5).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'unable')]")))
            LOGGER.error("Failed payment: " + driver.find_element_by_xpath("//*[contains(text(),'unable')]").text)
        except TimeoutException:
            return Result.unverified
        return Result.unverified
