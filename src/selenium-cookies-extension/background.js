function onRestoreCookiesPage(tabId, changeInfo, tabInfo) {
  if (changeInfo.status == 'complete') {
    wait_until_ready(restoreCookies)
  }
}

function wait_until_ready(function_when_ready) {
  browser.tabs.executeScript({
    code: "document.getElementById('status').textContent;"
  }).then((retval) => {
    if (retval === undefined || retval[0] !== 'dom-ready') {
      setTimeout(() => {
        wait_until_ready(function_when_ready)
      }, 100);
    } else {
      function_when_ready()
    }
  });
}

function restoreCookies() {
  browser.tabs.executeScript({
    code: "document.getElementById('content').textContent;"
  }).then((retval) => {
    cookies = JSON.parse(atob(retval))
    for (let c of cookies) {
      filtered_cookie = {
        expirationDate: c.expirationDate,
        firstPartyDomain: c.firstPartyDomain,
        httpOnly: c.httpOnly,
        name: c.name,
        path: c.path,
        sameSite: c.sameSite,
        secure: c.secure,
        storeId: c.storeId,
        url: 'https://' + c.domain,
        value: c.value
      };

      browser.cookies.set(filtered_cookie)
    }
    browser.tabs.executeScript({
      code: "document.getElementById('status').textContent = 'done'"
    })
  });
}

function onPersistCookiesPage(tabId, changeInfo, tabInfo) {
  if (changeInfo.status == 'complete') {
    persistCookies();
  }
}

function persistCookies() {
  browser.cookies.getAll({}).then((cookies) => {
    browser.tabs.executeScript({
      code: "document.getElementById('content').textContent = '" + btoa(JSON.stringify(cookies)) + "'"
    }).then(() => {
      browser.tabs.executeScript({
        code: "document.getElementById('status').textContent = 'dom-ready'"
      })
    });
  });
}

browser.tabs.onUpdated.addListener(onRestoreCookiesPage, {urls: ['file:///*restore-cookies.html']})
browser.tabs.onUpdated.addListener(onPersistCookiesPage, {urls: ['file:///*persist-cookies.html']})
browser.browserAction.onClicked.addListener(restoreCookies);