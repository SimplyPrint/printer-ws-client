# TODO: Change this.

import click
from typing import Any, Dict, Optional, Union, get_args, get_origin, Callable

from .client.app import ClientApp
from .client.config import PrinterConfig


class CommandBag:
    commands: Dict[str, click.Command]

    def list_commands(self, ctx):
        return sorted(self.commands.keys())

    def get_command(self, ctx, name):
        return self.commands.get(name)

    def add_command(self, command: click.Command):
        self.commands[command.name] = command


class ClientCliConfigManager(CommandBag, click.Group):
    """ Commands to interact with the configuration manager. """

    def __init__(self, app: ClientApp) -> None:
        super().__init__(name="config", help="Configuration manager commands")
        self.app = app
        self.commands = {}
        self.add_command(click.Command("list", callback=self.list_configs))
        self.add_command(click.Command("edit", callback=self.edit_config,
                                       params=[click.Argument(["index"], type=int)]))
        self.add_command(click.Command("add", callback=self.add_config))
        self.add_command(click.Command("new", callback=self.add_new_config, help="Add a new configuration"))
        self.add_command(
            click.Command("remove", callback=self.remove_config,
                          params=[click.Argument(["index"], type=int)]))

    def list_configs(self):
        configs = self.app.config_manager.get_all()

        for index, config in enumerate(configs):
            click.echo(f"{index}: {config}")

    def get_config_default(self, field: str, current_value: Any) -> Any:
        if current_value is None and field in ["id", "token"]:
            return 0 if field == "id" else "0"

        if current_value is not None:
            return current_value

        return ""

    def prompt_and_update_config(self, config: PrinterConfig):
        click.echo(f"Editing configuration {config}. Leave blank to keep current value")
        fields = list(sorted(config.__slots__))

        for field in fields:
            # Ask user for field value
            field_type = config.__annotations__[field] if field in config.__annotations__ else str

            if get_origin(field_type) is Union:
                field_type = get_args(field_type)[0]

            field_default = self.get_config_default(
                field, getattr(config, field) if hasattr(config, field) else None)

            value = click.prompt(f"Input {field}",
                                 default=field_default, show_default=field_default != "",
                                 type=field_type)

            if value is None or value == "":
                continue

            setattr(config, field, value)

    def get_config_by_index(self, index: int) -> Optional[PrinterConfig]:
        configs = self.app.config_manager.get_all()
        if 0 <= index < len(configs):
            return configs[index]
        return None

    def edit_config(self, index: int):
        config = self.get_config_by_index(index)

        if config:
            self.prompt_and_update_config(config)
            self.app.config_manager.persist(config)
            self.app.config_manager.flush()
            click.echo("Configuration updated.")
        else:
            click.echo("Configuration not found.")

    def add_config(self):
        config = self.app.config_manager.config_t.get_blank()
        self.prompt_and_update_config(config)
        self.app.config_manager.persist(config)
        self.app.config_manager.flush()
        click.echo("Configuration added.")

    def add_new_config(self):
        config = self.app.config_manager.config_t.get_new()
        self.app.config_manager.persist(config)
        self.app.config_manager.flush()
        click.echo("Configuration added.")

    def remove_config(self, index: int):
        config = self.get_config_by_index(index)

        if config:
            self.app.config_manager.remove(config)
            self.app.config_manager.flush()

            click.echo("Configuration removed.")
        else:
            click.echo("Configuration not found.")


class ClientCli(CommandBag, click.MultiCommand):
    app: ClientApp
    commands: Dict[str, click.Command]
    _client_runner: Optional[Callable[[], None]] = None

    def __init__(self, app: Optional[ClientApp] = None) -> None:
        super().__init__(name="simplyprint", help="SimplyPrint client CLI")
        self.app = app
        self.commands = {}

        # Register commands
        self.add_command(ClientCliConfigManager(self.app))
        self.add_command(click.Command("start", callback=self.start_client, help="Start the client"))

    @property
    def start_client(self):
        if self._client_runner is None:
            return self.app.run_blocking

        return self._client_runner

    @start_client.setter
    def start_client(self, value):
        self._client_runner = value
