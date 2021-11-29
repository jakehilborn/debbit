import logging
import random
import time

from selenium import common
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, WebDriverException, \
    ElementNotInteractableException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

import utils
from result import Result

LOGGER = logging.getLogger('debbit')


def web_automation(driver, merchant, amount):
    driver.get('https://www.amazon.com/gp/product/B086KKT3RX')

    WebDriverWait(driver, 90).until(expected_conditions.element_to_be_clickable((By.ID, "gcui-asv-reload-buynow-button")))
    for i in range(300):
        if driver.find_element_by_id("gcui-asv-reload-buynow-button").text == 'Buy Now':  # wait for 'Loading...' text to turn into 'Buy Now'
            break
        time.sleep(0.1)

    time.sleep(1 + random.random() * 2)  # slow down automation randomly to help avoid bot detection
    driver.find_element_by_id('gcui-asv-reload-form-custom-amount').send_keys(utils.cents_to_str(amount))
    time.sleep(1 + random.random() * 2)  # slow down automation randomly to help avoid bot detection
    driver.find_element_by_id("gcui-asv-reload-buynow-button").click()

    WebDriverWait(driver, 90).until(utils.AnyExpectedCondition(
        expected_conditions.element_to_be_clickable((By.ID, 'ap_email')),  # first time login
        expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'" + merchant.usr + "')]")),  # username found on login page
        # Already logged in
        expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Order Summary')]")),  # Checkout page
        expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'a payment method')]"))  # Another version of the checkout page
    ))

    if not driver.find_elements_by_xpath("//*[contains(text(),'Order Summary')]") and not driver.find_elements_by_xpath("//*[contains(text(),'a payment method')]"):  # Not in checkout, so we did not auto login. Finish login flow.
        if driver.find_elements_by_xpath("//*[contains(text(),'" + merchant.usr + "')]"):
            driver.find_element_by_xpath("//*[contains(text(),'" + merchant.usr + "')]").click()  # click username in case we're on the Switch Accounts page
            WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.ID, 'signInSubmit')))
            time.sleep(1 + random.random() * 2)

        if driver.find_elements_by_id('ap_email'):  # if first run, fill in email. If subsequent run, nothing to fill in
            try:
                driver.find_element_by_id('ap_email').send_keys(merchant.usr)
                time.sleep(1 + random.random() * 2)
            except ElementNotInteractableException:  # Sometimes this field is prefilled with Firstname Lastname and does not accept input
                pass

        if driver.find_elements_by_id('continue'):  # a/b tested new UI flow
            driver.find_element_by_id('continue').click()
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.ID, 'ap_password')))
            time.sleep(1 + random.random() * 2)

        if driver.find_elements_by_name('rememberMe'):
            time.sleep(1 + random.random() * 2)
            driver.find_element_by_name('rememberMe').click()

        driver.find_element_by_id('ap_password').send_keys(merchant.psw)
        time.sleep(1 + random.random() * 2)
        driver.find_element_by_id('signInSubmit').click()
        time.sleep(1 + random.random() * 2)

        handle_anti_automation_challenge(driver, merchant)

        try:  # Push Notification / Email MFA
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'approve the notification')]")))
            if driver.find_elements_by_xpath("//*[contains(text(),'approve the notification')]"):
                LOGGER.info('\n')
                LOGGER.info('Please approve the Amazon login notification sent to your email or phone. Debbit will wait up to 3 minutes.')
                for i in range(180):  # Wait for up to 3 minutes for user to approve login notification
                    if not driver.find_elements_by_xpath("//*[contains(text(),'approve the notification')]"):
                        break
                    time.sleep(1)
        except TimeoutException:
            pass

        try:  # OTP text message
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'phone number ending in')]")))
            if driver.find_elements_by_id('auth-mfa-remember-device'):
                driver.find_element_by_id('auth-mfa-remember-device').click()

            sent_to_text = driver.find_element_by_xpath("//*[contains(text(),'phone number ending in')]").text
            LOGGER.info(sent_to_text)
            LOGGER.info('Enter OTP here:')
            otp = input()

            driver.find_element_by_id('auth-mfa-otpcode').send_keys(otp)
            time.sleep(1 + random.random() * 2)
            driver.find_element_by_id('auth-signin-button').click()
            time.sleep(1 + random.random() * 2)
        except TimeoutException:
            pass

        try:  # OTP email validation
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'One Time Pass')]")))
            otp_email = True
        except TimeoutException:
            otp_email = False

        try:
            driver.find_element_by_xpath("//*[contains(text(),'one-time pass')]").click()
            time.sleep(1 + random.random() * 2)
            otp_email = True
        except common.exceptions.NoSuchElementException:
            pass

        if otp_email:
            if driver.find_elements_by_id('continue'):
                driver.find_element_by_id('continue').click()
                time.sleep(1 + random.random() * 2)

            handle_anti_automation_challenge(driver, merchant)

            try:  # User may have manually advanced to gift card screen or stopped at OTP input. Handle OTP input if on OTP screen.
                WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Enter OTP')]")))
                sent_to_text = driver.find_element_by_xpath("//*[contains(text(),'@')]").text
                LOGGER.info(sent_to_text)
                LOGGER.info('Enter OTP here:')
                otp = input()

                elem = driver.find_element_by_xpath("//input")
                elem.send_keys(otp)
                time.sleep(1 + random.random() * 2)
                elem.send_keys(Keys.TAB)
                time.sleep(1 + random.random() * 2)
                elem.send_keys(Keys.ENTER)
                time.sleep(1 + random.random() * 2)
            except TimeoutException:
                pass

        try:
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Not now')]")))
            driver.find_element_by_xpath("//*[contains(text(),'Not now')]").click()
            time.sleep(1 + random.random() * 2)
        except TimeoutException:  # add mobile number page
            pass

    # Now expecting to be on checkout page with debit card selection present
    WebDriverWait(driver, 30).until(utils.AnyExpectedCondition(
        expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Order Summary')]")),  # Checkout page
        expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'a payment method')]"))  # Another version of the checkout page
    ))

    if driver.find_elements_by_id('payChangeButtonId'):
        time.sleep(1 + random.random() * 2)
        driver.find_element_by_id('payChangeButtonId').click()
        WebDriverWait(driver, 10).until(expected_conditions.element_to_be_clickable((By.XPATH, "//span[contains(text(),'ending in " + merchant.card[-4:] + "')]")))

    for element in driver.find_elements_by_xpath("//span[contains(text(),'ending in " + merchant.card[-4:] + "')]"):
        try:  # Amazon has redundant non-clickable elements. This will try each one until one works.
            time.sleep(1 + random.random() * 2)
            element.click()
            break
        except WebDriverException:
            pass

    if driver.find_elements_by_id('orderSummaryPrimaryActionBtn'):
        driver.find_element_by_id('orderSummaryPrimaryActionBtn').click()  # Click "Use this payment method" button
    else:  # Find Continue text, the grandparent element of the text is the clickable Continue button
        driver.find_element_by_xpath("//span[contains(text(),'Continue')]").find_element_by_xpath('../..').click()

    WebDriverWait(driver, 10).until(utils.AnyExpectedCondition(
        expected_conditions.element_to_be_clickable((By.ID, 'submitOrderButtonId')),  # "Place your order" button showing, card ready to be used
        expected_conditions.element_to_be_clickable((By.ID, 'placeYourOrder')),  # Other checkout page "Place your order" button showing, card ready to be used
        expected_conditions.element_to_be_clickable((By.XPATH, "//input[@placeholder='ending in " + merchant.card[-4:] + "']"))  # Verify card flow
    ))

    if driver.find_elements_by_xpath("//input[@placeholder='ending in " + merchant.card[-4:] + "']"):  # Verify card flow
        elem = driver.find_element_by_xpath("//input[@placeholder='ending in " + merchant.card[-4:] + "']")
        time.sleep(1 + random.random() * 2)
        elem.send_keys(merchant.card)
        time.sleep(1 + random.random() * 2)
        elem.send_keys(Keys.TAB)
        time.sleep(1 + random.random() * 2)
        elem.send_keys(Keys.ENTER)

        time.sleep(10 + random.random() * 2)
        if driver.find_elements_by_id('orderSummaryPrimaryActionBtn'):
            driver.find_element_by_id('orderSummaryPrimaryActionBtn').click()  # Click "Use this payment method" button
        else:  # Find Continue text, the grandparent element of the text is the clickable Continue button
            driver.find_element_by_xpath("//span[contains(text(),'Continue')]").find_element_by_xpath('../..').click()

        WebDriverWait(driver, 10).until(utils.AnyExpectedCondition(
            expected_conditions.element_to_be_clickable((By.ID, 'submitOrderButtonId')),  # "Place your order" button showing, card ready to be used
            expected_conditions.element_to_be_clickable((By.ID, 'placeYourOrder')),  # Other checkout page "Place your order" button showing, card ready to be used
        ))

    time.sleep(1 + random.random() * 2)

    expected_order_total = 'Order total:$' + utils.cents_to_str(amount)
    if driver.find_element_by_id('subtotals-marketplace-spp-bottom').text != expected_order_total:
        LOGGER.error('Unable to verify order total is correct, not purchasing. Expected "' + expected_order_total + '", but found "' + driver.find_element_by_id('subtotals-marketplace-spp-bottom').text + '".')
        return Result.failed

    if driver.find_elements_by_id('submitOrderButtonId'):
        driver.find_element_by_id('submitOrderButtonId').click()  # Click "Place your order" button
    else:
        driver.find_element_by_id('placeYourOrder').click()  # Other checkout page click "Place your order" button

    try:
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'your order has been placed') or contains(text(),'Order placed')]")))
    except TimeoutException:
        LOGGER.error('Clicked "Place your order" button, but unable to confirm if order was successful.')
        return Result.unverified

    if driver.find_elements_by_xpath("//*[contains(text(), 'your order has been placed') or contains(text(),'Order placed')]"):
        return Result.success
    else:
        LOGGER.error('Clicked "Place your order" button, but unable to confirm if order was successful.')
        return Result.unverified


def handle_anti_automation_challenge(driver, merchant):
    try:
        WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'nter the characters')]")))

        time.sleep(1 + random.random() * 2)
        if driver.find_elements_by_id('ap_password'):
            driver.find_element_by_id('ap_password').send_keys(merchant.psw)

        LOGGER.info('amazon captcha detected')
        input('''
Anti-automation captcha detected. Please follow these steps, future runs shouldn't need captcha input unless you set "use_cookies: no" in config.txt.

1. Open the Firefox window that debbit created.
2. Input the captcha / other anti-automation challenges.
3. You should now be on the gift card reload page
4. Click on this terminal window and hit "Enter" to continue running debbit.
''')
    except TimeoutException:
        pass
