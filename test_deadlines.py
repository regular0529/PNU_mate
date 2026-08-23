import datetime

from deadlines import get_upcoming


def test_filters_to_window_and_sorts():
    today = datetime.date(2026, 8, 15)
    result = get_upcoming(today, within_days=10)
    assert all(today <= d[0] <= today + datetime.timedelta(days=10) for d in result)
    dates = [d[0] for d in result]
    assert dates == sorted(dates)


def test_excludes_past_dates():
    today = datetime.date(2026, 8, 15)
    result = get_upcoming(today, within_days=365)
    assert all(d[0] >= today for d in result)


if __name__ == "__main__":
    test_filters_to_window_and_sorts()
    test_excludes_past_dates()
    print("ok")
