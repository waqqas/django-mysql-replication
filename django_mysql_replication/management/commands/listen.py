from decouple import config
from django.core.management.base import BaseCommand
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import (
    DeleteRowsEvent,
    UpdateRowsEvent,
    WriteRowsEvent,
)

from django_mysql_replication.signals import row_deleted, row_inserted, row_updated
from django_mysql_replication.utils import get_app_model


class Command(BaseCommand):
    help = "Listen for DB changes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--blocking", type=bool, default=True, help="Wait for events"
        )

        parser.add_argument("--server_id", type=int, default=1, help="Slave identifier")
        parser.add_argument(
            "--host", type=str, default=config("MYSQL_HOST"), help="MySQL host"
        )
        parser.add_argument(
            "--port",
            type=int,
            default=config("MYSQL_PORT", cast=int),
            help="MySQL port",
        )
        parser.add_argument(
            "--user",
            type=str,
            default=config("MYSQL_SLAVE_USER"),
            help="MySQL slave user",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=config("MYSQL_SLAVE_PASSWORD"),
            help="MySQL slave user password",
        )

    def handle(self, *args, **options):
        connection_settings = {
            "host": "db",
            "port": options["port"],
            "user": options["user"],
            "password": options["password"],
        }

        try:
            stream = BinLogStreamReader(
                connection_settings=connection_settings,
                server_id=options["server_id"],
                blocking=options["blocking"],
                only_events=[DeleteRowsEvent, WriteRowsEvent, UpdateRowsEvent],
            )

            for event in stream:
                for row in event.rows:
                    # print("row:", row)

                    try:
                        Model = get_app_model(event.table)
                        if isinstance(event, WriteRowsEvent):
                            instance = Model(**row["values"])
                            row_inserted.send(sender=Model, instance=instance)
                        elif isinstance(event, UpdateRowsEvent):
                            before_instance = Model(**row["before_values"])
                            after_instance = Model(**row["after_values"])
                            row_updated.send(
                                sender=Model,
                                before_instance=before_instance,
                                after_instance=after_instance,
                            )
                        elif isinstance(event, DeleteRowsEvent):
                            instance = Model(**row["values"])
                            row_deleted.send(sender=Model, instance=instance)

                    except KeyError:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Table {event.table} can not be mapped to model"
                            )
                        )

            stream.close()

        except KeyboardInterrupt:
            pass
        self.stdout.write(self.style.SUCCESS("Done"))
