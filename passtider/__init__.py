from typing import Dict, Tuple
from time import perf_counter
from datetime import datetime
from os import remove

import requests

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta


def parse_available_times(result: str, start: float | None = None) -> None:
    if start is None:
        start = perf_counter()

    soup = BeautifulSoup(result, 'html.parser')

    tables = soup.select('table.timetable')

    total_available = 0
    total_places = len(tables)
    first_available: datetime | None = None
    first_place: str = ''

    if total_places > 0:
        print(f'{"stad":12} | {"antal":>5} | {"första":16}')
        print('{}+{}+{}'.format(
            '-' * 13,
            '-' * 7,
            '-' * 17,
        ))
        for table in tables:
            place = table.select_one('thead tr th strong#sectionName').text
            time_slots = [
                tag.attrs.get('data-fromdatetime', None)
                for tag in table.select(
                    'tbody tr td.timetable-cells div.cellcontainer '
                    'div[data-function="timeTableCell"]'
                )
            ]
            available = len(time_slots)
            total_available += available
            if available > 0:
                first = time_slots[0][:-3]
                first_date = datetime.strptime(first, '%Y-%m-%d %H:%M')

                if first_available is None or first_date < first_available:
                    first_available = first_date
                    first_place = place
            else:
                first = ' '

            print(f'{place:12} | {available:>5} | {first:16}')
    else:
        print('inga lediga tider hittades!')

    delta = perf_counter() - start

    print(
        f'det tog totalt {round(delta, 2)} sekunder att hitta '
        f'{total_available} lediga tider '
        f'på {total_places} kontor'
    )

    if first_available is not None:
        attrs = ['years', 'months', 'days']
        attrs_sv = {
            'years': 'år',
            'year': 'år',
            'months': 'månader',
            'month': 'månad',
            'days': 'dagar',
            'day': 'dag',
        }
        human_readable = lambda delta: ['%d %s' % (getattr(delta, attr), attrs_sv.get(attr if getattr(delta, attr) > 1 else attr[:-1])) for attr in attrs if getattr(delta, attr)]
        until = human_readable(relativedelta(first_available, datetime.now()))
        until_text = ', '.join(until[:-1])
        until_text += f' och {until[-1]}'
        print(f'tidigast lediga tiden är om {until_text} i {first_place}')


def do_post(
    session: requests.Session, data: Dict[str, str], label: str | None = None,
) -> str:
    start = perf_counter()

    response = session.post(
        'https://bokapass.nemoq.se/Booking/Booking/Next/vasternorrland',
        data=data,
    )

    if response.status_code != 200:
        response.raise_for_status()

    if label is None:
        label = response.url

    if len(response.history) != 1 or response.history[-1].status_code != 302:
        soup = BeautifulSoup(response.text, 'html.parser')
        validation_errors = soup.select('.validation-summary-errors ul li')

        errors = [tag.text for tag in validation_errors]

        with open('error.html', 'w+', encoding='utf-8') as fd:
            fd.write(response.text)

        raise requests.exceptions.HTTPError(
            f'"{label}" failed: {errors}',
        )

    delta = perf_counter() - start
    print(f'steg "{label}" tog {round(delta, 2)} sekunder')

    return response.text


def main() -> int:
    try:
        remove('errors.html')
    except OSError:
        pass

    with requests.Session() as client:
        start = perf_counter()
        response = client.get('https://bokapass.nemoq.se/Booking/Booking/Index/vasternorrland')

        if response.status_code != 200:
            response.raise_for_status()

        delta = perf_counter() - start
        print(f'Startsidan tog {round(delta, 2)} s')

        do_post(
            client,
            data={
                'FormId': '1',
                'ServiceGroupId': '14',
                'StartNextButton': 'Boka ny tid',
            },
            label='Boka ny tid',
        )

        do_post(
            client,
            data={
                'AgreementText': (
                    'För att kunna genomföra tidsbokning för ansökan om pass '
                    'och/eller id-kort krävs att dina personuppgifter '
                    'behandlas. Det är nödvändigt för att Polismyndigheten '
                    'ska kunna utföra de uppgifter som följer av '
                    'passförordningen (1979:664) och förordningen (2006:661) '
                    'om nationellt identitetskort och som ett led i '
                    'myndighetsutövning. För att åtgärda eventuellt '
                    'uppkomna fel kan också systemleverantören komma att nås '
                    'av personuppgifterna. Samtliga uppgifter raderas ur '
                    'tidsbokningssystemet dagen efter besöket.'
                ),
                'AcceptInformationStorage': ['true', 'false'],
                'NumberOfPeople': '1',
                'Next': 'Nästa',
            },
            label='Godkänn villkor',
        )

        do_post(
            client,
            data={
                'ServiceCategoryCustomers[0].CustomerIndex': '0',
                'ServiceCategoryCustomers[0].ServiceCategoryId': '2',
                'Next': 'Nästa',
            },
            label='Bor i Sverige',
        )

        now = datetime.now()

        result = do_post(
            client,
            data={
                'FormId': '1',
                'NumberOfPeople': '1',
                'RegionId': '0',
                'SectionId': '0',
                'NQServiceTypeId': '1',
                'FromDateString': now.strftime('%Y-%m-%d'),
                'SearchTimeHour': '8',
                'TimeSearchFirstAvailableButton': 'Första lediga tid',
            },
            label='Första lediga tid',
        )

        with open('result.html', 'w+', encoding='utf-8') as fd:
            fd.write(result)

        parse_available_times(result, start)


    return 0
