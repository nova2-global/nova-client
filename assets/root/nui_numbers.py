"""Digit grouping for NovaUI windows: 1234500 as "1,234,500" in English, with
each locale's own group separator ("1.234.500" in German, "1 234 500" with a
no-break space in French and Russian).

localeInfo.NumberToMoneyString is legacy's formatter and does not fit: it
appends the currency unit and groups with a dot in every locale. This helper
only groups, and reads the locale from the folder the client loaded its
strings from (localeInfo.APP_GET_LOCALE_PATH, "locale/<code>")."""

import localeInfo

DEFAULT_LOCALE = "en"
NBSP = " "

# The group separator of each shipped locale (CLDR's, with a no-break space
# where the locale writes a space; the Arabic client keeps Latin digits).
SEPARATORS = {
	"ae": ",", "br": ".", "cz": NBSP, "de": ".", "dk": ".", "en": ",", "es": ".", "fr": NBSP, "gr": ".",
	"hu": NBSP, "it": ".", "nl": ".", "pl": NBSP, "pt": NBSP, "ro": ".", "ru": NBSP, "tr": ".",
}


def current_locale():
	"""The code of the locale the strings were loaded from, "en" if unknown."""
	path = str(getattr(localeInfo, "APP_GET_LOCALE_PATH", "") or "").replace("\\", "/").rstrip("/")
	code = path.rsplit("/", 1)[-1].lower()
	return code if code in SEPARATORS else DEFAULT_LOCALE


def group(value, locale=None):
	"""A whole number, or text that is only digits (with an optional minus),
	grouped by threes with the locale's separator. Any other text (a range such
	as "30 / 60", an empty string) comes back as it was."""
	text = str(value).strip() if not isinstance(value, bool) else str(int(value))
	digits = text[1:] if text.startswith("-") else text
	if not digits.isdigit() or not digits.isascii():
		return str(value)
	separator = SEPARATORS.get(locale or current_locale(), SEPARATORS[DEFAULT_LOCALE])
	groups = []
	while len(digits) > 3:
		groups.insert(0, digits[-3:])
		digits = digits[:-3]
	groups.insert(0, digits)
	return ("-" if text.startswith("-") else "") + separator.join(groups)
