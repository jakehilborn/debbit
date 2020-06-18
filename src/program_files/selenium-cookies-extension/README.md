## What is this?

The code in this directory is an elaborate workaround regarding Selenium/Firefox handling of cookies. 

#### We Need Cookies

Many websites will present captchas or anti-automation challenges when a user uses a new web browser to log in. Cookies are stored on the web browser to indicate to websites that this particular machine has already logged in before so no need for a captcha or anti-automation challenge.

#### Selenium Does Not Keep Cookies
When Selenium launches Firefox, it creates a temporary copy of the default or a specified Firefox profile. Profiles are where cookies are saved. Since the copy is temporary, not only are the cookies temporary, but I could not even find where they are saved to disk in order to store them myself.

#### Firefox Limits Setting Cookies

Selenium does provide APIs to copy the cookies before closing the Firefox browser. However, the APIs for setting cookies on the next Firefox launch are limited. You're only allowed to set cookies for the webpage Firefox currently has open. In order to set the cookies for website.com, first you must open website.com. This is a decent but incomplete solution. Some websites redirect rules will send payments.website.com to login.website.com before Selenium has a chance to set any cookies.

#### WebExtensions APIs to the Rescue

Firefox extensions allow setting cookies for any domain. However, it's hard to get data in and out of Firefox extensions. Both Selenium and Firefox do have access to the DOM so we can use that for messaging. When the file persist-cookies.html is opened, a base64 encoding of all cookies is written to the DOM. Debbit then uses Selenium to read the DOM and save the cookies to a file. On the next run, Debbit uses Selenium to open restore-cookies.html and writes the previously saved cookies to the DOM. This extension then reads the DOM and loads those cookies into storage.

#### Bundling Extensions for Selenium

Selenium can be configured to use a Firefox profile. This profile is where extensions are installed. I've discovered you can remove all data from a Firefox profile but leave the extensions portion in place. This partial-profile works cross platform and contains only the installed extension and nothing else.
