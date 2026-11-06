// Main currency per country code, used only to label the salary field.
const EURO = "at be cy de ee es fi fr gr hr ie it lt lu lv mt nl pt si sk".split(" ");

const CURRENCIES = {
  gb: "GBP", us: "USD", ca: "CAD", au: "AUD", nz: "NZD", in: "INR", pk: "PKR",
  ae: "AED", sa: "SAR", qa: "QAR", kw: "KWD", bh: "BHD", om: "OMR", jo: "JOD",
  sg: "SGD", za: "ZAR", br: "BRL", mx: "MXN", pl: "PLN", ch: "CHF", se: "SEK",
  no: "NOK", dk: "DKK", jp: "JPY", cn: "CNY", kr: "KRW", tr: "TRY", ru: "RUB",
  ng: "NGN", ke: "KES", eg: "EGP", bd: "BDT", lk: "LKR", my: "MYR", id: "IDR",
  ph: "PHP", th: "THB", vn: "VND", hk: "HKD", il: "ILS", cz: "CZK", hu: "HUF",
  ro: "RON", ua: "UAH", ar: "ARS", cl: "CLP", co: "COP", pe: "PEN", ma: "MAD",
  gh: "GHS",
};

export function currencyFor(code) {
  if (EURO.includes(code)) return "EUR";
  return CURRENCIES[code] || "";
}
