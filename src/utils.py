import logging

from selenium.webdriver.support.wait import WebDriverWait

LOGGER = logging.getLogger('debbit')


# converts cents int to formatted dollar string
# 4 -> '0.04'
# 50 -> '0.50'
# 160 -> '1.60'
# 12345 -> '123.45'
def cents_to_str(cents):
    if cents < 10:
        return '0.0' + str(cents)
    elif cents < 100:
        return '0.' + str(cents)
    else:
        return str(cents)[:-2] + '.' + str(cents)[-2:]


# Removes all non-number characters and returns an int
# '$77.84' -> 7784
# 'balance: 1.50' -> 150
# '0.05' -> 5
def str_to_cents(str):
    return int(''.join([c for c in str if c.isdigit()]))


# This lambda function finishes the moment either element is visible.
# Returns False if element found indicating that we need to log in.
# Returns True if element found indicating that we are already logged in.
#
# To experiment with what to pass in here, try executing statements like these
# while your debugger is paused in your merchant's web_automation() function:

# driver.find_element(By.ID, 'some-element-id')
# driver.find_element(By.XPATH, "//*[contains(text(),'some text on webpage')]")
def is_logged_in(driver, timeout=30, logged_out_element=None, logged_in_element=None):
    login_status = WebDriverWait(driver, timeout).until(
        lambda driver:
        (driver.find_elements(*logged_out_element) and 'logged_out')
        or
        (driver.find_elements(*logged_in_element) and 'logged_in')
    )

    if login_status == 'logged_out':
        LOGGER.info('login_status=logged_out, logging in now')
        return False
    else:
        LOGGER.info('login_status=logged_in')
        return True
