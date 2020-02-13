import logging

from selenium import common
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from utils import cents_to_str
from result import Result

LOGGER = logging.getLogger('debbit')

#Written by /u/TNSepta, PM for any bugs or issues.
def web_automation(driver, merchant, amount):
    driver.get('https://www.optimum.net/pay-bill/payment-options/')

    WebDriverWait(driver, 90).until(expected_conditions.element_to_be_clickable((By.ID, 'loginPageUsername')))

    driver.find_element_by_id('loginPageUsername').send_keys(merchant.usr)
    driver.find_element_by_id('loginPagePassword').send_keys(merchant.psw)
    driver.find_element_by_xpath("//button[contains(text(),'Sign in to Optimum.net')]").click()

    WebDriverWait(driver, 90).until(expected_conditions.element_to_be_clickable((By.ID, 'otherAmountInput')))

    cur_balance = driver.find_element_by_xpath("//span[@class='payment--radio--bold ng-binding']").text
    LOGGER.info("Current balance is "+cur_balance)
    if int(''.join([c for c in cur_balance if c.isdigit()])) == 0:  # $77.84 -> 7784
        LOGGER.error('Optimum account balance is zero, will try again later.')
        return Result.skipped
    elif int(''.join([c for c in cur_balance if c.isdigit()])) < amount:
        LOGGER.error('Optimum account balance is too low to run, will try again later.')
        return Result.skipped

    driver.find_element_by_id('otherAmountInput').send_keys(cents_to_str(amount)) #Enter the amount
    driver.find_element_by_xpath("//span[contains(text(),'Other amount')]/preceding-sibling::div").click() #Select the radio button
    driver.find_element_by_xpath("//div[contains(text(),'Payment Method')]/following-sibling::div").click() #Open the selector dropdown box
    try:
        driver.find_element_by_xpath("//span[contains(text(),'"+merchant.card+"')]").click() #Select the payment method
    except:
        LOGGER.error('Failed to find payment method with name '+merchant.card)
        return Result.unverified
    buttonStr = (driver.find_element_by_id('otpSubmit').get_attribute('value'))
    expectStr = "Pay $"+cents_to_str(amount)+" now with "+merchant.card
    if buttonStr == expectStr:
        driver.find_element_by_id('otpSubmit').click()
        LOGGER.info('Submitting purchase: '+buttonStr)
    else:
        LOGGER.error('Failed to find valid pay button. ')
        LOGGER.info('Detected: '+buttonStr)
        LOGGER.info('Expected: '+expectStr)
        return Result.unverified

    #Check if the payment succeeded.
    try:
        WebDriverWait(driver, 90).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'Confirmation Number:')]")))
        LOGGER.info("Successful payment: "+driver.find_element_by_xpath("//*[contains(text(),'Confirmation Number:')]").text)
        return Result.success
    except TimeoutException:
        #Check if there was an error, if so log the error.
        try:
            WebDriverWait(driver, 5).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'unable')]")))
            LOGGER.error("Failed payment: "+driver.find_element_by_xpath("//*[contains(text(),'unable')]").text)
        except TimeoutException:
            return Result.unverified
        return Result.unverified
    return Result.unverified