import logging
import time

from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from debbit import Merchant

import utils
from result import Result

LOGGER = logging.getLogger('debbit')

'''
This is to reload easypaymetrocard with stored Primary or Secondary card.
'''


def web_automation(driver, merchant: Merchant, amount):
    driver.get('https://www.easypaymetrocard.com/vector/forte/cgi_bin/forteisapi.dll?ServiceName=ETCAccountWebSO&TemplateName=accounts/PrePaidPayment.html')
    time.sleep(5) # wait for page to load or redirect to login page
    logged_in = utils.is_logged_in(driver, timeout=90,
       logged_out_element=(By.ID, 'iPassword'),
       logged_in_element=(By.ID, 'securitycode')
    )

    if not logged_in:
        time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants

        try:  # some websites will have the username auto-filled in due to a previous login
            if hasattr(merchant, 'usr'):
                driver.find_element_by_id('username').send_keys(merchant.usr)
        except ElementNotInteractableException:
            pass
        try:  # only one of .usr and .accountnumber should exist
            if hasattr(merchant, 'accountnumber'):
                driver.find_element_by_id('iAccountNumber').send_keys(merchant.accountnumber)
        except ElementNotInteractableException:
            pass

        time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
        driver.find_element_by_id('iPassword').send_keys(merchant.psw)
        time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
        driver.find_element_by_xpath("//input[@type='submit']").click()
        
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.LINK_TEXT, 'One Time Payment')))

    driver.get('https://www.easypaymetrocard.com/vector/forte/cgi_bin/forteisapi.dll?ServiceName=ETCAccountWebSO&TemplateName=accounts/PrePaidPayment.html')

    assert merchant.card in ["Primary", "Secondary"], "Only supports existing Primary or Secondary card"
    card_xpath = "//input[@value='{}']".format(merchant.card)
    driver.find_element_by_xpath(card_xpath).click()
    time.sleep(2)
    driver.find_element_by_id("securitycode").send_keys(merchant.cvv)
    time.sleep(2)
    driver.find_element_by_id("iAmount").send_keys(utils.cents_to_str(amount))
    time.sleep(2)
    driver.find_element_by_id("Address1").send_keys(merchant.address1)
    time.sleep(2)
    driver.find_element_by_id("Address2").send_keys(merchant.address2)
    time.sleep(2)
    driver.find_element_by_id("City").send_keys(merchant.city)
    time.sleep(2)
    driver.find_element_by_id("usStates").send_keys(merchant.state)
    time.sleep(2)
    driver.find_element_by_id("iZip").send_keys(merchant.zip)
    time.sleep(2)
    driver.find_element_by_xpath("//input[@type='submit']").click()


    try:
        WebDriverWait(driver, 30).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'successfully processed')]")))
    except TimeoutException:
        return Result.unverified  # Purchase command was executed, yet we are unable to verify that it was successfully executed.
        # since debbit may have spent money but isn't sure, we log the error and stop any further payments for this merchant until the user intervenes

    time.sleep(5)  # sleep for a bit to show user that payment screen is reached
    return Result.success
