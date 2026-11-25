"""Curated world-city catalog for timezone search and short labels.

Keeping a focused list (instead of dumping all IANA zones into the menu)
gives faster search and clearer Persian/English labels on the taskbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class TimezoneEntry:
    """One selectable city/timezone shown in the picker."""

    zone_id: str
    city_fa: str
    city_en: str
    country_fa: str
    country_en: str

    @property
    def short_label(self) -> str:
        """Compact label for the two-line taskbar widget."""
        return self.city_fa

    @property
    def list_label(self) -> str:
        """Primary row text in the picker list."""
        return f"{self.city_fa} ({self.country_fa})"

    @property
    def search_blob(self) -> str:
        """Normalized haystack for substring filtering."""
        parts = (
            self.zone_id,
            self.city_fa,
            self.city_en,
            self.country_fa,
            self.country_en,
            self.zone_id.replace("_", " ").replace("/", " "),
        )
        return " ".join(parts).casefold()


# Major cities users typically want; IANA ids stay authoritative for offsets.
_CITY_ROWS: tuple[tuple[str, str, str, str, str], ...] = (
    # Middle East / Iran neighbors
    ("Asia/Tehran", "تهران", "Tehran", "ایران", "Iran"),
    ("Asia/Dubai", "دبی", "Dubai", "امارات", "UAE"),
    ("Asia/Muscat", "مسقط", "Muscat", "عمان", "Oman"),
    ("Asia/Qatar", "دوحه", "Doha", "قطر", "Qatar"),
    ("Asia/Kuwait", "کویت", "Kuwait", "کویت", "Kuwait"),
    ("Asia/Bahrain", "منامه", "Manama", "بحرین", "Bahrain"),
    ("Asia/Riyadh", "ریاض", "Riyadh", "عربستان", "Saudi Arabia"),
    ("Asia/Baghdad", "بغداد", "Baghdad", "عراق", "Iraq"),
    ("Asia/Damascus", "دمشق", "Damascus", "سوریه", "Syria"),
    ("Asia/Beirut", "بیروت", "Beirut", "لبنان", "Lebanon"),
    ("Asia/Jerusalem", "اورشلیم", "Jerusalem", "فلسطین/اسرائیل", "Israel"),
    ("Asia/Amman", "عمان", "Amman", "اردن", "Jordan"),
    ("Asia/Baku", "باکو", "Baku", "آذربایجان", "Azerbaijan"),
    ("Asia/Yerevan", "ایروان", "Yerevan", "ارمنستان", "Armenia"),
    ("Asia/Tbilisi", "تفلیس", "Tbilisi", "گرجستان", "Georgia"),
    ("Asia/Ashgabat", "عشق‌آباد", "Ashgabat", "ترکمنستان", "Turkmenistan"),
    ("Asia/Kabul", "کابل", "Kabul", "افغانستان", "Afghanistan"),
    ("Asia/Karachi", "کراچی", "Karachi", "پاکستان", "Pakistan"),
    ("Asia/Tashkent", "تاشکند", "Tashkent", "ازبکستان", "Uzbekistan"),
    ("Asia/Almaty", "آلماتی", "Almaty", "قزاقستان", "Kazakhstan"),
    ("Europe/Istanbul", "استانبول", "Istanbul", "ترکیه", "Turkey"),
    ("Asia/Nicosia", "نیکوزیا", "Nicosia", "قبرس", "Cyprus"),
    # Asia / Pacific
    ("Asia/Kolkata", "دهلی", "Delhi", "هند", "India"),
    ("Asia/Colombo", "کلمبو", "Colombo", "سری‌لانکا", "Sri Lanka"),
    ("Asia/Dhaka", "داکا", "Dhaka", "بنگلادش", "Bangladesh"),
    ("Asia/Kathmandu", "کاتماندو", "Kathmandu", "نپال", "Nepal"),
    ("Asia/Yangon", "یانگون", "Yangon", "میانمار", "Myanmar"),
    ("Asia/Bangkok", "بانکوک", "Bangkok", "تایلند", "Thailand"),
    ("Asia/Jakarta", "جاکارتا", "Jakarta", "اندونزی", "Indonesia"),
    ("Asia/Kuala_Lumpur", "کوالالامپور", "Kuala Lumpur", "مالزی", "Malaysia"),
    ("Asia/Singapore", "سنگاپور", "Singapore", "سنگاپور", "Singapore"),
    ("Asia/Manila", "مانیل", "Manila", "فیلیپین", "Philippines"),
    ("Asia/Ho_Chi_Minh", "هوشی‌مین", "Ho Chi Minh", "ویتنام", "Vietnam"),
    ("Asia/Hong_Kong", "هنگ‌کنگ", "Hong Kong", "چین", "China"),
    ("Asia/Shanghai", "شانگهای", "Shanghai", "چین", "China"),
    ("Asia/Taipei", "تایپه", "Taipei", "تایوان", "Taiwan"),
    ("Asia/Seoul", "سئول", "Seoul", "کره جنوبی", "South Korea"),
    ("Asia/Tokyo", "توکیو", "Tokyo", "ژاپن", "Japan"),
    ("Australia/Perth", "پرت", "Perth", "استرالیا", "Australia"),
    ("Australia/Adelaide", "آدلاید", "Adelaide", "استرالیا", "Australia"),
    ("Australia/Sydney", "سیدنی", "Sydney", "استرالیا", "Australia"),
    ("Australia/Melbourne", "ملبورن", "Melbourne", "استرالیا", "Australia"),
    ("Pacific/Auckland", "اوکلند", "Auckland", "نیوزیلند", "New Zealand"),
    ("Pacific/Honolulu", "هونولولو", "Honolulu", "آمریکا", "USA"),
    ("Pacific/Fiji", "فیجی", "Fiji", "فیجی", "Fiji"),
    # Europe
    ("Europe/London", "لندن", "London", "بریتانیا", "United Kingdom"),
    ("Europe/Dublin", "دوبلین", "Dublin", "ایرلند", "Ireland"),
    ("Europe/Lisbon", "لیسبون", "Lisbon", "پرتغال", "Portugal"),
    ("Europe/Madrid", "مادرید", "Madrid", "اسپانیا", "Spain"),
    ("Europe/Paris", "پاریس", "Paris", "فرانسه", "France"),
    ("Europe/Brussels", "بروکسل", "Brussels", "بلژیک", "Belgium"),
    ("Europe/Amsterdam", "آمستردام", "Amsterdam", "هلند", "Netherlands"),
    ("Europe/Berlin", "برلین", "Berlin", "آلمان", "Germany"),
    ("Europe/Zurich", "زوریخ", "Zurich", "سوئیس", "Switzerland"),
    ("Europe/Vienna", "وین", "Vienna", "اتریش", "Austria"),
    ("Europe/Rome", "رم", "Rome", "ایتالیا", "Italy"),
    ("Europe/Athens", "آتن", "Athens", "یونان", "Greece"),
    ("Europe/Helsinki", "هلسینکی", "Helsinki", "فنلاند", "Finland"),
    ("Europe/Stockholm", "استکهلم", "Stockholm", "سوئد", "Sweden"),
    ("Europe/Oslo", "اسلو", "Oslo", "نروژ", "Norway"),
    ("Europe/Copenhagen", "کپنهاگ", "Copenhagen", "دانمارک", "Denmark"),
    ("Europe/Warsaw", "ورشو", "Warsaw", "لهستان", "Poland"),
    ("Europe/Prague", "پراگ", "Prague", "چک", "Czechia"),
    ("Europe/Budapest", "بوداپست", "Budapest", "مجارستان", "Hungary"),
    ("Europe/Bucharest", "بخارست", "Bucharest", "رومانی", "Romania"),
    ("Europe/Sofia", "صوفیه", "Sofia", "بلغارستان", "Bulgaria"),
    ("Europe/Kyiv", "کی‌یف", "Kyiv", "اوکراین", "Ukraine"),
    ("Europe/Moscow", "مسکو", "Moscow", "روسیه", "Russia"),
    ("Europe/Minsk", "مینسک", "Minsk", "بلاروس", "Belarus"),
    # Africa
    ("Africa/Cairo", "قاهره", "Cairo", "مصر", "Egypt"),
    ("Africa/Casablanca", "کازابلانکا", "Casablanca", "مراکش", "Morocco"),
    ("Africa/Algiers", "الجزیره", "Algiers", "الجزایر", "Algeria"),
    ("Africa/Tunis", "تونس", "Tunis", "تونس", "Tunisia"),
    ("Africa/Lagos", "لاگوس", "Lagos", "نیجریه", "Nigeria"),
    ("Africa/Nairobi", "نایروبی", "Nairobi", "کنیا", "Kenya"),
    ("Africa/Johannesburg", "ژوهانسبورگ", "Johannesburg", "آفریقای جنوبی", "South Africa"),
    ("Africa/Addis_Ababa", "آدیس‌آبابا", "Addis Ababa", "اتیوپی", "Ethiopia"),
    # Americas
    ("America/Sao_Paulo", "سائوپائولو", "Sao Paulo", "برزیل", "Brazil"),
    ("America/Buenos_Aires", "بوئنوس‌آیرس", "Buenos Aires", "آرژانتین", "Argentina"),
    ("America/Santiago", "سانتیاگو", "Santiago", "شیلی", "Chile"),
    ("America/Lima", "لیما", "Lima", "پرو", "Peru"),
    ("America/Bogota", "بوگوتا", "Bogota", "کلمبیا", "Colombia"),
    ("America/Mexico_City", "مکزیکوسیتی", "Mexico City", "مکزیک", "Mexico"),
    ("America/Toronto", "تورنتو", "Toronto", "کانادا", "Canada"),
    ("America/Vancouver", "ونکوور", "Vancouver", "کانادا", "Canada"),
    ("America/New_York", "نیویورک", "New York", "آمریکا", "USA"),
    ("America/Chicago", "شیکاگو", "Chicago", "آمریکا", "USA"),
    ("America/Denver", "دنور", "Denver", "آمریکا", "USA"),
    ("America/Los_Angeles", "لس‌آنجلس", "Los Angeles", "آمریکا", "USA"),
    ("America/Phoenix", "فینیکس", "Phoenix", "آمریکا", "USA"),
    ("America/Anchorage", "انکوریج", "Anchorage", "آمریکا", "USA"),
    ("Atlantic/Reykjavik", "ریکیاویک", "Reykjavik", "ایسلند", "Iceland"),
    ("UTC", "یوتی‌سی", "UTC", "هماهنگ جهانی", "Coordinated Universal Time"),
)


@lru_cache(maxsize=1)
def get_timezone_catalog() -> tuple[TimezoneEntry, ...]:
    """Returns the immutable curated catalog (built once per process)."""
    return tuple(
        TimezoneEntry(zone_id, city_fa, city_en, country_fa, country_en)
        for zone_id, city_fa, city_en, country_fa, country_en in _CITY_ROWS
    )


@lru_cache(maxsize=1)
def _catalog_by_zone() -> dict[str, TimezoneEntry]:
    return {entry.zone_id: entry for entry in get_timezone_catalog()}


def find_timezone_entry(zone_id: str) -> TimezoneEntry | None:
    """Looks up a catalog entry by IANA id."""
    return _catalog_by_zone().get(zone_id)


def short_label_for_zone(zone_id: str) -> str:
    """Taskbar label for a zone; falls back to the city segment of the IANA id."""
    entry = find_timezone_entry(zone_id)
    if entry:
        return entry.short_label
    if not zone_id:
        return "—"
    return zone_id.rsplit("/", 1)[-1].replace("_", " ")


def filter_timezone_catalog(query: str) -> tuple[TimezoneEntry, ...]:
    """Filters the catalog by city, country, or IANA id (case-insensitive)."""
    catalog = get_timezone_catalog()
    needle = (query or "").strip().casefold()
    if not needle:
        return catalog
    return tuple(entry for entry in catalog if needle in entry.search_blob)
