(function () {
  var API = "https://realeastate-web-app.onrender.com";

  if (
    location.hostname.indexOf("yad2.co.il") === -1 &&
    location.hostname.indexOf("madlan.co.il") === -1
  ) {
    alert("הבוקמרקלט עובד רק בדפי יד2 או מדלן");
    return;
  }

  var overlay = document.createElement("div");
  overlay.style.cssText =
    "position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:999999;display:flex;align-items:center;justify-content:center;font-family:Heebo,sans-serif";
  overlay.innerHTML =
    '<div style="background:#fff;border-radius:16px;padding:32px 40px;text-align:center;direction:rtl;max-width:340px;box-shadow:0 20px 60px rgba(0,0,0,.3)">' +
    '<div style="width:48px;height:48px;border:4px solid #ef4444;border-top-color:transparent;border-radius:50%;margin:0 auto 16px;animation:bk-spin 0.8s linear infinite"></div>' +
    '<div style="font-size:18px;font-weight:600;color:#1f2937">שולף את פרטי הנכס...</div>' +
    "</div>" +
    "<style>@keyframes bk-spin{to{transform:rotate(360deg)}}</style>";
  document.body.appendChild(overlay);

  function done(msg, ok) {
    overlay.innerHTML =
      '<div style="background:#fff;border-radius:16px;padding:32px 40px;text-align:center;direction:rtl;max-width:340px;box-shadow:0 20px 60px rgba(0,0,0,.3)">' +
      '<div style="width:48px;height:48px;border-radius:50%;margin:0 auto 16px;display:flex;align-items:center;justify-content:center;background:' +
      (ok ? "#dcfce7" : "#fee2e2") +
      '">' +
      (ok
        ? '<svg width="24" height="24" fill="none" stroke="#16a34a" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>'
        : '<svg width="24" height="24" fill="none" stroke="#dc2626" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>') +
      "</div>" +
      '<div style="font-size:18px;font-weight:600;color:#1f2937;margin-bottom:8px">' +
      msg +
      "</div>" +
      '<button onclick="this.closest(\'div[style]\').parentElement.remove()" style="margin-top:12px;background:#ef4444;color:#fff;border:none;padding:8px 28px;border-radius:999px;font-size:14px;font-weight:500;cursor:pointer">סגור</button>' +
      "</div>";
  }

  try {
    var listing = extractListing();
    sendToServer(listing);
  } catch (e) {
    done("שגיאה בשליפת הנתונים: " + e.message, false);
  }

  function extractListing() {
    var source = location.hostname.indexOf("yad2") !== -1 ? "yad2" : "madlan";
    var result = {
      url: location.href,
      source: source,
      address: null,
      city: null,
      neighborhood: null,
      street: null,
      price: null,
      rooms: null,
      floor: null,
      total_floors: null,
      size_sqm: null,
      property_type: null,
      entry_date: null,
      description: null,
      has_parking: false,
      has_elevator: false,
      has_balcony: false,
      has_mamad: false,
      has_air_conditioning: false,
      is_furnished: false,
      contacts: [],
      images: [],
    };

    if (source === "yad2") {
      extractYad2Json(result);
      extractYad2Dom(result);
      extractYad2Features(result);
      extractYad2Images(result);
      extractYad2Contacts(result);
    } else {
      extractMadlanDom(result);
    }

    return result;
  }

  /* ── Yad2: __NEXT_DATA__ JSON extraction ── */
  function extractYad2Json(r) {
    try {
      var nd = window.__NEXT_DATA__;
      if (!nd) return;
      var props = (nd.props || {}).pageProps || {};
      var item = findListingObj(props, 0);
      if (!item) return;

      r.price = r.price || str(item.price || item.Price);
      r.rooms = r.rooms || str(item.rooms || item.Rooms || item.rooms_text);
      r.size_sqm =
        r.size_sqm ||
        str(
          item.square_meters ||
            item.SquareMeter ||
            item.squaremeter ||
            item.size
        );
      r.floor = r.floor || str(item.floor || item.Floor);
      r.total_floors =
        r.total_floors || str(item.TotalFloor_text || item.total_floor);
      r.description =
        r.description ||
        str(item.info_text || item.description || item.Description);
      r.property_type =
        r.property_type ||
        str(item.property_type || item.PropertyType || item.catId_text);
      r.entry_date =
        r.entry_date || str(item.date_of_entry || item.DateOfEntry);

      var addr = item.address_home || item.address || {};
      if (typeof addr === "object" && addr !== null) {
        r.city = r.city || str(typeof addr.city === "object" ? (addr.city || {}).text : addr.city);
        r.street = r.street || str(typeof addr.street === "object" ? (addr.street || {}).text : addr.street);
        r.neighborhood = r.neighborhood || str(typeof addr.neighborhood === "object" ? (addr.neighborhood || {}).text : addr.neighborhood);
        var houseNum = str(typeof addr.house === "object" ? (addr.house || {}).number : addr.house_number);
        if (r.street && houseNum) r.address = r.street + " " + houseNum + ", " + (r.city || "");
        else if (r.street) r.address = r.street + ", " + (r.city || "");
      } else if (typeof addr === "string") {
        r.address = addr;
      }
      if (!r.address) r.address = str(item.title || item.Title || item.address_text);

      var imgs = item.images || item.Images || [];
      if (Array.isArray(imgs)) {
        for (var i = 0; i < imgs.length; i++) {
          var img = imgs[i];
          var src = typeof img === "string" ? img : img.src || img.url;
          if (src) r.images.push(src);
        }
      }

      var cName = str(item.contact_name || item.ContactName);
      var cPhone = str(item.contact_phone || item.ContactPhone);
      if (cName || cPhone) r.contacts.push({ name: cName, phone: cPhone });
    } catch (_) {}
  }

  function findListingObj(obj, depth) {
    if (depth > 5 || !obj || typeof obj !== "object") return null;
    var keys = ["item", "listing", "feedItem", "data", "listingData", "ad"];
    for (var k = 0; k < keys.length; k++) {
      var c = obj[keys[k]];
      if (c && typeof c === "object" && ("price" in c || "rooms" in c || "Price" in c || "Rooms" in c))
        return c;
    }
    var vals = Object.values(obj);
    for (var v = 0; v < vals.length; v++) {
      if (vals[v] && typeof vals[v] === "object") {
        if ("price" in vals[v] || "rooms" in vals[v] || "Price" in vals[v] || "square_meters" in vals[v])
          return vals[v];
        var found = findListingObj(vals[v], depth + 1);
        if (found) return found;
      }
    }
    return null;
  }

  /* ── Yad2: DOM extraction ── */
  function extractYad2Dom(r) {
    try {
      var priceEl = document.querySelector('[data-testid="price"]');
      if (priceEl && !r.price) r.price = priceEl.textContent.trim();

      var addrEl =
        document.querySelector('[class*="floating-property-details_address"]') ||
        document.querySelector('[class*="address"]');
      var h1 = document.querySelector("h1");
      if (!r.street) r.street = (addrEl && addrEl.textContent.trim()) || (h1 && h1.textContent.trim());

      var subEl =
        document.querySelector('h2[data-testid="address"]') ||
        document.querySelector('[class*="address_address"]') ||
        document.querySelector('[class*="item-title_subTitle"]');
      if (subEl) {
        var parts = subEl.textContent.trim().split(",").map(function (s) { return s.trim(); });
        if (parts.length >= 3) {
          r.property_type = r.property_type || parts[0];
          r.neighborhood = r.neighborhood || parts[1];
          r.city = r.city || parts[2];
        } else if (parts.length === 2) {
          r.neighborhood = r.neighborhood || parts[0];
          r.city = r.city || parts[1];
        }
      }

      var detailItems = document.querySelectorAll('[data-testid="property-detail-item"]');
      detailItems.forEach(function (item) {
        var valueEl = item.querySelector('[data-testid="building-text"]');
        var labelEl = item.querySelector('[class*="itemValue"]');
        var value = valueEl ? valueEl.textContent.trim() : "";
        var label = labelEl ? labelEl.textContent.trim() : item.textContent.trim();
        if (label.indexOf("חדרים") !== -1 && value) r.rooms = r.rooms || value;
        else if (label.indexOf("מ") !== -1 && (label.indexOf("ר") !== -1 || label.indexOf("\u05F4") !== -1) && value)
          r.size_sqm = r.size_sqm || value;
        else if (label.indexOf("קרקע") !== -1 || label.indexOf("קומה") !== -1)
          r.floor = r.floor || value || label;
      });

      if (!r.rooms || !r.size_sqm) {
        var bd = document.querySelector('[data-testid="building-details"]');
        if (bd) {
          var text = bd.textContent;
          if (!r.rooms) { var m = text.match(/([\d.]+)\s*חדרים/); if (m) r.rooms = m[1]; }
          if (!r.size_sqm) { var m2 = text.match(/([\d,]+)\s*מ/); if (m2) r.size_sqm = m2[1].replace(",", ""); }
        }
      }

      var descEl = document.querySelector('[class*="description"], [class*="Description"], [class*="info_text"]');
      if (descEl && !r.description) r.description = descEl.textContent.trim();

      if (r.street && r.city) {
        r.address = r.neighborhood ? r.street + ", " + r.neighborhood + ", " + r.city : r.street + ", " + r.city;
      } else if (!r.address && h1) {
        r.address = h1.textContent.trim();
      }
    } catch (_) {}
  }

  /* ── Yad2: features ── */
  function extractYad2Features(r) {
    var FEATURES = {
      "מיזוג אויר": "has_air_conditioning",
      "מיזוג אוויר": "has_air_conditioning",
      "מרפסת": "has_balcony",
      "מעלית": "has_elevator",
      "חניה": "has_parking",
      "חנייה": "has_parking",
      'ממ"ד': "has_mamad",
      "ממ״ד": "has_mamad",
      "ממד": "has_mamad",
      "מרוהטת": "is_furnished",
      "ריהוט": "is_furnished",
    };

    function scan(text) {
      for (var kw in FEATURES) {
        if (text.indexOf(kw) !== -1) r[FEATURES[kw]] = true;
      }
    }

    if (r.description) scan(r.description);

    var els = document.querySelectorAll(
      "[class*='ameniti'], [class*='feature'], [class*='tag'], [data-testid*='amenit'], [data-testid*='feature']"
    );
    els.forEach(function (el) {
      var t = (el.textContent || "").trim();
      if (t && t.length < 50) scan(t);
    });
  }

  /* ── Yad2: images ── */
  function extractYad2Images(r) {
    if (r.images.length > 0) return;
    var skip = ["logo", "icon", "avatar", "pixel", "tracking", "1x1", "svg", "play.png"];
    var seen = {};
    var imgEls = document.querySelectorAll(
      "[class*='gallery'] img, [class*='Gallery'] img, [class*='carousel'] img, [class*='slider'] img, [class*='image-gallery'] img, [data-testid*='image'] img, picture img"
    );
    imgEls.forEach(function (img) {
      var src = img.src || img.dataset.src;
      if (!src || src.indexOf("http") !== 0) return;
      var low = src.toLowerCase();
      if (skip.some(function (s) { return low.indexOf(s) !== -1; })) return;
      var base = src.split("?")[0];
      if (!seen[base]) { seen[base] = true; r.images.push(src); }
    });
  }

  /* ── Yad2: contacts ── */
  function extractYad2Contacts(r) {
    if (r.contacts.length > 0) return;
    var phone = null;
    var telLinks = document.querySelectorAll("a[href^='tel:']");
    for (var i = 0; i < telLinks.length; i++) {
      var num = (telLinks[i].getAttribute("href") || "").replace("tel:", "").trim();
      if (num && num.length >= 9) { phone = num; break; }
    }

    var nameSelectors = [
      "[data-testid*='contact-name']",
      "[class*='contact-name']",
      "[class*='seller-name']",
      "[class*='ContactName']",
      "[class*='agent-name']",
    ];
    var name = null;
    for (var j = 0; j < nameSelectors.length; j++) {
      var el = document.querySelector(nameSelectors[j]);
      if (el) { name = el.textContent.trim(); if (name) break; }
    }

    if (phone || name) r.contacts.push({ name: name, phone: phone });
  }

  /* ── Madlan: basic DOM extraction ── */
  function extractMadlanDom(r) {
    try {
      var h1 = document.querySelector("h1");
      if (h1) r.address = h1.textContent.trim();

      var priceEl = document.querySelector('[class*="price"], [class*="Price"]');
      if (priceEl) r.price = priceEl.textContent.trim();

      var body = document.body.innerText || "";
      var roomsM = body.match(/([\d.]+)\s*חדרים/);
      if (roomsM) r.rooms = roomsM[1];
      var sqmM = body.match(/([\d,]+)\s*מ"ר/);
      if (sqmM) r.size_sqm = sqmM[1].replace(",", "");
      var floorM = body.match(/קומה\s*([\d]+)/);
      if (floorM) r.floor = floorM[1];
    } catch (_) {}
  }

  /* ── Helpers ── */
  function str(v) {
    if (v == null) return null;
    var s = String(v).trim();
    return s || null;
  }

  function sendToServer(listing) {
    fetch(API + "/api/push", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(listing),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || "שגיאה בשרת");
          done("הנכס נוסף בהצלחה!", true);
        });
      })
      .catch(function (err) {
        done("שגיאה: " + err.message, false);
      });
  }
})();
