function onRestoreCookiesPage(tabId, changeInfo, tabInfo) {
  if (changeInfo.status == 'complete') {
    wait_until_ready(restoreCookies)
  }
}

function wait_until_ready(function_when_ready) {
  browser.tabs.executeScript({
    code: `document.getElementById('ready').textContent;`
  }).then((retval) => {
    if (retval === undefined || retval[0] === 'false') {
      setTimeout(() => {
        wait_until_ready(function_when_ready)
      }, 100);
    } else {
      function_when_ready()
    }
  });
}

function restoreCookies() {
  console.log('restoring cookies');
  browser.tabs.executeScript({
    code: `document.getElementById('content').textContent;`
  }).then((retval) => {
    browser.cookies.set({url: 'https://jakehilborn.github.io/debbit/', name: 'retval', value: retval[0]})
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
      code: `document.getElementById('content').textContent = ` + "'" + JSON.stringify(cookies) + "'"
    }).then(() => {
      browser.tabs.executeScript({
        code: `document.getElementById('ready').textContent = 'true'`
      })
    });
  });
}

browser.tabs.onUpdated.addListener(onRestoreCookiesPage, {urls: ['file:///*restore-cookies.html']})
browser.tabs.onUpdated.addListener(onPersistCookiesPage, {urls: ['file:///*persist-cookies.html']})
