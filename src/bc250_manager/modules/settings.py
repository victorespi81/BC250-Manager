from bc250_manager.modules.base import ModulePage


class SettingsPage(ModulePage):
    def __init__(self) -> None:
        super().__init__(
            title="Settings",
            description="Application preferences and environment configuration will be grouped here.",
        )
