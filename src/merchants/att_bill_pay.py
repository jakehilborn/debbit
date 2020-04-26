import logging
import time

from selenium import common
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

import utils
from result import Result

LOGGER = logging.getLogger('debbit')

# Written by reddit user reddit.com/u/jonnno_, PM for any bugs or issues.


def web_automation(driver, merchant, amount):
    # Browse to login page first so that cookies can be set properly.
    driver.get('https://www.att.com/my/#/passthrough/overview')

    WebDriverWait(driver, 120).until(expected_conditions.element_to_be_clickable((By.ID, "password")))

    try:
        driver.find_element_by_id('userName').send_keys(merchant.usr)
    except common.exceptions.ElementNotInteractableException:
        pass
    try:
        driver.find_element_by_xpath("//a[@value='" + merchant.usr + "']").click()
    except common.exceptions.NoSuchElementException:
        pass

    driver.find_element_by_id('password').send_keys(merchant.psw)
    driver.find_element_by_xpath("//button[contains(@id,'loginButton')]").click()

    # Wait for potential promotions screen, regular account overview, or OTP flow
    WebDriverWait(driver, 30).until(utils.AnyExpectedCondition(
        expected_conditions.element_to_be_clickable((By.XPATH, "//img[contains(@src,'btnNoThanks')]")),
        expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Make a payment')]")),
        expected_conditions.element_to_be_clickable((By.NAME, "Send code"))
    ))

    try:  # OTP text validation
        driver.find_element_by_name("Send code").click()
        WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.ID, "verificationCodeInput")))
        sent_to_text = driver.find_element_by_xpath("//*[contains(text(),'We sent it to')]").text.strip()
        LOGGER.info(sent_to_text)
        LOGGER.info('Enter OTP here: ')
        otp = input()

        elem = driver.find_element_by_id("verificationCodeInput")
        elem.send_keys(otp)
        elem.send_keys(Keys.ENTER)
    except common.exceptions.NoSuchElementException:
        pass

    # Wait for potential promotions screen or regular account overview
    WebDriverWait(driver, 30).until(utils.AnyExpectedCondition(
        expected_conditions.element_to_be_clickable((By.XPATH, "//img[contains(@src,'btnNoThanks')]")),
        expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Make a payment')]"))
    ))

    try:  # Dismiss promotions screen if it appeared
        driver.find_element_by_xpath("//*[contains(@src,'btnNoThanks')]").click()
        WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Make a payment')]")))
    except common.exceptions.NoSuchElementException:
        pass

    # Navigate from main account screen to payment screen. Change URL rather than clicking on button because the latter sometimes seems to stall.
    driver.get("https://www.att.com/my/#/makePayment")

    # Enter amount and select payment card
    WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.ID, "pmtAmount0")))
    elem = driver.find_element_by_id('pmtAmount0')
    elem.clear()
    elem.send_keys(utils.cents_to_str(amount))
    elem = driver.find_element_by_id("paymentMethod0")
    beforeFirstPaymentCard = "Select Payment Method"
    afterLastPaymentCard = "New checking / savings account"
    while elem.get_attribute("value").lower() != beforeFirstPaymentCard.lower():
        elem.send_keys(Keys.UP)
    while elem.get_attribute("value").lower() != merchant.card.lower() and elem.get_attribute("value").lower() != afterLastPaymentCard.lower():
        elem.send_keys(Keys.DOWN)
    if elem.get_attribute("value").lower() == afterLastPaymentCard.lower():
        raise Exception("Payment method " + merchant.card + " not found in list of saved payment methods")

    # Continue
    elem.send_keys(Keys.ENTER)
    try:
        WebDriverWait(driver, 20).until(expected_conditions.presence_of_element_located((By.XPATH, "//html/body/div[contains(@class,'modalwrapper active')]//p[contains(text(),'paying more than the amount due')]")))
        driver.find_element_by_xpath("//html/body/div[contains(@class,'modalwrapper active')]//button[text()='OK']").click()
    except TimeoutException:
        pass

    # Submit
    WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.XPATH, "//button[text()='Submit']")))
    WebDriverWait(driver, 20).until(expected_conditions.invisibility_of_element_located((By.ID, "loaderOverlay")))
    time.sleep(2)
    driver.find_element_by_xpath("//button[text()='Submit']").click()

    try:
        WebDriverWait(driver, 20).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'Thank you for your payment')]")))
        WebDriverWait(driver, 20).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[text()='$" + utils.cents_to_str(amount) + "']")))
    except TimeoutException:
        return Result.unverified  # Purchase command was executed, yet we are unable to verify that it was successfully executed.
        # since debbit may have spent money but isn't sure, we log the error and stop any further payments for this merchant until the user intervenes

    return Result.success
