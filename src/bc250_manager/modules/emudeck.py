from bc250_manager.modules.base import ModulePage


class EmuDeckPage(ModulePage):
    def __init__(self) -> None:
        super().__init__(
            title="EmuDeck",
            description="EmuDeck configuration, paths, and emulator status will be managed here.",
        )
