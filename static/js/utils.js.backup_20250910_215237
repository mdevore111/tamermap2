// static/js/utils.js

/**
 * isEventUpcoming
 * Returns true if startDateStr is between now and the specified days from now.
 * Uses the day range from the event slider if available, otherwise defaults to 30 days.
 */
export function isEventUpcoming(startDateStr) {
  if (!startDateStr) return false;
  
  // Get maximum days from slider or use default of 30
  let maxDays = 30;
  if (window.domCache && window.domCache.eventDaysSlider) {
    maxDays = parseInt(window.domCache.eventDaysSlider.value) || 30;
  }
  
  const now = new Date();
  const start = new Date(startDateStr);
  const days = (start - now) / (1000 * 60 * 60 * 24);
  return days >= 0 && days <= maxDays;
}

/**
 * parseTimeForToday
 * Parses a time string like "8:00 AM" into a Date object set for today.
 *
 * @param {string} timeStr - Time string with optional AM/PM (e.g. "8:00 AM").
 * @returns {Date|null} Date object for today at the given time, or null if invalid.
 */
function parseTimeForToday(timeStr) {
  if (!timeStr || typeof timeStr !== 'string') return null;
  const parts = timeStr.trim().split(/\s+/);
  if (parts.length === 0) return null;
  const [timePart, modifier] = parts.length === 1 ? [parts[0], ''] : parts;
  const timeMatch = timePart.match(/(\d{1,2}):(\d{2})/);
  if (!timeMatch) return null;
  let hour = parseInt(timeMatch[1], 10);
  const minute = parseInt(timeMatch[2], 10);
  if (/PM/i.test(modifier) && hour < 12) hour += 12;
  if (/AM/i.test(modifier) && hour === 12) hour = 0;
  const date = new Date();
  date.setHours(hour, minute, 0, 0);
  return date;
}

/**
 * isOpenNow
 * Determines if a store is currently open based on its opening hours string.
 *
 * @param {string} openingHours - Multiline string representing opening hours.
 * @returns {boolean} True if the current time is within the operating hours.
 */
export function isOpenNow(openingHours) {
  if (!openingHours || typeof openingHours !== 'string') return false;
  const daysOfWeek = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const now = new Date();
  const today = daysOfWeek[now.getDay()];
  const lines = openingHours.split(/[\r\n]+/).map(line => line.trim());
  const todaysLine = lines.find(line => line.startsWith(`${today}:`));
  if (!todaysLine) return false;
  const timesPart = todaysLine.substring(today.length + 1).trim();
  if (/open\s*24/i.test(timesPart)) return true;
  const ranges = timesPart.split(',').map(r => r.trim());
  for (let range of ranges) {
    const parts = range.split(/[\u2013\u2014\-–]/).map(part => part.trim());
    if (parts.length < 2) continue;
    let startStr = parts[0];
    let endStr = parts[1];
    if (!/[AP]M/i.test(startStr) && /[AP]M/i.test(endStr)) {
      const match = endStr.match(/([AP]M)/i);
      if (match) startStr += ` ${match[1]}`;
    }
    const startDate = parseTimeForToday(startStr);
    const endDate = parseTimeForToday(endStr);
    if (!startDate || !endDate) continue;
    if (endDate < startDate) endDate.setDate(endDate.getDate() + 1);
    if (now >= startDate && now <= endDate) return true;
  }
  return false;
}

// Make isOpenNow available globally for the route planner
window.isOpenNow = isOpenNow;
