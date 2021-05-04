from dataclasses import dataclass
from datetime import date, timedelta
import os
from time import sleep

from bs4 import BeautifulSoup
import click
from colorama import Fore, init
import requests

from cal_setup import get_calendar_service


init(autoreset=True)

BPP_URL = "https://thepeteplan.wordpress.com/beginner-training/"


@dataclass
class Workout(object):
    details: str
    description: str
    required: bool
    week: int
    number: int

    @property
    def smart_details(self):
        if self.required:
            return self.details
        else:
            return f"[{self.details}]"

    @property
    def pretty(self):
        result = Fore.RED if self.required else Fore.BLUE
        result += f"Week {self.week}, Workout {self.number}: {self.details}"
        return result

    @property
    def pretty_w_description(self):
        result = Fore.RED if self.required else Fore.BLUE
        result += f"Week {self.week}, Workout {self.number}: {self.details}"
        result += f"\n{Fore.RESET}{self.description}"
        return result

    @classmethod
    def from_string(cls, s, week, number):
        try:
            details, description = s.split(" – ", 1)
            return cls(
                details=details.lstrip("[").rstrip("]"),
                description=description,
                required=details[0] != "[",
                week=week,
                number=number,
            )
        except ValueError:
            print(s)
            raise

    @classmethod
    def from_site(cls):
        results = []
        res = requests.get(BPP_URL)
        soup = BeautifulSoup(res.text, features="html.parser")
        start_ix = None
        week_ix = 1
        workout_ix = 1
        paragraphs = [
            x.get_text().strip()
            for x in soup.findAll("p", class_="MsoNormal")
            if x.get_text().strip()
        ]
        for ix, p in enumerate(paragraphs):
            if p == "The 24 week ‘Pete Plan’ explained":
                start_ix = ix + 2
        for p in paragraphs[start_ix:]:
            if p.startswith("Week") and p.endswith(":"):
                continue
            details, description = p.split(" – ", 1)
            required = True
            if details[0] == "[" and details[-1] == "]":
                required = False
                details = details.lstrip("[").rstrip("]")
            results.append(
                cls(
                    details=details,
                    description=description,
                    required=required,
                    week=week_ix,
                    number=workout_ix,
                )
            )
            workout_ix += 1
            if workout_ix > 5:
                workout_ix = 1
                week_ix += 1
            if week_ix > 24:
                break
        return results

    def create_calendar_event(self, date, calendar_id=None):
        service = get_calendar_service()
        event_result = (
            service.events()
            .insert(
                calendarId=calendar_id if calendar_id else os.environ["CALENDAR_ID"],
                body={
                    "summary": f"BPP|{self.week}.{self.number} - {self.smart_details}",
                    "description": self.description,
                    "start": {"date": str(date)},
                    "end": {"date": str(date + timedelta(days=1))},
                },
            )
            .execute()
        )
        return event_result["id"]


@click.group()
def cli():
    pass


@cli.command()
@click.option("--week", type=int)
@click.option("--number", type=int)
@click.option("--description/--no-description", default=False)
def list(week, number, description):
    for workout in Workout.from_site():
        text = workout.pretty_w_description if description else workout.pretty
        if week:
            if workout.week == week:
                if workout.number == number or number is None:
                    click.echo(text)  # print week or specific workout
        elif number:
            if (workout.week - 1) * 5 + workout.number == number:
                click.echo(text)  # print the nth workout in the plan
        else:
            click.echo(text)  # print all workouts


@cli.command()
@click.option("--calendar-id")
@click.option("--rest-days", default="6,7")
@click.argument("start_date")
def populate_calendar(start_date, calendar_id, rest_days):
    workouts = Workout.from_site()
    workout_ix = 0
    rest_days = [int(d) - 1 for d in rest_days.split(",")]
    assert len(rest_days) >= 2, "Not enough rest days! You must have at least two."
    for week_ix in range(24):
        for day_ix in range(7):
            if day_ix in rest_days:
                continue
            d = date.fromisoformat(start_date) + timedelta(weeks=week_ix, days=day_ix)
            event_id = workouts[workout_ix].create_calendar_event(d, calendar_id)
            click.echo(f"{workouts[workout_ix].pretty}: {event_id}")
            workout_ix += 1
            sleep(1)
        workout_ix += len(rest_days) - 2


if __name__ == "__main__":
    cli()
