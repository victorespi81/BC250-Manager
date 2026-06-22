from bc250_manager.modules.base import ModulePage


class DashboardPage(ModulePage):
    def __init__(self) -> None:
        super().__init__(
            title="Dashboard",
            description="Overview area for BC250 status, shortcuts, and future health indicators.",
        )
