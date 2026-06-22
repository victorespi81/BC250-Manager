from bc250_manager.modules.base import ModulePage


class DisksPage(ModulePage):
    def __init__(self) -> None:
        super().__init__(
            title="Disks",
            description="Disk discovery, storage layout, and maintenance workflows will live here.",
        )
