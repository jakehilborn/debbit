console.log("test add-on load start")


function storeCookies(cookies) {
  browser.storage.local.set({"jakecookies":cookies})
}

function cookiesChanged() {
  console.log("cookies were changed")
  var getting = browser.cookies.getAll({
    name: "jaketest"
  });
  getting.then(storeCookies);
}

function setCookies(cookies) {
  for (let cookie of cookies['jakecookies']) {
    let newcookie = {
      'url': 'https://' + cookie['domain'] + '/',
      'name': cookie['name'],
      'value': cookie['value']
    }

    browser.cookies.set(newcookie);

    let newcookie2 = {
      'url': 'http://yo.com/',
      'name': cookie['name'],
      'value': cookie['value']
    }

    browser.cookies.set(newcookie2);
  }

  browser.cookies.onChanged.addListener(cookiesChanged)
}

// browser.cookies.onChanged.addListener(cookiesChanged)
browser.storage.local.get("jakecookies").then(setCookies, null);

function forceLoad() {
  browser.storage.local.get("jakecookies").then(setCookies, null);
}

console.log("test add-on load end")
