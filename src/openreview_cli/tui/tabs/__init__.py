"""Tab content widgets — Home, Review, Clients, Playbooks, Settings, Prompts."""

from openreview_cli.tui.tabs.clients import ClientsTab
from openreview_cli.tui.tabs.home import HomeTab
from openreview_cli.tui.tabs.playbooks import PlaybooksTab
from openreview_cli.tui.tabs.prompts import PromptsTab
from openreview_cli.tui.tabs.review import ReviewTab
from openreview_cli.tui.tabs.settings import SettingsTab

__all__ = [
    "ClientsTab",
    "HomeTab",
    "PlaybooksTab",
    "PromptsTab",
    "ReviewTab",
    "SettingsTab",
]
