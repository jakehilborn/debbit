console.log("test add-on load start")

//browser.tabs.create({url: "/my-page.html"}).then(() => {
//  browser.tabs.executeScript({
//    code: `console.log('location:', window.location.href);`
//  });
//});

function restoreCookies() {
  console.log('restoreCookies activated')
//  browser.tabs.get(1).then(() => {
//    browser.tabs.executeScript({
//      code: `console.log('location:', window.location.href);`
//    });
//  });
  browser.tabs.executeScript({
//    code: `console.log('location:', window.location.href);`
    code: `document.getElementById('cookie-content').textContent;`
  }).then((retval) => {
    browser.cookies.set({url: 'https://jakehilborn.github.io/debbit/', name: 'retval', value: retval[0]})
  });
}

function onRestoreCookiesPage(tabId, changeInfo, tabInfo) {
  console.log(`Updated tab: ${tabId}`);
  console.log("Changed attributes: ", changeInfo);
  console.log("New tab Info: ", tabInfo);

  if (changeInfo.status == 'complete') {
    console.log('status is complete, restoring cookies');
    restoreCookies();
  }
}

//browser.tabs.onUpdated.addListener(onRestoreCookiesPage, {urls: ['https://jakehilborn.github.io/debbit/']})
browser.tabs.onUpdated.addListener(onRestoreCookiesPage, {urls: ['file:///*restore-cookies.html']})
//browser.tabs.onUpdated.addListener(onRestoreCookiesPage)

function persistCookies() {
  console.log('persistCookies activated')
  browser.cookies.getAll({}).then((cookies) => {
    browser.tabs.executeScript({
      code: `document.getElementById('welcome-to-another-page').textContent = ` + "'" + JSON.stringify(cookies) + "'"
    }).then(() => {
      console.log('cookies sent to dom')
    });
  });
}

function onPersistCookiesPage(tabId, changeInfo, tabInfo) {
  console.log(`Updated tab: ${tabId}`);
  console.log("Changed attributes: ", changeInfo);
  console.log("New tab Info: ", tabInfo);

  if (changeInfo.status == 'complete') {
    console.log('status is complete, persisting cookies');
    persistCookies();
  }
}

browser.tabs.onUpdated.addListener(onPersistCookiesPage, {urls: ['https://jakehilborn.github.io/debbit/another-page.html']})


//var port = browser.runtime.connectNative("ping_pong");
//
///*
//Listen for messages from the app.
//*/
//port.onMessage.addListener((response) => {
//  console.log("Received: " + response);
//});
//
///*
//On a click on the browser action, send the app a message.
//*/
//browser.browserAction.onClicked.addListener(() => {
//  console.log("Sending:  ping");
//  port.postMessage("ping");
//});
//
//
//function gotCookie(cookie) {
//  console.log("loaded cookie jakekey: " + cookie['jakekey'])
//}
//
//function getCookie() {
//  browser.storage.sync.get("jakekey").then(gotCookie, null);
//}
//
//function setCookie() {
//  browser.storage.sync.set({"jakekey":"jakeval"})
//}
//
//function saveCookies(cookies) {
//  var body = JSON.stringify(cookies);
//  var blob = new Blob([body], {type: 'text/plain'});
//  var objectURL = URL.createObjectURL(blob);
//  browser.downloads.download({url: objectURL, filename: Date.now() + 'jakecookies.txt', saveAs: false, conflictAction: 'overwrite'});
//}
//
//function cookiesChanged() {
//  console.log("cookies were changed")
//  var getting = browser.cookies.getAll({});
//  getting.then(saveCookies);
//}
//
//browser.cookies.onChanged.addListener(cookiesChanged)

console.log("test add-on load end")
