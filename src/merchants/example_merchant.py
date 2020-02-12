import logging

from selenium import common
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

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
    driver.get('https://duckduckgo.com/')

    WebDriverWait(driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, 'search_form_input_homepage')))

    try:  # check if hypothetical bill has already been paid by seeing if remaining balance is $0.00
        driver.find_element_by_xpath("//*[contains(text(),'$0.00'").click()
        LOGGER.error('Example merchant balance is zero, will try again later.')
        return Result.skipped  # if $0.00 found on page, do not throw an error, but also don't retry for a while so we return Result.skipped
    except common.exceptions.NoSuchElementException:
        pass  # $0.00 not on page so continue

    driver.find_element_by_id('search_form_input_homepage').send_keys(merchant.usr)
    driver.find_element_by_id('search_form_input_homepage').send_keys(', ')
    driver.find_element_by_id('search_form_input_homepage').send_keys(cents_to_str(amount))  # 5 -> 0.05

    driver.find_element_by_id('search_button_homepage').click()

    try:
        WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((
                By.XPATH, "//*[contains(text(),'" + merchant.usr + ', ' + cents_to_str(amount) + "')]"
            )))
    except TimeoutException:
        return Result.unverified  # Purchase command was executed, yet we are unable to verify that it was successfully executed.
        # since debbit may have spent money but isn't sure, we log the error and stop any further payments for this merchant until the user intervenes

    return Result.success
