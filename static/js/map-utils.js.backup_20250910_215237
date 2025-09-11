// map-utils.js
// Provides utility functions for the map application, including icon selection
// for retailers and formatting of opening hours into a grouped, concise HTML format.

"use strict";

// Global mapping of retailer names to corresponding icon filenames.
window.retailerColors = {
  "Safeway": "safeway.png",
  "Kroger": "kroger.png",
  "Fred Meyer": "fred-meyer.png",
  "Albertsons": "albertsons.png",
  "King Soopers": "king-sooper.png",
  "Frys": "frys.png",
  "Jewel-Osco": "jewel-osco.png",
  "Vons": "vons.png",
  "Shaw's": "shaws.png",
  "QFC": "qfc.png",
  "Food 4 Less": "food4less.png",
  "WinCo Foods": "winco-foods.png",
  "Smith's": "smiths.png",
  "Pick 'n Save": "pick-n-save.png",
  "Tom Thumb": "tom-thumb.png",
  "Pavillions": "pavillions.png",
  "Woodman's Market": "woodmans-market.png",
  "Randalls": "randalls.png",
  "FoodMaxx": "foodmaxx.png",
  "Card Shop": "card-shop.png",
  "Best Buy": "best-buy.png",
  "Costco": "costco.png",
  "WinCo Foods": "winco-foods.png",
};

/**
 * getPinColor
 * Returns the appropriate pin icon filename for a retailer based on its type or name.
 *
 * @param {Object} retailer - The retailer object containing 'retailer' and 'retailer_type' properties.
 * @returns {string} The filename for the retailer's pin icon.
 */
window.getPinColor = function (retailer) {
  // If the retailer type is "Card Shop", return its icon immediately.
  if (retailer.retailer_type === "Card Shop") {
    return "card-shop.png";
  }
  // Otherwise, look up the retailer's name in the mapping; default to "other.png" if not found.
  return window.retailerColors[retailer.retailer] || "other.png";
};

/**
 * formatHours
 * Groups consecutive days with identical opening hours and returns a concise HTML representation.
 *
 * The input should be a multiline string with each day's hours, e.g.:
 * "Monday: 8am-5pm
 *  Tuesday: 8am-5pm
 *  ...
 *  Sunday: 10am-4pm"
 *
 * @param {string} hoursString - The multiline string of opening hours.
 * @returns {string} An HTML string with grouped hours.
 */
window.formatHours = function (hoursString) {
  const daysOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const hoursMap = {};

  // Build a map from day to its hours.
  hoursString.split("\n").forEach((line) => {
    const parts = line.split(":");
    if (parts.length >= 2) {
      const day = parts[0].trim();
      const hours = parts.slice(1).join(":").trim();
      hoursMap[day] = hours;
    }
  });

  const grouped = [];
  let currentGroup = { days: [], hours: null };

  // Group consecutive days with identical hours.
  daysOrder.forEach((day) => {
    const currentHours = hoursMap[day] || "N/A";
    if (currentHours !== currentGroup.hours) {
      if (currentGroup.days.length) {
        grouped.push(currentGroup);
      }
      currentGroup = { days: [day], hours: currentHours };
    } else {
      currentGroup.days.push(day);
    }
  });
  if (currentGroup.days.length) {
    grouped.push(currentGroup);
  }

  // Build HTML for each group.
  return grouped
    .map((group) => {
      const dayText =
        group.days.length > 1
          ? `${group.days[0].slice(0, 3)} - ${group.days[group.days.length - 1].slice(0, 3)}`
          : group.days[0].slice(0, 3);
      return `<div class="hours-row"><span class="day">${dayText}</span><span class="hours">${group.hours}</span></div>`;
    })
    .join("");
};
