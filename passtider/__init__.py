import re

from typing import Dict, List, Optional
from time import perf_counter
from datetime import datetime

import requests

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from emoji import emojize


def eprint(text: str, end: Optional[str] = '\n') -> None:
    print(emojize(text), end=end, flush=True)


def human_readable(delta: relativedelta) -> List[str]:
    attrs = ['years', 'months', 'days']
    attrs_sv = {
        'years': 'år',
        'year': 'år',
        'months': 'månader',
        'month': 'månad',
        'days': 'dagar',
        'day': 'dag',
    }

    result: List[str] = []

    for attr in attrs:
        value = getattr(delta, attr)
        if not value:
            continue

        word = attr if value > 1 else attr[:-1]
        word_sv = attrs_sv.get(word)

        result.append(f'{value} {word_sv}')

    return result


def parse_available_times(
    region: str, result: str, start: float | None = None,
) -> None:
    if start is None:
        start = perf_counter()

    soup = BeautifulSoup(result, 'html.parser')

    tables = soup.select('table.timetable')

    total = dict(available=0, places=len(tables))
    first = dict(available=None, place=None)

    if total['places'] > 0:
        print(f'{"stad":12} | {"antal":>5} | {"första":16}')
        print(f'{"-"*13}+{"-"*7}+{"-"*17}')

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
            if available < 1:
                continue

            total['available'] += available
            first_raw = time_slots[0][:-3]
            first_date = datetime.strptime(
                first_raw,
                '%Y-%m-%d %H:%M',
            )

            if (
                first['available'] is None or
                first_date < first['available']
            ):
                first = dict(available=first_date, place=place)

            print(f'{place:12} | {available:>5} | {first_raw:16}')
    else:
        eprint(f':cross_mark: inga lediga tider hittades i {region}!')

    eprint(
        f'\n:alarm_clock: det tog totalt {round((perf_counter() - start), 2)} sekunder att hitta '
        f'{total["available"]} lediga tider '
        f'på {total["places"]} kontor i {region} län'
    )

    if first['available'] is not None:
        diff = relativedelta(first['available'], datetime.now())
        until = human_readable(diff)
        if len(until) > 1:
            until_text = ', '.join(until[:-1])
            until_text += f' och {until[-1]}'
        else:
            until_text = until[0]

        if getattr(diff, 'years', 0) > 0:
            icon = ':angry_face:'
        elif getattr(diff, 'months', 0) > 0:
            icon = ':weary_face:'
        elif getattr(diff, 'days', 0) > 25:
            icon = ':slightly_smiling_face:'
        elif getattr(diff, 'days', 0) > 15:
            icon = ':beaming_face_with_smiling_eyes:'
        else:
            icon = ':star-struck:'

        eprint(f'{icon} tidigast lediga tiden är om {until_text} i {first["place"]}')

    print('')


def do_post(
    region: str,
    session: requests.Session,
    data: Dict[str, str],
    label: str | None = None,
) -> str:
    response = session.post(
        f'https://bokapass.nemoq.se/Booking/Booking/Next/{region}',
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

        raise requests.exceptions.HTTPError(
            f'"{label}" failed: {errors}',
        )

    return response.text


def main() -> int:
    eprint('\n:calendar: letar efter lediga tider, ha tålamod...', end='\n\n')

    regions: Dict[str, str] = {
        'vasternorrland': '14',
        'gavleborg': '19',
        'jamtland': '18',
    }

    start = perf_counter()

    for region, service_group_id in regions.items():
        try:
            with requests.Session() as client:
                start_region = perf_counter()
                response = client.get(
                    f'https://bokapass.nemoq.se/Booking/Booking/Index/{region}',
                )

                if response.status_code != 200:
                    response.raise_for_status()

                do_post(
                    region,
                    client,
                    data={
                        'FormId': '1',
                        'ServiceGroupId': service_group_id,
                        'StartNextButton': 'Boka ny tid',
                    },
                    label='Boka ny tid',
                )

                do_post(
                    region,
                    client,
                    data={
                        'AgreementText': (
                            'För att kunna genomföra tidsbokning för ansökan om '
                            'pass och/eller id-kort krävs att dina '
                            'personuppgifter behandlas. Det är nödvändigt för '
                            'att Polismyndigheten ska kunna utföra de uppgifter '
                            'som följer av passförordningen (1979:664) och '
                            'förordningen (2006:661) om nationellt identitetskort '
                            'och som ett led i myndighetsutövning. För att '
                            'åtgärda eventuellt uppkomna fel kan också '
                            'systemleverantören komma att nås av '
                            'personuppgifterna. Samtliga uppgifter raderas ur '
                            'tidsbokningssystemet dagen efter besöket.'
                        ),
                        'AcceptInformationStorage': ['true', 'false'],
                        'NumberOfPeople': '1',
                        'Next': 'Nästa',
                    },
                    label='Godkänn villkor',
                )

                do_post(
                    region,
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
                    region,
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

                parse_available_times(region, result, start_region)
        except requests.exceptions.RequestException as e:
            message = re.sub(r' for url: .*', '', str(e))
            eprint(f':cross_mark: det gick inte att hämta lediga tider i {region}: {message}', end='\n\n')

    delta = perf_counter() - start
    eprint(f'\n:chequered_flag: det tog totalt {round(delta, 2)} sekunder att leta tider i {len(regions.keys())} län')

    return 0
