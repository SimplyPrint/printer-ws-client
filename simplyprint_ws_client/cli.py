import click

from .app import ClientApp, ClientOptions

class ClientCli(click.MultiCommand):
    app: ClientApp

    def __init__(self, options: ClientOptions) -> None:
        super().__init__(name="simplyprint", help="SimplyPrint client CLI")
        self.app = ClientApp(options)
